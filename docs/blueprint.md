# GTM operating model

This design describes the full account lifecycle. The local runtime implements research, draft review, strategy discussions and experiment proposals.

## 1. Direction and scope

The initial purpose is internal revenue generation. A product for other companies may follow after the internal team demonstrates repeatable value, but tenant management, customer billing, and a public product are outside the first release.

The agreed direction is a team with different roles, autonomy to research and execute, direct collaboration between agents, structured strategy discussions, experiments, and ongoing improvement. Agents should eventually help negotiate with prospects. The architecture should support those capabilities without requiring a large roster on day one.

The proposed first release consists of one orchestrator, a research specialist, a sales specialist, and an evaluator that runs on demand or on a schedule. Proposal and negotiation responsibilities initially sit with the sales specialist using a restricted offer catalog; a separate deal agent becomes useful when commercial complexity justifies it.

Start with one existing offer, one defined customer segment, and one acquisition channel. Email is an illustrative pilot channel, not a settled choice. A narrow scope makes outcomes easier to interpret and exposes missing information sooner.

Success means more economically useful customer opportunities with less operator effort. Activity is supporting evidence: a large volume of research, emails, or agent discussion is not by itself a business result. Track qualified opportunities, won customers, contribution margin, acquisition cost, and human time alongside quality and delivery indicators.

Initial non-goals include unrestricted self-modification, autonomous changes to pricing authority, general internet access with arbitrary execution, and simultaneous optimization of every channel and segment. Those restrictions are product design choices that preserve an understandable pilot.

## 2. Owner experience and control room

The owner should be able to answer five questions quickly: What is the team trying to achieve? What is happening with each prospect? What is it learning? What needs my decision? What is the cost and business result?

The Pipeline view shows accounts, their current stage, one conversation owner, last meaningful event, next action, supporting evidence, and any commitments. Selecting an account opens its complete history, including human actions. Work awaiting a reply should not appear as agent failure.

The Strategy Room view shows structured discussions. Each discussion has a question, evidence packet, competing proposals, a challenge round, and a decision. Show concise rationales and source references rather than private model reasoning. The owner can contribute information, reject an assumption, or change priorities.

The Learning view shows experiments, allocation, maturity of outcomes, primary metrics, uncertain findings, and playbook versions. It must be possible to inspect why a strategy was adopted and the accounts or segments to which the evidence applies.

An Exceptions queue collects decisions outside current authority: unusual contract requests, conflicting product information, missing commercial terms, and changes to policy. Routine work continues where independent of an exception.

Global controls include pause outbound activity, pause a campaign or account, reduce spend, inspect audit records, and restore a previous playbook. A pause stops new external actions; pending provider operations are reconciled and displayed. A rollback cannot retract messages already delivered or erase promises already made.

A periodic owner digest should report material results, decisions, experiments, and blockers. Its schedule is configurable. Avoid sending an alert for every agent message or unchanged status.

## 3. Architecture and execution layers

Use a hybrid architecture. Model-driven agents handle interpretation, research, planning, and conversation. Conventional application code handles durable state, authorization, scheduling, account ownership, spend accounting, retries, and delivery reconciliation. A prompt is not an enforcement mechanism.

The owner supplies goals and an approved policy. The orchestrator turns goals and incoming events into scoped tasks. Specialists complete those tasks using a gateway of permitted tools. Tool outcomes and customer events are recorded in a shared data store. The evaluator reviews outputs and experiments; validated playbook changes feed future tasks.

Logical components are the control-room interface, workflow service, agent runtime, policy and tool gateway, relational store, evidence storage, connector adapters, and evaluator. These can initially live in one application with a worker process. Logical separation does not require a fleet of microservices.

The workflow service owns an event queue, task leases, bounded retries, deduplication, and recovery after restart. Agents should receive compact task context instead of repeatedly reading the entire company history. The relational store remains the source of truth; semantic retrieval is optional and supports discovery rather than replacing exact account and permission checks.

External connectors may include the existing CRM, research providers, a sending account, calendar, and an approved proposal system. Choose the actual stack after inspecting current tools. Do not select a new CRM simply to accommodate the agents.

Separate a decision from an action: the agent proposes a structured command, the gateway checks authority and current state, and the connector executes it. The result returns as a durable event with provider identifiers. This separation makes failures and business decisions distinguishable.

The accompanying Mermaid file specifies the component relationships, learning loop, account lifecycle, and outbound action sequence.

## 4. Agent responsibilities and handoffs

The orchestrator owns the campaign objective, account priorities, assignment, queue health, experiment allocation, and resolution of disagreements. It must identify the expected deliverable, budget, deadline, and stopping condition for each delegated task. It cannot expand its own policy or declare a strategy successful without the required evidence.

The research agent produces account briefs with verified fit signals, likely needs, appropriate contacts, source dates, and missing information. It distinguishes what a company publicly states from what the agent infers. It can recommend exclusion or further research. It does not promise product capabilities or send outreach in the initial role definition.

The sales agent owns the customer conversation from first contact through qualification. It uses approved claims, answers known questions, records objections, handles follow-ups, and requests help when facts are missing. It uses a stable sender identity. Multiple agents may contribute internally, but only the assigned owner controls the outbound conversation.

The deal function maps needs to approved packages, prepares proposals, and negotiates permitted concessions. Initially this is a sales capability. Later it can be a separate agent that advises the conversation owner without starting a second thread with the buyer.

The evaluator reviews evidence quality, labeling, experiments, and candidate playbook revisions. It should receive immutable outcome records and evaluate independently before seeing advocates' final conclusions where feasible. It cannot approve pricing-policy changes or silently rewrite observed outcomes.

A handoff contains the account and task identifiers, current stage, evidence references, promises already made, open questions, recommended next action, active experiment, current playbook, and applicable policy. The receiving role acknowledges ownership through the workflow service. An informal agent message does not transfer ownership.

Expand roles only when workload or evidence shows a distinct skill boundary. A large roster adds coordination cost and creates more opportunities for conflicting interpretations.

## 5. Orchestration and account lifecycle

The proposed account lifecycle is discovered, researched, eligible, ready, contacted, engaged, qualified, proposal, negotiation, and won or lost. Nurture and suppressed are additional states. A human-assisted pilot may stop autonomous progression at qualified or proposal.

Every transition has evidence. Researched requires a usable brief; eligible requires confirmed inclusion and exclusion checks; contacted requires provider acknowledgment; qualified requires the configured qualification criteria; won requires authoritative commercial confirmation. An agent's optimism never moves an account to won.

Readiness includes a current policy, permitted channel, usable contact record, approved offer, available budget, contact eligibility, and no active suppression. Qualification should use a written rubric covering fit, relevant problem, buying process, and a meaningful agreed next step. Adapt the rubric to the business instead of inventing a universal score.

Events trigger work: a new account, reply, scheduled follow-up, proposal response, delivery issue, owner change, or experiment review. Timer events wake only due tasks. A waiting task should release its worker rather than keep an agent running indefinitely.

Prioritization starts with transparent rules: customer fit, evidence of need, strength and freshness of buying signals, current engagement, and expected research effort. Predictive scoring is optional later. Record the reasons for priority so the owner can correct assumptions.

The workflow service obtains an account lease before mutating its conversation. Immediately before sending, it checks for newer replies, suppression changes, human intervention, and stale drafts. A human reply invalidates queued automated follow-ups that were based on the previous state.

Temporary connector failures receive bounded retries with backoff. Invalid policy or missing data routes to a blocked task with a specific recovery condition. Exhausted retries enter an exception queue. Restarting the service must resume pending work without duplicating external actions.

## 6. Agent discussions and decisions

Collaboration happens both during individual deals and across strategy reviews. A sales agent may ask research to verify a fact without calling a full strategy meeting. A strategy review is justified by a recurring objection, a completed outcome window, conflicting evidence, or a material performance change.

Use a bounded discussion protocol. First, create an evidence packet and a precise question. Second, each relevant role submits an independent proposal. Third, an assigned challenger examines missing evidence, alternative explanations, and costs. Fourth, the orchestrator chooses a decision or a test. The evaluator checks that the proposed test can answer the question.

Independent proposals reduce simple imitation between agents. Multiple agents using similar models are not independent witnesses; agreement does not turn an unsupported claim into a fact. Product truth and customer outcomes must come from authoritative records.

Every proposal states the observation, hypothesis, suggested change, expected business effect, evidence, alternative explanation, and falsification condition. Every decision records the selected action, owner, scope, spend ceiling, review condition, dissent, and decision-maker.

Proposed initial limits are three discussion rounds and four participants per strategy discussion. These are configurable operating limits, not estimates of optimal team size. If discussion remains unresolved, select a safe discriminating experiment, retain the baseline, or ask the owner when the decision is outside authority.

The room is an operating tool rather than continuous chatter. Agents do not debate unchanged conditions. A new discussion should reference an existing one when the question is materially the same. Link all discussion outcomes to the relevant task, experiment, policy exception, or playbook revision.

Useful outputs are decisions and testable hypotheses. A transcript without an accountable next action is unfinished work.

## 7. Shared memory and evidence

Keep four categories distinct: facts, hypotheses, experiments, and playbooks. A fact includes a source and observation time. A hypothesis is an explanation to investigate. An experiment records a controlled change. A playbook describes an approach adopted for a specified context.

Account memory includes contact identity, fit evidence, message history, qualification notes, objections, proposals, agreed next steps, and commitments. Campaign memory includes segment definitions, offer versions, active experiments, budgets, and channel policy. Organization memory includes approved product claims, commercial terms, exclusions, and escalation owners.

Each evidence item needs an identifier, source locator, captured time, author or connector, claim, evidence type, and freshness policy. Store contradictions explicitly. If an old product page conflicts with the approved offer catalog, the agent should surface the conflict and use the designated authoritative source.

Confidence should describe evidence quality, not just a model-generated percentage. A direct statement from a prospect and an inference from a job posting have different evidentiary status. Two articles repeating the same original claim do not constitute two independent confirmations.

Memory writes should be structured and attributable. Preserve raw events separately from summaries. Correct a mistaken summary through a revision and retain the reason. Derived summaries must reference their source events so important claims can be checked.

Retrieve only the information needed for the task. Role permissions determine access, particularly for commercial terms and personal contact data. Define retention and deletion policies before live use; deleting a contact must account for derived summaries and embeddings while retaining only records permitted by the adopted policy.

Future multi-company productization would require strict tenant isolation. The internal pilot should already scope all records by workspace to avoid mixing unrelated campaigns or business units.

## 8. Autonomous learning and playbook changes

The first learning mechanism updates retrieved knowledge, targeting rules, message templates, and playbooks. Model retraining is unnecessary for this phase. Fine-tuning can be considered later if enough suitable data and a concrete evaluation justify it.

Use the cycle observe, hypothesize, test, evaluate, and adopt or revert. Capture failure cases as well as successes. Discarded hypotheses remain searchable so the team does not repeatedly rediscover them without new evidence.

Allow immediate factual updates when new verified information arrives. Changing a general sales strategy requires broader evidence. One buyer's objection belongs in that buyer's account record; it should not automatically rewrite the company-wide sales approach.

Candidate playbooks move through draft, offline evaluation, eligible for experiment, limited live test, validated for scope, and active. A candidate may instead be rejected or remain inconclusive. Promotion records the dataset or cohort, evaluation result, decision, applicability, policy version, and rollback target.

Keep prompt changes, model changes, and playbook changes separately versioned. If all three change at once, the team cannot readily attribute the result. Start by adjusting one meaningful variable and retaining the baseline for comparison.

The owner can allow automatic promotion of low-risk playbook changes after defined evidence and quality gates. Changes to prices, authority, permitted claims, connectors, secrets, or spend ceilings remain outside this learning loop. A successful campaign does not authorize the system to enlarge its permissions.

Validated strategies may stop working. Schedule re-evaluation when the offer, segment, channel, or market context changes, or when mature outcomes deteriorate. Retain historical versions so a rollback restores behavior prospectively. Existing customer commitments survive the rollback.

## 9. Experiment design and interpretation

Every experiment starts with a written decision question, a primary metric, target segment, eligibility criteria, allocation unit, baseline, changed variable, observation window, budget, stopping rules, and promotion rules. Choose these before viewing results.

Randomize at account level where multiple contacts share the same buying decision. Keep an account in one variant for the experiment. Concurrent experiments need exclusion rules or a deliberate factorial design; otherwise changing messaging and targeting together creates ambiguous conclusions.

Allocate a capped portion of eligible traffic to experiments and keep the rest on the established playbook. The appropriate fraction depends on volume and risk and is intentionally unset in the configuration. Assign comparable eligible accounts using a reproducible randomization key. Preserve assignment even when delivery fails so exclusions cannot favor a variant.

Sample size depends on the baseline conversion rate, smallest useful improvement, outcome delay, and desired uncertainty. There is no universal minimum. With low volume, treat qualitative evidence as directional and mark results inconclusive when appropriate. A calendar deadline does not make an underpowered comparison conclusive.

Use mature cohorts for primary comparisons. An account still inside its response window is pending, not a failure. Record both account-level assignment and provider delivery status. Report primary results on the preregistered denominator and delivery-adjusted views separately, with their different interpretations.

Frequent unplanned peeking can create false winners. Prefer a fixed analysis point for the first pilot; adopt a documented sequential method only when properly implemented. Report effect size and uncertainty alongside raw counts. Model opinion cannot substitute for a measured business result.

Possible decisions are adopt within tested scope, continue until the predefined review, reject, or inconclusive. Stop early for operational problems such as policy failures or contact complaints under the configured stop rules. A safer operation does not imply a statistically successful strategy.

## 10. Metrics and economic evaluation

Define a qualified opportunity in the offer-specific rubric before testing. A positive reply or booked meeting is not automatically qualified. A qualified opportunity should show relevant fit, a concrete problem or interest, a viable buying path, and an agreed next step according to that rubric.

Primary pilot measurement can be qualified opportunities per eligible assigned account, measured within a fixed outcome window. Also show delivery, positive replies, meetings held, proposals, wins, time to stage, and operator intervention. Preserve cohort, channel, segment, offer, and playbook identifiers.

Qualified opportunity rate equals accounts reaching qualified status divided by eligible assigned accounts. Win rate must state its denominator, such as qualified opportunities whose closing window has matured. Do not compare a mature baseline with an immature new variant.

Cost per qualified opportunity equals attributed campaign acquisition cost divided by qualified opportunities. Cost per new customer equals acquisition cost divided by won customers. When the denominator is zero, show undefined with the actual spend and count. Never display zero cost per customer in that case.

Include model usage, research and enrichment, infrastructure allocation, sending tools, and operator time in an agreed cost definition. Separate cash outlay from fully loaded cost so the owner can make either comparison consistently.

Contribution margin subtracts agreed variable fulfillment costs from revenue. Sales volume gained through excessive discounts may reduce business value. Track retained customers and realized revenue later, when enough time has passed; avoid treating pipeline value as cash collected.

A pilot scorecard should compare the agent-assisted process with a documented current process. Keep changes in offer and segment visible. If no usable baseline exists, the first cohort establishes one rather than claiming improvement.

## 11. Negotiation and commercial authority

Negotiation autonomy comes from a versioned commercial policy: approved packages, price floors, discount rules, concession combinations, payment terms, contract templates, and escalation conditions. The policy should make allowed exchanges explicit, such as a permitted discount in return for an approved annual commitment.

Begin with information gathering and proposal drafting. Add authority to send approved offers after the pilot demonstrates accurate product statements and reliable policy enforcement. Permit bounded negotiation only when the offer catalog and pricing calculations are complete.

The gateway checks the full effective deal, including setup fees, recurring fees, free periods, waived charges, payment timing, and combined concessions. Two individually allowed concessions may produce a prohibited total discount. A model should not calculate the authoritative payable amount in prose.

Promises about implementation, service levels, integrations, custom features, exclusivity, or liability need an approved source and scope. Unknown capabilities trigger a targeted question to the owner. Repeated prospect requests create product feedback; they do not automatically become new product commitments.

Maintain a commitments ledger with the exact approved terms, who offered them, when, the recipient, expiration, and proposal version. A revised playbook cannot invalidate a prospect's existing offer. Explicitly define whether agents may only propose terms or may also accept and bind the business; acceptance remains disabled until deliberately authorized.

During the pilot, have a human handle final acceptance, contract execution, and exceptions. Later expansion should follow observed reliability and business preference. The agent must represent its sender identity and capabilities truthfully and must never invent credentials, customer results, or scarcity to close a deal.

## 12. Policy and external action controls

Separate hard policy from editable playbooks. Hard policy covers business identity, channel eligibility, suppression, spending, approved claims, commercial authority, data access, and allowed tools. An owner-controlled policy version is evaluated on every consequential action.

The external action gateway receives a typed request with actor, account, task, requested action, evidence, current state version, and idempotency key. It checks permissions and current conditions before execution. A stale state version forces re-evaluation rather than sending from outdated context.

For outreach, check contact eligibility and suppression immediately before sending. Provider acknowledgments, bounces, replies, and opt-outs become authoritative events. Stop queued outreach when a contact opts out, when the account is paused, or when a human takes ownership.

Set explicit channel frequency and sending limits based on the selected provider and operating policy. Applicability of outreach requirements depends on channel and geography and must be resolved for the actual pilot. This blueprint does not prescribe a universal legal rule or imply that a contact's public email grants permission for every use.

Secrets remain in application-managed storage and are not placed in shared prompts or agent memory. Tools expose narrow business actions rather than unrestricted provider credentials. Research pages and inbound messages are untrusted content: their text cannot change policy, authorize a tool, or redirect confidential information.

Default starter configuration disables outbound actions because the actual offer, channel, and limits are unspecified. This is a template state, not a request to approve these documents. Once the owner configures and authorizes the workflow, routine permitted actions should execute without repeated approval prompts.

## 13. Reliability and observability

Each run, task, account, discussion, experiment, action, and outcome gets a durable identifier. Carry those identifiers through logs and connector calls. Store enough context to reproduce the decision inputs without logging secrets or unnecessary personal data.

Record the model and prompt version, playbook and policy version, retrieved evidence identifiers, tool requests, tool outcomes, token or usage cost, and decision summary. Collect concise explanations of decisions rather than attempting to expose private chain-of-thought.

Use an outbox or equivalent durable action queue. Reserve budget and write the intended action atomically before execution. After provider success, store the provider identifier. On timeout, reconcile provider state before retrying; an unknown response is not proof that nothing was sent.

Concurrency requires one active account owner and a lease or version check around writes. Duplicate webhooks are deduplicated by provider and event identifier. Out-of-order webhooks should not move an account backward or revive a suppressed contact.

Set limits for task duration, tool calls, discussion rounds, retries, and campaign spend. Stop repeated unproductive work. If research yields no suitable contact after its limit, return an explicit incomplete result and the reason rather than inventing an address.

Monitor delivery failures, queue age, missing outcomes, suppressed-contact attempts, unsupported claims, budget usage, and repeated policy rejections. Distinguish operational alarms from business underperformance. Repair the integration before attributing failed delivery to bad messaging.

A pause and recovery drill should verify that scheduled actions stop, in-flight actions are reconciled, unresolved commitments remain visible, and resumption does not replay old work.

## 14. Reference data model and interfaces

Use workspace-scoped identifiers even for the internal release. Core records are accounts, contacts, evidence, tasks, discussions, decisions, actions, outcomes, experiments, assignments, playbook versions, policy versions, and commitments.

Accounts store stage, owner, version, relevant segment, and CRM references. Contacts belong to accounts and have channel-specific eligibility and suppression state. Evidence references a source and a claim. A task captures assignment, status, expected output, budget, and stopping condition.

Experiments reference immutable baseline and candidate versions. Assignments link accounts to exactly one variant within an experiment. Outcomes reference account, event time, source, and any relevant assignment. Attribute business results through these records rather than text similarity.

Store actual external actions separately from agent proposals. An action records intent, authorization result, payload reference, execution state, idempotency key, provider reference, and errors. Status should distinguish queued, rejected, executing, succeeded, failed, and unknown. Unknown requires reconciliation.

The supporting JSON Schema describes the discussion proposal, experiment specification, playbook change, and external action request. The configuration file demonstrates the required business settings and safe initialization. These contracts are implementation starters; a production database still requires migrations, indexes, referential constraints, concurrency tests, and connector-specific validation.

Tool interfaces should accept typed business inputs and return explicit outcomes. For example, research returns evidence references and unresolved questions; sending returns a durable provider reference or unknown status; proposal generation returns calculated terms and policy evaluation. Never encode success only as a conversational sentence.

Choose a relational database and durable job mechanism that fit existing infrastructure. Add vector search only when evidence retrieval needs it. Model-provider selection should be based on task evaluations, latency, and actual cost rather than a fixed preference in this document.

## 15. Evaluation before live use

Evaluate both business reasoning and system behavior. Offline agent tests can verify qualification judgments, factual grounding, objection handling, and commercial boundaries. Integration tests verify the actual gateway, database, queue, and provider adapter behavior. A prompt-only test cannot prove external enforcement works.

Build cases from realistic situations: incomplete company information, ambiguous buyer intent, conflicting product facts, an out-of-scope discount, combined concessions, opt-outs, an instruction hidden in a prospect message, and a human reply arriving before an automated follow-up.

Include failure recovery: provider timeout after an apparent send, duplicate reply webhooks, worker restart after budget reservation, expired ownership lease, stale playbook, and missing experiment assignment. Test the expected final state, not just the wording of an agent answer.

Set explicit acceptance criteria. Required controls include no duplicate send in the retry scenario, no outbound action to a suppressed contact, no unsupported commercial commitment, and no promotion of a strategy without its configured evidence. These are release expectations, not claims of achieved reliability.

Use separate development and holdout cases. When changing a prompt or model, rerun relevant regressions and preserve results. An evaluator should not be allowed to weaken its own grading criteria to pass a candidate. Human spot checks remain useful for nuance and calibration.

In shadow mode, the agents research and draft against real or permissioned historical context while external actions remain disabled. Compare their proposed decisions with operator judgments and correct missing business knowledge. Then start a small live cohort within approved policy and observe mature outcomes before expanding.

The bundled acceptance-cases file specifies concrete scenarios and pass conditions to convert into automated tests when the runtime exists.

## 16. Implementation sequence and release gates

Phase 0 defines the business. Select the offer, customer segment, channel, approved claims, qualification rubric, commercial policy, owner, budget, and current-process baseline. Exit when those inputs are explicit and internally consistent.

Phase 1 builds the execution foundation: account store, evidence records, task queue, ownership, policy gateway, action log, suppression, and one connector in a sandbox or disabled-send mode. Exit after recovery, duplicate prevention, and policy enforcement tests pass.

Phase 2 adds orchestrator, research, and sales roles with task contracts and shared memory. Run shadow tasks and inspect account briefs and drafts. Exit when the agreed evaluation set passes and the operator can trace statements back to evidence.

Phase 3 launches a bounded live pilot. Activate only the authorized action types, observe delivery and replies, and verify that the operator can intervene. Exit when outcome tracking is reliable and the pilot produces enough mature evidence for the planned review. No duration guarantees a useful sample.

Phase 4 adds structured strategy discussions, experiment assignment, evaluator decisions, and playbook versioning. Run one interpretable experiment. Exit when the system can show its baseline, assignments, outcomes, uncertainty, and adoption or rejection decision.

Phase 5 expands negotiation and scope. Add an explicit deal role if necessary, broaden permitted commercial exchanges, or add another segment or channel. Expand one dimension at a time so new failures can be diagnosed. Multi-company productization follows only after the internal economics and operational reliability justify it.

Implementation effort depends on existing CRM quality, connectors, and offer readiness. The roadmap deliberately uses completion gates instead of invented deadlines. Each phase should deliver a useful operator-visible capability.

## 17. Worked operating example

This is an illustrative scenario, not a real campaign or measured result. Assume an internal team sells a standardized service to a defined B2B segment. The actual service, price, and segment remain to be selected.

The research agent finds accounts with a recent operational change and records source evidence. The orchestrator checks inclusion rules, removes duplicates, and assigns eligible accounts. The sales agent prepares an approved message and the gateway verifies policy before any send.

A recurring objection appears: prospects are uncertain about implementation effort. The sales agent proposes emphasizing onboarding. Research proposes changing the target segment. The evaluator notes that changing both would obscure which change helped.

The strategy room selects a messaging experiment while holding the offer, segment, channel, and qualification rubric constant. Accounts are assigned once to baseline or candidate. The candidate explains the approved onboarding process; it does not invent a faster deployment promise.

Early replies look encouraging, but several accounts have not reached the observation deadline. The evaluator labels the result pending and avoids promotion. At the planned review, it compares mature outcomes and uncertainty. If evidence is weak, the correct decision is inconclusive; if improvement meets the predefined criteria without operational degradation, the playbook can be promoted within the tested segment.

A prospect then requests a discount plus waived setup. The deal function evaluates the combined effective price. If the package is outside permitted terms, it routes a concrete exception with the buyer's request, economics, and proposed response to the owner. Other permitted account work continues.

The owner sees the account history, experiment, decision, and commercial exception in one place. The benefit is traceable progress and learning, not merely more generated messages.

## 18. Open decisions and next implementation inputs

The following inputs are intentionally unresolved: the business and product to sell; ideal customer profile and exclusions; target geographies and language; initial channel; existing CRM and sender identity; approved product claims; qualification rubric; pricing and concession authority; budget; operator availability; data retention; and the definition of an economically worthwhile result.

Before implementation, fill in business-config.example.json and replace unset values with explicit choices. Empty fields must remain visible blockers for dependent live actions rather than silently inheriting permissive defaults. Configure only the autonomy the owner actually wants.

The first implementation decision is whether current infrastructure can support durable account state and a narrow action gateway. The second is which task produces the fastest useful feedback for this offer. Those answers should drive framework and model choices.

Preserve a distinction between confirmed requirements, proposed defaults, and measured findings. This blueprint confirms the desired internal team and learning behavior, proposes the architecture and operating rules, and contains no measured campaign results.

The initial deliverable should be a functioning path from one eligible account to one inspected next action, with evidence, policy, ownership, and outcomes recorded. Add the strategy room once this execution path produces trustworthy feedback. Add broader autonomy only as that evidence supports it.
