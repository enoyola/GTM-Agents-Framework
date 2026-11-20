from contextlib import closing
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gtm_agents.codex_bridge import CodexBridge
from gtm_agents.deal_desk import DEMO_POLICY, DEMO_REQUIREMENTS, prepare_deal, validate_policy, validate_request
from gtm_agents.demo import seed
from gtm_agents.discovery import DEMO_NOTES
from gtm_agents.providers import FixtureProvider, OpenAIProvider
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, SCHEMA, Store


class DealDeskTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = Store(self.root / 'demo.db', demo=True)
        seed(self.store)
        self.account = self.store.snapshot()['accounts'][0]['id']

    def request(self, key, **fields):
        return {'kind':'deal_desk','account_id':self.account,'request_key':key,
                'deal_request':{'buyer_requirements':DEMO_REQUIREMENTS, **fields}}

    def run_deal(self, key, **fields):
        request = self.request(key, **fields)
        task = self.store.enqueue(request)['id']
        Runtime(self.store,FixtureProvider()).run_once()
        self.assertEqual(self.store.enqueue(request)['id'], task)
        row = self.store.snapshot()['deal_proposals'][0]
        self.assertEqual(row['status'],'completed',row['error'])
        return row

    def test_standard_and_stacked_concessions_review_history(self):
        first = self.run_deal('standard',discount_pct='5.00')
        self.assertEqual(first['result']['recommendation'],'proposal')
        self.assertEqual(first['package']['net_price'],'950.00')
        second = self.run_deal('exception',discount_pct='10',credit='100',payment_days=60)
        self.assertEqual(second['result']['recommendation'],'exception')
        self.assertEqual(second['package']['net_price'],'800.00')
        self.assertEqual(len(second['package']['exceptions']),3)
        self.assertEqual(second['exception_owner'],'Commercial lead')
        self.assertEqual(second['expires_at'] - second['created_at'],30*86400)
        self.store.review_deal(second['task_id'])
        self.store.review_deal(second['task_id'])
        with self.assertRaises(DomainError): self.store.review_discovery(second['task_id'])
        state = Store(self.store.path,demo=True).snapshot()
        self.assertTrue(state['deal_proposals'][0]['reviewed_at'])
        self.assertEqual(sum(e['kind']=='deal.reviewed' for e in state['events']),1)
        self.assertFalse(state['drafts'])
        self.assertEqual(state['accounts'][0]['stage'],'new')

    def test_rounding_and_policy_boundaries(self):
        policy = deepcopy(DEMO_POLICY)
        p = policy['packages'][0]
        p.update(list_price='10.05',floor='9.04',max_discount_pct='10')
        def evaluate(**fields):
            req = validate_request({'buyer_requirements':'Pilot',**fields})
            return prepare_deal(validate_policy(policy),req,None,1)['packages'][0]
        quote = evaluate(discount_pct='10')
        self.assertEqual((quote['discount_amount'],quote['net_price'],quote['exceptions']),('1.01','9.04',[]))
        self.assertEqual(len(evaluate(discount_pct='10',credit='0.01')['exceptions']),2)
        self.assertTrue(evaluate(special_terms='Guarantee delivery on Friday.')['exceptions'])
        p.update(list_price='0.01',floor='0.01',max_discount_pct='0.00')
        self.assertTrue(evaluate(discount_pct='1')['exceptions'])  # Rounding cannot authorize a higher discount.
        for fields in ({'credit':-1},{'credit':1.25},{'credit':'0.001'},{'discount_pct':'101'},
                       {'payment_days':True},{'unexpected':'value'}):
            with self.assertRaises(DomainError): evaluate(**fields)
        for bad in ([p,p],[{**p,'floor':'100'}],[{**p,'scope':''}]):
            with self.assertRaises(DomainError): validate_policy({**policy,'packages':bad})

    def test_versioned_configuration_and_catalog_scope(self):
        previous = self.run_deal('frozen')
        config = self.store.config()
        changed = deepcopy(config['deal_policy'])
        changed['packages'][0]['list_price']='1100.00'
        pending = self.store.enqueue(self.request('pending'))['id']
        self.store.save_config({**config,'deal_policy':changed})
        Runtime(self.store,FixtureProvider()).run_once()
        state=self.store.snapshot()
        self.assertEqual(next(t['status'] for t in state['tasks'] if t['id']==pending),'failed')
        self.assertEqual(state['deal_proposals'][1]['package']['list_price'], '1000.00')
        self.assertEqual(state['deal_proposals'][1]['policy_version'],previous['policy_version'])
        with self.assertRaises(DomainError): self.store.enqueue(self.request('stale-form',policy_version=config['version']))
        with self.assertRaises(DomainError): self.store.enqueue(self.request('frozen',credit='1'))
        self.store.enqueue({'kind':'account_review','account_id':self.account,'request_key':'regular'})
        self.assertNotIn('deal_policy', self.store.claim()['input']['config'])
        self.store.save_config({**self.store.config(),'deal_policy':None})
        with self.assertRaisesRegex(DomainError,'catalog'): self.store.enqueue(self.request('empty'))

    def test_only_current_reviewed_qualified_brief_from_same_account_can_attach(self):
        lookup = self.store.enqueue({'kind':'discovery_qualification','account_id':self.account,
                                     'conversation_notes':DEMO_NOTES,'request_key':'qualified'})['id']
        Runtime(self.store,FixtureProvider()).run_once()
        req = self.request('attach',discovery_task_id=lookup)
        with self.assertRaises(DomainError): self.store.enqueue(req)
        self.store.review_discovery(lookup)
        other = self.store.snapshot()['accounts'][1]['id']
        with self.assertRaises(DomainError): self.store.enqueue({**req,'account_id':other})
        self.store.enqueue(req)
        context = self.store.claim()['input']['deal']
        self.assertEqual(context['discovery']['recommendation'],'advance')
        self.assertNotIn('conversation_notes',context['discovery'])
        self.store.add_evidence(self.account,{'claim':'New context','source':'Fixture'})
        with self.assertRaisesRegex(DomainError,'current'): self.store.enqueue({**req,'request_key':'changed'})

    def test_api_codex_contract_and_forced_exception(self):
        local = Store(self.root/'local.db')
        local.save_config({**self.store.config(),'version':local.config()['version']})
        account=local.add_account({'name':'Example','domain':'example.org','contact':'Private person',
                                   'claim':'An unrelated account note','source':'Fixture'})['id']
        req={**self.request('codex',credit='200'),'account_id':account}
        bridge=CodexBridge(local)
        task=bridge.queue(req)['id']
        self.assertEqual(bridge.start(task)['ready_roles'],['deal_desk'])
        packet=bridge.packet(task,'deal_desk')
        self.assertNotIn('Private person',json.dumps(packet))
        result={'recommendation':'exception','package_id':'approval-pilot','basis_quote':DEMO_REQUIREMENTS,
                'fit_summary':'Artwork approvals fit the configured scope.','open_items':[]}
        for change in ({'recommendation':'proposal'}, {'package_id':'invented'}, {'basis_quote':'Wrong text'},
                       {'net_price':'9999'}, {'recommendation':'clarify'}):
            with self.assertRaises(DomainError):
                bridge.submit(packet['assignment_id'],'fixture-role',{**result,**change})
        self.assertTrue(bridge.submit(packet['assignment_id'],'fixture-role',result)['completed'])
        self.assertTrue(bridge.submit(packet['assignment_id'],'fixture-role',result)['deduplicated'])
        def opener(request,timeout):
            body=json.loads(request.data)
            self.assertEqual(json.loads(body['input'])['task'],packet['context'])
            self.assertEqual(body['instructions'],packet['instructions'])
            self.assertEqual(body['text']['format']['schema'],packet['result_schema'])
            return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[
                {'type':'output_text','text':json.dumps(result)}]}]}).encode())
        local.enqueue({**req,'request_key':'api'})
        Runtime(local,OpenAIProvider('test','test-key',opener)).run_once()
        self.assertEqual([r['result'] for r in local.snapshot()['deal_proposals']],[result,result])

    def test_clarify_and_v6_migration(self):
        row=self.run_deal('unknown',buyer_requirements='We need a new warehouse.')
        self.assertEqual(row['result']['recommendation'],'clarify')
        self.assertIsNone(row['package'])
        path=self.root/'old.db'
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(SCHEMA.replace("'discovery_qualification','deal_desk'","'discovery_qualification'"))
            db.execute('DROP TABLE deal_reviews')
            db.execute("INSERT INTO tasks VALUES ('old',NULL,'discovery_qualification','completed','key','{}','{}',NULL,NULL,1,NULL,1,1)")
            db.execute("INSERT INTO discovery_reviews VALUES ('old',2)")
            db.execute('PRAGMA user_version=6')
        migrated=Store(path)
        with migrated.connect() as db:
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)
        self.assertEqual(migrated.snapshot()['discovery_briefs'][0]['reviewed_at'],2)
