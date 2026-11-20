from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gtm_agents.codex_bridge import CodexBridge
from gtm_agents.discovery import DEMO_CLOSE, DEMO_NOTES, DEMO_RUBRIC, validate_discovery
from gtm_agents.providers import FixtureProvider, OpenAIProvider
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, SCHEMA, Store


class DiscoveryCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def workspace(self, demo):
        store = Store(self.root / ('demo.db' if demo else 'local.db'), demo=demo)
        store.save_config({**store.config(), 'business_name':'Example', 'offer':'Workflow pilot',
                           'segment':'Operations', 'qualification_rubric':DEMO_RUBRIC,
                           'approved_claims':['A pilot is available.']})
        account = store.add_account({'name':'Example Press','domain':'example.org',
                                     'claim':'Internal note','contact':'Private contact','source':'Fixture'})
        return store, account['id']

    def request(self, account, notes, key):
        return {'kind':'discovery_qualification','conversation_notes':notes,'request_key':key,'account_id':account}

    def test_demo_decisions_history_and_review(self):
        store, account = self.workspace(True)
        runtime = Runtime(store,FixtureProvider())
        initial = store.snapshot()
        for key, notes in [('advance',DEMO_NOTES),('clarify','The seller thinks there is a need.'),('close',DEMO_CLOSE)]:
            req = self.request(account,notes,key)
            task = store.enqueue(req)['id']
            with self.assertRaises(DomainError): store.review_discovery(task)
            self.assertTrue(runtime.run_once())
            self.assertEqual(store.enqueue(req)['id'],task)
            record = store.snapshot()['discovery_briefs'][0]
            self.assertEqual(record['result']['recommendation'],key)
            self.assertEqual(record['conversation_notes'],notes)
            self.assertEqual(record['qualification_rubric'],DEMO_RUBRIC)
            for finding in record['result']['findings']:
                self.assertIn(finding['quote'],notes)
            if key=='advance':
                self.assertEqual({f['category'] for f in record['result']['findings']},
                                 {'need','constraint','decision_participant'})
            if key=='clarify':
                self.assertEqual(record['result']['findings'],[])
                self.assertTrue(record['result']['open_questions'])
            with self.assertRaises(DomainError): store.review_reply(task)
            store.review_discovery(task)
            store.review_discovery(task)
        current = Store(store.path,demo=True).snapshot()
        self.assertTrue(all(r['reviewed_at'] for r in current['discovery_briefs']))
        self.assertEqual(sum(e['kind']=='discovery.reviewed' for e in current['events']),3)
        for field in ('accounts','evidence','drafts'):
            self.assertEqual(current[field],initial[field])

    def test_codex_and_api_scoped_contract_and_modified_notes(self):
        store, account = self.workspace(False)
        bridge = CodexBridge(store)
        req = self.request(account,'Buyer: We chose to end the project.', 'meeting')
        task = bridge.queue(req)['id']
        self.assertEqual(bridge.start(task)['ready_roles'],['discovery_qualification'])
        packet = bridge.packet(task,'discovery_qualification')
        self.assertEqual(packet['context'],{'conversation_notes':req['conversation_notes'],'offer':'Workflow pilot',
                                           'qualification_rubric':DEMO_RUBRIC})
        with self.assertRaises(DomainError): bridge.queue({**req,'conversation_notes':'Different notes.'})
        result = {'findings':[],'open_questions':[],'recommendation':'close','rationale':'Buyer ended the project.',
                  'decision_quote':'We chose to end the project.'}
        with self.assertRaises(DomainError):
            bridge.submit(packet['assignment_id'],'test-agent',{**result,'decision_quote':'We signed.'})
        self.assertTrue(bridge.submit(packet['assignment_id'],'test-agent',result)['completed'])
        self.assertTrue(bridge.submit(packet['assignment_id'],'test-agent',result)['deduplicated'])
        def opener(request,timeout):
            body = json.loads(request.data)
            self.assertEqual(body['instructions'],packet['instructions'])
            self.assertEqual(body['text']['format']['schema'],packet['result_schema'])
            self.assertEqual(json.loads(body['input'])['task'],packet['context'])
            self.assertNotIn('tools',body)
            return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[
                {'type':'output_text','text':json.dumps(result)}]}]}).encode())
        store.enqueue({**req,'request_key':'api'})
        self.assertTrue(Runtime(store,OpenAIProvider('test','test-key',opener)).run_once())
        self.assertEqual([r['result'] for r in store.snapshot()['discovery_briefs']],[result,result])

    def test_validation_catches_unsupported_findings_decisions_and_unresolved_questions(self):
        ctx = {'conversation_notes':DEMO_NOTES,'qualification_rubric':DEMO_RUBRIC}
        finding = {'category':'need','finding':'Track approvals.','quote':'We need to track artwork approvals.'}
        brief = {'recommendation':'advance','rationale':'Confirmed need, owner and next step.',
                 'decision_quote':'Please prepare a pilot outline for our review.','findings':[finding],
                 'open_questions':[]}
        self.assertEqual(validate_discovery(brief,ctx),brief)
        for changes in ({'findings':[]}, {'decision_quote':''}, {'recommendation':'clarify'},
                        {'findings':[{**finding,'quote':'Budget approved.'}]}, {'open_questions':[None]}):
            with self.assertRaises(DomainError): validate_discovery({**brief,**changes},ctx)
        with self.assertRaises(DomainError): validate_discovery(brief,{**ctx,'qualification_rubric':''})

    def test_empty_rubric_intake_stale_suppressed_and_idempotency(self):
        store, account = self.workspace(True)
        store.save_config({**store.config(),'qualification_rubric':''})
        req = self.request(account,DEMO_NOTES,'no-rubric')
        for notes in ('  ',None,'x'*12001):
            with self.assertRaises(DomainError): store.enqueue({**req,'conversation_notes':notes})
        with self.assertRaises(DomainError): store.enqueue({**req,'kind':'account_review'})
        store.enqueue(req)
        Runtime(store,FixtureProvider()).run_once()
        self.assertEqual(store.snapshot()['discovery_briefs'][0]['result']['recommendation'],'clarify')
        store.enqueue({**req,'request_key':'stale'})
        store.save_config({**store.config(),'qualification_rubric':'new criteria'})
        Runtime(store,FixtureProvider()).run_once()
        self.assertEqual(store.snapshot()['discovery_briefs'][0]['status'],'failed')
        store.suppress(account)
        with self.assertRaises(DomainError): store.enqueue({**req,'request_key':'suppressed'})

    def test_v5_migration_keeps_existing_reply_review(self):
        path = self.root / 'v5.db'
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(SCHEMA.replace("'reply_triage','discovery_qualification','deal_desk'", "'reply_triage'"))
            db.execute('DROP TABLE discovery_reviews')
            db.execute("INSERT INTO tasks VALUES ('old',NULL,'reply_triage','completed','old','{}','{}',NULL,NULL,1,NULL,1,1)")
            db.execute("INSERT INTO reply_reviews VALUES ('old',2)")
            db.execute('PRAGMA user_version=5')
        store = Store(path)
        with store.connect() as db:
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)
        self.assertEqual(store.snapshot()['reply_triages'][0]['reviewed_at'],2)
