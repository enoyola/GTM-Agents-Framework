import io
import json
from pathlib import Path
import tempfile
import unittest

from gtm_agents.codex_bridge import CodexBridge
from gtm_agents.demo import seed
from gtm_agents.providers import FixtureProvider, OpenAIProvider
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, Store


class PriorityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.demo = Store(self.root / 'demo.db', demo=True)
        seed(self.demo)

    def assess(self, store, account, key):
        request = {'kind': 'account_priority', 'account_id': account['id'], 'request_key': key}
        task = store.enqueue(request)
        self.assertTrue(Runtime(store, FixtureProvider()).run_once())
        self.assertEqual(store.enqueue(request)['id'], task['id'])
        self.assertEqual(store.snapshot()['tasks'][0]['status'], 'completed')

    def test_insertion_order_and_disqualifying_evidence(self):
        original = self.demo.snapshot()
        reverse = Store(self.root / 'reverse.db', demo=True)
        reverse.save_config({**original['config'], 'version': reverse.config()['version']})
        for account in original['accounts']:  # snapshot order is newest first
            note = next(r for r in original['evidence'] if r['account_id']==account['id'])
            reverse.add_account({**note, **account})

        rankings = []
        for store in (self.demo, reverse):
            for account in store.snapshot()['accounts']:
                self.assess(store, account, account['domain'])
            rankings.append([(p['domain'], p['fit']) for p in store.snapshot()['priorities']])
        self.assertEqual(rankings[0], rankings[1])
        self.assertEqual([d for d, _ in rankings[0]], ['forma-packaging.example','atlas-supply.example','northline.example'])

        top = self.demo.snapshot()['priorities'][0]
        self.demo.add_evidence(top['account_id'], {'kind':'customer_statement', 'source':'Fictional owner',
                                                  'claim':'Business has closed permanently.'})
        self.assertFalse(next(p for p in self.demo.snapshot()['priorities'] if p['domain']==top['domain'])['current'])
        self.assess(self.demo, {'id':top['account_id']}, 'changed')
        result = self.demo.snapshot()['priorities'][-1]
        self.assertEqual((result['domain'],result['fit']), (top['domain'],'excluded'))
        self.assertIn('closed permanently', result['reason'])
        evidence = self.demo.snapshot()['evidence']
        self.assertIn(result['reason'], [e['claim'] for e in evidence if e['id'] in result['evidence_ids']])

        self.demo.enqueue({'kind':'strategy','request_key':'shortlist','question':'What should we test?'})
        task = self.demo.claim()
        self.assertEqual([a['domain'] for a in task['input']['accounts']], [d for d, _ in rankings[0][1:]])

    def test_strategy_uses_older_assessed_account_and_its_cited_evidence(self):
        account = next(a for a in self.demo.snapshot()['accounts'] if a['domain']=='forma-packaging.example')
        for index in range(21):
            self.demo.add_account({'name':f'Example {index}', 'domain':f'new-{index}.example',
                                   'claim':'Unassessed account', 'source':'Fixture'})
            self.demo.add_evidence(account['id'], {'claim':f'Unconfirmed note {index}',
                                                    'source':'Fixture', 'kind':'hypothesis'})
        self.assess(self.demo,account,'assess-older')
        self.demo.enqueue({'kind':'strategy','question':'What should we test?','request_key':'older'})
        task = self.demo.claim()
        self.assertEqual([row['id'] for row in task['input']['accounts']], [account['id']])
        cited = task['input']['shortlist'][0]['evidence_ids']
        self.assertTrue(set(cited) <= {row['id'] for row in task['input']['evidence']})
        self.assess(self.demo,account,'reassess')
        with self.assertRaisesRegex(DomainError,'assessment changed'):
            self.demo.run_context(task)

    def test_stale_and_suppressed_shortlists_cannot_seed_strategy(self):
        account = self.demo.snapshot()['accounts'][0]
        self.assess(self.demo, account, 'priority')
        self.demo.save_config({**self.demo.config(),'priority_exclusions':'A new rule'})
        self.assertFalse(self.demo.snapshot()['priorities'][0]['current'])
        request = {'kind':'strategy','request_key':'stale','question':'Which accounts?'}
        with self.assertRaises(DomainError): self.demo.enqueue(request)
        self.demo.suppress(account['id'])
        self.assertEqual(self.demo.snapshot()['priorities'], [])
        with self.assertRaises(DomainError): self.demo.enqueue(request)

    def test_codex_and_api_use_same_contract_and_scoped_evidence(self):
        store = Store(self.root / 'local.db')
        store.save_config({**self.demo.config(),'version':store.config()['version']})
        account = store.add_account({'name':'Example','domain':'example.org','claim':'Uses a review workflow',
                                     'kind':'observation','source':'Operator','contact':'Private contact'})
        bridge = CodexBridge(store)
        request = {'kind':'account_priority','account_id':account['id'],'request_key':'codex'}
        task = bridge.queue(request)['id']
        self.assertEqual(bridge.start(task)['ready_roles'], ['prioritizer'])
        packet = bridge.packet(task,'prioritizer')
        self.assertNotIn('Private contact', json.dumps(packet))
        ref = packet['context']['evidence'][0]['id']
        result = {'fit':'possible_fit','reason':'A review workflow is documented.',
                  'missing_fact':'Who owns the review?', 'evidence_ids':[ref]}
        with self.assertRaises(DomainError):
            bridge.submit(packet['assignment_id'],'test-role',{**result,'evidence_ids':['wrong-account']})
        bridge.submit(packet['assignment_id'],'test-role',result)
        self.assertTrue(bridge.submit(packet['assignment_id'],'test-role',result)['deduplicated'])
        self.assertEqual(store.snapshot()['priorities'][0]['reason'], result['reason'])

        def opener(req,timeout):
            body = json.loads(req.data)
            self.assertEqual(body['instructions'], packet['instructions'])
            self.assertEqual(body['text']['format']['schema'], packet['result_schema'])
            self.assertEqual(json.loads(body['input'])['task'], packet['context'])
            return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[
                {'type':'output_text','text':json.dumps(result)}]}]}).encode())
        store.enqueue({**request,'request_key':'api'})
        Runtime(store,OpenAIProvider('test','test-key',opener)).run_once()
        current = store.snapshot()['priorities']
        self.assertEqual(len(current),1)
        self.assertNotEqual(current[0]['task_id'],task)
        self.assertEqual(Store(store.path).snapshot()['priorities'],current)

    def test_legacy_latest_review_stage_repaired_on_open(self):
        account = self.demo.snapshot()['accounts'][0]
        class Withheld(FixtureProvider):
            def generate(self, role, context, previous):
                result, usage = super().generate(role,context,previous)
                if role == 'sales': result['recommendation'] = 'research_more'
                return result, usage
        for key, provider in [('initial',FixtureProvider()),('latest',Withheld())]:
            self.demo.enqueue({'kind':'account_review','account_id':account['id'],'request_key':key})
            Runtime(self.demo,provider).run_once()
        with self.demo.write() as db:
            db.execute("UPDATE accounts SET stage='drafted' WHERE id=?", (account['id'],))
            db.execute('PRAGMA user_version=3')
        reopened = Store(self.demo.path,demo=True).snapshot()
        self.assertEqual(next(a['stage'] for a in reopened['accounts'] if a['id']==account['id']), 'needs_research')
        self.assertEqual([d['status'] for d in reopened['drafts']], ['blocked','needs_review'])
