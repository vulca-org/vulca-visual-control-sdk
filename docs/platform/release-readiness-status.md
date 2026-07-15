# Platform Release Readiness Status

**Status:** Working release gate summary
**Last updated:** 2026-07-16

## Current Claims We Can Make

- Vulca has a Claude plugin package shape at the repository root: `.claude-plugin/plugin.json`, `.mcp.json`, and `skills/`.
- Vulca has a public Git-backed Codex marketplace source at `vulca-org/vulca-visual-agent-plugin`, backed by `plugins/vulca/.codex-plugin/plugin.json`, `plugins/vulca/.mcp.json`, and `plugins/vulca/skills/`.
- Codex can be documented as a plugin plus MCP target. OpenAI's plugin submission portal is available, but a directory listing must not be claimed before submission and acceptance.
- ChatGPT can be documented as a remote MCP app/prototype target with a remote-safe streamable HTTP entry point, `vulca-mcp-remote`.
- Google/Gemini can be documented as a provider path now, with ADK / Vertex Agent Engine later.
- Redraw is an advanced workflow today. v0.22 target-aware mask refinement is merged, but polished `/inpaint` or `/redraw-layer` promotion remains gated on real-image dogfood evidence.

## Claims We Should Not Make Yet

- Do not claim the public Codex listing has already launched.
- Do not claim Google has a Vulca plugin marketplace path.
- Do not claim cultural terminology guarantees better generation.
- Do not lead marketplace copy with redraw quality until v0.22 is dogfooded on representative real images.
- Do not present transparent layer assets as final after-images.

## Verification Evidence

Revalidated from the public Plugin repository after the rename on 2026-07-15:

```bash
/Applications/ChatGPT.app/Contents/Resources/codex plugin marketplace add vulca-org/vulca-visual-agent-plugin
/Applications/ChatGPT.app/Contents/Resources/codex plugin add vulca --marketplace vulca-visual-agent-plugin
```

Observed with an isolated `CODEX_HOME`: added marketplace `vulca-visual-agent-plugin` from public GitHub and installed `vulca@vulca-visual-agent-plugin` version `0.23.1`.

The following Claude evidence remains the historical 2026-05-01 validation record:

```bash
/Users/yhryzy/.local/bin/claude plugin validate .
```

Observed: validation passed.

Run in `/Users/yhryzy/dev/vulca-plugin` on 2026-05-01:

```bash
/Users/yhryzy/.local/bin/claude plugin validate .
/Users/yhryzy/.local/bin/claude plugin validate .claude-plugin/plugin.json
```

Observed: marketplace and plugin manifest validation passed. `vulca-plugin` PR #9 synced the standalone plugin repository to v0.19.0 and was merged at commit `55b6bb371544cd199e43f493b763d34e9cb85f5e`.

```bash
/Users/yhryzy/.local/bin/claude --plugin-dir . --print --max-budget-usd 0.20 --permission-mode dontAsk "Reply with only the Vulca plugin skill names you can see from loaded plugins; do not use tools."
```

Observed skills:

- `vulca:visual-discovery`
- `vulca:decompose`
- `vulca:evaluate`
- `vulca:visual-spec`
- `vulca:visual-brainstorm`
- `vulca:using-vulca-skills`
- `vulca:visual-plan`

```bash
/opt/homebrew/bin/python3 scripts/sync_plugin.py
/opt/homebrew/bin/python3 scripts/sync_plugin.py --check
```

Observed: synced `.agents/skills` into `.claude/skills`, `skills`, and `plugins/vulca/skills`, then checked plugin package README and manifest drift.

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_prompting.py tests/test_visual_discovery_docs_truth.py tests/test_visual_discovery_prompting.py tests/test_visual_discovery_benchmark.py tests/test_gemini_image_size.py tests/test_generate_image_extended_signature.py -q
```

Observed: 60 passed.

```bash
grep -RIn "culture term[s] guarantee\|cultural term[s] guarantee\|always improves generatio[n]\|proves cultural promptin[g]\|official Codex public listing is liv[e]\|official Codex public publishing is liv[e]\|OpenAI plugin marketplac[e]\|21 MCP tool[s]\|20 MCP tool[s]\|21 tool[s]\|\.Codex/skill[s]" README.md pyproject.toml .claude-plugin .agents/skills .claude/skills skills docs/product docs/platform plugins/vulca src/vulca/mcp_server.py
```

Observed: no matches.

Run after v0.22 merge:

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_mask_refine.py tests/test_layers_redraw_refinement.py tests/test_redraw_review_contract.py -q
```

Observed: 14 passed.

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_mask_refine.py tests/test_layers_redraw_refinement.py tests/test_layers_redraw_crop_pipeline.py tests/test_layers_redraw_quality_gates.py tests/test_layers_redraw_strategy.py tests/test_layers_redraw.py tests/test_provider_edit_capabilities.py tests/vulca/providers/test_capabilities.py -q
```

Observed: 44 passed.

Run after adding the ChatGPT remote-safe MCP entry point:

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_mcp_remote_profile.py -q
```

Observed: 14 passed.

## Manual Gates Remaining

- Optional: run a full interactive `claude --plugin-dir .` session if you want UI-level confirmation beyond `plugin validate` and non-interactive skill discovery.
- Optional: open Codex UI and confirm the `vulca-visual-agent-plugin` marketplace source and `vulca` plugin appear as expected.
- Deploy `vulca-mcp-remote` behind HTTPS/auth/logging before connecting it to ChatGPT developer mode from a public URL.
- For ChatGPT App resubmission, the public privacy policy route is live at
  `https://vulcaart.art/chatgpt-app-privacy`; complete
  `docs/platform/chatgpt-app-resubmission-checklist.md`.
- Review marketplace copy and capture fresh ChatGPT app screenshots before submission.
- Dogfood v0.22 redraw on representative real images and confirm the user-facing after-image is `source_pasteback_path`.
- Decide what to do with main-worktree untracked generated artifacts before any broad cleanup.
