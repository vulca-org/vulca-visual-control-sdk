# VULCA

<p align="center">
  <img src="assets/brand/vulca-logo.svg" alt="Vulca logo" width="240">
</p>

[![PyPI](https://img.shields.io/pypi/v/vulca.svg)](https://pypi.org/project/vulca/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/vulca/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/LICENSE)
[![CI](https://github.com/vulca-org/vulca-visual-control-sdk/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/vulca-org/vulca-visual-control-sdk/actions/workflows/ci.yml)
[![MCP Tools](https://img.shields.io/badge/MCP_tools-current-blueviolet.svg)](https://github.com/vulca-org/vulca-visual-agent-plugin)

**Vulca turns fuzzy visual intent into controlled creative production.**

Discover the direction, compile the brief, route the model, edit the pixels,
and evaluate the result — as agent-native artifacts and MCP tools.

One-click models are getting stronger. Vulca does not try to beat them at raw
generation. Vulca sits around them: it helps agents clarify what should be made,
choose and constrain the right provider, preserve non-target pixels during edits,
and record why a result does or does not fit the cultural and visual brief.

```text
fuzzy intent
  -> /visual-discovery
  -> /visual-brainstorm
  -> /visual-spec
  -> /visual-plan
  -> generate / decompose / edit / evaluate
  -> archived artifacts
```

| Stage | What Vulca gives the agent | Status |
|---|---|---|
| Discover | Taste/culture profile, direction cards, sketch prompts | PR-ready |
| Specify | `proposal.md`, `design.md`, `plan.md` | Current |
| Generate | Provider-routed image calls across OpenAI, Gemini, ComfyUI, mock | Current |
| Edit | Semantic layers, masks, redraw, inpaint, composite, paste-back | Current + v0.22 hardening |
| Evaluate | L1-L5 cultural and visual scoring | Current |
| Archive | Prompts, masks, layers, evaluations, errors, user overrides | Current |

## Product direction: VULCA Workspace

The SDK and MCP tools are the execution layer. The product direction is
**VULCA Workspace**: a Creative Repo surface for AI-native teams to review
briefs, visual variants, agent findings, evidence packs, and release gates
before anything is treated as ready for public release.

The current Workspace preview is review-first, not an editor replacement:
Review Inbox, Single Asset Review, Context Drawer, typed review checks,
decision actions, manual upload intake, and a visible `public_ready=false`
release boundary. Agents can advise inside the workflow, but human reviewers
own release decisions.

See [Workspace current-state audit](docs/product/workspace-current-state-audit.md)
for how the Workspace preview connects to the SDK/MCP tools, website, PPT proof
lab, and protected project context.

> *Concrete demo below: Michelangelo's *Creation of Adam* → 5 semantic layers via `/decompose` (background · adam · god_and_angels · red_cloak · green_ground), decomposed locally on Apple Silicon (ComfyUI + Ollama) with zero cloud API calls. SDK surface: MCP tools plus agent skills, validated by the test suite.*

## What happens when you run `/decompose`

```
> /decompose assets/showcase/originals/creation-of-adam.jpg

Claude: I'll inspect the fresco and plan a semantic decomposition.
[tool_use: view_image(path="assets/showcase/originals/creation-of-adam.jpg")]
[tool_use: layers_split(
    path="assets/showcase/originals/creation-of-adam.jpg",
    mode="orchestrated",
    plan={"domain": "fresco", "entities": [
        {"name": "background",     "prompt": "the pale cream sky of the ceiling",
         "semantic_path": "background"},
        {"name": "adam",           "prompt": "the reclining nude male figure on the left",
         "semantic_path": "subject.person[0]"},
        {"name": "god_and_angels", "prompt": "the bearded figure of God with the angel group",
         "semantic_path": "subject.person[1]"},
        {"name": "red_cloak",      "prompt": "the billowing dark red cloak around God",
         "semantic_path": "subject.drapery"},
        {"name": "green_ground",   "prompt": "the mossy green ground beneath Adam",
         "semantic_path": "foreground.ground"}]})]
[tool_result: {"layers": [
    {"name": "background",     "semantic_path": "background"},
    {"name": "adam",           "semantic_path": "subject.person[0]"},
    {"name": "god_and_angels", "semantic_path": "subject.person[1]"},
    {"name": "red_cloak",      "semantic_path": "subject.drapery"},
    {"name": "green_ground",   "semantic_path": "foreground.ground"}]}]

Claude: 5 layers extracted — each person figure isolated, drapery and ground separated from the pale fresco sky. Want to redraw God's cloak, composite with a different background, or run another image?
```

## Quick start

**Realistic setup time:** ~1 minute if you already use Claude Code with [`uv`](https://docs.astral.sh/uv/getting-started/installation/?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-04-20) installed; ~5–10 minutes from scratch (Claude Code + `uv` + plugin + key config).

**Prerequisite:** `uv` installed (provides `uvx`). Without `uv`, substitute `uvx --from vulca[mcp] vulca-mcp` with `python -m vulca.mcp_server` in Path B.

### Path A — plugin install (recommended)

```bash
pip install vulca[mcp]==0.23.1
claude plugin install vulca-org/vulca-visual-agent-plugin
```

Then in Claude Code: `> /decompose /path/to/your_image.jpg`

### Path B — no plugin (power user)

```bash
pip install vulca[mcp]==0.23.1

# Register MCP server — add to ~/.claude/settings.json:
# {"mcpServers": {"vulca": {"command": "uvx", "args": ["--from", "vulca[mcp]==0.23.1", "vulca-mcp"]}}}

# Install the /decompose skill:
mkdir -p ~/.claude/skills/decompose
curl -o ~/.claude/skills/decompose/SKILL.md \
  "https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/v0.23.1/.claude/skills/decompose/SKILL.md?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-05-11"
```

<p align="center">
  <img src="assets/showcase/originals/creation-of-adam.jpg" alt="Creation of Adam original" height="150">
  →
  <img src="assets/showcase/layers/creation-of-adam/adam.png" alt="Adam figure" height="150">
  <img src="assets/showcase/layers/creation-of-adam/god_and_angels.png" alt="God with angels" height="150">
  <img src="assets/showcase/layers/creation-of-adam/red_cloak.png" alt="Red cloak drapery" height="150">
  <img src="assets/showcase/layers/creation-of-adam/background.png" alt="Background ceiling sky" height="150">
</p>
<p align="center"><em>Michelangelo's <em>Creation of Adam</em> → 4 of 5 agent-produced semantic layers: <code>subject.person[0]</code> (Adam) · <code>subject.person[1]</code> (God + angels) · <code>subject.drapery</code> (red cloak) · <code>background</code>. Hierarchical path + the 5th layer (<code>foreground.ground</code>) in <a href="assets/showcase/layers/creation-of-adam/manifest.json">manifest.json</a>.</em></p>

---

## Why agent-native

Most image SDKs ship a "brain" — a VLM planner that decides what to generate, how to compose, when to stop. Claude Code already has a brain. What it can't do is cut pixels: run SAM + YOLO + DINO + SegFormer, diff masks, score against a cultural rubric, composite with alpha. Vulca is the **hands**, not another brain.

Practical consequences of this framing:
- **Tools return structured JSON + paths**, not prose. The agent inspects, branches, retries.
- **No hidden LLM/planning decisions** inside tools — every tool call surfaces its detection report; the agent sees what ran, can branch, and can roll back.
- **The skill we ship (`.claude/skills/decompose/SKILL.md`) is a declarative prompt, not a wrapper.** The agent reads it directly. Future skills follow the same shape.
- **Vulca doesn't host a model** — it drives yours (ComfyUI / Gemini / OpenAI / mock) with structured tooling. No overlap with hosted image APIs; the value is in the pixel-level work between "agent planned" and "image on disk."
- **Local-first is a first-class path** — ComfyUI + Ollama + MPS tested end-to-end; no cloud key required.

---

## What Vulca takes off your agent's hands

| Cluster | What your agent delegates to Vulca | Skill | Tools |
|---|---|:---:|---|
| **Decompose** | Extract 10–20 semantic layers from any image with real transparency. | ✅ `/decompose` | `layers_split` (orchestrated), `layers_list` |
| **Edit** | Redraw one region or one layer without touching the rest. Composite back. | Roadmap | `inpaint_artwork`, `layers_edit`, `layers_redraw`, `layers_transform`, `layers_composite`, `layers_export`, `layers_evaluate` |
| **Evaluate** | Judge a visual against L1–L5 cultural criteria over 13 traditions with citable rationale. | ✅ `/evaluate` | `evaluate_artwork`, `list_traditions`, `get_tradition_guide`, `search_traditions` |
| **Create** | Generate a new image from intent + tradition guidance, optionally in structured layers. | — | `create_artwork`, `generate_image` |
| **Discovery / Brief / Studio** | Turn fuzzy intent into direction cards, then a reviewable proposal.md; mock sketch records by default, real provider sketch only after explicit opt-in. | ✅ `/visual-discovery`, ✅ `/visual-brainstorm` | `brief_parse`, `generate_concepts(provider="mock")`, `compose_prompt_from_design` |
| **Admin** | Expose intermediate artifacts, unload models, archive sessions. | — | `view_image`, `unload_models`, `archive_session`, `sync_data` |

```
User intent ─▶ Claude Code (planning) ─▶ Vulca MCP tools ─▶ Image artifacts ─┐
       ▲                                                                    │
       └──────────── visible via view_image ◀───────────────────────────────┘
```

### Roadmap — no promises, just honest order

- **Next skill:** `/inpaint` (region-level edit), after real-image dogfood validates the v0.22 redraw routes
- **Then:** `/layered-create` (structured generation)
- **Beyond:** community-driven — file an issue with your workflow

See [docs/agent-native-workflow.md](docs/agent-native-workflow.md) for the deeper walkthrough.

---

<details>
<summary><strong>Evaluate — three modes (L1–L5 cultural scoring)</strong></summary>

Beyond decomposition, Vulca evaluates any image against a cultural tradition across 5 dimensions (L1 Visual Perception, L2 Technical Execution, L3 Cultural Context, L4 Critical Interpretation, L5 Philosophical Aesthetics) in three modes. The MCP tool is `evaluate_artwork`; the CLI is `vulca evaluate`. The `/evaluate` skill wraps `evaluate_artwork` for agent-led critique and next-action guidance.

### Strict (binary cultural judgment)

```
$ vulca evaluate artwork.png -t chinese_xieyi

  Score:     90%    Tradition: chinese_xieyi    Risk: low
    L1 Visual Perception         90%  ✓
    L2 Technical Execution       85%  ✓
    L3 Cultural Context          90%  ✓
    L4 Critical Interpretation  100%  ✓
    L5 Philosophical Aesthetics  90%  ✓
```

### Reference (mentor — professional terminology, not a verdict)

```
$ vulca evaluate artwork.png -t chinese_xieyi --mode reference

  L3 Cultural Context          95%  (traditional)
     To push further: adding a poem (题画诗) for poetry-calligraphy-
     painting-seal (诗书画印) harmony.
```

### Fusion (cross-tradition comparison)

```
$ vulca evaluate artwork.png -t chinese_xieyi,japanese_traditional,western_academic --mode fusion

  Dimension                Chinese Xieyi  Japanese Trad  Western Acad
  Overall Alignment               93%            90%           8%

  Closest tradition: chinese_xieyi (93%)
```

</details>

<details>
<summary><strong>Structured creation — <code>--layered</code> mode</strong></summary>

Vulca can plan a layer structure from a tradition's knowledge and emit each layer as a separate transparent PNG, with the first layer serving as a style anchor for the rest (Defense 3, v0.14+).

```bash
vulca create "水墨山水，松间茅屋" -t chinese_xieyi --layered --provider comfyui
# → 5 layers: paper, distant_mountains, mountains_pines, hut_figure, calligraphy
```

Works across traditions — photography produces depth layers, gongbi produces line-art + wash layers, brand design produces logo + background + typography.

```python
import vulca
result = vulca.create("水墨山水", provider="comfyui", tradition="chinese_xieyi", layered=True)
for layer in result.layers:
    print(layer.name, layer.path, layer.coverage)
```

From an agent, invoke via the `create_artwork` MCP tool (Path A/B above). The `/layered-create` skill is on the roadmap.

</details>

<details>
<summary><strong>Inpaint + layer editing — pixel-level preservation outside the target</strong></summary>

Two orthogonal flows for targeted change:

**Region inpaint** (no decomposition — pick a region, regenerate only that area):

```bash
vulca inpaint artwork.png --region "the sky in the upper portion" \
  --instruction "dramatic stormy clouds" -t chinese_xieyi --provider comfyui
```

**Layer redraw** (after `/decompose` — swap one layer without touching the rest):

```bash
vulca layers lock ./layers/ --layer calligraphy_and_seals
vulca layers redraw ./layers/ --layer background_sky \
  -i "warm golden sunset with orange and purple gradients"
vulca layers composite ./layers/ -o final.png
```

Layer operations available: `add`, `remove`, `reorder`, `toggle`, `lock`, `merge`, `duplicate`. All provider-agnostic (works with ComfyUI, Gemini, OpenAI, mock).

From an agent, these map to `inpaint_artwork`, `layers_edit`, `layers_redraw`, `layers_composite`, `layers_export`. The `/inpaint` skill is on the roadmap.

</details>

---

## Research

| Paper | Venue | Contribution |
|-------|-------|--------------|
| [**VULCA Framework**](https://aclanthology.org/2025.findings-emnlp.103/?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-04-20) | EMNLP 2025 Findings | 5-dimension evaluation framework for culturally-situated multimodal LLM tasks |
| [**VULCA-Bench**](https://arxiv.org/abs/2601.07986?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-04-20) | arXiv | L1–L5 definitions, 7,410 samples, 9 traditions |
| [**Art Critique**](https://arxiv.org/abs/2601.07984?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-04-20) | arXiv | Cross-cultural expert-level critique evaluation with VLMs |

### Citation

```bibtex
@inproceedings{yu2025vulca,
  title     = {A Structured Framework for Evaluating and Enhancing Interpretive
               Capabilities of Multimodal LLMs in Culturally Situated Tasks},
  author    = {Yu, Haorui and Ruiz-Dolz, Ramon and Yi, Qiufeng},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2025},
  pages     = {1945--1971},
  year      = {2025}
}

@article{yu2026vulcabench,
  title   = {VULCA-Bench: A Benchmark for Culturally-Aware Visual Understanding at Five Levels},
  author  = {Yu, Haorui},
  journal = {arXiv preprint arXiv:2601.07986},
  year    = {2026}
}
```

---

## 13 cultural traditions

`chinese_xieyi` `chinese_gongbi` `japanese_traditional` `western_academic` `islamic_geometric` `watercolor` `african_traditional` `south_asian` `contemporary_art` `photography` `brand_design` `ui_ux_design` `default`

Custom traditions via YAML — `vulca evaluate painting.jpg --tradition ./my_style.yaml`.

---

## Apple Silicon / MPS quickstart

```bash
pip install vulca[mcp,tools]==0.23.1
# Local stack: ComfyUI + Ollama, full MPS support
```

See [docs/apple-silicon-mps-comfyui-guide.md](docs/apple-silicon-mps-comfyui-guide.md) for the full [ComfyUI](https://github.com/comfyanonymous/ComfyUI?utm_source=github-readme&utm_medium=oss&utm_campaign=refresh-2026-04-20) + Ollama setup tested on MPS.

---

## Cloud provider SDKs

Install provider SDKs only when you need hosted image backends:

```bash
pip install vulca[providers]

# Google GenAI / Gemini / Nano Banana
export GEMINI_API_KEY="..."

# OpenAI Images / Responses image tool
export OPENAI_API_KEY="..."
```

Built-in image provider IDs:

| Provider ID | Backend path | Use when |
|---|---|---|
| `gemini` / `nb2` | Google GenAI image generation | direct Gemini/Nano Banana image calls |
| `gemini-tools` / `nb2-tools` | Google GenAI image generation plus opt-in tools | image calls that may use `tool_profile="web"`, `"url"`, or `"code"` |
| `openai` | OpenAI Images API | direct image generation/editing with GPT Image models |
| `openai-responses` | OpenAI Responses API `image_generation` tool | conversational or multi-turn image flows with `previous_response_id` |
| `comfyui` | local ComfyUI | local-first generation, edits, and layer workflows |
| `mock` | deterministic local mock | tests, docs, and dry runs |

```python
import asyncio
import os
from vulca.providers import get_image_provider


async def main():
    nb2 = get_image_provider("nb2-tools", api_key=os.environ["GEMINI_API_KEY"])
    sketch = await nb2.generate(
        "one green square on a white background",
        raw_prompt=True,
        width=512,
        height=512,
        tool_profile="web",
    )

    openai = get_image_provider("openai-responses", api_key=os.environ["OPENAI_API_KEY"])
    final = await openai.generate(
        "one blue circle on a white background",
        raw_prompt=True,
        width=1024,
        height=1024,
        quality="low",
        output_format="png",
    )

    print(sketch.mime, final.metadata["response_id"])


asyncio.run(main())
```

---

<details>
<summary>CLI / SDK cheat sheet</summary>

```bash
# Create
vulca create "intent" -t tradition --provider mock|gemini|nb2|openai|openai-responses|comfyui
  --layered                    # structured layer generation
  --hitl                       # pause for human review
  --reference ref.png          # reference image
  --colors "#hex1,#hex2"       # color palette constraint
  -o output.png

# Evaluate
vulca evaluate image.png -t tradition --mode strict|reference|fusion
  --skills brand,audience,trend  # extra commercial scoring skills

# Layers
vulca layers analyze image.png
vulca layers split image.png -o dir --mode extract|regenerate|sam
vulca layers redraw dir --layer name -i "instruction"
vulca layers add dir --name name --content-type type
vulca layers toggle dir --layer name --visible true|false
vulca layers lock dir --layer name
vulca layers merge dir --layers a,b --name merged
vulca layers duplicate dir --layer name
vulca layers composite dir -o output.png
vulca layers export dir --format ora -o layers.ora
vulca layers import-ora layers.ora imported-dir
vulca layers evaluate dir -t tradition
vulca layers regenerate dir --provider gemini

# Inpainting
vulca inpaint image.png --region "description or x,y,w,h"
  --instruction "what to change" -t tradition --count 4 --select 1

# Tools (algorithmic, no API cost)
vulca tools run brushstroke_analyze --image art.png -t chinese_xieyi
vulca tools run whitespace_analyze --image art.png -t chinese_xieyi
vulca tools run composition_analyze --image art.png -t chinese_xieyi
vulca tools run color_gamut_check --image art.png -t chinese_xieyi
vulca tools run color_correct --image art.png -t chinese_xieyi

# Utilities
vulca traditions                        # list all traditions
vulca tradition tradition_name          # detailed guide
vulca tradition --init my_style         # generate template YAML
vulca evolution tradition_name          # check evolved weights
vulca sync [--push-only|--pull-only]    # cloud sync
```

```python
# Python SDK
import vulca
result = vulca.evaluate("artwork.png", tradition="chinese_xieyi")
print(result.score, result.suggestions, result.L3)

# Structured creation
result = vulca.create("水墨山水", provider="comfyui",
                      tradition="chinese_xieyi", layered=True)

# Layer operations
from vulca.layers import analyze_layers, split_extract, composite_layers
import asyncio
layers = asyncio.run(analyze_layers("artwork.png"))
results = split_extract("artwork.png", layers, output_dir="./layers")
composite_layers(results, width=1024, height=1024, output_path="composite.png")

# Self-evolution weights
weights = vulca.get_weights("chinese_xieyi")
# → {"L1": 0.10, "L2": 0.20, "L3": 0.35, "L4": 0.15, "L5": 0.20}
```

</details>

OpenRaster interchange is an advanced/experimental, non-generative Effect Pack. See [the round-trip contract](docs/effect-packs/openraster-roundtrip.md) for protected invariants, evidence, and first-version limits.

<details>
<summary>Architecture</summary>

```
┌──────────────────────────────────────────────────────────────┐
│                         User Intent                          │
└──────┬───────────┬──────────────┬──────────────┬─────────────┘
       │           │              │              │
  ┌────▼──┐  ┌─────▼───┐  ┌──────▼─────┐  ┌─────▼─────┐
  │  CLI  │  │ Python  │  │    MCP     │  │  ComfyUI  │
  │       │  │   SDK   │  │ MCP tools  │  │  11 nodes │
  └───┬───┘  └────┬────┘  └──────┬─────┘  └─────┬─────┘
      └───────────┴───────┬──────┴───────────────┘
                          │
                 vulca.pipeline.execute()
                          │
              ┌───────────▼───────────┐
              │    Image Providers    │
              │  ComfyUI │ Gemini     │
              │  OpenAI  │ Responses  │
              │  Tools   │ Mock       │
              └───────────────────────┘
```

| Provider | Generate | Inpaint | Layered | Multilingual |
|----------|----------|---------|---------|--------------|
| ComfyUI  | ✓        | ✓       | ✓       | English-only |
| Gemini   | ✓        | ✓       | ✓       | CJK native   |
| Gemini Tools | ✓    | ✓       | ✓       | CJK native   |
| OpenAI   | ✓        | —       | —       | English-only |
| OpenAI Responses | ✓ | —      | —       | English-only |
| Mock     | ✓        | ✓       | ✓       | —            |

All 8 end-to-end pipeline phases validated on the local stack (ComfyUI + Ollama, Apple Silicon MPS). See the MPS guide linked above.

</details>

<details>
<summary>Self-evolution (how weights drift per tradition over sessions)</summary>

Every session feeds back into the tradition's L1–L5 weights. Gating: minimum 5 sessions + 3 feedback sessions before weights shift. `strict` mode reinforces conformance, `reference` mode tracks exploration.

```
$ vulca evolution chinese_xieyi

  Dim     Original    Evolved     Change
  L1        10.0%     10.0%      0.0%
  L2        15.0%     20.0%     +5.0%    ← Technical Execution strengthened
  L3        25.0%     35.0%    +10.0%    ← Cultural Context most evolved
  L4        20.0%     15.0%     -5.0%
  L5        30.0%     20.0%    -10.0%
  Sessions: 71
```

From an agent: `/evaluate` calls the `evaluate_artwork` MCP tool and returns evolved weights alongside scores.

</details>

---

## Showcase — agent-produced layer separations

<p align="center">
  <img src="assets/showcase/originals/starry-night.jpg" alt="Starry Night original" height="150">
  →
  <img src="assets/showcase/layers/starry-night/background.png" alt="swirling sky with stars" height="150">
  <img src="assets/showcase/layers/starry-night/subject.png" alt="dark cypress tree" height="150">
  <img src="assets/showcase/layers/starry-night/foreground.png" alt="village and hills" height="150">
</p>
<p align="center"><em>Van Gogh's <em>Starry Night</em> → 3 layers: <code>background</code> (swirling blue sky with yellow stars) · <code>subject</code> (the dark cypress tree) · <code>foreground</code> (the small village and hills). See <a href="assets/showcase/layers/starry-night/manifest.json">manifest.json</a>.</em></p>

<p align="center">
  <img src="assets/showcase/originals/migrant-mother.jpg" alt="Migrant Mother photograph" height="180">
  →
  <img src="assets/showcase/layers/migrant-mother/subject.png" alt="the seated mother" height="180">
  <img src="assets/showcase/layers/migrant-mother/foreground.png" alt="two children" height="180">
  <img src="assets/showcase/layers/migrant-mother/background.png" alt="dark backdrop" height="180">
</p>
<p align="center"><em>Dorothea Lange's <em>Migrant Mother</em> (1936, FSA — public domain photograph) → 3 layers: <code>subject</code> (the seated woman) · <code>foreground</code> (the two children leaning against her) · <code>background</code> (the dark cloth backdrop). Shows <code>/decompose</code> also works on real photographs, not only painted masters. See <a href="assets/showcase/layers/migrant-mother/manifest.json">manifest.json</a>.<br/>Works across domains — 24 masterworks have been run through <code>/decompose</code>, producing 3–15 semantic layers each.</em></p>

---

## Support

- **Issues:** [github.com/vulca-org/vulca-visual-control-sdk/issues](https://github.com/vulca-org/vulca-visual-control-sdk/issues) — bug reports, feature requests, workflow needs that should become a skill
- **Plugin:** [vulca-org/vulca-visual-agent-plugin](https://github.com/vulca-org/vulca-visual-agent-plugin) — version-tracked with the SDK; install in Claude Code, Gemini CLI, or Codex Desktop/CLI
- **Web platform:** [vulcaart.art](https://vulcaart.art) and [vulca-platform](https://github.com/yha9806/vulca-platform) — the deployed demo/site and platform workspace
- **Skill source:** [`.claude/skills/decompose/SKILL.md`](.claude/skills/decompose/SKILL.md) in this repo — the only source of truth for the `/decompose` flow
- **Skill source:** [`.claude/skills/visual-discovery/SKILL.md`](.claude/skills/visual-discovery/SKILL.md) — **`/visual-discovery`** explores fuzzy visual intent into taste profile, culture analysis, direction cards, and proposal-ready handoff. It is text/artifact-first: mock sketch records are allowed by default; real provider sketch generation requires explicit opt-in. The Codex/Superpowers mirror lives at [`.agents/skills/visual-discovery/SKILL.md`](.agents/skills/visual-discovery/SKILL.md).
- **Skill source:** [`.claude/skills/visual-brainstorm/SKILL.md`](.claude/skills/visual-brainstorm/SKILL.md) — **`/visual-brainstorm`** turns fuzzy visual intent (topic, optional sketch, optional references) into a reviewable `proposal.md`. Zero-pixel, Discovery-metadata only. Scoped to 2D illustrative/editorial imagery (poster, illustration, packaging, brand visual, cover art, photography brief, hero visuals for UI).

## License

Apache 2.0. See [LICENSE](LICENSE).

> Issues and PRs welcome. Development syncs from a private monorepo via `git subtree`.
