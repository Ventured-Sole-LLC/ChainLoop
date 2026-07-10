# ADR 001: Synthetic Medical Logistics Demo, Inspired by a Real Operational Incident

## Context

Ventured Sole LLC's courier division serves a regional, multi-site clinical and anatomic pathology laboratory network, the kind of operation that runs well over a hundred patient service centers across a state, often expanding into new locations every year. Around the time of the incident that inspired this project, the client was actively opening two new lab locations. More locations means more daily handoff points, and more handoff points means more places a specimen can quietly fall through the cracks.

That's exactly what happened. A courier arrived to collect the day's specimens and found the prior day's specimens still sitting there, uncollected, temperature-sensitive blood products that had already blown past their safe window. Nobody had flagged it. Nobody knew until the courier physically saw it. Every party involved, lab staff, the courier, the receiving lab, had assumed someone else already handled it.

That's not a routing problem or a GPS problem. It's a visibility problem, the same root cause behind every Operational Trust Platform I've built: work moves between people and organizations with no shared, trusted record of what actually happened and when.

## Decision

ChainLoop models a specimen chain-of-custody workflow using synthetic data only. It never stores PHI, real patient identifiers, real specimen IDs, or real client data. V1 is deliberately scoped to four actors, Lab Tech, Courier, Receiving Lab, and Ops Supervisor, one specimen type, one SLA window, and one escalation path, built on an event-sourced custody log: `SpecimenCollected -> CourierAccepted -> InTransit -> Delivered -> LabVerified`. If a specimen is not delivered within its SLA window, the system triggers an escalation notification.

## Reasoning

Synthetic data keeps this project safe to discuss and demo publicly with zero risk of exposing real patient or client information, and it protects Ventured Sole from any compliance exposure a real-data demo could create. Scoping v1 to a tight actor list and one specimen type, instead of a fully generalized configurable system, lets the core reliability pattern, custody tracking, SLA timing, escalation, get built and proven correctly before adding the complexity of multiple specimen types with different safe-handling windows.

The underlying pattern here isn't unique to medical logistics. Anything that requires a defensible chain of custody with a real time-sensitivity component generalizes the same way: legal evidence transport between firms, courts, and storage facilities; forensic evidence handling; pharmaceutical and blood bank logistics. ChainLoop is scoped to medical specimens for v1 because that's the real incident that surfaced this problem, but the architecture itself isn't healthcare-specific, and that's worth remembering as this grows.

SoleLoop proved workflow and approval architecture. ChainLoop is a genuinely different problem: operational reliability under time-sensitive, safety-critical conditions, extending the same Operational Trust Platform thinking into a new domain.

## Alternatives Considered

Considered building a fully generalized, multi-actor, multi-specimen-type system from the start, including Hospital Unit/Clinic Staff, Dispatch Coordinator, Compliance/QA Officer, Client Administrator, and Patient-facing views. Rejected for v1: each of these either duplicates an existing v1 actor's function (Hospital Unit into Lab Tech), turns the project into dispatch/routing software rather than custody visibility (Dispatch Coordinator), belongs to a later read-only or multi-tenant phase (Compliance/QA Officer, Client Administrator), or introduces privacy/HIPAA complexity with no architectural benefit at this stage (Patient).

Considered using anonymized real incident data. Rejected: even anonymized, real specimen or client data carries residual risk and isn't necessary to demonstrate the architecture.

## Revisit If

A second specimen type with genuinely different handling requirements is needed, at that point the SLA window and safe-handling rules should become configurable per specimen type rather than hardcoded for v1. Secondary actors get added one at a time, only when a real use case demands them, not speculatively. If this ever generalizes beyond medical logistics into legal chain-of-custody or another regulated-transport domain, that's a new ADR, not a silent scope expansion of this one.

## Update (July 9, 2026)

All four v1 Lambdas are built, deployed, and verified end to end: `SpecimenCollected`, `CourierAccepted`, `CourierStatusUpdate` (handling both `IN_TRANSIT` and `DELIVERED`), and `LabVerified`. A single specimen was pushed through the complete lifecycle (`COLLECTED -> ACCEPTED -> IN_TRANSIT -> DELIVERED -> VERIFIED`) via real HTTP requests authenticated as each of the four actor roles, confirming correct state-guard enforcement, idempotent writes, and EventBridge publication at every step.

Not yet built: the SLA-checker Lambda that scans the `status-sla-index` GSI for overdue specimens and triggers escalation, the actual reliability piece this project exists to demonstrate.

## Update (July 10, 2026)

The SLA-checker Lambda is live, running on a 5-minute EventBridge Scheduler cycle. Verified with a real test: manually set a specimen's sla_due_at into the past, confirmed the scheduled Lambda detected it on its next run, updated escalation_status to ESCALATED, and published both an SNS alert and an EventBridge event, without any human triggering the check. This closes the loop on the actual incident that inspired this project: a specimen missing its safe window is now something the system catches automatically, not something a courier discovers by chance.

All five states of the v1 custody lifecycle, plus automated SLA enforcement, are now built, deployed, and verified end to end.
