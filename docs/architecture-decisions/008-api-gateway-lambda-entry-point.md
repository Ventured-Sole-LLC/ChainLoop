# ADR 008: API Gateway and Lambda as the Scan Submission Entry Point

## Context

Every custody event starts somewhere real: a Lab Tech logging a collection, a Courier scanning a pickup or delivery, a Receiving Lab confirming receipt. All four v1 actors need a way to submit these actions into ChainLoop, authenticated, validated, and reliably, before anything reaches the event log, EventBridge, or downstream consumers.

## Decision

ChainLoop reuses the same synchronous API Gateway plus Lambda pattern proven in SoleLoop, with Cognito JWT authorization, as its scan submission entry point. Each entry Lambda performs the full validate, persist, publish pipeline from ADR 003 in one synchronous request: check the idempotency key (ADR 005), write to the custody log with a conditional write, publish the resulting event to EventBridge (ADR 003), then return a confirmation to the caller. A dedicated Cognito user pool, `dev-ChainLoop-users`, holds the four v1 actor groups (Lab Tech, Courier, Receiving Lab, Ops Supervisor), separate from SoleLoop's user pool, since these are different people with different roles.

## Reasoning

Actors need to know their scan was actually recorded before they walk away, a courier confirming a pickup needs a real yes or no, not a "maybe, check back later." That requirement, an authenticated actor needing a synchronous, trustworthy confirmation, is exactly the same shape SoleLoop's endpoints already solved well. Reusing it here means the mobile or web client stays simple: authenticate, submit a scan, get a clear response, no need for a persistent connection or a different protocol.

The one real difference from SoleLoop is what the entry Lambda does internally. SoleLoop's Lambdas wrote directly to their own projection table and returned. ChainLoop's entry Lambda carries more responsibility: it has to perform the idempotent persist step and then publish to EventBridge before it can honestly tell the caller "recorded," since the event bus is the mechanism that lets the SLA timer, the projection updater, and the notification service all react independently, per ADR 003.

## Alternatives Considered

**AWS IoT Core.** Rejected for v1: IoT Core is built for persistent-connection hardware devices reporting continuously. ChainLoop's actors are people using a phone or handheld scanner to submit discrete actions, a well-understood HTTPS request model, not a device-telemetry model.

**Clients publishing directly to EventBridge, skipping API Gateway and Lambda entirely.** Rejected: this would require giving mobile clients IAM credentials capable of publishing to EventBridge directly, bypassing authentication, validation, and the idempotency check that has to happen before anything is considered durably recorded. The entry Lambda's validation step is not optional overhead, it is the thing that keeps the custody log trustworthy.

**GraphQL/AppSync.** Rejected for v1: no real-time subscription requirement exists yet in this scope, and introducing GraphQL adds a learning curve without a corresponding need. Worth revisiting if a live-updating Ops dashboard becomes a real requirement later.

## Consequences

**Positive**
- Reuses a proven, well-understood entry pattern rather than introducing a new one
- Keeps the client (mobile or web) simple: authenticate, POST, get a synchronous answer
- Actors get an honest, immediate confirmation that their action was recorded

**Negative**
- The entry Lambda does more work per request than SoleLoop's equivalent Lambdas did, validate, persist, and publish, all before responding, which is more logic to get right in one function
- A separate Cognito user pool means separate user management from SoleLoop, more infrastructure to maintain, though this is the correct tradeoff for genuinely different actors and roles

## Revisit If

A real-time push requirement emerges, for example an Ops dashboard that needs to update the instant a scan comes in without polling or refreshing, at which point AppSync or a WebSocket-based approach should be evaluated on its own merits. Also revisit if automated scanning hardware ever replaces manual actor-driven entry, at which point IoT Core becomes a genuine fit rather than an unnecessary one.