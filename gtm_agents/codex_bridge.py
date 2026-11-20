"""Local Codex handoffs. No model calls, background spawns, or credential access."""
import json
import sqlite3
import time

from .providers import SHARED, ROLE_PROMPTS, RESULT_SCHEMA, validate_result
from .research import RESEARCH_PROMPT, FINDINGS_SCHEMA, public_url, validate_findings
from .store import DomainError, encode, required, uid

LEASE_SECONDS=1800

class CodexProvider:
    name='codex'
    model='Codex session (inherited)'
    ready=True
    execution_mode='codex'


def workflow(kind):
    if kind=='account_research':return ['research_search','research_extract','evaluator']
    if kind=='strategy':return ['research','sales','evaluator','orchestrator']
    return ['research','sales','evaluator']


def dependencies(kind,role):
    roles=workflow(kind)
    if role not in roles:raise DomainError('Role is not part of this workflow.')
    if kind=='strategy' and role in ('research','sales'):return []
    return roles[:roles.index(role)]


def validate_report(result):
    """External source provenance is agent-reported, never fabricated API annotations."""
    if not isinstance(result,dict) or set(result)!= {'summary','content','sources','citations'}:
        raise DomainError('Research report requires summary, content, sources and citations.')
    required(result['summary'],'Summary',5000);required(result['content'],'Report',40000)
    if not isinstance(result['sources'],list) or not 1<=len(result['sources'])<=20:
        raise DomainError('Research needs 1–20 public sources.')
    ids=set();urls=set()
    for source in result['sources']:
        if not isinstance(source,dict) or set(source)!={'id','url','title','retrieved_at'}:
            raise DomainError('Each source requires id, url, title and retrieved_at (Unix seconds).')
        identifier=required(source['id'],'Source id',100)
        if identifier!=source['id']:raise DomainError('Source IDs must not contain surrounding whitespace.')
        url=public_url(source['url'])
        required(source['title'],'Source title',500)
        if identifier in ids or url in urls:raise DomainError('Duplicate source id or URL.')
        ids.add(identifier);urls.add(url)
        stamp=source['retrieved_at']
        if type(stamp) not in (int,float) or not 0<stamp<=time.time()+300:
            raise DomainError('Invalid source collection time.')
    if not isinstance(result['citations'],list) or not 1<=len(result['citations'])<=100:
        raise DomainError('Research needs inline citations.')
    for ref in result['citations']:
        if not isinstance(ref,dict) or set(ref)!={'source_id','start','end'}:
            raise DomainError('Invalid citation structure.')
        if not isinstance(ref['source_id'],str) or ref['source_id'] not in ids:
            raise DomainError('Citation refers to an unknown source.')
        if type(ref['start']) is not int or type(ref['end']) is not int or not 0<=ref['start']<ref['end']<=len(result['content']):
            raise DomainError('Citation must cover text in the report (Unicode character offsets).')
    cited={ref['source_id'] for ref in result['citations']}
    return {**result,'sources':[{**s,'url':public_url(s['url']),'cited':s['id'] in cited} for s in result['sources']],
            'provenance':'codex_agent_reported'}


class CodexBridge:
    def __init__(self,store):
        if store.demo:raise DomainError('Codex bridge requires a real workspace.')
        self.store=store

    def queue(self,data):return self.store.enqueue(data,executor='codex')

    def _task(self,db,task_id,current=True):
        row=db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not row:raise DomainError('Task not found.',404)
        task={**dict(row),'input':json.loads(row['input'])}
        if task['input'].get('executor')!='codex':raise DomainError('Task belongs to the API worker.',409)
        if current:self.store.check_current(db,task)
        return task

    def status(self,task_id):
        with self.store.connect() as db:
            task=self._task(db,task_id,False)
            runs={r['role'] for r in db.execute('SELECT role FROM agent_runs WHERE task_id=?',(task_id,))}
            assignments=[dict(r) for r in db.execute('SELECT id,role,agent_id,created_at FROM codex_assignments WHERE task_id=?',(task_id,))]
            return {'task_id':task_id,'kind':task['kind'],'status':task['status'],'error':task['error'],
                    'completed_roles':[r for r in workflow(task['kind']) if r in runs],
                    'ready_roles':[r for r in workflow(task['kind']) if r not in runs and set(dependencies(task['kind'],r))<=runs] if task['status']=='queued' or (task['status']=='running' and task['lease_until']>time.time()) else [],
                    'lease_until':task['lease_until'],'assignments':assignments}

    def start(self,task_id):
        with self.store.connect() as db:
            task=self._task(db,task_id,False)
            if task['status']=='running':
                self.store.check_current(db,task)
                return self.status(task_id)
            if task['status']!='queued':raise DomainError('Only queued work can start; inspect completed or failed work.',409)
        if not self.store.claim(LEASE_SECONDS,'codex',task_id):raise DomainError('Task cannot be claimed. Check pause or another worker.',409)
        return self.status(task_id)

    def heartbeat(self,task_id):
        with self.store.write() as db:
            self._task(db,task_id)
            db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()+LEASE_SECONDS,task_id))
        return self.status(task_id)

    def packet(self,task_id,role):
        with self.store.write() as db:
            task=self._task(db,task_id)
            runs={r['role']:json.loads(r['output']) for r in db.execute('SELECT role,output FROM agent_runs WHERE task_id=?',(task_id,))}
            needed=dependencies(task['kind'],role)
            if not set(needed)<=set(runs):raise DomainError('Required predecessor roles have not completed.',409)
            existing=db.execute('SELECT packet FROM codex_assignments WHERE task_id=? AND role=?',(task_id,role)).fetchone()
            if existing:return json.loads(existing['packet'])
            context={**task['input'],'kind':task['kind']}
            previous={r:runs[r] for r in needed}
            if role=='research_search':
                account=context['accounts'][0]
                context={'company':{'name':account['name'],'domain':account['domain']},'focus':context['question']}
                instructions=RESEARCH_PROMPT+'\nUse the available Codex web tools. Cite only pages actually read. Retrieval timestamps must reflect this run. Report source limitations honestly. Do not invent provider search-call metadata.'
                schema={'summary':'string','content':'string with inline source markers','sources':[{'id':'src_1','url':'public URL','title':'page title','retrieved_at':'Unix seconds'}],
                        'citations':[{'source_id':'src_1','start':'integer Unicode offset','end':'integer exclusive offset'}]}
            elif role=='research_extract':
                context={'company':context['accounts'][0]['name'],'report':runs['research_search']}
                instructions=RESEARCH_PROMPT+'\nIn this extraction stage, do not browse. Extract at most 12 candidate findings using only the supplied report. Cite its source IDs; mark source dates unknown when unavailable. All findings require review.'
                schema=FINDINGS_SCHEMA
            else:
                if task['kind']=='account_research':
                    context['kind']='research_validation'
                    context['evidence']=[{'id':f'candidate_{i+1}',**f} for i,f in enumerate(runs['research_extract']['findings'])]
                    context['research_report']=runs['research_search']
                instructions=SHARED+'\nAssigned role: '+role+'\n'+ROLE_PROMPTS[role]
                schema=RESULT_SCHEMA
            assignment=uid('assignment')
            packet={'assignment_id':assignment,'task_id':task_id,'role':role,'instructions':instructions,
                    'context':context,'previous_role_outputs':previous,'result_schema':schema,
                    'execution_rules':'Run in a fresh Codex agent with no inherited conversation. Read only this packet and permitted public sources. Do not inspect other agents, credentials, or workspace databases. Do not modify application code or send messages. Write the result JSON to the output path supplied by the parent. Parent imports the result with the actual Codex agent ID.'}
            db.execute('INSERT INTO codex_assignments VALUES (?,?,?,?,NULL,NULL,?)',(assignment,task_id,role,encode(packet),time.time()))
            db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()+LEASE_SECONDS,task_id))
            self.store.event(db,'codex.assigned',{'role':role,'assignment_id':assignment},task['account_id'],task_id)
            return packet

    def submit(self,assignment_id,agent_id,result):
        agent_id=required(agent_id,'Actual Codex agent ID',200)
        if not isinstance(result,dict) or len(encode(result))>150000:raise DomainError('Result must be a bounded JSON object.')
        with self.store.write() as db:
            row=db.execute('SELECT * FROM codex_assignments WHERE id=?',(assignment_id,)).fetchone()
            if not row:raise DomainError('Assignment not found.',404)
            if row['result'] is not None:
                if row['agent_id']==agent_id and json.loads(row['result'])==result:return {'task_id':row['task_id'],'deduplicated':True}
                raise DomainError('Assignment already has a different result or agent identity.',409)
            task=self._task(db,row['task_id'])
            packet=json.loads(row['packet']);role=row['role'];context=packet['context']
            if role=='research_search':validated=validate_report(result)
            elif role=='research_extract':validated=validate_findings(result,context['report'])
            else:validated=validate_result(result,context)
            try:
                db.execute('UPDATE codex_assignments SET agent_id=?,result=? WHERE id=?',(agent_id,encode(result),assignment_id))
            except sqlite3.IntegrityError:
                raise DomainError('Use a distinct Codex agent execution for each role in a task.',409) from None
            usage={'input_tokens':None,'output_tokens':None,'agent_id':agent_id,'assignment_id':assignment_id,'execution':'codex','metering':'not exposed by bridge'}
            self.store.save_run(task,role,validated,'codex','inherited Codex session; model not reported',usage,db=db)
            db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()+LEASE_SECONDS,task['id']))
            runs={r['role']:json.loads(r['output']) for r in db.execute('SELECT role,output FROM agent_runs WHERE task_id=?',(task['id'],))}
            complete=set(runs)==set(workflow(task['kind']))
            if complete:
                if task['kind']=='account_research':self.store.complete_research(task,runs,db=db)
                else:self.store.complete(task,runs,db=db)
            return {'task_id':task['id'],'role':role,'completed':complete,'deduplicated':False}

    def fail(self,task_id,reason):
        reason=required(reason,'Failure reason',1000)
        with self.store.connect() as db:task=self._task(db,task_id,False)
        if task['status']!='running':raise DomainError('Only running tasks can be marked interrupted.',409)
        self.store.fail(task,reason)
        return self.status(task_id)
