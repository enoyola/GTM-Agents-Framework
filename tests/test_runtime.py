import io
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError

from gtm_agents.demo import seed
from gtm_agents.providers import FixtureProvider, OpenAIProvider, validate_result
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, Store


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.sqlite3'
        self.store=Store(self.path,demo=True)
        seed(self.store)
        self.account=self.store.snapshot()['accounts'][0]
        self.runtime=Runtime(self.store,FixtureProvider())

    def queue(self,key='request-1'):
        return self.store.enqueue({'kind':'account_review','account_id':self.account['id'],'request_key':key})

    def test_review_persists_after_reopening_database(self):
        self.queue()
        self.assertTrue(self.runtime.run_once())
        state=Store(self.path,demo=True).snapshot()
        self.assertEqual(state['tasks'][0]['status'],'completed')
        self.assertEqual(len(state['agent_runs']),3)
        self.assertEqual(state['drafts'][0]['status'],'needs_review')
        self.assertFalse(state['outbound_enabled'])
        self.assertTrue(set(state['drafts'][0]['evidence_ids']) <= {e['id'] for e in state['evidence'] if e['account_id']==self.account['id']})

    def test_idempotent_request_and_conflicting_reuse(self):
        first=self.queue()
        self.assertEqual(first['id'],self.queue()['id'])
        self.assertEqual(len(self.store.snapshot()['tasks']),1)
        with self.assertRaises(DomainError):
            self.store.enqueue({'kind':'strategy','question':'Different request','request_key':'request-1'})

    def test_only_one_active_task_per_account(self):
        self.queue()
        with self.assertRaises(DomainError):self.queue('second-request')

    def test_two_workers_cannot_claim_same_task(self):
        self.queue()
        barrier=threading.Barrier(2)
        def claim():
            barrier.wait()
            return self.store.claim()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:claim(),range(2)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_suppression_cancels_queued_task_and_blocks_new_task(self):
        self.queue()
        self.store.suppress(self.account['id'])
        self.assertFalse(self.runtime.run_once())
        self.assertEqual(self.store.snapshot()['tasks'][0]['status'],'canceled')
        with self.assertRaises(DomainError):self.queue('again')

    def test_suppression_during_model_call_cannot_commit_result(self):
        outer=self
        class InterruptingProvider(FixtureProvider):
            def generate(self,role,context,previous):
                result=super().generate(role,context,previous)
                outer.store.suppress(outer.account['id'])
                return result
        self.queue()
        Runtime(self.store,InterruptingProvider()).run_once()
        state=self.store.snapshot()
        self.assertEqual(state['tasks'][0]['status'],'canceled')
        self.assertEqual(state['drafts'],[])
        self.assertEqual(state['agent_runs'],[])

    def test_new_evidence_invalidates_queued_context(self):
        self.queue()
        self.store.add_evidence(self.account['id'],{'claim':'Changed context','source':'operator'})
        self.runtime.run_once()
        state=self.store.snapshot()
        self.assertEqual(state['tasks'][0]['status'],'failed')
        self.assertIn('changed',state['tasks'][0]['error'])
        self.assertEqual(state['drafts'],[])

    def test_config_revision_invalidates_queued_context(self):
        self.queue()
        config=self.store.config()
        self.store.save_config({**config,'offer':'Revised offer'})
        self.runtime.run_once()
        self.assertEqual(self.store.snapshot()['tasks'][0]['status'],'failed')

    def test_config_optimistic_version_prevents_overwrite(self):
        original=self.store.config()
        self.store.save_config({**original,'offer':'First edit'})
        with self.assertRaises(DomainError):self.store.save_config({**original,'offer':'Lost edit'})
        self.assertEqual(self.store.config()['offer'],'First edit')

    def test_pause_prevents_claim_and_resume_requires_fresh_context(self):
        self.queue()
        self.store.pause(True)
        self.assertIsNone(self.store.claim())
        self.store.pause(False)
        self.runtime.run_once()
        self.assertEqual(self.store.snapshot()['tasks'][0]['status'],'failed')

    def test_expired_lease_does_not_replay_ambiguous_call(self):
        self.queue()
        claimed=self.store.claim(lease_seconds=-1)
        self.assertIsNone(self.store.claim())
        task=self.store.snapshot()['tasks'][0]
        self.assertEqual(task['status'],'failed')
        self.assertEqual(task['attempts'],1)
        with self.store.write() as db:
            with self.assertRaises(DomainError):self.store.check_current(db,claimed)

    def test_strategy_independence_and_experiment_deduplication(self):
        previous_seen={}
        class RecordingProvider(FixtureProvider):
            def generate(self,role,context,previous):
                previous_seen[role]=list(previous)
                return super().generate(role,context,previous)
        self.store.enqueue({'kind':'strategy','question':'Which workflow should we test?','request_key':'strategy-one'})
        Runtime(self.store,RecordingProvider()).run_once()
        self.assertEqual(previous_seen['research'],[])
        self.assertEqual(previous_seen['sales'],[])
        self.assertEqual(previous_seen['evaluator'],['research','sales'])
        state=self.store.snapshot()
        discussion=state['discussions'][0]
        first=self.store.create_experiment(discussion['id'])
        second=self.store.create_experiment(discussion['id'])
        self.assertEqual(first,second)
        experiment=self.store.snapshot()['experiments'][0]
        self.assertEqual(experiment['status'],'draft')

    def test_no_live_action_can_be_authorized(self):
        self.queue();self.runtime.run_once()
        draft=self.store.snapshot()['drafts'][0]
        result=self.store.inspect_draft(draft['id'])
        self.assertFalse(result['allowed'])
        self.store.add_evidence(self.account['id'],{'claim':'New data','source':'operator'})
        result=self.store.inspect_draft(draft['id'])
        self.assertTrue(any('evidence changed' in r for r in result['reasons']))

    def test_old_discussion_cannot_be_promoted_into_new_offer_context(self):
        self.store.enqueue({'kind':'strategy','question':'What should we test?','request_key':'strategy-versioned'})
        self.runtime.run_once()
        discussion=self.store.snapshot()['discussions'][0]
        self.store.save_config({**self.store.config(),'offer':'A materially different offer'})
        with self.assertRaises(DomainError):self.store.create_experiment(discussion['id'])
        self.assertEqual(self.store.snapshot()['experiments'],[])

    def test_duplicate_domains_are_rejected(self):
        with self.assertRaises(DomainError):
            self.store.add_account({'name':'Duplicate','domain':self.account['domain'].upper(),'claim':'A claim','source':'operator'})

    def test_demo_cannot_be_reopened_as_real_workspace(self):
        with self.assertRaises(DomainError):Store(self.path,demo=False)

    def test_demo_seed_is_idempotent_and_preserves_user_edits(self):
        config=self.store.config()
        self.store.save_config({**config,'offer':'My changed demo offer'})
        seed(self.store)
        self.assertEqual(len(self.store.snapshot()['accounts']),3)
        self.assertEqual(self.store.config()['offer'],'My changed demo offer')

    def test_unconfigured_real_workspace_blocks_model_work(self):
        real=Store(Path(self.temp.name)/'real.sqlite3')
        config=real.config()
        self.assertEqual(config['business_name'],'')
        self.assertEqual(config['offer'],'')
        self.assertEqual(config['approved_claims'],[])
        account=real.add_account({'name':'Local account','domain':'local-account.example','claim':'Operator observation','source':'Operator note'})
        with self.assertRaises(DomainError):
            real.enqueue({'kind':'account_review','account_id':account['id'],'request_key':'real-task'})
        self.assertEqual(real.snapshot()['tasks'],[])

    def test_bad_provider_result_cannot_create_artifacts(self):
        class BadProvider(FixtureProvider):
            def generate(self,role,context,previous):
                result,usage=super().generate(role,context,previous)
                result['evidence_ids']=['invented-evidence']
                return validate_result(result,context),usage
        self.queue();Runtime(self.store,BadProvider()).run_once()
        state=self.store.snapshot()
        self.assertEqual(state['tasks'][0]['status'],'failed')
        self.assertEqual(state['drafts'],[])

    def test_evaluator_block_is_preserved(self):
        class BlockingProvider(FixtureProvider):
            def generate(self,role,context,previous):
                result,usage=super().generate(role,context,previous)
                if role=='evaluator':result['recommendation']='blocked'
                return result,usage
        self.queue();Runtime(self.store,BlockingProvider()).run_once()
        draft=self.store.snapshot()['drafts'][0]
        self.assertEqual(draft['status'],'blocked')
        self.assertIn('Writer or evaluator withheld this draft.',self.store.inspect_draft(draft['id'])['reasons'])

    def test_withheld_copy_and_unresolved_review_never_become_ready_drafts(self):
        for role in ('sales','evaluator'):
            for decision in ('research_more','blocked','retain_baseline','test'):
                with self.subTest(role=role,decision=decision):
                    class WithholdingProvider(FixtureProvider):
                        def generate(self,assigned_role,context,previous):
                            result,usage=super().generate(assigned_role,context,previous)
                            if assigned_role==role:result['recommendation']=decision
                            return result,usage
                    self.queue(f'{role}-{decision}')
                    Runtime(self.store,WithholdingProvider()).run_once()
                    draft=self.store.snapshot()['drafts'][0]
                    self.assertEqual(draft['status'],'blocked')
                    self.assertFalse(self.store.inspect_draft(draft['id'])['allowed'])


class ProviderCase(unittest.TestCase):
    def setUp(self):
        self.context={'accounts':[{'name':'Demo','is_demo':True}], 'evidence':[{'id':'ev-test'}], 'kind':'account_review'}
        self.result={'summary':'A sourced summary','recommendation':'draft','evidence_ids':['ev-test'],
                     'uncertainties':[],'content':'A draft','experiment_hypothesis':''}

    def test_openai_request_contract_and_usage(self):
        def opener(request,timeout):
            body=json.loads(request.data)
            self.assertFalse(body['store'])
            self.assertEqual(body['model'],'test-model')
            self.assertEqual(body['text']['format']['type'],'json_schema')
            self.assertTrue(body['text']['format']['strict'])
            self.assertNotIn('tools',body)
            return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(self.result)}]}],
                                         'usage':{'input_tokens':10,'output_tokens':20}}).encode())
        output,usage=OpenAIProvider('test-model','test-key',opener).generate('research',self.context,{})
        self.assertEqual(output,self.result)
        self.assertEqual(usage,{'input_tokens':10,'output_tokens':20})

    def test_refusal_and_incomplete_are_failures(self):
        for response in [{'status':'incomplete'}, {'status':'completed','output':[{'content':[{'type':'refusal','refusal':'No'}]}]}]:
            provider=OpenAIProvider('test-model','test-key',lambda *a,**kw:io.BytesIO(json.dumps(response).encode()))
            with self.assertRaises(DomainError):provider.generate('research',self.context,{})

    def test_http_error_does_not_leak_provider_body_or_key(self):
        def opener(*a,**kw):raise HTTPError('https://api.openai.com',401,'secret-response',{},io.BytesIO(b'test-key'))
        with self.assertRaises(DomainError) as result:
            OpenAIProvider('test-model','test-key',opener).generate('research',self.context,{})
        self.assertNotIn('test-key',str(result.exception))
        self.assertNotIn('secret-response',str(result.exception))

    def test_fixture_rejects_actual_accounts(self):
        self.context['accounts'][0]['is_demo']=False
        with self.assertRaises(DomainError):FixtureProvider().generate('research',self.context,{})

    def test_unknown_evidence_and_wrong_shape_are_rejected(self):
        for result in [{**self.result,'evidence_ids':['other-account']},{**self.result,'content':None},{**self.result,'extra':'unexpected'}]:
            with self.assertRaises(DomainError):validate_result(result,self.context)


if __name__=='__main__':unittest.main()
