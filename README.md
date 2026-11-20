# GTM Agents Framework

GTM Agents helps a go-to-market team decide who to approach, what it can credibly say, and which sales idea to test next. You give the agents an offer, an audience and evidence about a company. They return work you can inspect in a local dashboard, from a cited research finding to a draft message or an experiment proposal. All outreach stays in draft form.

For example, the demo includes a fictional packaging company where artwork revisions need approval before production. That observation gives Sales a handoff to ask about. The Evaluator can then flag any claim about delays or costs that the observation alone cannot support.

## What each agent does

| Agent | Its job |
| --- | --- |
| **Account Prioritization** | Assesses an account against your target segment, qualification rubric and exclusions. Its fit decision cites evidence, explains the reason and identifies one fact to verify. Current assessments form the shortlist for strategy. |
| **Research** | Writes an account brief from the evidence on file. It explains why the offer might fit and lists what Sales still needs to learn. In a strategy discussion, it proposes an approach independently of Sales. |
| **Sales** | Uses the brief and the approved offer to draft a message for a specific recipient. If a credible message needs more evidence, it explains what is missing. In a strategy discussion, it contributes the seller’s perspective. |
| **Reply Triage** | Reads a buyer reply you paste into Pipeline, identifies the request, quotes the words behind its interpretation and suggests an internal next action for you to review. |
| **Discovery and Qualification** | Turns conversation notes into a Sales brief. It cites buyer-confirmed needs, constraints and decision participants, lists open questions, and recommends advancing, clarifying or closing against your qualification rubric. |
| **Deal Desk** | Matches buyer requirements to an approved fixed-fee package and prepares an internal proposal, exception request or clarification. The runtime calculates the net price and checks commercial limits. |
| **Evaluator** | Reviews another agent’s work. It checks research claims against citations, reads a draft from the recipient’s perspective, and challenges assumptions in strategy proposals. |
| **Orchestrator** | Closes a strategy discussion. After reading both proposals and the critique, it records whether to keep the current approach, gather more evidence or propose a test. |

Public research has two additional assignments. The **Collector** looks up the company and writes a report with citations. The **Extractor** reads that report, separates observations from hypotheses and links each finding to its source. The Evaluator reviews the findings before you decide which to accept.

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

To try prioritization, choose **Assess priority** on each fictional account in **Pipeline**. The shortlist shows the reasoning and the next fact to verify. In the scripted demo, Forma Packaging leads because of its documented artwork approval step. To see the ranking change, check that **Business setup → Priority exclusions** contains `Business has closed permanently.` (prefilled in a new demo). Add the observation `Business has closed permanently.` to that fictional account and assess it again. The demo recognizes this exact scenario. In Codex or API mode, the agent interprets the targeting rules and evidence.

To try **Reply Triage**, select an account in **Pipeline**, choose **Triage a reply**, paste `How much does the pilot cost?` and select **Queue triage**. Compare the quoted words with the suggested pricing handoff to Sales, then select **Mark reviewed**. Try `Please ask our operations team.` for a referral or `Please remove me from your list.` for an opt-out. The offline demo recognizes canned examples and sends other wording to manual review. Codex and the API worker interpret free-form replies.

To try **Discovery and Qualification**, open an account in **Pipeline**, select **Qualify a conversation → Use demo notes → Create discovery brief**. The example buyer needs artwork approvals tracked, identifies the process owner and requests an outline. Compare the **advance** recommendation with the excerpts and the remaining question about approval authority. To try **close**, paste `Buyer: We have ended this project. Please close the opportunity.` Other free-form notes use the scripted **clarify** fallback in the demo. Codex and the API worker interpret free-form notes using the **Qualification rubric** in **Business setup**.

To try **Deal Desk** in a new demo, select **Pipeline → an account → Prepare a deal proposal → Use demo request**. Enter a 5% discount and queue the review. The fictional USD 1,000 pilot yields a USD 950 proposal. Run the same request with a 10% discount and a USD 100 credit: the USD 800 net price falls below the USD 850 floor and exceeds the 10% combined concession limit. The card identifies the commercial exception owner. **Mark reviewed** records the operator’s review only.

Press `Ctrl+C` in the terminal to stop. Run the same command again to reopen your demo with its saved work.

## How the agents work together

| Workflow | Order of work | What you review |
| --- | --- | --- |
| Account prioritization | Assess each selected account → order by fit, breaking ties by domain | A shortlist of current strong and possible fits. Accounts needing research and excluded accounts retain their reasons in Pipeline. |
| Public research | Collector → Extractor → Evaluator | A cited report and findings to accept or reject. |
| Account review | Research → Sales → Evaluator | A message for human review when Sales and the Evaluator both recommend it, or an explanation of why it was held. |
| Reply triage | Operator supplies reply → Reply Triage interprets it → operator reviews the recommendation | The original message, supporting quote, intent and proposed handoff. Marking it reviewed records your review. You decide separately whether to act. |
| Discovery and qualification | Operator supplies notes → agent applies the qualification rubric → Sales reviews the brief | Findings linked to notes, unresolved questions and an advance, clarify or close recommendation. Marking it reviewed records the review. |
| Deal review | Buyer requirements and optional reviewed discovery → Deal Desk matches scope → application checks terms → operator reviews | A versioned internal proposal, a commercial exception with reasons, or a question to resolve before quoting. |
| Strategy discussion | Research and Sales propose independently → Evaluator critiques both → Orchestrator decides | The two proposals, critique and decision. A proposed test can become an experiment brief. |

## Use your own workspace

Stop the demo, then run `python3 -m gtm_agents serve` from the repository directory to open a separate workspace. In **Business setup**, enter your offer, target audience and approved claims under your business name. In **Pipeline**, add a company and a sourced observation, then select **Run account review**.

For prioritization, fill in **Target customer segment** and any **Priority exclusions** in **Business setup**. Run **Assess priority** on the accounts you want to compare. Each assessment is one agent task. Changes to evidence or business settings make the affected assessments outdated. Once you have saved an assessment, new strategy discussions draw on up to 20 currently shortlisted accounts. Before the first assessment, strategy uses the existing recent-account selection.

The account stage shows **Drafted** when Sales and the Evaluator recommend a draft for human review. A held review shows **Needs research** when either role requests more evidence, or **Needs revision** otherwise.

For Deal Desk, open **Business setup → Deal Desk catalog and pricing policy**. Set a currency, validity period and exception owner. Add each package’s approved scope, fixed fee, floor, combined discount limit and standard payment period. Save configuration before queuing work. Each request covers one package in one currency; use the additional terms field for delivery promises, other concessions or existing commitments requiring review. You may attach a current, reviewed discovery brief for the same account that recommends advancing. The real workspace starts with an empty catalog. Existing demo workspaces can configure the same [fictional example policy](docs/deal-policy.example.json).

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
