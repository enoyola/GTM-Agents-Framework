import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gtm_agents.codex_bridge import CodexBridge
from gtm_agents.providers import FixtureProvider, OpenAIProvider
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, SCHEMA, Store
from gtm_agents.triage import validate_triage


class ReplyTriageCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.local = Store(self.root / 'local.db')
        self.demo = Store(self.root / 'demo.db', demo=True)
        self.account = self.add_account(self.local)
        self.demo_account = self.add_account(self.demo)
        self.bridge = CodexBridge(self.local)

    @staticmethod
    def add_account(store):
        return store.add_account({'name':'Example Studio','domain':'studio.example',
                                  'contact':'Private contact', 'claim':'Private operations note',
                                  'source':'Fixture'})['id']

    def request(self, text, key='reply', demo=False):
        return {'kind':'reply_triage','account_id':self.demo_account if demo else self.account,
                'reply_text':text,'request_key':key}

    def test_demo_routes_and_persists_distinct_inbound_messages(self):
        for text, intent, route in [
            ('How much does the pilot cost?', 'pricing', 'review_pricing_with_sales'),
            ('Please ask our operations team.', 'referral', 'review_referral'),
            ('No thanks, we are not interested.', 'decline','review_closure'),
            ('Please remove me from your list.', 'opt_out','review_suppression'),
            ('Anything else?', 'unclear','review_manually'),
        ]:
            with self.subTest(intent=intent):
                request = self.request(text,key=intent,demo=True)
                task = self.demo.enqueue(request)['id']
                self.assertTrue(Runtime(self.demo,FixtureProvider()).run_once())
                self.assertEqual(self.demo.enqueue(request)['id'],task)
                row = self.demo.snapshot()['reply_triages'][0]
                self.assertEqual(row['reply_text'],text)
                self.assertIsNone(row['reviewed_at'])
                self.assertEqual((row['result']['intent'],row['result']['next_action']), (intent,route))
                self.assertIn(row['result']['quote'],text)
                self.demo.review_reply(task)
                self.demo.review_reply(task)
        state = Store(self.demo.path,demo=True).snapshot()
        self.assertEqual(len(state['reply_triages']),5)
        self.assertTrue(all(r['reviewed_at'] for r in state['reply_triages']))
        self.assertEqual(sum(e['kind']=='reply.reviewed' for e in state['events']),5)
        self.assertEqual(state['accounts'][0]['stage'],'new')
        self.assertFalse(state['accounts'][0]['suppressed'])
        self.assertFalse(state['drafts'])
        self.assertEqual(len(state['tasks']),5)

    def test_api_and_codex_use_only_reply_and_share_contract(self):
        text = 'El precio, ¿incluye instalación?'
        result = {'intent':'pricing','quote':'¿incluye instalación?', 'summary':'Asks what the price includes.',
                  'next_action':'review_pricing_with_sales'}
        task = self.bridge.queue(self.request(text))['id']
        self.assertEqual(self.bridge.start(task)['ready_roles'],['reply_triage'])
        packet = self.bridge.packet(task,'reply_triage')
        self.assertEqual(packet['context'],{'reply_text':text})
        with self.assertRaises(DomainError):
            self.bridge.submit(packet['assignment_id'],'unit-agent',{**result,'quote':'invented'})
        self.assertTrue(self.bridge.submit(packet['assignment_id'],'unit-agent',result)['completed'])
        self.assertTrue(self.bridge.submit(packet['assignment_id'],'unit-agent',result)['deduplicated'])

        def opener(request,timeout):
            body = json.loads(request.data)
            self.assertEqual(body['instructions'],packet['instructions'])
            self.assertEqual(body['text']['format']['schema'],packet['result_schema'])
            self.assertEqual(json.loads(body['input']),{'task':{'reply_text':text},'previous_role_outputs':{}})
            self.assertNotIn('tools',body)
            return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[
                {'type':'output_text','text':json.dumps(result)}]}]}).encode())
        self.local.enqueue(self.request(text,key='api'))
        Runtime(self.local,OpenAIProvider('test','test-key',opener)).run_once()
        self.assertEqual([r['result'] for r in self.local.snapshot()['reply_triages']], [result,result])

    def test_invalid_input_retries_and_review_preconditions(self):
        for text in (None,'  ','x'*5001):
            with self.assertRaises(DomainError): self.bridge.queue(self.request(text))
        with self.assertRaises(DomainError):
            self.bridge.queue({**self.request('secret'), 'kind':'account_review'})
        request = self.request('No thanks.')
        task = self.bridge.queue(request)['id']
        self.assertEqual(self.bridge.queue(request)['id'],task)
        with self.assertRaises(DomainError): self.bridge.queue(self.request('Different message.'))
        with self.assertRaises(DomainError): self.local.review_reply(task)
        with self.assertRaises(DomainError): self.local.review_reply('absent')
        self.local.suppress(self.account)
        self.assertEqual(self.local.snapshot()['reply_triages'][0]['status'],'canceled')
        with self.assertRaises(DomainError): self.bridge.start(task)

    def test_invalid_result_cannot_suggest_inconsistent_action_or_invent_words(self):
        ctx = {'reply_text':'Please stop.'}
        valid = {'intent':'opt_out','quote':'Please stop.','summary':'Asks for contact to stop.',
                 'next_action':'review_suppression'}
        for changes in ({'next_action':'review_interest_with_sales'}, {'intent':[]}, {'quote':'keep going'},
                        {'summary':'   '}, {'send':True}):
            with self.assertRaises(DomainError): validate_triage({**valid,**changes},ctx)

    def test_v4_migration_preserves_foreign_keys_and_adds_triage(self):
        path = self.root / 'legacy.db'
        old = SCHEMA.replace("'account_priority','reply_triage'", "'account_priority'")
        with sqlite3.connect(path) as db:
            db.executescript(old)
            db.execute('DROP TABLE reply_reviews')
            db.execute("INSERT INTO tasks VALUES ('prior',NULL,'strategy','completed','key','{}','{}',NULL,NULL,1,NULL,1,1)")
            db.execute("INSERT INTO agent_runs VALUES ('run','prior','research','{}','fixture','test','{}',1)")
            db.execute('PRAGMA user_version=4')
        store = Store(path)
        with store.connect() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],5)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('SELECT task_id FROM agent_runs').fetchone()[0],'prior')
        account_id = self.add_account(store)
        store.enqueue({**self.request('Hello'), 'account_id':account_id})
        self.assertEqual(store.snapshot()['reply_triages'][0]['status'],'queued')
