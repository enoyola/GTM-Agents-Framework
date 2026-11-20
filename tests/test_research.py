import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gtm_agents.config import load_env
from gtm_agents.providers import OpenAIProvider
from gtm_agents.research import parse_search, public_url, validate_findings
from gtm_agents.runtime import Runtime
from gtm_agents.store import DomainError, Store, SCHEMA


def search_body():
    return {'status':'completed','output':[
        {'type':'web_search_call','status':'completed','action':{'type':'search','sources':[{'url':'https://example.com/about'}]}},
        {'type':'message','content':[{'type':'output_text','text':'Acme distributes parts. [1]',
            'annotations':[{'type':'url_citation','start_index':24,'end_index':27,'url':'https://example.com/products','title':'Products'}]}]}],
        'usage':{'input_tokens':100,'output_tokens':100}}


def findings():
    return {'summary':'Distribution workflow to validate','uncertainties':['Current systems and pain unconfirmed'],
            'findings':[{'kind':'observation','claim':'Acme distributes parts.','source_ids':['src_1'],'source_date':'unknown'},
                        {'kind':'hypothesis','claim':'Could quote intake be a useful workflow to explore?','source_ids':['src_1'],'source_date':'unknown'}]}


class ResearchProvider:
    name='test';model='test';ready=True
    def search(self,context):return parse_search(search_body()),{'input_tokens':1,'output_tokens':1}
    def extract(self,context,report):return validate_findings(findings(),report),{'input_tokens':1,'output_tokens':1}
    def generate(self,role,context,previous):
        return {'summary':'Review candidates','recommendation':'research_more','evidence_ids':['candidate_1'],
                'uncertainties':['No pain confirmed'],'content':'Check sources before accepting.','experiment_hypothesis':''}, {'input_tokens':1,'output_tokens':1}


class ResearchCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'real.sqlite3'
        self.store=Store(self.path)
        self.store.save_config({**self.store.config(),'business_name':'Example Studio','offer':'Test pilot',
                                'approved_claims':['Test pilot available'],'segment':'Test discovery'})
        self.account=self.store.add_account({'name':'Acme','domain':'example.com','claim':'Might fit distribution workflows',
                                             'kind':'hypothesis','source':'Operator hypothesis'})['id']
    def queue(self):
        return self.store.enqueue({'kind':'account_research','account_id':self.account,'question':'Confirm public workflows', 'request_key':'research-1'})
    def research(self,provider=None):
        self.queue();Runtime(self.store,provider or ResearchProvider()).run_once()
        return self.store.snapshot()

    def test_research_collects_candidates_not_accepted_facts(self):
        state=self.research()
        self.assertEqual(state['tasks'][0]['status'],'completed')
        self.assertEqual(len(state['agent_runs']),3)
        self.assertEqual(len(state['research_findings']),2)
        self.assertEqual(len(state['evidence']),1)
        self.assertEqual(state['evidence'][0]['kind'],'hypothesis')
        self.assertFalse(state['drafts'])
        self.assertEqual(Store(self.path).snapshot()['research_findings'],state['research_findings'])

    def test_acceptance_preserves_kind_and_supports_multiple_findings(self):
        state=self.research()
        for finding in state['research_findings']:
            result=self.store.review_finding(finding['id'],'accepted')
            self.assertEqual(result,self.store.review_finding(finding['id'],'accepted'))
        state=self.store.snapshot()
        self.assertEqual(len(state['evidence']),3)
        self.assertEqual(state['accounts'][0]['version'],3)
        self.assertEqual({e['kind'] for e in state['evidence']},{'observation','hypothesis'})
        self.assertTrue(all('https://example.com/products' in e['source'] for e in state['evidence'][:2]))

    def test_rejection_does_not_add_evidence(self):
        f=self.research()['research_findings'][0]
        self.store.review_finding(f['id'],'rejected')
        self.assertEqual(len(self.store.snapshot()['evidence']),1)
        with self.assertRaises(DomainError):self.store.review_finding(f['id'],'accepted')

    def test_evaluator_block_cannot_be_accepted(self):
        class Blocked(ResearchProvider):
            def generate(self,*args):
                result,usage=super().generate(*args);result['recommendation']='blocked';return result,usage
        f=self.research(Blocked())['research_findings'][0]
        self.assertEqual(f['status'],'blocked')
        with self.assertRaises(DomainError):self.store.review_finding(f['id'],'accepted')

    def test_stale_findings_cannot_be_accepted(self):
        f=self.research()['research_findings'][0]
        self.store.add_evidence(self.account,{'claim':'New customer context','source':'Operator'})
        with self.assertRaises(DomainError):self.store.review_finding(f['id'],'accepted')

    def test_paused_findings_cannot_be_accepted(self):
        f=self.research()['research_findings'][0];self.store.pause(True)
        with self.assertRaises(DomainError):self.store.review_finding(f['id'],'accepted')

    def test_suppression_after_search_stops_subsequent_calls(self):
        store=self.store;account=self.account
        class Suppressing(ResearchProvider):
            def search(self,context):
                report=super().search(context);store.suppress(account);return report
            def extract(self,*args):raise AssertionError('Must not make another call')
        state=self.research(Suppressing())
        self.assertEqual(state['tasks'][0]['status'],'canceled')
        self.assertFalse(state['research_findings'])

    def test_extraction_failure_preserves_search_without_replay(self):
        class Failed(ResearchProvider):
            def extract(self,*args):raise DomainError('Unsupported source citation')
        state=self.research(Failed())
        self.assertEqual(state['tasks'][0]['status'],'failed')
        self.assertEqual(len(state['agent_runs']),1)
        self.assertFalse(state['research_findings'])
        self.assertIsNone(self.store.claim())

    def test_request_deduplication_includes_research_question(self):
        first=self.queue();self.assertEqual(first['id'],self.queue()['id'])
        with self.assertRaises(DomainError):
            self.store.enqueue({'kind':'account_research','account_id':self.account,'question':'Different focus','request_key':'research-1'})

    def test_demo_cannot_call_live_search(self):
        demo=Store(Path(self.temp.name)/'demo.sqlite3',demo=True)
        with self.assertRaises(DomainError):demo.enqueue({'kind':'account_research','question':'Research','request_key':'demo'})

    def test_v1_migration_preserves_foreign_keys_and_existing_records(self):
        oldpath=Path(self.temp.name)/'v1.sqlite3'
        old_schema=SCHEMA.replace("'account_review','strategy','account_research'","'account_review','strategy'")
        with sqlite3.connect(oldpath) as db:db.executescript(old_schema)
        # Seed a complete legacy graph directly, including a child of tasks.
        with sqlite3.connect(oldpath) as db:
            db.execute("INSERT INTO tasks VALUES ('t',NULL,'strategy','completed','key','{}','{}',NULL,NULL,1,NULL,1,1)")
            db.execute("INSERT INTO agent_runs VALUES ('run','t','research','{}','test','test','{}',1)")
            db.execute('PRAGMA user_version=1')
        migrated=Store(oldpath)
        with migrated.connect() as db:
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT task_id FROM agent_runs').fetchone()[0],'t')
            self.assertIn('account_research',db.execute("SELECT sql FROM sqlite_master WHERE name='tasks'").fetchone()[0])
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='active_account_task'").fetchone())


class ResearchContractCase(unittest.TestCase):
    def test_search_requires_real_completed_call_and_valid_citations(self):
        body=search_body()
        # The sample citation covers the last three characters exactly.
        body['output'][1]['content'][0]['annotations'][0].update(start_index=23,end_index=26)
        self.assertEqual(len(parse_search(body)['sources']),2)
        for broken in [dict(body,output=body['output'][1:]),dict(body,output=body['output'][:1])]:
            with self.assertRaises(DomainError):parse_search(broken)

    def test_no_arbitrary_source_or_customer_statement(self):
        report=parse_search(search_body())
        for kind,refs in [('observation',['invented']),('observation',['src_2']),('customer_statement',['src_1']),('observation',[])]:
            result=findings();result['findings'][0].update(kind=kind,source_ids=refs)
            with self.assertRaises(DomainError):validate_findings(result,report)

    def test_unsafe_urls_rejected_and_fragments_deduplicated(self):
        for url in ['javascript:alert(1)','file:///etc/passwd','https://localhost/','http://127.0.0.1/',
                    'https://a.internal/','https://user:pass@example.com/','https://example.com:8080/', 'https://example.com\\@example.org/']:
            with self.assertRaises(DomainError,msg=url):public_url(url)
        self.assertEqual(public_url('https://example.com/about#team'),'https://example.com/about')

    def test_search_only_sends_public_identity_and_focus_and_enforces_budget(self):
        def opener(request,timeout):
            payload=json.loads(request.data)
            self.assertEqual(payload['tools'],[{'type':'web_search','search_context_size':'low'}])
            self.assertEqual(payload['max_tool_calls'],3)
            self.assertEqual(payload['tool_choice'],'required')
            self.assertFalse(payload['store'])
            self.assertNotIn('private',payload['input'])
            return io.BytesIO(json.dumps(search_body()).encode())
        context={'accounts':[{'name':'Acme','domain':'example.com','contact':'private'}],
                 'evidence':[{'claim':'private'}],'config':{'offer':'private'},'question':'Check workflows'}
        report,usage=OpenAIProvider('test','secret',opener).search(context)
        self.assertEqual(usage['web_search_calls'],1)

    def test_extraction_has_strict_schema_and_no_tools(self):
        def opener(request,timeout):
            payload=json.loads(request.data)
            self.assertNotIn('tools',payload)
            self.assertTrue(payload['text']['format']['strict'])
            return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(findings())}]}]}).encode())
        result,_=OpenAIProvider('test','secret',opener).extract({'accounts':[{'name':'Acme'}]},parse_search(search_body()))
        self.assertEqual(len(result['findings']),2)

    def test_env_file_is_explicit_allowlisted_and_not_executed(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{},clear=True):
            path=Path(temp)/'.env'
            path.write_text('OPENAI_API_KEY="test-only"\nGTM_MODEL=test-model\n')
            load_env(path)
            self.assertEqual(os.environ['OPENAI_API_KEY'],'test-only')
            path.write_text('OPENAI_API_KEY=replaced\n');load_env(path)
            self.assertEqual(os.environ['OPENAI_API_KEY'],'test-only')
            path.write_text('UNSUPPORTED=secret-value\n')
            with self.assertRaises(DomainError) as error:load_env(path)
            self.assertNotIn('secret-value',str(error.exception))
