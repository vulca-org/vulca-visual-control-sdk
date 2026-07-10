---
name: Feature request
about: Propose a new feature or improvement
title: "[feat] "
labels: enhancement
assignees: ''
---

## Problem

<!-- What can't you do today that you need to do? Describe the workflow,
     not the feature. -->

## Proposed solution

<!-- If you have one in mind. Otherwise leave this blank — the problem
     statement is enough. -->

## Agent-native discipline check

Vulca is an agent's hands and eyes, not its brain. Before proposing, confirm:

- [ ] The feature keeps decisions at the **agent layer** (no hardcoded thresholds, no Python-side prompt construction, no silent fallbacks that hide decisions from the agent).
- [ ] The feature exposes information through an **MCP tool schema** or a **skill body**, not by embedding logic in Python SDK code.
- [ ] There's a **dogfooding story** — a real cultural-evaluation workflow this unblocks. Describe it in one sentence.

If any of these are "no" but you still think the feature belongs, open a **[Discussion](https://github.com/vulca-org/vulca-visual-control-sdk/discussions)** first instead of an issue — we'll figure out together whether it's an agent-layer or SDK-layer concern.

See [CONTRIBUTING.md § Anti-patterns](../../CONTRIBUTING.md#anti-patterns--what-will-not-be-merged) for what won't be merged.

## Alternatives considered

<!-- Other approaches you thought about. This helps the maintainer not
     re-do your design work. -->

## Cultural / tradition angle (optional)

<!-- If this feature touches cultural evaluation (L1-L5 dimensions,
     tradition YAML, cross-cultural framing), note which tradition /
     framework you're thinking about. -->
