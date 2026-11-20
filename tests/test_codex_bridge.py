import json
import io
import tempfile
import time
import unittest
from pathlib import Path

from gtm_agents.codex_bridge import CodexBridge, validate_report
from gtm_agents.providers import FixtureProvider, OpenAIProvider
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, Store


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'bridge.sqlite3';self.store=Store(self.path)
        self.store.save_config({**self.store.config(),'business_name':'Example Studio','offer':'Test pilot',
                               'approved_claims':['Test pilot available'],'segment':'Test discovery only'})
        self.account=self.store.add_account({'name':'Example','domain':'example.com','claim':'Operator-selected offer','source':'Operator'})['id']
        self.bridge=CodexBridge(self.store)

    def task(self,kind='strategy'):
        data={'kind':kind,'question':'Test discovery','request_key':kind}
        if kind!='strategy':data['account_id']=self.account
        task=self.bridge.queue(data)['id'];self.bridge.start(task);return task

    def result(self,packet,recommendation='research_more'):
        return {'summary':'Evidence limited','recommendation':recommendation,
                'evidence_ids':[e['id'] for e in packet['context']['evidence']],
                'uncertainties':['No measured outcomes'],'content':'Validate the workflow with a buyer before pitching.', 'experiment_hypothesis':''}

    def submit(self,task,role,agent=None):
        packet=self.bridge.packet(task,role)
        return self.bridge.submit(packet['assignment_id'],agent or 'agent-'+role,self.result(packet))

    def test_api_worker_cannot_claim_codex_work_and_reverse(self):
        queued=self.bridge.queue({'kind':'strategy','question':'Question','request_key':'codex'})['id']
        self.assertFalse(Runtime(self.store,FixtureProvider()).run_once())
        api=self.store.enqueue({'kind':'account_review','account_id':self.account,'request_key':'api'})['id']
        with self.assertRaises(DomainError):self.bridge.start(api)
        self.assertEqual(self.store.claim()['id'],api)
        self.assertEqual(self.bridge.start(queued)['status'],'running')

    def test_strategy_proposals_are_independent_even_after_one_finishes(self):
        task=self.task();self.submit(task,'research')
        sales=self.bridge.packet(task,'sales')
        self.assertEqual(sales['previous_role_outputs'],{})
        self.assertNotIn('research',sales['context'])
        with self.assertRaises(DomainError):self.bridge.packet(task,'evaluator')
        self.submit(task,'sales')
        self.assertEqual(set(self.bridge.packet(task,'evaluator')['previous_role_outputs']),{'research','sales'})

    def test_every_role_requires_distinct_recorded_identity(self):
        task=self.task();self.submit(task,'research','same-agent')
        packet=self.bridge.packet(task,'sales')
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'same-agent',self.result(packet))
        self.assertEqual(self.bridge.status(task)['completed_roles'],['research'])

    def test_codex_and_api_use_the_same_writer_and_reviewer_policy(self):
        task=self.task('account_review');self.submit(task,'research')
        for role in ('sales','evaluator'):
            packet=self.bridge.packet(task,role);captured={}
            result=self.result(packet,'draft')
            def opener(request,timeout):
                captured.update(json.loads(request.data))
                return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[
                    {'type':'output_text','text':json.dumps(result)}]}]}).encode())
            OpenAIProvider('test-model','test-key',opener).generate(role,packet['context'],packet['previous_role_outputs'])
            self.assertEqual(captured['instructions'],packet['instructions'])
            self.bridge.submit(packet['assignment_id'],'agent-'+role,result)

    def test_codex_withheld_writer_cannot_be_approved_by_evaluator(self):
        task=self.task('account_review');self.submit(task,'research');self.submit(task,'sales')
        packet=self.bridge.packet(task,'evaluator')
        self.bridge.submit(packet['assignment_id'],'agent-evaluator',self.result(packet,'draft'))
        state=Store(self.path).snapshot()
        self.assertEqual(state['tasks'][0]['status'],'completed')
        self.assertEqual(state['drafts'][0]['status'],'blocked')

    def test_result_dedup_and_conflicting_resubmit(self):
        task=self.task();packet=self.bridge.packet(task,'research');result=self.result(packet)
        self.bridge.submit(packet['assignment_id'],'agent-research',result)
        self.assertTrue(self.bridge.submit(packet['assignment_id'],'agent-research',result)['deduplicated'])
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'agent-research',{**result,'content':'Changed'})

    def test_final_decision_and_agent_runs_survive_restart(self):
        task=self.task()
        for role in ('research','sales','evaluator','orchestrator'):result=self.submit(task,role)
        self.assertTrue(result['completed'])
        state=Store(self.path).snapshot()
        self.assertEqual(state['tasks'][0]['status'],'completed')
        self.assertEqual(state['tasks'][0]['executor'],'codex')
        self.assertEqual(len(state['discussions']),1)
        self.assertEqual(len(state['agent_runs']),4)
        self.assertTrue(all(r['provider']=='codex' and r['usage']['input_tokens'] is None for r in state['agent_runs']))
        self.assertEqual(len({a['agent_id'] for a in self.bridge.status(task)['assignments']}),4)

    def test_stale_input_rejects_external_result(self):
        task=self.task();packet=self.bridge.packet(task,'research')
        self.store.add_evidence(self.account,{'claim':'Changed context','source':'Operator'})
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'agent',self.result(packet))
        self.assertFalse(self.store.snapshot()['agent_runs'])

    def test_pause_and_expiry_cannot_be_bypassed_with_heartbeat(self):
        task=self.task();self.store.pause(True)
        with self.assertRaises(DomainError):self.bridge.heartbeat(task)
        self.store.pause(False)
        with self.store.write() as db:db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()-1,task))
        with self.assertRaises(DomainError):self.bridge.heartbeat(task)

    def test_expired_or_stale_task_can_be_closed_without_resurrection(self):
        task=self.task()
        with self.store.write() as db:db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()-1,task))
        self.assertEqual(self.bridge.status(task)['ready_roles'],[])
        self.assertEqual(self.bridge.fail(task,'Agent interrupted')['status'],'failed')
        with self.assertRaises(DomainError):self.bridge.start(task)

    def test_suppression_rejects_submission_and_creates_no_result(self):
        task=self.task('account_review');packet=self.bridge.packet(task,'research')
        self.store.suppress(self.account)
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'research',self.result(packet))
        self.assertFalse(self.store.snapshot()['agent_runs'])

    def test_invalid_result_is_not_recorded(self):
        task=self.task();packet=self.bridge.packet(task,'research')
        result=self.result(packet);result['evidence_ids']=['invented']
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'agent',result)
        self.assertFalse(self.store.snapshot()['agent_runs'])

    def test_wrong_executor_cannot_reuse_request_key(self):
        self.bridge.queue({'kind':'strategy','question':'Question','request_key':'same'})
        with self.assertRaises(DomainError):self.store.enqueue({'kind':'strategy','question':'Question','request_key':'same'})

    def test_search_context_excludes_crm_notes(self):
        task=self.task('account_research');packet=self.bridge.packet(task,'research_search')
        self.assertEqual(set(packet['context']),{'company','focus'})
        self.assertNotIn('Operator-selected offer',json.dumps(packet))

    def test_research_persists_report_candidates_and_real_provenance(self):
        task=self.task('account_research');packet=self.bridge.packet(task,'research_search')
        report={'summary':'Company page','content':'A company [1].',
                'sources':[{'id':'src_1','url':'https://example.com','title':'Company','retrieved_at':time.time()}],
                'citations':[{'source_id':'src_1','start':10,'end':13}]}
        self.bridge.submit(packet['assignment_id'],'collector',report)
        packet=self.bridge.packet(task,'research_extract')
        findings={'summary':'Candidate','uncertainties':['Unverified pain'], 'findings':[{'kind':'hypothesis','claim':'Could intake matter?','source_ids':['src_1'],'source_date':'unknown'}]}
        self.bridge.submit(packet['assignment_id'],'extractor',findings)
        self.submit(task,'evaluator')
        state=self.store.snapshot()
        self.assertEqual(state['tasks'][0]['status'],'completed')
        self.assertEqual(state['tasks'][0]['output']['research_search']['provenance'],'codex_agent_reported')
        self.assertEqual(len(state['research_findings']),1)
        self.assertEqual(len(state['evidence']),1)

    def test_atomic_final_submission_rolls_back_on_artifact_failure(self):
        task=self.task()
        for role in ('research','sales','evaluator'):self.submit(task,role)
        packet=self.bridge.packet(task,'orchestrator')
        from unittest.mock import patch
        with patch.object(self.store,'complete',side_effect=DomainError('simulated storage failure')):
            with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'orchestrator',self.result(packet))
        self.assertEqual(len(self.store.snapshot()['agent_runs']),3)
        self.assertEqual(self.bridge.status(task)['ready_roles'],['orchestrator'])
        self.assertTrue(self.bridge.submit(packet['assignment_id'],'orchestrator',self.result(packet))['completed'])

    def completed_research(self):
        task=self.task('account_research');packet=self.bridge.packet(task,'research_search')
        report={'summary':'Research','content':'Company [1].','sources':[{'id':'src_1','url':'https://example.com','title':'Official site','retrieved_at':time.time()}],
                'citations':[{'source_id':'src_1','start':0,'end':7}]}
        self.bridge.submit(packet['assignment_id'],'collector',report)
        packet=self.bridge.packet(task,'research_extract')
        self.bridge.submit(packet['assignment_id'],'extractor',{'summary':'Unreviewed','uncertainties':['Volume unknown'],'findings':[{'kind':'hypothesis','claim':'Could scheduling help?','source_ids':['src_1'],'source_date':'unknown'}]})
        self.submit(task,'evaluator');return task

    def test_strategy_attaches_pending_research_without_accepting_it(self):
        research=self.completed_research()
        request={'kind':'strategy','question':'Choose a segment','request_key':'attached','research_task_ids':[research]}
        task=self.bridge.queue(request)['id'];self.bridge.start(task)
        packet=self.bridge.packet(task,'research')
        self.assertEqual(packet['context']['supporting_research'][0]['task_id'],research)
        self.assertEqual(len(packet['context']['evidence']),1)
        self.assertEqual(self.store.snapshot()['research_findings'][0]['status'],'pending')
        self.assertTrue(self.bridge.queue(request)['deduplicated'])
        with self.assertRaises(DomainError):self.bridge.queue({**request,'research_task_ids':[]})
        self.submit(task,'research')
        sales=self.bridge.packet(task,'sales')
        self.assertEqual(sales['previous_role_outputs'],{})
        self.assertEqual(sales['context']['supporting_research'],packet['context']['supporting_research'])

    def test_invalid_or_blocked_research_cannot_attach(self):
        request={'kind':'strategy','question':'Choose','request_key':'invalid','research_task_ids':['missing']}
        with self.assertRaises(DomainError):self.bridge.queue(request)
        research=self.completed_research()
        with self.store.write() as db:
            output=json.loads(db.execute('SELECT output FROM tasks WHERE id=?',(research,)).fetchone()[0])
            output['evaluator']['recommendation']='blocked'
            db.execute('UPDATE tasks SET output=? WHERE id=?',(json.dumps(output),research))
        with self.assertRaises(DomainError):self.bridge.queue({**request,'research_task_ids':[research]})

    def test_research_rejection_invalidates_running_strategy(self):
        research=self.completed_research()
        task=self.bridge.queue({'kind':'strategy','question':'Choose','request_key':'review-change','research_task_ids':[research]})['id']
        self.bridge.start(task);packet=self.bridge.packet(task,'research')
        finding=self.store.snapshot()['research_findings'][0]
        self.store.review_finding(finding['id'],'rejected')
        with self.assertRaises(DomainError):self.bridge.submit(packet['assignment_id'],'research-agent',self.result(packet))

    def test_report_rejects_invalid_sources_and_offsets(self):
        for report in [{}, {'summary':'Summary','content':'Text','sources':[],'citations':[]}]:
            with self.assertRaises(DomainError):validate_report(report)

if __name__=='__main__':unittest.main()
