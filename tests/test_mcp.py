"""Real stdio transport tests; use .venv/bin/python after installing the optional SDK."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from gtm_agents.store import Store

HAS_MCP=importlib.util.find_spec('mcp') is not None
if HAS_MCP:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client


@unittest.skipUnless(HAS_MCP,'Optional MCP SDK is not installed in this Python environment')
class McpCase(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_tool_discovery_handoffs_and_error_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'mcp.sqlite3';store=Store(path)
            store.save_config({**store.config(),'business_name':'Example Studio','offer':'Test pilot',
                               'approved_claims':['Test pilot available'],'segment':'Test-only audience'})
            store.add_account({'name':'Test','domain':'example.com','claim':'Operator note','source':'Operator'})
            script=Path(__file__).resolve().parents[1]/'scripts/gtm_mcp.py'
            params=StdioServerParameters(command=sys.executable,args=[str(script),'--db',str(path)],cwd=directory)
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    tools=await session.list_tools()
                    self.assertEqual(len(tools.tools),8)
                    self.assertTrue(next(t for t in tools.tools if t.name=='gtm_workspace_state').annotations.readOnlyHint)
                    async def call(name,args):
                        result=await session.call_tool(name,args)
                        self.assertFalse(result.isError,result)
                        return result.structuredContent or json.loads(result.content[0].text)
                    state=await call('gtm_workspace_state',{})
                    self.assertNotIn('OPENAI_API_KEY',json.dumps(state))
                    task=(await call('gtm_queue_task',{'kind':'strategy','request_key':'mcp-roundtrip','question':'What should we validate?'}))['id']
                    await call('gtm_start_task',{'task_id':task})
                    await call('gtm_heartbeat',{'task_id':task})
                    status=await call('gtm_task_status',{'task_id':task})
                    self.assertEqual(status['ready_roles'],['research','sales'])
                    premature=await session.call_tool('gtm_agent_packet',{'task_id':task,'role':'orchestrator'})
                    self.assertTrue(premature.isError)
                    for role in ('research','sales','evaluator','orchestrator'):
                        packet=await call('gtm_agent_packet',{'task_id':task,'role':role})
                        result={'summary':'Needs evidence','recommendation':'research_more', 'content':'Validate with the buyer.',
                                'evidence_ids':[e['id'] for e in packet['context']['evidence']], 'uncertainties':['No outcomes'],'experiment_hypothesis':''}
                        await call('gtm_submit_result',{'assignment_id':packet['assignment_id'],'agent_id':'test-'+role,'result':result})
                    self.assertEqual((await call('gtm_task_status',{'task_id':task}))['status'],'completed')
                    self.assertEqual(len((await call('gtm_workspace_state',{}))['discussions']),1)
                    task=(await call('gtm_queue_task',{'kind':'strategy','request_key':'mcp-failed','question':'Interrupted test'}))['id']
                    await call('gtm_start_task',{'task_id':task})
                    self.assertEqual((await call('gtm_fail_task',{'task_id':task,'reason':'Test interruption'}))['status'],'failed')
                    invalid=await session.call_tool('gtm_submit_result',{'assignment_id':'missing','agent_id':'test','result':{}})
                    self.assertTrue(invalid.isError)

if __name__=='__main__':unittest.main()
