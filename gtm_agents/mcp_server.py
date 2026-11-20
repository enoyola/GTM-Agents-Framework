"""Optional MCP stdio transport over the same validated local bridge."""
from typing import Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .codex_bridge import CodexBridge
from .store import Store


def create_server(path):
    store=Store(path);bridge=CodexBridge(store)
    server=FastMCP('GTM-Agents',instructions='Use these tools for the configured local GTM workspace. Separate fresh Codex agents execute each assigned role. This server does not spawn agents. Never fabricate a role execution or auto-accept research findings. No outreach tools are exposed.',log_level='WARNING')
    read=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
    write=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)

    @server.tool(annotations=read)
    def gtm_workspace_state() -> dict:
        """Read local accounts, evidence, pending tasks, saved research and decisions. No credentials returned."""
        return store.snapshot()

    @server.tool(annotations=write)
    def gtm_queue_task(kind:Literal['account_research','account_review','strategy','account_priority'],request_key:str,account_id:str|None=None,question:str='',research_task_ids:list[str]|None=None) -> dict:
        """Queue authorized GTM work for Codex. Does not call a model, browse or send outreach. Reuse request_key only for identical work."""
        return bridge.queue({'kind':kind,'request_key':request_key,'account_id':account_id,'question':question,'research_task_ids':research_task_ids or []})

    @server.tool(annotations=write)
    def gtm_start_task(task_id:str) -> dict:
        """Claim a queued Codex task for 30 minutes. Then dispatch its ready roles as distinct fresh Codex agents."""
        return bridge.start(task_id)

    @server.tool(annotations=read)
    def gtm_task_status(task_id:str) -> dict:
        """Read completed and ready roles, lease expiry, and recorded agent identities for a Codex task."""
        return bridge.status(task_id)

    @server.tool(annotations=write)
    def gtm_agent_packet(task_id:str,role:str) -> dict:
        """Freeze scoped role instructions, context and result schema for one fresh agent. Blocks premature evaluation; independent proposals receive no sibling outputs."""
        return bridge.packet(task_id,role)

    @server.tool(annotations=write)
    def gtm_submit_result(assignment_id:str,agent_id:str,result:dict) -> dict:
        """Persist a genuine separate Codex agent result with its actual execution ID. Validates schema, references and state; final submission commits the research or decision atomically."""
        return bridge.submit(assignment_id,agent_id,result)

    @server.tool(annotations=write)
    def gtm_heartbeat(task_id:str) -> dict:
        """Extend a still-owned, current task lease by 30 minutes while its Codex agents work. Does not resurrect expired work."""
        return bridge.heartbeat(task_id)

    @server.tool(annotations=write)
    def gtm_fail_task(task_id:str,reason:str) -> dict:
        """Mark interrupted Codex work failed with a concise non-secret reason; preserves partial agent outputs."""
        return bridge.fail(task_id,reason)

    return server
