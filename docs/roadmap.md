# Implementation roadmap

These phases describe the target system. The [README](../README.md) summarizes the executable release.

## Phase 0 - Define the pilot

Owner: business owner, supported by implementer.

- P0.1: Select one offer, segment, channel, language, and geography. Output: populated business scope.
- P0.2: Approve product claims, qualification rubric, pricing policy, and sender identity. Output: authoritative versioned sources.
- P0.3: Define budgets, contact eligibility, suppression, retention, and operator escalation. Output: initial policy.
- P0.4: Define business metrics and capture the current-process baseline. Output: denominator and cost definitions.

Gate: live prerequisites are explicit; null configuration values block dependent operations. Phase 1 depends on a usable policy draft; live activation depends on completed Phase 0.

## Phase 1 - Build a reliable execution path

Owner: implementer.

- P1.1: Persist accounts, contacts, evidence, events, tasks, actions, and policy versions.
- P1.2: Add one-account ownership, state versions, task leases, and restart recovery.
- P1.3: Implement the typed tool gateway with authorization and budget reservation.
- P1.4: Integrate one provider with outbox, idempotency where supported, webhooks, and unknown-result reconciliation.
- P1.5: Add pause, suppression, audit views, and operator takeover.

Gate: duplicate, stale-state, opt-out, timeout, restart, and budget scenarios pass against the actual service and connector adapter. No model is required to prove these controls.

## Phase 2 - Add useful agent work

Owner: implementer and operator.

- P2.1: Add orchestrator, research, and sales task contracts and role instructions.
- P2.2: Ground account briefs and drafts in source evidence and approved claims.
- P2.3: Implement structured memory with facts separated from hypotheses.
- P2.4: Build development and holdout evaluation cases.
- P2.5: Run shadow accounts and inspect source accuracy, qualification, and recommended actions.

Gate: required agent evaluations pass; operator can explain a draft from its evidence and policy. Outbound remains disabled during shadow mode.

## Phase 3 - Run a bounded live cohort

Owner: business owner authorizes scope; operator monitors; service executes.

- P3.1: Activate only approved action types and configure channel limits.
- P3.2: Observe delivery, replies, qualification, and operator interventions.
- P3.3: Reconcile provider outcomes and CRM state.
- P3.4: Review mature cohort performance and costs against the baseline.

Gate: trustworthy outcomes, reliable intervention, and acceptable operation within the owner's configured thresholds. Live activation is a separate future implementation action, not an effect of these documents.

## Phase 4 - Add measurable learning

Owner: implementer and evaluator; business owner sets promotion authority.

- P4.1: Implement evidence packets, independent proposals, challenge round, and decision records.
- P4.2: Add immutable experiment specifications and account-level allocation.
- P4.3: Implement cohort maturity, primary metrics, uncertainty analysis, and incomplete-data handling.
- P4.4: Add candidate playbook versions, evaluation, promotion, and rollback.
- P4.5: Run one interpretable experiment and publish an evidence-backed decision.

Gate: reproduce the decision from assignments and outcomes; reject or leave inconclusive when evidence is insufficient. Agent consensus alone cannot pass this gate.

## Phase 5 - Expand useful autonomy

Owner: business owner and implementer.

- P5.1: Add proposal calculations, commitments ledger, and bounded negotiation.
- P5.2: Extract a deal specialist only if workload justifies it.
- P5.3: Add one new segment, channel, or offer at a time and rerun relevant evaluations.
- P5.4: Consider productization only after internal reliability and economics are demonstrated.

Gate: expanded permissions are explicit; existing customer commitments remain intact; outcome measurement survives the added complexity.

## Technology decisions to make during implementation

The local implementation uses SQLite and leased tasks. Codex is the default execution host, with an optional OpenAI API worker. Reconcile existing outreach trackers before introducing a delivery connector. Evaluate models separately for research, sales, and assessment using realistic tasks. Start with structured retrieval; add semantic search if ordinary retrieval is insufficient. Use narrowly scoped connector adapters and keep business policy independent of the model provider.

## Definition of the first useful vertical slice

One eligible account can be researched, assigned, given a grounded draft, checked against policy, and shown to the operator with its next action and evidence. The same record can later receive a confirmed external outcome without losing ownership or duplicating work.
