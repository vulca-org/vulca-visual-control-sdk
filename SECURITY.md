# Security Policy

## Supported Versions

Only the latest released minor version on PyPI (`pip install vulca`) is
supported with security patches. Currently: **v0.17.x**.

## Reporting a Vulnerability

Email **yuhaorui48@gmail.com** with subject `vulca-security: <short title>`.
Please do not open a public issue or Discussion for anything that could
affect users running Vulca locally against their own ComfyUI / Gemini /
Ollama providers.

I aim to acknowledge within **72 hours** and target a patch release within
**~7 days** for high-severity issues (arbitrary file write via layer output
paths, prompt-injection escalation through `evaluate` VLM output,
credential leakage in provider adapters). Solo-maintainer project —
timelines are best-effort, not contractual.

## Scope

**In scope:**
- The `vulca` PyPI package.
- The `vulca-org/vulca-visual-agent-plugin` Claude Code / Cursor plugin.
- Any shipped MCP tool schema + `.claude/skills/*`.
- **Workflow JSON shipped inside the `vulca` package or `vulca-org/vulca-visual-agent-plugin`** (e.g., bundled ComfyUI graph templates, skill-embedded example workflows) — regressions or RCE-class issues here are our responsibility.
- **Workflow JSON synthesized by Vulca skills / MCP tools** from agent input (e.g., a `/decompose` or `/visual-plan` tool writing a workflow that a prompt-injected VLM response could influence) — the synthesis path is in scope even when the execution environment is local.

**Out of scope:**
- Third-party providers themselves (ComfyUI, Gemini, Ollama) — report those upstream.
- Vulnerabilities requiring a **user-authored or hand-installed** malicious ComfyUI workflow JSON (if the user pasted untrusted workflow YAML from the internet and Vulca executes it locally, that's a user-trust-boundary issue, not a Vulca vulnerability).

## Known limitations

- **`local` provider sentinel leak**: when a session has mixed provider configs, the `local` sentinel may inadvertently resolve to a cloud provider (tracked in project memory `project_local_provider_sentinel.md`). Safe when ComfyUI + Ollama are the only providers; surface with caution in mixed setups. Fix planned for v0.18+.

## Disclosure

Fixes are announced in `CHANGELOG.md` and tagged releases. Reporters
are credited unless they request otherwise.
