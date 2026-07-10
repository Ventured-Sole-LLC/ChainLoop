# ADR 009: Two-Hour SLA Window for the Synthetic Specimen Type

## Context

The SLA-checker Lambda (still to be built) needs a real deadline to compare against, not just a timestamp copied from the collection event. Something has to define how long a specimen can sit before it's considered at risk.

## Decision

For v1, every specimen gets a fixed 2-hour SLA window, calculated at collection time as `collected_at + 2 hours`, stored as `sla_due_at` on the projection record. This value is hardcoded (`SLA_WINDOW_HOURS = 2` in the SpecimenCollected Lambda), not configurable per specimen type, matching the single-specimen-type scope already set in ADR 001.

## Reasoning

Two hours is a reasonable, defensible window for a temperature-sensitive blood product moving through a pickup-to-lab handoff, long enough to allow for realistic pickup and transit time, short enough that a real delay is still actionable when the SLA-checker catches it. The specific number matters less than having a real, computed deadline instead of a placeholder, this is the value that makes the SLA-checker's query meaningful rather than trivially true or false for every specimen.

Hardcoding this in the collection Lambda, rather than building a configurable rules engine, follows the same discipline as ADR 001's scope decision: prove the reliability pattern (a real deadline, a real overdue check, a real escalation) before adding the complexity of per-specimen-type configuration.

## Alternatives Considered

Considered making the SLA window configurable per specimen type from the start. Rejected for v1, per ADR 001: there is only one specimen type in scope, so a configuration system would have nothing real to configure yet.

Considered leaving `sla_due_at` equal to the collection timestamp (the prior, incorrect behavior). Rejected: this made every specimen appear immediately overdue, which is not a real SLA, it is a placeholder that happened to occupy the right field name.

## Revisit If

A second specimen type is introduced with a genuinely different safe-handling window, at which point `SLA_WINDOW_HOURS` should become a lookup keyed by specimen type rather than a single constant.
