# ADR 006: DynamoDB Table Design, Event Log Plus SLA-Aware Projection

## Context

SoleLoop proved the CQRS split, an append-only event log for full history, and a projection table for current state, works well for workflow visibility: what's the status of this request, who submitted it, what happened to it. ChainLoop needs that same visibility, but also something SoleLoop never required: a way to efficiently answer "which specimens are currently overdue on their SLA and haven't moved to the next state?" That's a time-based reliability query, not a workflow-status query, and it needs its own access pattern designed in from the start rather than bolted on later.

## Decision

ChainLoop uses two DynamoDB tables, following the same split proven in SoleLoop:

**`ChainLoopEventLog`** (immutable custody history)
- Partition key: `specimen_id`
- Sort key: `timestamp_event_type_event_id`
- Purpose: retrieve the full, ordered custody history for one specimen.

**`ChainLoopProjection`** (current state, one item per specimen)
- Partition key: `specimen_id`
- Sort key: `record_type`
- Fields: `current_status`, `last_event_at`, `sla_due_at`, `current_owner`, `specimen_type`, `escalation_status`

**GSI on the projection table: `status-sla-index`**
- Partition key: `current_status`
- Sort key: `sla_due_at`
- Purpose: let the SLA-checker Lambda run a single `Query`, not a `Scan`, for something like `current_status = IN_TRANSIT AND sla_due_at <= now`, finding every specimen that's overdue without reading the entire table.

## Reasoning

The event log answers "what happened to this specimen and when," which is naturally keyed by `specimen_id`, exactly the same shape SoleLoop already proved for request history. The projection table answers "what's true right now," and matters here for a reason SoleLoop didn't have: an SLA checker needs to ask that question across every active specimen at once, on a schedule, not just when someone looks up one specific record.

Scanning the event log directly for overdue specimens would mean reading every event for every specimen, then computing current state and SLA status in application code, on every scheduled check. That gets slower and more expensive as the event log grows, and it recomputes the same answer repeatedly instead of maintaining it. The projection table already carries the current state after every event; adding the `status-sla-index` GSI means the SLA checker's job becomes a single, cheap, targeted query instead of a full-table computation.

This is the concrete difference between what SoleLoop needed and what ChainLoop needs: SoleLoop's projection table supported point lookups and ownership-scoped listing. ChainLoop's projection table also needs to support "give me every active item whose deadline has passed," which is exactly what a GSI keyed on status and a time field is built for.

## Alternatives Considered

**Scan the event log for overdue specimens.** Rejected: requires reading and recomputing state from full history on every SLA check, which gets more expensive as history grows and duplicates work the projection table already does.

**Scan the projection table without a GSI, filtering in application code.** Rejected: a `Scan` reads every item in the table regardless of filter, then discards non-matching ones. As specimen volume grows, this scales poorly compared to a targeted `Query` against an index built for exactly this access pattern.

**Store SLA deadlines in a separate table entirely, decoupled from the projection.** Rejected: this splits related state (current status and its deadline) across two places that both need to stay in sync, adding a consistency risk for no real benefit over keeping both fields on the same projection item.

## Revisit If

Specimen volume grows large enough that even the GSI query pattern needs further optimization (for example, sharding the SLA check by specimen type or region), or a second SLA rule per specimen type is introduced, at which point `sla_due_at` alone may not be sufficient and the projection schema should be revisited explicitly.