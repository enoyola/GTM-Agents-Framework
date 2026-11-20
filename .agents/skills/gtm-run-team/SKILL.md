---
name: gtm-run-team
description: Coordinate queued prioritization, public research, account reviews and strategy discussions through the local GTM Codex bridge.
---

# Run the GTM team

Resolve the intended database before claiming a task. A registered MCP server is bound to one database. If its identity is unclear, use the local CLI with the same explicit database path as the dashboard.

1. Read state, select queued work, claim it, then request only the ready role packets. Reuse a request key only for the same logical request.
2. Assign a fresh agent to each packet. Pass only its packet and result path. Tell it to read only its assigned inputs, leave other files alone and return the result there. Public browsing belongs to the research collector.
3. Submit the exact result using the returned agent identity. Research and Sales strategy proposals are independent. Give the Evaluator both proposals, then give the Orchestrator the proposals and critique.
4. Renew the lease during work. On interruption inspect saved runs. Mark expired work failed and use a fresh task when a retry is justified.
5. Report the stored result, open questions and next owner decision. A reviewed draft is an internal artifact. Candidate findings need an operator decision.

For an `account_priority` task, dispatch the single `prioritizer` role. Reassess after the account evidence or targeting criteria change.

The [bridge runbook](../../../docs/codex-execution.md) gives the CLI commands, packet dependencies and recovery procedure.
