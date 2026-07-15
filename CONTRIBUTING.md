# Contributing to Vulca

Vulca is a solo-maintained, dogfooding-driven project: every feature ships
only after the maintainer uses it on a real cultural-evaluation workflow.
PRs are welcome but will be judged against that bar.

## Before you start

1. Skim `README.md` and the active plan in `docs/superpowers/plans/`.
2. Confirm the change is **agent-native** — Vulca is an agent's hands and
   eyes, not its brain. Features that hide decisions from the agent or
   centralise prompt logic in Python are unlikely to land.
3. For anything non-trivial, open a Discussion first.

## Dev loop

```bash
pip install -e ".[dev,mcp]"
pytest tests/               # 12 cv2/layered baseline failures are expected locally (see .github/workflows/ci.yml ignore-list)
ruff check src/ tests/      # narrow rule set (E9/F63/F7/F82) in v0.17.x — expands in v0.17.12+
```

The MCP surface lives in `src/vulca/mcp_server.py`. Any new tool must:
- have a schema test under `tests/test_mcp_parity.py` or `tests/test_mcp_new_tools.py`
- be listed in the plugin manifest at `vulca-org/vulca-visual-agent-plugin`
- survive a live ship-gate (see `docs/superpowers/plans/*.md`)

## Anti-patterns — what will NOT be merged

The "agent-native discipline" check on the PR template is load-bearing. Concrete patterns that **look** fine but will be rejected:

- **Hardcoded evaluation / composition thresholds** in Python (e.g., `DEFAULT_QUALITY_THRESHOLD = 0.7`, `MIN_L3_SCORE = 0.6`). Thresholds are the agent's runtime decision informed by the user's acceptance rubric — encoding a default centralises that choice away from the agent.
- **Python-side prompt construction / prompt templates** embedded in the SDK or MCP layer. Prompts are derived by `/visual-spec` from tradition + user directive; any Python-side prompt shim reads agent-intent into code.
- **Silent fallbacks that hide a failed tool call** (e.g., catching a provider error and returning a `"default"` result so the agent "keeps going"). Failures should surface to the agent so it can decide retry / degrade / abort — silent success is the single most corrosive anti-pattern for agent-native tooling.

When in doubt: ask "would a Python refactor make the agent's job easier?" If yes, the change probably belongs in a skill body or a provider adapter, not in `src/vulca/`.

## PR checklist

- One logical change per PR; commit messages follow existing style
  (see `git log` — `feat(...)`, `fix(...)`, `docs(plan): ...`).
- Tests added/updated; `pytest` passes (modulo pre-existing baseline).
- `CHANGELOG.md` updated under the next unreleased section.
- No binary artefacts (`gen_*.png`, `*.pth`) committed — see `.gitignore`.

By contributing you agree your work is licensed Apache-2.0.
