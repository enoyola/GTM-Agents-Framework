"""Bounded workflows with durable intermediate results and stale-input checks."""
import logging
import threading

from .store import DomainError

log=logging.getLogger(__name__)


class Runtime:
    def __init__(self,store,provider):
        self.store=store
        self.provider=provider
        self.stop_event=threading.Event()

    def run_once(self):
        task=self.store.claim()
        if not task:
            return False
        context={**task['input'],'kind':task['kind']}
        runs={}
        roles=['research','sales','evaluator']
        if task['kind']=='strategy':roles.append('orchestrator')
        try:
            if task['kind']=='account_research':
                self.research(task,context)
                return True
            for role in roles:
                if self.stop_event.is_set():
                    raise DomainError('Worker stopped. Partial results are retained; retry explicitly.')
                self.store.run_context(task)
                # Research and sales submit independent proposals for strategy reviews.
                previous={} if task['kind']=='strategy' and role in ('research','sales') else runs.copy()
                result,usage=self.provider.generate(role,context,previous)
                self.store.save_run(task,role,result,self.provider.name,self.provider.model,usage)
                runs[role]=result
            self.store.complete(task,runs)
        except DomainError as error:
            self.store.fail(task,str(error))
        except Exception:
            # Log the exception class locally, without prompt bodies or secret-bearing details.
            log.error('Task %s failed with an internal runtime error',task['id'])
            self.store.fail(task,'Internal runtime error. Inspect the task and implementation before retrying.')
        return True

    def research(self,task,context):
        runs={}
        for role in ('research_search','research_extract','evaluator'):
            if self.stop_event.is_set():raise DomainError('Worker stopped; retry explicitly.')
            self.store.run_context(task)
            if role=='research_search':
                result,usage=self.provider.search(context)
            elif role=='research_extract':
                result,usage=self.provider.extract(context,runs['research_search'])
            else:
                findings=runs['research_extract']['findings']
                evidence=[{'id':f'candidate_{i+1}',**f} for i,f in enumerate(findings)]
                critique={**context,'evidence':evidence,'kind':'research_validation',
                          'research_report':runs['research_search']}
                result,usage=self.provider.generate('evaluator',critique,runs.copy())
            self.store.save_run(task,role,result,self.provider.name,self.provider.model,usage)
            runs[role]=result
        self.store.complete_research(task,runs)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                did_work=self.run_once()
            except Exception:
                log.error('Worker could not access the queue; will retry.')
                did_work=False
            if not did_work:self.stop_event.wait(0.75)

    def start(self):
        thread=threading.Thread(target=self.loop,name='gtm-worker',daemon=True)
        thread.start()
        return thread
