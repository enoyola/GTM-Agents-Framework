# GTM Agents Framework

A local team of agents for evidence-based account research, message drafting and sales strategy. Start here to try the workflow on fictional accounts or adapt it to a business in a separate private workspace.

## Try the team

Use Python 3.11 or newer. From this repository, run the scripted demo with the standard library.

```sh
python3 -m gtm_agents serve --demo
```

Open [the local dashboard](http://127.0.0.1:8765). Inspect an account review to see what Research supplied, what Sales drafted and how the Evaluator judged it. Open the strategy discussion to compare the two proposals and read the Orchestrator’s decision. The demo uses fictional records and makes no model calls.

For an empty workspace, stop the demo and run `python3 -m gtm_agents serve`. In **Business setup**, enter a business name, offer, audience and approved claims. Add an account with a sourced observation or an explicitly labeled hypothesis. Queue a review, then ask Codex to run the pending task. The default executor uses the current Codex session. The [execution guide](docs/codex-execution.md) covers CLI handoffs, optional MCP registration and recovery.

## How work moves

| Workflow | Handoff | What the operator receives |
| --- | --- | --- |
| Public research | Collector → Extractor → Evaluator | Cited report and candidate findings to accept or reject |
| Account review | Research → Sales → Evaluator | Proposed copy for review when both Sales and Evaluator recommend a draft, otherwise a blocked artifact |
| Strategy | Independent Research and Sales proposals → Evaluator → Orchestrator | Decision with dissent, uncertainties and a possible experiment |

The runtime supports internal research, drafting and planning. External delivery, deal execution and live experiment enrollment fall outside its capabilities.

## Reuse the framework

- Read the [operating methodology](docs/blueprint.md), [role descriptions](docs/roles.md) and [development roadmap](docs/roadmap.md) for the broader design.
- Use the [team coordination](.agents/skills/gtm-run-team/SKILL.md), [outreach review](.agents/skills/gtm-review-outreach/SKILL.md) and [experiment design](.agents/skills/gtm-design-experiment/SKILL.md) skills in Codex.
- Copy a [strategy discussion](templates/strategy-discussion.md), [experiment specification](templates/experiment.md) or [playbook change](templates/playbook-change.md) into the private workspace when recording a decision.
- Use the [blank business configuration](docs/business-config.example.json) as a planning worksheet. Runtime configuration is saved through Business setup. The [exchange schema](docs/contracts.schema.json) and [acceptance scenarios](docs/acceptance-cases.json) describe the target system.

## Workspace boundary

Keep reusable code, methodology, skills, blank templates and synthetic fixtures here. Store real account records, contact details, research packets, messages, approvals and outcomes in the operator’s private workspace. Pass `--db /absolute/path/to/private/gtm.sqlite3` to both the dashboard and the Codex CLI when using an external database. Point any MCP registration at that same database. Keep credentials in the local environment.

## Verify a change

```sh
python3 -m unittest discover -s tests -v
node --check gtm_agents/static/app.js
```

Tests use temporary databases. Install the optional dependencies from `requirements-mcp.lock` to include the MCP stdio integration test.
