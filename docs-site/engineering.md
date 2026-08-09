---
layout: default
title: Engineering library
permalink: /engineering/
---

Everything needed to understand, extend, test, or automate {{ site.data.product.display_name }}
is readable on this site. Start with the short page for your task; open the complete
source-synchronized reference only when you need implementation detail.

## Build and contribute

| Read | Use it for |
|---|---|
| [Development]({{ '/development/' | relative_url }}) | Clone the project, run it, understand the gate, and prepare a pull request. |
| [Agent contributor contract]({{ '/development/agent-contract/' | relative_url }}) | Quick commands and the repository non-negotiables. |
| [Complete development guide]({{ '/development/guide/' | relative_url }}) | Test-suite map, goldens, bundle pins, Forge checks, and the full pre-PR checklist. |
| [Architecture]({{ '/development/architecture/' | relative_url }}) | Boot, event flow, governance, UI state, delegation, persistence, and change locations. |
| [Design contract]({{ '/development/design-contract/' | relative_url }}) | Normative strings, states, layout, themes, and interaction requirements. |
| [Architecture research]({{ '/development/research/' | relative_url }}) | Stack choice, event boundary, risk analysis, and reuse decisions. |
| [Design background]({{ '/development/design-background/' | relative_url }}) | The presentation rationale behind the normative contract. |

## Complete product references

| Read | Use it for |
|---|---|
| [Complete user guide]({{ '/reference/user-guide/' | relative_url }}) | Every day-to-day interaction, command family, shortcut, and recovery path. |
| [Settings reference]({{ '/configuration/settings/' | relative_url }}) | Every settings key, scope, environment variable, and notification option. |
| [Install reference]({{ '/setup/install-reference/' | relative_url }}) | Exact installer guarantees, machine changes, verification, and uninstall. |
| [Session control protocol]({{ '/automation/session-control/' | relative_url }}) | Authenticated automation, leases, handoffs, audit, replay, and attachment. |
| [Python SDK]({{ '/automation/python/' | relative_url }}) | Consume the versioned subprocess protocol from Python. |
| [TypeScript SDK]({{ '/automation/typescript/' | relative_url }}) | Consume the same protocol from TypeScript. |

## Adoption and decisions

| Read | Use it for |
|---|---|
| [Staged adoption policy]({{ '/development/adoption/' | relative_url }}) | Understand the five evidence-gated rollout stages and rollback policy. |
| [Adoption runbook]({{ '/development/adoption/runbook/' | relative_url }}) | Execute a stage, record evidence, and make the owner decision. |
| [ADR-0005: modes and trust]({{ '/development/decisions/0005-interaction-modes/' | relative_url }}) | Why modes and permission posture remain independent. |
| [ADR-0006: full-screen shell]({{ '/development/decisions/0006-full-screen-shell/' | relative_url }}) | Why this is a pinned full-screen terminal experience. |
| [ADR-0007: architecture]({{ '/development/decisions/0007-architecture/' | relative_url }}) | The accepted layering, event, runtime, rewind, and testing decisions. |
| [ADR-0008: command name]({{ '/development/decisions/0008-console-script-name/' | relative_url }}) | Why the executable remains `{{ site.data.product.command }}`. |

These long references are synchronized from their authoritative repository files during the
Pages build. The friendly guides remain intentionally shorter; the detailed pages do not
fork the source material into another hand-maintained copy.
