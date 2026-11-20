"""Durable records. Every write uses a short, explicit SQLite transaction."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
import time
import uuid


class DomainError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def encode(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def required(value, label, maximum=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise DomainError(f"{label} is required and must be at most {maximum} characters.")
    return value.strip()


DEFAULT_CONFIG = {
    "business_name": "", "offer": "",
    "segment": "", "approved_claims": [],
    "qualification_rubric": "", "paused": False,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (
 id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL UNIQUE,
 segment TEXT NOT NULL DEFAULT '', contact TEXT NOT NULL DEFAULT '',
 stage TEXT NOT NULL DEFAULT 'new', owner TEXT NOT NULL DEFAULT 'sales',
 suppressed INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 is_demo INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
 kind TEXT NOT NULL CHECK(kind IN ('observation','customer_statement','hypothesis')),
 claim TEXT NOT NULL, source TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, account_id TEXT REFERENCES accounts(id),
 kind TEXT NOT NULL CHECK(kind IN ('account_review','strategy','account_research')),
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','canceled')),
 request_key TEXT NOT NULL UNIQUE, input TEXT NOT NULL, output TEXT,
 lease_token TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS active_account_task ON tasks(account_id)
 WHERE account_id IS NOT NULL AND status IN ('queued','running');
CREATE UNIQUE INDEX IF NOT EXISTS active_strategy_task ON tasks(kind)
 WHERE kind='strategy' AND status IN ('queued','running');
CREATE TABLE IF NOT EXISTS agent_runs (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
 role TEXT NOT NULL, output TEXT NOT NULL, provider TEXT NOT NULL,
 model TEXT NOT NULL, usage TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(task_id,role)
);
CREATE TABLE IF NOT EXISTS drafts (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
 account_id TEXT NOT NULL REFERENCES accounts(id), body TEXT NOT NULL,
 evidence_ids TEXT NOT NULL, account_version INTEGER NOT NULL,
 config_version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'needs_review',
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS discussions (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
 question TEXT NOT NULL, decision TEXT NOT NULL, recommendation TEXT NOT NULL,
 hypothesis TEXT NOT NULL, evidence_ids TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
 id TEXT PRIMARY KEY, discussion_id TEXT NOT NULL UNIQUE REFERENCES discussions(id),
 title TEXT NOT NULL, hypothesis TEXT NOT NULL, primary_metric TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status='draft'),
 config_version INTEGER NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
 account_id TEXT REFERENCES accounts(id), task_id TEXT REFERENCES tasks(id),
 detail TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS research_findings (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
 account_id TEXT NOT NULL REFERENCES accounts(id), kind TEXT NOT NULL,
 claim TEXT NOT NULL, source_ids TEXT NOT NULL, source_date TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','blocked')),
 evidence_id TEXT REFERENCES evidence(id), created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS codex_assignments (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), role TEXT NOT NULL,
 packet TEXT NOT NULL, agent_id TEXT, result TEXT, created_at REAL NOT NULL,
 UNIQUE(task_id,role), UNIQUE(task_id,agent_id)
);

"""


class Store:
    def __init__(self, path, demo=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.demo = demo
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 3:
                raise DomainError('This database was created by a newer runtime. Use a compatible application version.')
            if db.execute("SELECT name FROM sqlite_master WHERE name='metadata'").fetchone():
                existing=db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
                if existing and existing['value']!=('demo' if demo else 'local'):
                    raise DomainError('This database belongs to a different workspace mode. Use a separate demo database.')
            # Rebuild only the task CHECK constraint; keep all IDs and referencing rows.
            old=db.execute("SELECT sql FROM sqlite_master WHERE name='tasks'").fetchone()
            if old and 'account_research' not in old['sql']:
                db.execute('PRAGMA foreign_keys=OFF')
                db.execute('BEGIN IMMEDIATE')
                create=SCHEMA.split('CREATE TABLE IF NOT EXISTS tasks (')[1].split(');')[0]
                db.execute('CREATE TABLE tasks_v2 ('+create+');')
                db.execute('INSERT INTO tasks_v2 SELECT * FROM tasks')
                db.execute('DROP TABLE tasks')
                db.execute('ALTER TABLE tasks_v2 RENAME TO tasks')
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise DomainError('Database migration failed its reference check.')
                db.commit()
                db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA)
            mode = 'demo' if demo else 'local'
            existing = db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
            if existing and existing['value'] != mode:
                raise DomainError('This database belongs to a different workspace mode. Use a separate demo database.')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('mode',?)", (mode,))
            db.execute("INSERT OR IGNORE INTO settings VALUES (1,1,?)", (encode(DEFAULT_CONFIG),))
            db.execute("PRAGMA user_version=3")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def write(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def event(self, db, kind, detail, account_id=None, task_id=None):
        db.execute("INSERT INTO events(kind,account_id,task_id,detail,created_at) VALUES (?,?,?,?,?)",
                   (kind, account_id, task_id, encode(detail), time.time()))

    def config(self, db=None):
        if db is None:
            with self.connect() as connection:
                return self.config(connection)
        row = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return {**json.loads(row['value']), "version": row['version']}

    def save_config(self, data):
        if not isinstance(data.get('approved_claims'), list) or len(data['approved_claims']) > 30:
            raise DomainError('Approved claims must be a list of at most 30 statements.')
        claims = [required(c, 'Claim', 1000) for c in data['approved_claims']]
        fields = {k: required(data.get(k), k.replace('_', ' ').capitalize(), 3000)
                  for k in ('business_name', 'offer', 'segment')}
        rubric = data.get('qualification_rubric', '')
        if not isinstance(rubric, str) or len(rubric) > 5000:
            raise DomainError('Qualification rubric must be text, at most 5000 characters.')
        with self.write() as db:
            old = self.config(db)
            if data.get('version') != old['version']:
                raise DomainError('Configuration changed. Refresh before saving.', 409)
            new = {**fields, 'approved_claims': claims, 'qualification_rubric': rubric,
                   'paused': old['paused']}
            db.execute("UPDATE settings SET version=version+1,value=? WHERE id=1", (encode(new),))
            self.event(db, 'config.updated', {'version': old['version'] + 1})
        return self.config()

    def pause(self, paused):
        if not isinstance(paused, bool):
            raise DomainError('Paused must be true or false.')
        with self.write() as db:
            config = self.config(db)
            config.pop('version')
            config['paused'] = paused
            db.execute("UPDATE settings SET version=version+1,value=? WHERE id=1", (encode(config),))
            self.event(db, 'team.paused' if paused else 'team.resumed', {})
        return self.config()

    def account(self, account_id, db):
        row = db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not row:
            raise DomainError('Account not found.', 404)
        return dict(row)

    def add_account(self, data):
        name = required(data.get('name'), 'Company name', 160)
        domain = required(data.get('domain'), 'Company domain', 255).lower()
        import re
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}', domain):
            raise DomainError('Use a company domain such as company.example, without a URL path.')
        segment = data.get('segment', '')
        contact = data.get('contact', '')
        if not all(isinstance(v, str) and len(v) <= 500 for v in (segment, contact)):
            raise DomainError('Segment and contact must be text of at most 500 characters.')
        claim = required(data.get('claim'), 'Initial evidence', 5000)
        source = required(data.get('source'), 'Evidence source', 1000)
        kind=data.get('kind','observation')
        if kind not in ('observation','customer_statement','hypothesis'):
            raise DomainError('Unknown evidence kind.')
        identifier = uid('acct')
        with self.write() as db:
            try:
                db.execute("INSERT INTO accounts(id,name,domain,segment,contact,is_demo,created_at) VALUES (?,?,?,?,?,?,?)",
                           (identifier, name, domain, segment, contact, int(self.demo), time.time()))
            except sqlite3.IntegrityError:
                raise DomainError('An account with that domain already exists.', 409)
            db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                       (uid('ev'), identifier, kind, claim, source, time.time()))
            self.event(db, 'account.created', {'name': name, 'is_demo': self.demo}, identifier)
        return {'id': identifier}

    def add_evidence(self, account_id, data):
        claim = required(data.get('claim'), 'Evidence', 5000)
        source = required(data.get('source'), 'Source', 1000)
        kind = data.get('kind', 'observation')
        if kind not in ('observation', 'customer_statement', 'hypothesis'):
            raise DomainError('Unknown evidence kind.')
        with self.write() as db:
            self.account(account_id, db)
            identifier = uid('ev')
            db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                       (identifier, account_id, kind, claim, source, time.time()))
            db.execute("UPDATE accounts SET version=version+1 WHERE id=?", (account_id,))
            self.event(db, 'evidence.added', {'evidence_id': identifier, 'kind': kind}, account_id)
        return {'id': identifier}

    def suppress(self, account_id):
        with self.write() as db:
            self.account(account_id, db)
            db.execute("UPDATE accounts SET suppressed=1,stage='suppressed',version=version+1 WHERE id=?", (account_id,))
            db.execute("UPDATE tasks SET status='canceled',error='Account suppressed',updated_at=? WHERE account_id=? AND status IN ('queued','running')", (time.time(), account_id))
            db.execute("UPDATE drafts SET status='invalidated' WHERE account_id=?", (account_id,))
            self.event(db, 'account.suppressed', {}, account_id)
        return {'ok': True}

    def enqueue(self, data, executor="api"):
        if executor not in ("api","codex"):raise DomainError("Unknown executor.")
        if executor=="codex" and self.demo:raise DomainError("Use the real workspace for Codex executions.")
        kind = data.get('kind', 'account_review')
        if kind not in ('account_review', 'strategy', 'account_research'):
            raise DomainError('Unknown task kind.')
        if kind=='account_research' and self.demo:
            raise DomainError('Web research is available only in the real workspace.',409)
        question=required(data.get('question'),'Public research focus',2000) if kind=='account_research' else ''
        request_key = required(data.get('request_key'), 'Request key', 200)
        research_ids=data.get('research_task_ids',[])
        if not isinstance(research_ids,list) or len(research_ids)>3 or any(not isinstance(x,str) for x in research_ids) or len(set(research_ids))!=len(research_ids):
            raise DomainError('Supply up to three distinct research task IDs.')
        if research_ids and kind!='strategy':raise DomainError('Research attachments are for strategy discussions only.')
        with self.write() as db:
            existing = db.execute("SELECT * FROM tasks WHERE request_key=?", (request_key,)).fetchone()
            if existing:
                same = existing['kind'] == kind and existing['account_id'] == data.get('account_id') and json.loads(existing['input']).get('executor','api')==executor
                if kind in ('strategy','account_research'):
                    same = same and json.loads(existing['input'])['question'] == data.get('question', '').strip()
                same = same and json.loads(existing['input']).get('research_task_ids',[])==research_ids
                if not same:
                    raise DomainError('Request key already belongs to a different task.', 409)
                return {'id': existing['id'], 'deduplicated': True}
            config = self.config(db)
            if config['paused']:
                raise DomainError('The team is paused. Resume before queuing work.', 409)
            fields=('business_name','offer','approved_claims') if kind=='account_research' else ('business_name','offer','segment','approved_claims')
            if not all(config.get(k) for k in fields):
                raise DomainError('Set the business, offer, segment and approved claims before running agents.', 409)
            account_id = data.get('account_id') if kind != 'strategy' else None
            if kind != 'strategy':
                account = self.account(account_id, db)
                if account['suppressed']:
                    raise DomainError('This account is suppressed.', 409)
                accounts = [account]
            else:
                question = required(data.get('question'), 'Strategy question', 2000)
                accounts = [dict(r) for r in db.execute("SELECT * FROM accounts WHERE suppressed=0 ORDER BY created_at DESC LIMIT 20")]
                if not accounts:
                    raise DomainError('Add at least one account with evidence first.', 409)
            evidence = []
            for account in accounts:
                evidence.extend(dict(r) for r in db.execute("SELECT * FROM evidence WHERE account_id=? ORDER BY created_at DESC LIMIT 20", (account['id'],)))
            context = {'executor':executor, 'config': config, 'accounts': accounts, 'evidence': evidence, 'question': question}
            if research_ids:
                context['research_task_ids']=research_ids
                context['supporting_research']=[]
                for research_id in research_ids:
                    report=db.execute('SELECT * FROM tasks WHERE id=?',(research_id,)).fetchone()
                    if not report or report['kind']!='account_research' or report['status']!='completed':
                        raise DomainError('Attach only completed public research.',409)
                    output=json.loads(report['output'])
                    if output['evaluator']['recommendation']=='blocked':raise DomainError('Blocked research cannot support strategy.',409)
                    account=self.account(report['account_id'],db)
                    if account['suppressed']:raise DomainError('Research account is suppressed.',409)
                    original=json.loads(report['input'])
                    if original['config']['version']!=config['version']:raise DomainError('Research configuration changed; rerun research.',409)
                    accepted=db.execute("SELECT count(*) FROM research_findings WHERE task_id=? AND status='accepted'",(research_id,)).fetchone()[0]
                    if account['version']!=original['accounts'][0]['version']+accepted:raise DomainError('Research account context changed; rerun research.',409)
                    if not any(a['id']==account['id'] for a in accounts):raise DomainError('Research account is outside the strategy account set.',409)
                    findings=[dict(r) for r in db.execute('SELECT id,status,claim FROM research_findings WHERE task_id=?',(research_id,))]
                    context['supporting_research'].append({'task_id':research_id,'account_id':account['id'],
                        'report':output['research_search'],'extraction':output['research_extract'],'evaluation':output['evaluator'],
                        'finding_review_states':findings,'status':'Research context only; pending findings are not accepted evidence. Rejected findings must not support conclusions.'})
            if len(encode(context)) > 70000:
                raise DomainError('Evidence packet is too large. Narrow the account set or evidence.', 409)
            identifier = uid('task')
            try:
                db.execute("INSERT INTO tasks(id,account_id,kind,status,request_key,input,created_at,updated_at) VALUES (?,?,?,'queued',?,?,?,?)",
                           (identifier, account_id, kind, request_key, encode(context), time.time(), time.time()))
            except sqlite3.IntegrityError:
                raise DomainError('Equivalent work is already queued or running.', 409)
            self.event(db, 'task.queued', {'kind': kind}, account_id, identifier)
        return {'id': identifier, 'deduplicated': False}

    def claim(self, lease_seconds=120, executor="api", task_id=None):
        with self.write() as db:
            if self.config(db)['paused']:
                return None
            # Do not replay an ambiguous paid model call after a worker crash.
            expired = db.execute("SELECT id FROM tasks WHERE status='running' AND lease_until<?", (time.time(),)).fetchall()
            for row in expired:
                db.execute("UPDATE tasks SET status='failed',error='Worker lease expired; inspect partial runs before retrying.',updated_at=? WHERE id=?", (time.time(), row['id']))
                self.event(db, 'task.interrupted', {'reason': 'lease_expired'}, task_id=row['id'])
            row = db.execute("SELECT * FROM tasks WHERE status='queued' AND COALESCE(json_extract(input,'$.executor'),'api')=? AND (? IS NULL OR id=?) ORDER BY created_at LIMIT 1",(executor,task_id,task_id)).fetchone()
            if not row:
                return None
            token = uid('lease')
            db.execute("UPDATE tasks SET status='running',lease_token=?,lease_until=?,attempts=attempts+1,updated_at=? WHERE id=?",
                       (token, time.time()+lease_seconds, time.time(), row['id']))
            self.event(db, 'task.started', {'kind': row['kind']}, row['account_id'], row['id'])
            return {**dict(row), 'status':'running', 'lease_token':token, 'input':json.loads(row['input'])}

    def check_current(self, db, task):
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task['id'],)).fetchone()
        if row['status'] != 'running' or row['lease_token'] != task['lease_token'] or row['lease_until'] < time.time():
            raise DomainError('Task ownership expired or was canceled.', 409)
        config = self.config(db)
        if config['paused'] or config['version'] != task['input']['config']['version']:
            raise DomainError('Business configuration changed or the team paused. Rerun with current inputs.', 409)
        for snapshot in task['input']['accounts']:
            account = self.account(snapshot['id'], db)
            if account['suppressed'] or account['version'] != snapshot['version']:
                raise DomainError('Account evidence or ownership changed. Rerun with current inputs.', 409)
        for report in task['input'].get('supporting_research',[]):
            current=[dict(r) for r in db.execute('SELECT id,status,claim FROM research_findings WHERE task_id=?',(report['task_id'],))]
            if current!=report['finding_review_states']:raise DomainError('Attached research review changed. Rerun strategy.',409)

    def run_context(self, task):
        with self.write() as db:
            self.check_current(db, task)
            db.execute("UPDATE tasks SET lease_until=? WHERE id=?", (time.time()+120, task['id']))

    def save_run(self, task, role, result, provider, model, usage, db=None):
        if db is None:
            with self.write() as connection:
                return self.save_run(task, role, result, provider, model, usage, db=connection)
        self.check_current(db, task)
        db.execute("INSERT INTO agent_runs VALUES (?,?,?,?,?,?,?,?)",
                   (uid('run'), task['id'], role, encode(result), provider, model, encode(usage), time.time()))
        self.event(db, 'agent.completed', {'role': role, 'provider': provider, 'usage': usage}, task['account_id'], task['id'])

    def complete(self, task, runs, db=None):
        if db is None:
            with self.write() as connection:
                return self.complete(task, runs, db=connection)
        self.check_current(db, task)
        if task['kind'] == 'account_review':
            account = task['input']['accounts'][0]
            draft = runs['sales']
            # A withheld message or unresolved critique must not become a reviewable draft.
            blocked = draft['recommendation'] != 'draft' or runs['evaluator']['recommendation'] != 'draft'
            db.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?)",
                       (uid('draft'), task['id'], account['id'], draft['content'], encode(draft['evidence_ids']),
                        account['version'], task['input']['config']['version'], 'blocked' if blocked else 'needs_review', time.time()))
            db.execute("UPDATE accounts SET stage='drafted' WHERE id=?", (account['id'],))
        else:
            result = runs['orchestrator']
            db.execute("INSERT INTO discussions VALUES (?,?,?,?,?,?,?,?)",
                       (uid('discussion'), task['id'], task['input']['question'], result['content'], result['recommendation'], result['experiment_hypothesis'], encode(result['evidence_ids']), time.time()))
        db.execute("UPDATE tasks SET status='completed',output=?,updated_at=? WHERE id=?", (encode(runs), time.time(), task['id']))
        self.event(db, 'task.completed', {'kind': task['kind']}, task['account_id'], task['id'])

    def complete_research(self, task, runs, db=None):
        if db is None:
            with self.write() as connection:
                return self.complete_research(task, runs, db=connection)
        self.check_current(db,task)
        blocked=runs['evaluator']['recommendation']=='blocked'
        for finding in runs['research_extract']['findings']:
            db.execute("INSERT INTO research_findings VALUES (?,?,?,?,?,?,?,?,NULL,?)",
                       (uid('finding'),task['id'],task['account_id'],finding['kind'],finding['claim'],
                        encode(finding['source_ids']),finding['source_date'],'blocked' if blocked else 'pending',time.time()))
        db.execute("UPDATE tasks SET status='completed',output=?,updated_at=? WHERE id=?",
                   (encode(runs),time.time(),task['id']))
        self.event(db,'research.completed',{'candidates':len(runs['research_extract']['findings']),
                                          'blocked':blocked},task['account_id'],task['id'])

    def review_finding(self, finding_id, decision):
        if decision not in ('accepted','rejected'):raise DomainError('Accept or reject a finding.')
        with self.write() as db:
            row=db.execute('SELECT * FROM research_findings WHERE id=?',(finding_id,)).fetchone()
            if not row:raise DomainError('Finding not found.',404)
            if row['status']==decision:return {'id':finding_id,'evidence_id':row['evidence_id']}
            if row['status']!='pending':raise DomainError('This finding has already been reviewed or blocked.',409)
            account=self.account(row['account_id'],db)
            if account['suppressed']:raise DomainError('Account is suppressed.',409)
            evidence_id=None
            if decision=='accepted':
                task=db.execute('SELECT input,output FROM tasks WHERE id=?',(row['task_id'],)).fetchone()
                context=json.loads(task['input'])
                config=self.config(db)
                if config['paused'] or config['version']!=context['config']['version']:
                    raise DomainError('Business setup changed or team is paused. Run fresh research before accepting.',409)
                # Other accepted findings in this same report account for these version increments.
                accepted=db.execute("SELECT count(*) FROM research_findings WHERE task_id=? AND status='accepted'",(row['task_id'],)).fetchone()[0]
                if account['version']!=context['accounts'][0]['version']+accepted:
                    raise DomainError('Account context changed. Run fresh research before accepting.',409)
                report=json.loads(task['output'])['research_search']
                refs=set(json.loads(row['source_ids']))
                sources=[x for x in report['sources'] if x['id'] in refs]
                source='Operator-reviewed model research; '+ '; '.join(x['url'] for x in sources)
                evidence_id=uid('ev')
                db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)',
                           (evidence_id,row['account_id'],row['kind'],row['claim'],source,time.time()))
                db.execute('UPDATE accounts SET version=version+1 WHERE id=?',(row['account_id'],))
            db.execute('UPDATE research_findings SET status=?,evidence_id=? WHERE id=?',(decision,evidence_id,finding_id))
            self.event(db,'research.'+decision,{'finding_id':finding_id,'evidence_id':evidence_id},row['account_id'],row['task_id'])
        return {'id':finding_id,'evidence_id':evidence_id}

    def fail(self, task, message):
        with self.write() as db:
            changed = db.execute("UPDATE tasks SET status='failed',error=?,updated_at=? WHERE id=? AND status='running' AND lease_token=?",
                                 (message, time.time(), task['id'], task['lease_token'])).rowcount
            if changed:
                self.event(db, 'task.failed', {'reason': message}, task['account_id'], task['id'])

    def create_experiment(self, discussion_id):
        with self.write() as db:
            discussion = db.execute("SELECT * FROM discussions WHERE id=?", (discussion_id,)).fetchone()
            if not discussion:
                raise DomainError('Discussion not found.', 404)
            if discussion['recommendation'] != 'test' or not discussion['hypothesis']:
                raise DomainError('This discussion has no experiment recommendation.', 409)
            existing = db.execute("SELECT id FROM experiments WHERE discussion_id=?", (discussion_id,)).fetchone()
            if existing:
                return {'id': existing['id']}
            task = db.execute("SELECT input FROM tasks WHERE id=?", (discussion['task_id'],)).fetchone()
            context = json.loads(task['input'])
            config_version = self.config(db)['version']
            if context['config']['version'] != config_version:
                raise DomainError('Business setup changed after this discussion. Run a new discussion before saving an experiment.', 409)
            for snapshot in context['accounts']:
                current = self.account(snapshot['id'], db)
                if current['suppressed'] or current['version'] != snapshot['version']:
                    raise DomainError('Account evidence changed after this discussion. Run a new discussion before saving an experiment.', 409)
            identifier = uid('exp')
            db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,'draft',?,?)",
                       (identifier, discussion_id, discussion['question'], discussion['hypothesis'],
                        'Qualified opportunities per eligible assigned account', config_version, time.time()))
            self.event(db, 'experiment.drafted', {'experiment_id': identifier})
        return {'id': identifier}

    def inspect_draft(self, draft_id):
        with self.write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise DomainError('Draft not found.', 404)
            account = self.account(row['account_id'], db)
            config = self.config(db)
            reasons = ['Outbound delivery is not implemented in this release.', 'Human review of claims and terms is required.']
            if account['suppressed']: reasons.append('Account is suppressed.')
            if account['version'] != row['account_version']: reasons.append('Account evidence changed after this draft.')
            if config['version'] != row['config_version']: reasons.append('Business configuration changed after this draft.')
            if config['paused']: reasons.append('Team is paused.')
            if row['status'] == 'blocked': reasons.append('Writer or evaluator withheld this draft.')
            self.event(db, 'policy.checked', {'draft_id':draft_id,'allowed':False,'reasons':reasons}, account['id'])
            return {'allowed': False, 'mode':'shadow', 'reasons': reasons}

    def snapshot(self):
        with self.connect() as db:
            result = {'config': self.config(db), 'demo': self.demo, 'outbound_enabled':False}
            for table in ('accounts','evidence','tasks','agent_runs','drafts','discussions','experiments','events','research_findings'):
                order = 'id' if table=='events' else 'created_at'
                rows = [dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY {order} DESC LIMIT 300')]
                for row in rows:
                    for field in ('input','output','detail','usage','evidence_ids','source_ids'):
                        if field in row and row[field] is not None:
                            row[field] = json.loads(row[field])
                    # Raw model inputs are available in storage, not repeatedly sent to the UI.
                    if table=='tasks':
                        row['executor']=row['input'].get('executor','api')
                        row.pop('input',None)
                    row.pop('lease_token',None)
                result[table] = rows
            return result
