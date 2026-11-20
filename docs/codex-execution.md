# Codex execution and local MCP connection

GTM-Agents is the durable record. Codex is the execution host. The application does not call a model API or spawn Codex from its web server in this mode. A Codex coordinator dispatches actual fresh role agents and imports their results through the bridge. This works now through local CLI tools; the MCP stdio server exposes the same operations to a client that has loaded the project configuration.

## Run the dashboard

```bash
python3 -m gtm_agents serve
```

Codex is now the default executor. Create/queue research, account reviews or a strategy discussion, then ask Codex: **“Run the pending GTM tasks using separate agents.”** Merely clicking a dashboard button does not wake this chat. This release has no scheduled dispatcher. Codex usage limits and connected tool permissions apply. The API worker remains available through `serve --executor api --env-file .env`; it will not claim Codex work.

## Role graph

| Workflow | Separate agent executions |
|---|---|
| Account prioritization | One prioritizer per assessed account |
| Public research | Collector → Extractor → Evaluator |
| Account review | Research → Sales → Evaluator |
| Strategy | Research and Sales independently → Evaluator → Orchestrator |

Each role uses our existing instructions and contracts. Strategy proposals can run concurrently. Later agents see only required predecessor outputs. The evaluator records critique; the orchestrator records the final decision. The original independent proposals are retained unchanged.

Fresh context is enforced by the coordinator's dispatch protocol, not an operating-system sandbox. Agents still share the host filesystem/tools. The bridge checks distinct reported agent IDs, but cannot cryptographically attest their origin or which model ran. The coordinator must use actual IDs returned by Codex, never invented labels. Metering is `null`, not zero, when unavailable.

## MCP installation

The optional MCP transport uses the official Python SDK, pinned in `requirements-mcp.lock`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.lock
```

Register a project-local server in `.codex/config.toml` using absolute paths (example below). This machine-specific file is ignored by Git. Project MCP configuration is loaded only for trusted projects. Reload/restart the MCP connection in Codex to load newly registered tools. The server uses stdio, not a public HTTP endpoint, and binds to one configured SQLite workspace. No API key or authentication token is needed for the local bridge.

```toml
[mcp_servers.gtm_framework]
command = "/absolute/path/GTM-Agents-Framework/.venv/bin/python"
args = ["/absolute/path/GTM-Agents-Framework/scripts/gtm_mcp.py", "--db", "/absolute/path/GTM-Agents-Framework/data/gtm.sqlite3"]
startup_timeout_sec = 20
tool_timeout_sec = 30
```

The project registration does not change global credentials, trust, or approval settings. MCP exposes eight tools: workspace state, queue, start, task status, agent packet, submit result, heartbeat, and fail. It does not expose email delivery, research acceptance, arbitrary SQL, arbitrary filesystem operations or arbitrary model calls. A local user with access to SQLite remains trusted; these are not multi-user authorization controls.

Official references: [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [building an MCP server](https://developers.openai.com/plugins/build/mcp-server).

## Equivalent CLI operations

All operations accept `--db`; the default is `data/gtm.sqlite3`. Run from the repository root. Input/result JSON is read from files without shell evaluation. `--output` writes returned JSON to the requested path.

```bash
python3 -m gtm_agents codex state
python3 -m gtm_agents codex queue --input work/task-request.json
python3 -m gtm_agents codex start --task-id TASK_ID
python3 -m gtm_agents codex packet --task-id TASK_ID --role research --output work/research-packet.json
python3 -m gtm_agents codex submit --assignment-id ASSIGNMENT_ID --agent-id ACTUAL_CODEX_AGENT_ID --input work/research-result.json
python3 -m gtm_agents codex status --task-id TASK_ID
python3 -m gtm_agents codex heartbeat --task-id TASK_ID
python3 -m gtm_agents codex fail --task-id TASK_ID --reason "Agent execution interrupted"
```

For a priority assessment, queue `{"kind":"account_priority","account_id":"ACCOUNT_ID","request_key":"UNIQUE_KEY"}`. Request the `prioritizer` packet and submit its result through the usual bridge. Each assessment uses saved evidence and the configured targeting rules. The workspace state includes the latest assessments under `priorities`. A fresh task key requests a new assessment.

A strategy request contains `kind: strategy`, `question`, and an explicit unique `request_key`. Account work additionally requires `account_id`. Public research uses `kind: account_research` and a public focus in `question`. Prefer tool arguments or JSON files over interpolating business text into shell commands.

## Coordinator procedure

1. Inspect state and choose a queued Codex task. Claim it with `start`; an existing current claim returns its status. API-tagged tasks cannot be claimed by this bridge.
2. Obtain a packet for each ready role. Each packet is immutable and bound to one task, role, and assignment ID. A strategy Sales packet excludes Research even if Research already finished.
3. Dispatch a **fresh** Codex subagent with only that packet and its result file path. Do not fork the full conversation. Instruct the agent to avoid sibling output, credentials and database files. No hidden reasoning is requested or persisted.
4. Import its exact JSON result using its actual Codex identity. The bridge validates references/schema and rechecks the task lease, account versions, config version and suppression. An identical repeated submission is idempotent; conflicting results/identities are rejected.
5. Dispatch newly ready roles. Renew the 30-minute lease while agents work. Expired work cannot be resurrected; mark it failed and inspect partial results before a new task.
6. The last submission atomically stores the final role, research findings or discussion/decision, and completion event. Storage failure rolls back the last submission so a retry cannot strand a completed role without its artifact.

## Draft review

Sales and Evaluator must each recommend `draft` for a `needs_review` artifact; either withholding recommendation leaves it blocked. The evaluator must assess the actual submitted Sales text, not rewrite it and pass the original. Editorial checks are model judgments; operator review is still necessary.

Existing assignments and imported results are immutable snapshots. Editing the policy does not rewrite a prior packet or re-evaluate an old draft. Inspect and close interrupted work as needed, then create fresh tasks/assignments for the new policy. Label coordinator-written examples honestly. Neither this update nor a successful import authorizes outreach.

## Research provenance

The Codex collector saves actual public URLs, titles, collection timestamps and Unicode offsets for inline citations. Its report is explicitly marked `codex_agent_reported`; it is not represented as an OpenAI API search response. Structural validation cannot independently prove the browsing occurred or that a source supports a sentence. Only actual browsing results should be submitted.

Extraction and evaluation use the saved report. Findings remain pending (or blocked), and do not automatically enter accepted account evidence. Citations remain clickable in the dashboard. No raw webpage snapshots or verified outcome claims are implied. Codex tool-call counts and costs are not exposed or bounded by the API adapter's web-search limit; the coordinator should keep research focused and obey the session budget.

## Persistence and recovery

Schema version 4 adds account priorities and repairs legacy account stages for held reviews. Earlier versions introduced immutable `codex_assignments` alongside existing `agent_runs`, research candidates, discussions and events. Task inputs carry `executor: codex`; legacy/API tasks default to `api`. Default dashboard startup does not start the API worker. A running API worker filters its queue and cannot execute a Codex task.

All completed outputs remain in SQLite even when the Codex turn ends. Raw role packet/result files in `work/` are temporary handoff artifacts. Restart the dashboard to view saved work; no API key is needed. Back up SQLite before upgrading a valuable workspace.

## Research-informed strategy

Strategy requests may include `research_task_ids`, a list of up to three completed, unblocked public research tasks. The bridge freezes each report, extraction, evaluator critique and finding review states in the strategy packet. Pending candidates remain pending; this does not accept them into account evidence. Strategy roles cite task/source IDs in prose and reserve `evidence_ids` for actual evidence records. Blocked reports, stale configuration/account context and suppressed accounts are rejected. Changed review states invalidate running strategy work. Both independent proposing roles receive the same attached research without seeing each other's proposal.
