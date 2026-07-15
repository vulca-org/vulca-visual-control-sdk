# Platform Manual Review Checklist

**Status:** Human review checklist
**Last verified:** 2026-05-01

Use this checklist before merging or submitting Vulca to a plugin directory.

## Files To Review

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/*/SKILL.md`
- `.agents/plugins/marketplace.json`
- `plugins/vulca/.codex-plugin/plugin.json`
- `plugins/vulca/.mcp.json`
- `plugins/vulca/skills/*/SKILL.md`
- `docs/platform/*.md`
- `docs/platform/release-readiness-status.md`
- `docs/product/platform-distribution-realtime-brief.md`
- `docs/product/provider-capabilities.md`
- `docs/product/roadmap.md`

## Automated Checks

Run:

```bash
python scripts/sync_plugin.py
python scripts/sync_plugin.py --check
python -m pytest tests/test_visual_discovery_docs_truth.py tests/test_prompting.py -q
```

Then scan for overclaims:

```bash
grep -RIn "21 MCP tool[s]\|20 MCP tool[s]\|always improves generatio[n]\|proves cultural promptin[g]\|official Codex public listing is liv[e]" README.md pyproject.toml .claude-plugin .agents/skills .claude/skills skills docs/product docs/platform plugins/vulca src/vulca/mcp_server.py
```

Expected: no matches.

## Claude Manual Gate

Run in a clean Claude Code session:

```bash
claude --plugin-dir .
```

Verify:

- the plugin appears as `vulca`;
- skills are namespaced as `/vulca:<skill>`;
- `.mcp.json` starts `vulca-mcp`;
- `/vulca:visual-discovery` can complete a mock/no-cost workflow;
- `/vulca:evaluate` can evaluate an existing local artifact;
- redraw and inpaint are not presented as polished top-level user skills.

## Codex Manual Gate

The installed ChatGPT desktop CLI in this environment is `codex-cli 0.144.2` and exposes:

```bash
codex plugin marketplace add .
codex plugin add vulca --marketplace vulca-visual-agent-plugin
```

Then restart Codex and verify:

- `Vulca Visual Agent Plugin` appears as a marketplace source;
- `Vulca` appears as an installable plugin;
- bundled skills are visible after install;
- `vulca-mcp` can start;
- plugin copy does not contain scaffold placeholder markers.

Before public submission, confirm the publisher has Apps Management write access and a verified developer or business identity, then use `https://platform.openai.com/plugins`.

## Redraw Gate

Before marketplace copy leads with redraw:

- run its redraw-focused tests;
- dogfood representative real images where target-aware masks avoid editing unrelated pixels;
- confirm final user-facing image uses paste-back output, not sparse transparent layer output.
