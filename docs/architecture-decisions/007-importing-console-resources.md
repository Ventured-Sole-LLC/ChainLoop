# ADR 007: Importing Console-Created Dev Resources Into OpenTofu State

## Context

The DynamoDB tables (`dev-ChainLoopEventLog`, `dev-ChainLoopProjection`, with its `status-sla-index` GSI), the EventBridge bus (`dev-ChainLoop-events`), and the SNS topic with email subscription (`dev-ChainLoop-alerts`) were created directly in the AWS console, deliberately, to walk through the console-equivalent of each Terraform resource before writing the code, the same console-fluency habit carried over from SoleLoop. OpenTofu's state file has no record of any of it.

## Decision

Rather than deleting these resources and letting OpenTofu create them fresh, write the OpenTofu configuration to match what already exists, then use `tofu import` to bring each resource under OpenTofu's management without recreating anything.

## Reasoning

Adopting infrastructure that already exists is a real, common situation, someone builds something by hand, or inherits infrastructure nobody documented, and it needs to come under IaC management afterward. Practicing the import workflow now, on low-stakes dev resources, is more valuable than avoiding the situation entirely by deleting and starting over. It also keeps the actual resources in place rather than needlessly destroying and recreating working infrastructure.

## Alternatives Considered

**Delete the console-created resources and let OpenTofu create them from scratch.** Rejected: simpler, but throws away a legitimate opportunity to practice a skill that comes up constantly in real infrastructure work, and destroys working resources for no functional benefit.

## Revisit If

This pattern of console-first, import-after becomes the norm rather than the exception, at which point it's worth asking whether resources should be written in OpenTofu first going forward, to avoid needing this reconciliation step at all.