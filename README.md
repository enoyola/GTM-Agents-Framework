# GTM Agents Framework

GTM Agents helps a go-to-market team decide who to approach, what it can credibly say, and which sales idea to test next. You give the agents an offer, an audience and evidence about a company. They return work you can inspect in a local dashboard, from a cited research finding to a draft message or an experiment proposal. All outreach stays in draft form.

For example, the demo includes a fictional packaging company where artwork revisions need approval before production. That observation gives Sales a handoff to ask about. The Evaluator can then flag any claim about delays or costs that the observation alone cannot support.

## Try the demo

You need Git and Python 3.11 or newer. The demo runs on your computer with Python’s standard library, three fictional accounts and scripted agent responses. You can try it without an API key or a Codex account.

```sh
git clone https://github.com/enoyola/GTM-Agents-Framework.git
cd GTM-Agents-Framework
python3 -m gtm_agents serve --demo
```

Leave the terminal running and open the [local dashboard](http://127.0.0.1:8765). On the first launch, the demo automatically runs an account review and a strategy discussion.

1. In **Pipeline**, select the account marked **Drafted**. Read **Account evidence**, then scroll to **Latest outreach draft** and **Evaluator notes**. Compare the original observation with what the draft actually claims.
2. In **Strategy room**, find the discussion “How should we explain a focused workflow pilot?” Read the Research and Sales proposals, the Evaluator’s challenge and the **Orchestrator decision**. Notice which part of the message the team proposes changing and what it would hold constant.
3. Select **Create experiment brief**, then open **Learning**. You’ll see the hypothesis, the proposed metric and the details a person would still need to define before running the test.

Press `Ctrl+C` in the terminal to stop. Run the same command again to reopen your demo with its saved work.

## How the agents work together

| When you want to… | Who does what | What you review |
| --- | --- | --- |
| Research a company | A **Collector** gathers public sources. An **Extractor** turns the cited report into individual findings. The **Evaluator** checks whether the report supports each claim. | A cited report and candidate findings. You decide which findings to accept as account evidence. |
| Prepare a first message | **Research** briefs **Sales** on the account evidence and open questions. Sales proposes a message. The **Evaluator** reads that exact draft from the recipient’s perspective and checks its claims. | A draft for human review if Sales and the Evaluator both recommend it, or a record of why the draft was held. |
| Decide what to test | **Research** and **Sales** propose approaches independently. The **Evaluator** challenges both. The **Orchestrator** weighs the proposals and critique and records a decision. | Both proposals, the critique and the decision. If the decision calls for a test, you can save an experiment brief. |

## Use your own workspace

Stop the demo, then run `python3 -m gtm_agents serve` from the repository directory to open a separate workspace. In **Business setup**, enter your offer, target audience and approved claims under your business name. In **Pipeline**, add a company and a sourced observation, then select **Run account review**.

The default workflow uses your Codex session. After queuing the review, open this repository in Codex and ask it to **“Run the pending GTM tasks using separate agents.”** Return to the dashboard to inspect the results. For CLI handoffs, optional MCP registration and recovery, see the [execution guide](docs/codex-execution.md).

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
