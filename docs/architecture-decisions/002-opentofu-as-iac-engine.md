# ADR 002: OpenTofu as ChainLoop's Infrastructure-as-Code Engine

## Context

Terraform became the de facto standard for infrastructure as code, and SoleLoop was built entirely on it. In August 2023, HashiCorp changed Terraform's license from the Mozilla Public License 2.0 (MPL 2.0), a permissive open-source license, to the Business Source License (BSL 1.1), which restricts building products or services that compete with HashiCorp's own commercial offerings. Within weeks, a coalition of infrastructure companies forked the last MPL-licensed release into OpenTofu, which now lives under the Linux Foundation with a multi-organization Technical Steering Committee, and entered the CNCF as a sandbox project in April 2025. IBM acquired HashiCorp in early 2025, and Terraform has remained under BSL since.

OpenTofu and Terraform still share the same HCL syntax, the same provider ecosystem, and compatible state files, migrating between them is close to a binary swap for most configurations. They have started to diverge technically: OpenTofu has shipped native state encryption, early variable evaluation, and provider iteration with for_each, features the open-source Terraform CLI still doesn't have.

## Decision

ChainLoop's infrastructure will be provisioned with OpenTofu instead of Terraform.

## Reasoning

Infrastructure tooling is a long-lived organizational dependency, and the governance model behind it matters. OpenTofu is steered by a multi-vendor technical committee rather than a single commercial owner, which means no one company can unilaterally change its license terms again the way HashiCorp did in 2023. For a project meant to model reliable, auditable infrastructure, choosing a tool with that same resilience felt like the right foundation, not just a preference.

HCL knowledge from SoleLoop transfers directly, there's no meaningful learning curve in adopting OpenTofu, which made this an easy decision rather than a costly one. SoleLoop already demonstrated Terraform end to end; building ChainLoop on OpenTofu intentionally broadens hands-on experience across both branches of the modern IaC ecosystem, rather than repeating the same tool on a second project.

## Alternatives Considered

**Terraform.** Already proven in SoleLoop. Not selected here specifically to build real experience with the openly governed alternative, and because OpenTofu's governance model better fits a project built around reliability and long-term trust.

**AWS CloudFormation.** Rejected: CloudFormation locks infrastructure definitions to AWS specifically, and the multi-cloud, provider-agnostic HCL ecosystem is more transferable experience.

**AWS CDK.** Rejected: CDK is imperative, infrastructure defined through general-purpose programming languages, while this project is deliberately about declarative infrastructure and the discipline that comes with plan-before-apply review.

## Revisit If

HashiCorp reverses the BSL license change, or OpenTofu's governance or provider ecosystem meaningfully regresses relative to Terraform's. Either would be worth reassessing this decision on its merits, not out of habit.