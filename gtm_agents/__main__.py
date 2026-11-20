import argparse
import json
from .config import load_env
from .codex_bridge import CodexBridge, CodexProvider
from pathlib import Path

from .demo import seed
from .providers import provider_for
from .runtime import Runtime
from .server import LocalServer
from .store import Store, DomainError


def main():
    parser=argparse.ArgumentParser(description='GTM control room (local, shadow only)')
    sub=parser.add_subparsers(dest='command',required=True)
    serve=sub.add_parser('serve',help='Start the control room with Codex handoffs or an API worker')
    serve.add_argument('--port',type=int,default=8765)
    serve.add_argument('--db',type=Path)
    serve.add_argument('--demo',action='store_true',help='Use separate fictional records and scripted agents; no API requests')
    serve.add_argument('--executor',choices=['codex','api'],default='codex',help='Codex handoffs by default; api runs the standalone model worker')
    serve.add_argument('--env-file',type=Path,help='Explicit local credentials file (never executed)')
    doctor=sub.add_parser('doctor',help='Check configuration without printing credentials')
    doctor.add_argument('--env-file',type=Path)
    doctor.add_argument('--live',action='store_true',help='Make one small paid model request; no CRM data or search')
    bridge=sub.add_parser('codex',help='Durable handoffs for separate Codex agents; no model API key')
    bridge.add_argument('--db',type=Path,default=Path('data/gtm.sqlite3'))
    bridge.add_argument('action',choices=['state','queue','start','status','packet','submit','heartbeat','fail'])
    bridge.add_argument('--task-id')
    bridge.add_argument('--role')
    bridge.add_argument('--assignment-id')
    bridge.add_argument('--agent-id')
    bridge.add_argument('--reason')
    bridge.add_argument('--input',type=Path,help='Task request or result JSON file')
    bridge.add_argument('--output',type=Path,help='Write returned JSON to a file')
    args=parser.parse_args()
    if args.command=='codex':
        try:
            store=Store(args.db);connection=CodexBridge(store)
            data=None
            if args.input:
                if args.input.stat().st_size>200000:raise DomainError('Input JSON file is too large.')
                data=json.loads(args.input.read_text())
                if not isinstance(data,dict):raise DomainError('Input must be a JSON object.')
            if args.action=='state':result=store.snapshot()
            elif args.action=='queue':result=connection.queue(data or {})
            elif args.action=='packet':result=connection.packet(args.task_id,args.role)
            elif args.action=='submit':result=connection.submit(args.assignment_id,args.agent_id,data)
            elif args.action=='fail':result=connection.fail(args.task_id,args.reason)
            else:result=getattr(connection,args.action)(args.task_id)
            output=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(output)
                print(json.dumps({'saved':str(args.output.resolve())}))
            else:print(output,end='')
            return
        except (DomainError,OSError,ValueError) as error:
            parser.error(str(error) if isinstance(error,DomainError) else 'Cannot read or write bridge JSON.')

    try:
        load_env(args.env_file)
        if args.command=='doctor':
            provider=provider_for()
            if args.live:
                print(json.dumps(provider.check_connection()))
            else:
                print(json.dumps({'provider':provider.name,'configured':provider.ready,
                                  'model':provider.model,'live_verified':False}))
            return
    except DomainError as error:
        parser.error(str(error))
    path=args.db or Path('data/demo.sqlite3' if args.demo else 'data/gtm.sqlite3')
    try:
        store=Store(path,demo=args.demo)
        provider=CodexProvider() if not args.demo and args.executor=='codex' else provider_for(args.demo)
        if args.demo:
            seed(store)
            snapshot=store.snapshot()
            if not snapshot['tasks']:
                store.enqueue({'kind':'account_review','account_id':snapshot['accounts'][0]['id'],'request_key':'demo-initial-review'})
                store.enqueue({'kind':'strategy','question':'How should we explain a focused workflow pilot?','request_key':'demo-initial-strategy'})
        server=LocalServer(('127.0.0.1',args.port),store,provider)
    except (DomainError,OSError) as error:
        parser.error(str(error))
    runtime=Runtime(store,provider)
    thread=runtime.start() if provider.name!='codex' else None
    print(f'GTM Agents: http://127.0.0.1:{server.server_address[1]}',flush=True)
    print(f'Workspace: {"fictional demo (scripted, no API calls)" if args.demo else "local"}. Outbound delivery: unavailable.',flush=True)
    if provider.name=='codex':print('Codex mode: queue work here, then ask Codex to run pending GTM tasks. No background model worker.',flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop_event.set()
        server.server_close()
        if thread:thread.join(timeout=2)


if __name__=='__main__':main()
