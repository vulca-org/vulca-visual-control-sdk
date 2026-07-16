# OpenAI Codex And ChatGPT Integration Guide

**Status:** Draft implementation guide
**Last verified:** 2026-04-30

## Official Path

Codex now has a plugin directory / marketplace experience and a plugin manifest format at `.codex-plugin/plugin.json`. Codex plugins can package skills, MCP servers, agents, hooks, commands, and assets.

OpenAI's Codex plugin docs also describe local and Git-backed marketplace sources. They currently describe official public plugin publishing as coming soon, so the near-term Vulca path is repo-local marketplace validation plus a public repository install path.

Sources:

- [Codex plugins](https://developers.openai.com/codex/plugins)
- [Build a Codex plugin](https://developers.openai.com/codex/plugins/build)
- [OpenAI Docs MCP](https://platform.openai.com/docs/docs-mcp)
- [Building MCP servers for ChatGPT and API integrations](https://platform.openai.com/docs/mcp/)
- [Connectors and MCP servers](https://platform.openai.com/docs/guides/tools-remote-mcp)
- [ChatGPT Developer mode](https://platform.openai.com/docs/guides/developer-mode)

## Codex Plugin Package

This branch adds a repo-local package:

- `plugins/vulca/.codex-plugin/plugin.json`
- `plugins/vulca/.mcp.json`
- `plugins/vulca/skills/`
- `.agents/plugins/marketplace.json`

The package is intentionally self-contained for Codex validation. The copied skills should be refreshed when `.agents/skills/` changes.

Run:

```bash
python scripts/sync_plugin.py
python scripts/sync_plugin.py --check
```

Current Codex CLI:

```bash
codex plugin marketplace add .
codex plugin add vulca --marketplace vulca-visual-agent-plugin
```

## Local Codex MCP

Codex can also connect to Vulca as a plain MCP server:

```bash
codex mcp add vulca -- vulca-mcp
codex mcp list
```

Use this path for developer workflows that only need tools and do not need bundled skills or plugin UI metadata.

## ChatGPT Remote MCP

Start with a conservative remote MCP allowlist:

- `list_traditions`
- `get_tradition_guide`
- `search_traditions`
- `compose_prompt_from_design`
- `evaluate_artwork`

Do not expose generation, redraw, inpaint, paste-back, or filesystem-writing layer tools by default. Add those only behind explicit approval, clear cost labeling, and image/file privacy review.

Vulca now includes a remote-safe FastMCP entry point:

```bash
VULCA_REMOTE_WORKSPACE_ROOT=/absolute/path/to/workspace vulca-mcp-remote
```

By default this serves streamable HTTP on `http://127.0.0.1:8765/mcp`. Use this for local OpenAI Responses API experiments. ChatGPT developer mode requires a remotely reachable HTTPS endpoint and should not be connected to a public server until auth, logging, and deployment review are complete.

Responses API remote MCP tests should use an allowlist and approval requirement:

```python
tools = [
    {
        "type": "mcp",
        "server_label": "vulca",
        "server_url": "https://example.com/mcp",
        "allowed_tools": [
            "list_traditions",
            "get_tradition_guide",
            "compose_prompt_from_design",
            "evaluate_artwork",
        ],
        "require_approval": "always",
    }
]
```

## Release Gate

Before public install instructions:

- validate the repo marketplace in a clean Codex Desktop session;
- verify `vulca-mcp` is available in the target environment;
- verify `vulca-mcp-remote` starts with `VULCA_REMOTE_WORKSPACE_ROOT` set before ChatGPT remote MCP experiments;
- publish and submit the privacy policy at `https://vulcaart.art/chatgpt-app-privacy`;
- audit the raw remote MCP responses against `docs/platform/chatgpt-app-resubmission-checklist.md`;
- recapture OpenAI App screenshots and test evidence with `docs/platform/chatgpt-app-screenshot-and-test-evidence.md`;
- run one no-cost `/visual-discovery` or prompt-composition workflow;
- confirm generated artifacts stay in the workspace;
- confirm public copy says official Codex public publishing is still pending unless OpenAI has opened it.
