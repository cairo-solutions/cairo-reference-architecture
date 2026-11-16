# ADR-004: Agents propose, humans approve consequential actions

**Status:** Accepted. Amended November 16, 2026 to add [standing approvals](#standing-approvals).

## Context

The operating model uses several specialized AI agents: intake, proposal generation, GRC assessment, delivery tracking, content, and workflow audit. They hand work to each other. Without explicit limits, a chain of agents could draft a proposal, price it, and send it to a prospect with no person ever looking at it.

## Decision

Every agent action is classed as one of three types:

| Class | Examples | Rule |
|---|---|---|
| **Internal and reversible** | Summarize a lead, score it, draft a document, update a status field | Agent acts on its own; the action is logged |
| **Agent-to-agent handoff** | Intake → proposal, content → review | Posted as an approval card in a team channel; the director approves or returns it |
| **External or binding** | Sending a quote, publishing content, contacting a cold lead, committing spend | Requires explicit human approval at a review gate. No exceptions. |

Additional rules:

- **Reviewing agents may send work back** to the originating agent before it reaches the director. Loops are capped (for example, two revisions) before escalating to a person, so agents cannot iterate indefinitely.
- **When the director rejects work**, the director states the reason and chooses which agent it returns to. Rejection routing is a human decision, not an automated rule.
- **Inbound data from trusted channels** (for example, a client submitting an intake form) may be written to the CRM automatically. **Outbound lists** (prospects the business will contact) require review before entering the CRM.

## Standing approvals

*Added November 16, 2026.*

A standing approval is the director approving, in advance, one narrowly defined external or binding action, so that an agent may take it without a per-instance review. It is an exception to the "no exceptions" rule above, so each one is recorded here with its scope, its limits, and how it ends. Anything outside the stated scope falls back to the review gate.

### SA-1: Website strategy-session hold and invoice

| Field | Contents |
|---|---|
| Decided | November 16, 2026, by the director. Resolves the open question raised in [ADR-008](008-website-chat-with-in-conversation-tools.md). |
| Agent | The website reception agent only |
| Action | Place a 24-hour hold on the director's calendar and email the invoice for the fixed-price strategy session |
| Conditions | The visitor has confirmed the time and their email address in the conversation. The session is the fixed-price strategy session at its published price. |
| Limits | The hold is not a confirmed booking until the invoice is paid, and it lapses after 24 hours if unpaid. The server-side limit on holds stays in place: a second hold for the same visitor is refused and goes to human review. |
| Not covered | Any other service, custom or discounted pricing, rescheduling, cancellations, refunds, and any booking for an existing client. These go through the review gate as before. |
| Records | Each hold and invoice should leave a record the director can review after the fact. Whether every use is logged has not been verified. |
| Ending it | The director can withdraw SA-1 at any time by amending this record. |

A standing approval is a decision, not evidence that the controls behind it work. Its assurance status is tracked separately in [build status](../architecture/build-status.md).

## Consequences

- Throughput is limited by human review at the gates. That is intentional: the gates sit on the actions where errors are expensive or public.
- Every gate produces an approval record, which provides an audit trail for clients who ask how AI decisions are supervised.
- Maps directly to NIST AI RMF *Govern* and *Manage* functions (see [governance mapping](../governance/nist-ai-rmf-mapping.md)).
