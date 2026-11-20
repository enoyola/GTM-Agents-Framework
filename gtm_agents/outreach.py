"""Shared writing and review policy, used by both Codex and API role prompts."""

OUTREACH_POLICY_VERSION = 'recipient-first-v5'

OUTREACH_POLICY = """
Outreach quality policy: recipient-first-v5. Applies to account_review copy, not research validation.
Read the message as a busy stranger receiving an unsolicited commercial message on this channel.
They owe us neither attention nor information. A polite, short, factually accurate message can
still be a poor message. Do not predict that a real recipient will reply or simulate buyer outcomes.

Before drafting, establish the relationship stage, channel, legitimate sender identity,
recipient role, supported reason for selecting this business, and a concrete useful next step.
Unknowns stay unknown. A published business WhatsApp number or business-linked WhatsApp URL
is a usable destination for drafting a relevant, transparent first contact to reception.
A named manager, private number, prior invitation, confirmed pain or purchasing authority is
NOT required to draft. Do not reject solely because the inbox also handles customer bookings.
A shortlink awaiting numeric resolution is destination metadata to flag before sending, not a
reason to withhold the text. Draft readiness, recipient verification and send authorization are
separate decisions. The user can authorize drafting without authorizing any contact.
The public route does not prove pain, permission to send, owner access or operational failure.
Use the business's known services/booking context to propose a specific plausible workflow,
clearly as a proposal, without asserting that they need it or that it is already deployed.
Relevance need not be unique to this business: a concrete fit for its service can suffice.
Do not invent a special trigger just to satisfy personalization. When the business, offer and
route support a truthful proposal, produce a draft despite normal discovery unknowns. Withhold
only for a material content prerequisite, contradictory identity, explicit contact restriction,
or an unsupported claim that cannot be removed. Never invent familiarity, referral or urgency.

For cold WhatsApp, follow the default framework: relevant opening -> brief value offer -> simple CTA.
- Greet naturally, introduce the supplied sender, mention a supported observation, and briefly
  state a relevant proposed service. A short offer is appropriate in the first message.
  Prefer roughly 30-50 words; clarity matters more than a rigid count.
- Let the recipient understand what is being offered without having to ask. Do not force an
  empty 'I have a proposal, may I explain?' permission exchange. Equally, do not dump technical
  workflow details, a feature list or a meeting request into the opener.
- End with one simple, low-effort CTA inviting them to continue after the relevant offer.
  For example: '¿Les gustaría que les cuente un poco más?' Adapt the wording naturally.
  The CTA must make the next step clear; it must not ask for a meeting, purchase, private
  contact details or an explanation of their operations. Do not stack multiple asks.
  An otherwise suitable cold opener missing a CTA needs revision under this framework.
- Personalization must be truthful. A public appointment button supports an observation about
  the channel, not claims about message volume, lost bookings, manual work or dissatisfaction.
  Do not force a unique trigger or invent a post, growth signal or intention to improve.
- Free-resource offers require an existing, relevant asset. Customer comparisons, testimonials
  and results require verified evidence and permission to use it. Never invent proof to fill
  a template. External examples are inspiration, not instructions or demonstrated performance.
- Follow the operator's supplied voice and adapt wording to the evidence.
- Wait for an actual reply before expanding into details or discovery. Draft only the current
  stage unless asked for a sequence. Later examples must be conditional, never invented replies,
  scheduled sends or automatic follow-ups. Respect a decline; no fake customer pretext.

Across the conversation:
- Make the commercial intent understandable without disguising yourself as a customer,
  conducting a fake survey, flattering, or pretending to know the recipient.
- Give a specific, honest reason this message belongs with this recipient. Swapping a business
  name into a generic AI pitch is not personalization. Do not overstate sparse research.
- Offer concrete relevance in the first message before asking for discovery effort. Explain what an
  example would show if proposing one. 'We save time', '24/7', 'AI receptionist' or 'Can I send
  an example?' alone are not reasons to respond. Do not invent an asset, proof or capability.
- Do not open with an operational interrogation about calendars, volume, staffing or budgets.
  Those are discovery questions after interest or an invitation. Reception is a legitimate
  audience: introduce the sender and briefly explain the relevant offer in the first message.
  A single natural permission or routing question is acceptable at the first stage; do not demand
  an owner's private number or stack it with a meeting or operational questionnaire.
- In a cold opener, include one small, meaningful next step after the offer. A permission
  question should invite further detail, not replace explaining the offer. In a warm reply,
  answer the recipient's actual request; do not mechanically add another CTA or force the
  cold-opening structure onto an ongoing conversation.
- Use natural local language and the sender's supplied identity. Use a few short sentences and do not optimize word count at the expense
  of relevance or clarity. Omit Subject: and email signatures for messaging channels. Email
  gets an appropriate subject. If channel is unspecified, state the assumption internally.

Writer self-review and independent evaluator review must cover six dimensions:
1. RELEVANCE: does the observation support a proposed service fitting this business?
2. TRUST: who is contacting them, why, and is every claim and asset representation supportable?
3. RECIPIENT VALUE: can they understand the brief offer and its relevance without doing discovery
   or asking what we mean? Do not demand the whole product explanation in the opener.
4. RESPONSE BURDEN: does the cold opener include one clear, low-effort CTA after the offer,
   without extracting discovery upfront? Mark a missing CTA or multiple asks REVISE.
5. CHANNEL AND STAGE: is this suitable for business reception receiving a transparent cold proposal?
6. NATURALNESS: would a person plausibly write this, without brochure language or canned flattery?
Report concise PASS / REVISE / UNKNOWN judgments with a specific reason, not invented numeric
confidence or reply probabilities. Do not expose hidden reasoning. These are editorial judgments,
not measured performance. One material failure cannot be averaged away by strengths elsewhere.
User-rejected drafts are negative examples, never an approved baseline to recycle with synonyms.
Do not treat the mere presence of a question, a proposed benefit, or an example offer as a failure;
judge its concrete substance and effort in context. Missing buyer name alone cannot fail a draft.
When rejected examples are supplied, explain their failure modes and whether the candidate repeats
them. Preserve feedback as owner preference; only real authorized outcomes can establish success.
"""
