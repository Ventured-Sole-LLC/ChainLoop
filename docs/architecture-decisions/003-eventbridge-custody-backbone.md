# ADR 003: EventBridge as the Custody Event Backbone

## Context

SoleLoop's Lambdas were largely self-contained: a request came in, one Lambda validated it, wrote to DynamoDB, and returned a response. ChainLoop's custody events don't fit that shape. A courier accepting custody changes more than one subsystem simultaneously: the custody log needs a new entry, the specimen's SLA timer needs to reset, the projection needs to reflect the new state, and Ops may need a notification if something about the handoff looks wrong. That's one event with several independent reactions, not one request with one job.

## Decision

Each custody event (`SpecimenCollected`, `CourierAccepted`, `InTransit`, `Delivered`, `LabVerified`) is first validated and durably recorded as part of the custody history, then published to Amazon EventBridge for asynchronous downstream processing. EventBridge rules route each event to whichever consumers care about that specific type, the SLA timer logic, the projection updater, and the notification service.

## Reasoning

Direct Lambda-to-Lambda invocation would work for today's four consumers, but it hardcodes fan-out into the code itself and increases blast radius, a failure in downstream processing becomes directly coupled to the producer's execution path. Adding a fifth consumer later means editing every producer to know about it. EventBridge inverts that: **producers publish an event and don't need to know who's listening.** New consumers subscribe by adding a rule, not by modifying the event source. Future consumers could include compliance analytics, SLA reporting, or predictive delay detection, all addable without touching existing producers.

EventBridge also decouples processing time. Producers complete their responsibility once the event has been accepted by the event bus, so downstream consumers can evolve independently without adding latency to the actor performing the custody scan.

SNS was a real option too, and it's already proven working well in SoleLoop's alerting. The difference is filtering: EventBridge lets each rule match on the event's actual content (event type, specimen ID, actor), so a single bus can carry every custody event type and each consumer only receives what it needs. SNS still has a role downstream, specifically for the notification/escalation step, just not as the backbone itself.

This also sets up a reusable pattern every custody event should follow, worth naming explicitly:

### ChainLoop Event Processing Pattern

Every custody event follows the same pipeline:

Validate → Persist → Publish → Notify → Audit

Building that pipeline once, as a module the way `lambda-endpoint` was built for SoleLoop, rather than repeating it for each of the five event types, is the platform-engineering lesson SoleLoop already proved. This project applies it from day one instead of extracting it after the fact.

## Consequences

**Positive**
- Producers remain unaware of downstream consumers
- New consumers can be added without modifying existing services
- Each consumer can scale independently
- The custody log stays the single source of truth regardless of what happens downstream in EventBridge

**Negative**
- Event ordering must be considered explicitly, EventBridge doesn't guarantee strict ordering the way a single sequential log would
- Event schemas become long-lived contracts once consumers depend on them
- Debugging becomes distributed across multiple consumers instead of one call stack

## Alternatives Considered

**Direct Lambda-to-Lambda invocation.** Rejected: couples every producer to every consumer it needs to call, increases blast radius since downstream failures propagate directly into the producer's execution path, and makes it harder to add new consumers without touching existing code.

**SNS only.** Rejected as the sole backbone: SNS handles the alerting use case well (proven in SoleLoop) but lacks EventBridge's content-based filtering across many event types on one bus. SNS remains useful downstream of EventBridge for the notification/escalation step specifically.

**Kinesis.** Rejected for v1: Kinesis is built for high-volume continuous streams. Custody events are discrete and occasional, not a continuous stream, so Kinesis would add operational complexity without a corresponding need. Worth revisiting only if courier GPS position streaming becomes a genuinely continuous data source later.

## Revisit If

A consumer needs sub-second latency EventBridge can't guarantee, or event volume grows into genuinely continuous streaming territory (frequent GPS position updates rather than discrete custody scans). Either would be a real reason to reconsider Kinesis specifically for that data path, not for custody events themselves.