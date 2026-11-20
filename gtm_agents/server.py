"""Local single-user HTTP interface; no authentication or deployment claims."""
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .store import DomainError

STATIC=Path(__file__).parent/'static'


class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True

    def __init__(self, address, store, provider):
        self.store=store
        self.provider=provider
        self.csrf_token=secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version='GTM-Agents/0.3'

    def log_message(self,format,*args):
        pass

    def allowed_host(self):
        port=self.server.server_address[1]
        return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')

    def respond(self,status,payload,content_type='application/json; charset=utf-8'):
        data=json.dumps(payload).encode() if content_type.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed_host():
            return self.respond(403,{'error':'Local access only.'})
        path=urlsplit(self.path).path
        if path=='/api/state':
            data=self.server.store.snapshot()
            provider=self.server.provider
            data['runtime']={'provider':provider.name,'model':provider.model,
                             'ready':getattr(provider,'ready',True),'csrf_token':self.server.csrf_token}
            return self.respond(200,data)
        if path=='/api/health':
            return self.respond(200,{'ok':True,'mode':'shadow'})
        static={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
        if path not in static:
            return self.respond(404,{'error':'Not found.'})
        file=STATIC/static[path]
        return self.respond(200,file.read_bytes(),mimetypes.guess_type(str(file))[0]+'; charset=utf-8')

    def do_POST(self):
        if not self.allowed_host():
            return self.respond(403,{'error':'Local access only.'})
        origin=self.headers.get('Origin')
        if origin and origin!=f"http://{self.headers['Host']}":
            return self.respond(403,{'error':'Cross-origin writes are not allowed.'})
        if not secrets.compare_digest(self.headers.get('X-GTM-Token',''),self.server.csrf_token):
            return self.respond(403,{'error':'Session token missing. Refresh the page.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.respond(415,{'error':'Use application/json.'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<2 or size>100000:
                raise DomainError('Invalid request size.',413)
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise DomainError('Expected a JSON object.')
            path=urlsplit(self.path).path
            store=self.server.store
            if path=='/api/accounts':result=store.add_account(data)
            elif path=='/api/evidence':result=store.add_evidence(data.get('account_id'),data)
            elif path=='/api/suppress':result=store.suppress(data.get('account_id'))
            elif path=='/api/config':result=store.save_config(data)
            elif path=='/api/pause':result=store.pause(data.get('paused'))
            elif path=='/api/tasks':
                if not getattr(self.server.provider,'ready',True):
                    raise DomainError('Model is not configured. Set GTM_MODEL and OPENAI_API_KEY before running agents.',409)
                result=store.enqueue(data,executor=getattr(self.server.provider,'execution_mode','api'))
            elif path=='/api/research-findings':result=store.review_finding(data.get('finding_id'),data.get('decision'))
            elif path=='/api/experiments':result=store.create_experiment(data.get('discussion_id'))
            elif path=='/api/check-draft':result=store.inspect_draft(data.get('draft_id'))
            else:raise DomainError('Not found.',404)
            self.respond(200,result)
        except DomainError as error:
            self.respond(error.status,{'error':str(error)})
        except (ValueError,UnicodeDecodeError):
            self.respond(400,{'error':'Invalid JSON request.'})
        except Exception:
            self.respond(500,{'error':'Internal error. The action was not confirmed.'})
