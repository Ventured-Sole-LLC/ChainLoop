# ADR 004: FHIR Task and Specimen Resource Shapes as the Event Schema

## Context

ChainLoop needs a schema for its custody events. The fastest path is a custom JSON schema built exactly to this project's needs, one only ChainLoop itself understands. The alternative is modeling events using an established healthcare interoperability standard, so the events carry meaning a real lab or hospital system could someday recognize without translation, directly extending the interoperability differentiation named in earlier discussions of this project's scope.

## Decision

Custody events are shaped using two FHIR resources, not one custom schema. The `Specimen` resource represents the physical thing being tracked: its identifier, type, collection details, and condition. The `Task` resource represents the custody workflow itself: `Task.owner` reflects the party currently responsible for the custody task (Lab Tech, then Courier, then Receiving Lab, as responsibility transfers), `Task.businessStatus` captures the domain-specific phase (the FHIR specification's own example for this field is literally `"Specimen collected"`), and `Task.status` tracks the resource through FHIR's standard lifecycle (`requested`, `accepted`, `in-progress`, `completed`, among others).

## Reasoning

`Task` exists in FHIR specifically to represent a unit of work moving between owners with a trackable status, which is exactly ChainLoop's custody problem, not a shape being forced onto it. `Specimen` exists specifically to describe the sample itself. Splitting the two matches how FHIR intends them to be used together rather than overloading one resource to do both jobs.

A custom internal schema would be faster to build today, but it wouldn't mean anything outside ChainLoop. Shaping events as `Task` and `Specimen` from the start means the custody events could, in principle, be understood by any system that already speaks FHIR, without ChainLoop needing to build a translation layer later. That's the actual interoperability story: not a promise to integrate with a real hospital system in v1, but a decision that doesn't have to be undone if that opportunity comes later.

## Alternatives Considered

**Custom internal JSON schema.** Rejected: fastest to build, but has no meaning to any system outside ChainLoop, and would need to be redesigned from scratch if real interoperability ever mattered.

**`Specimen` alone, with custody state encoded as extensions.** Rejected: this reinvents what `Task` already exists to do. Extensions are the right tool for genuinely novel data FHIR has no field for, not a substitute for an existing, well-fitted resource.

**Standing up a fully FHIR-compliant server (validation, full resource lifecycle, real API conformance).** Rejected for v1: that's a meaningfully larger project than proving the custody/SLA/escalation pattern. V1 borrows the resource *shapes* as event payloads; it does not claim to be a certified FHIR server.

## Consequences

**Positive**
- Custody events carry a schema a real healthcare system could plausibly recognize
- `Task`'s built-in status lifecycle removes the need to invent a custom state enum
- Sets up a genuine, defensible answer to "why FHIR" beyond citing the standard's name

**Negative**
- FHIR resources carry more fields than ChainLoop's v1 actually needs, real discipline is required to use only what applies rather than over-populating unused fields for their own sake
- Risks scope creep toward building full FHIR compliance before the core custody/SLA pattern is proven, worth resisting deliberately

## Revisit If

Real interoperability with an actual lab or hospital system becomes a genuine goal, at that point this ADR's scope boundary (resource shapes only, not a certified FHIR server) should be revisited as its own decision, not quietly expanded.