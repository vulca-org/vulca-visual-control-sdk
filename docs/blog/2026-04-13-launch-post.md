---
title: "I Built a Free Local AI Art Pipeline on My Mac — Here's What Broke"
published: false
tags: python, machinelearning, opensource, ai
series: vulca
cover_image: https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/readme/tradition_grid.png
---

What if you could run a complete AI art creation pipeline — 13 cultural traditions, 5-dimension scoring, structured layer generation — entirely on your MacBook, for free?

No cloud API key. No GPU server. Just `pip install vulca`.

![Chinese Xieyi ink wash landscape](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/gallery/chinese_xieyi.png)
![Japanese traditional snow temple](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/gallery/japanese_traditional.png)
![Brand design tea packaging](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/gallery/brand_design.png)

*Three traditions, one SDK — generated locally via ComfyUI/SDXL on Apple Silicon, zero cloud API cost.*

These images were generated on an Apple Silicon Mac running ComfyUI locally. No Midjourney subscription. No Replicate credits. No DALL-E API calls. The evaluation scores below come from a VLM (Gemma 4 via Ollama) running on the same machine:

```
$ vulca evaluate art.png -t chinese_xieyi --mode reference

  Score:     90%    Tradition: chinese_xieyi    Risk: low

    L1 Visual Perception         ██████████████████░░ 90%  ✓
    L2 Technical Execution       █████████████████░░░ 85%  ✓
    L3 Cultural Context          ██████████████████░░ 90%  ✓
    L4 Critical Interpretation   ████████████████████ 100%  ✓
    L5 Philosophical Aesthetics  ██████████████████░░ 90%  ✓
```

This post is not a product announcement. It is a technical deep dive into what it took to build [VULCA](https://github.com/vulca-org/vulca-visual-control-sdk) — the bugs we hit, the architectural decisions we made, and the code that holds it together.

---

## 1. What is VULCA + The Local Stack

VULCA is an AI-native cultural art creation SDK. It generates, evaluates, decomposes, and evolves visual art across 13 cultural traditions. It runs locally (ComfyUI + Ollama) or in the cloud (Gemini).

Not another Midjourney wrapper or ComfyUI plugin — a standalone SDK for cultural art intelligence.

The project started as academic research. The [VULCA Framework](https://aclanthology.org/2025.findings-emnlp/) was published at EMNLP 2025 Findings, and [VULCA-Bench](https://arxiv.org/abs/2601.07986) provides 7,410 annotated samples with L1-L5 cultural scoring definitions. The SDK implements this research as a production tool.

### Architecture

```
┌─────────────────────────────────────────────┐
│                  vulca CLI                   │
├─────────────┬──────────┬────────────────────┤
│   create    │ evaluate │  layers / studio   │
├─────────────┴──────────┴────────────────────┤
│              Cultural Engine                 │
│   13 traditions × L1-L5 scoring rubrics     │
├──────────────────┬──────────────────────────┤
│  Image Providers │      VLM Providers       │
│  ┌────────────┐  │  ┌────────────────────┐  │
│  │  ComfyUI   │  │  │  Ollama (Gemma 4)  │  │
│  │  (local)   │  │  │  (local)           │  │
│  ├────────────┤  │  ├────────────────────┤  │
│  │  Gemini    │  │  │  Gemini            │  │
│  │  (cloud)   │  │  │  (cloud)           │  │
│  └────────────┘  │  └────────────────────┘  │
└──────────────────┴──────────────────────────┘
```

### Quickstart

```bash
pip install vulca

# Point at your local ComfyUI + Ollama
export VULCA_IMAGE_BASE_URL=http://localhost:8188
export VULCA_VLM_MODEL=ollama_chat/gemma4

# Generate
vulca create "Misty mountains after spring rain" -t chinese_xieyi --provider comfyui -o art.png

# Evaluate
vulca evaluate art.png -t chinese_xieyi --mode reference
```

### Provider Architecture: Pluggable, Not Locked In

VULCA does not depend on any single backend. Image providers are pluggable classes. ComfyUI is one provider. Gemini is another. You can add your own.

The key design insight: providers declare their capabilities as a frozen set. VULCA uses these capabilities to decide how to format prompts, whether to pass CJK text directly, and whether RGBA output is available.

```python
# ComfyUI: CLIP-based encoder, English-only, returns raw RGBA
class ComfyUIImageProvider:
    capabilities: frozenset[str] = frozenset({"raw_rgba"})
```

```python
# Gemini: LLM-based encoder, understands CJK natively, returns raw RGBA
class GeminiImageProvider:
    capabilities: frozenset[str] = frozenset({"raw_rgba", "multilingual_prompt"})
```

The `multilingual_prompt` capability is the difference between a 120-token structured prompt (Gemini can handle it) and a compressed 60-token flat prompt (CLIP will truncate anything beyond 77 tokens). More on this in section 5.

When you ask ComfyUI to generate an image, VULCA constructs a complete ComfyUI workflow as a JSON dict and submits it via the REST API. No ComfyUI nodes to install. No custom workflows to import. The entire workflow is built programmatically:

```python
workflow = {
    "prompt": {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": secrets.randbelow(2**63), "steps": 20, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": kwargs.get("checkpoint",
                         "sd_xl_base_1.0.safetensors")}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": full_prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative_prompt or "", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "vulca", "images": ["8", 0]}},
    }
}
```

That is from [`src/vulca/providers/comfyui.py` lines 42-62](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/src/vulca/providers/comfyui.py#L42). It constructs a standard SDXL pipeline: checkpoint loader, empty latent, two CLIP text encoders (positive + negative), KSampler, VAE decode, save. The workflow is submitted as a single POST to `/prompt`, and VULCA polls `/history/{prompt_id}` until the image is ready.

After the image comes back, VULCA validates it is actually a valid PNG before accepting it:

```python
if len(raw_bytes) < 1000 or raw_bytes[:4] != b'\x89PNG':
    raise ValueError(
        f"ComfyUI returned invalid image "
        f"({len(raw_bytes)} bytes, header={raw_bytes[:4]!r})"
    )
```

That validation was added in commit [`fdc0e45`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/fdc0e45) after we discovered that certain PyTorch MPS bugs cause ComfyUI to return 4KB files with valid PNG headers but all-zero pixel data.

---

## 2. L1-L5 Cultural Evaluation

Most AI art tools generate. VULCA evaluates.

The evaluation framework scores artwork across five dimensions, each measuring a different aspect of cultural and artistic quality:

| Dimension | What It Measures |
|-----------|-----------------|
| **L1** Visual Perception | Composition, color harmony, spatial arrangement |
| **L2** Technical Execution | Rendering quality, technique fidelity, craftsmanship |
| **L3** Cultural Context | Tradition-specific motifs, canonical conventions |
| **L4** Critical Interpretation | Cultural sensitivity, contextual framing |
| **L5** Philosophical Aesthetics | Artistic depth, emotional resonance, spiritual qualities |

These are not arbitrary categories. They come from the [VULCA-Bench paper](https://arxiv.org/abs/2601.07986), which defines L1-L5 across 7,410 annotated samples.

### 13 Traditions, Custom Weights

Each tradition is defined as a YAML file with its own L1-L5 weight distribution. Chinese freehand ink painting (xieyi) weights philosophical aesthetics (L5) at 30% and cultural context (L3) at 25%, because the tradition values spiritual resonance and canonical motifs above raw technical rendering. A brand design tradition would weight L2 (technical execution) much higher.

```yaml
# src/vulca/cultural/data/traditions/chinese_xieyi.yaml
name: chinese_xieyi
display_name:
  en: "Chinese Freehand Ink (Xieyi)"
  zh: "中国写意"

weights:
  L1: 0.10
  L2: 0.15
  L3: 0.25
  L4: 0.20
  L5: 0.30

terminology:
  - term: spirit resonance and vitality
    term_zh: "气韵生动"
    definition:
      en: "The first of Xie He's Six Principles of Chinese Painting..."
    category: aesthetics
    l_levels: [L4, L5]
```

The 13 supported traditions are: `chinese_xieyi`, `chinese_gongbi`, `japanese_traditional`, `western_academic`, `islamic_geometric`, `watercolor`, `african_traditional`, `south_asian`, `brand_design`, `photography`, `contemporary_art`, `ui_ux_design`, and `default`.

### Three Evaluation Modes

- **Strict** (judge): Conformance scoring. How well does the art meet the tradition's standards?
- **Reference** (mentor): Cultural guidance with professional terminology. Not a judge, a mentor.
- **Fusion**: Multi-tradition comparison. Pass comma-separated traditions and get cross-cultural analysis.

### The API: Three Lines to Score Any Image

```python
import vulca

result = await vulca.aevaluate(
    "artwork.png",
    tradition="chinese_xieyi",
    mode="reference",
)
print(result.score, result.l1, result.l2, result.l3, result.l4, result.l5)
```

The full `aevaluate()` signature from [`src/vulca/evaluate.py`](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/src/vulca/evaluate.py#L12):

```python
async def aevaluate(
    image: str | Path,
    *,
    intent: str = "",
    tradition: str = "",
    subject: str = "",
    skills: list[str] | None = None,
    api_key: str = "",
    mock: bool = False,
    mode: str = "strict",
    sparse: bool = False,
) -> EvalResult:
```

The `sparse` parameter is worth calling out. When `sparse=True`, VULCA runs a `BriefIndexer` that determines which L1-L5 dimensions are most relevant to the given intent. All five dimensions are still scored (consistency matters), but the `sparse_activation` metadata tells callers which dimensions were most salient. This is useful in pipeline mode where you want to focus review on the dimensions that matter for a specific prompt.

---

## 3. Deep Dive: Structured Layer Generation

VULCA does not generate images. It generates layers.

The pipeline works like this:

1. **Intent parsing** — user prompt is analyzed for tradition, subject, and composition intent
2. **VLM planning** — Gemma 4 (via Ollama) decomposes the prompt into a layer plan: background, mid-ground elements, foreground, calligraphy/text
3. **Per-layer generation** — each layer is generated as a separate image with transparent background
4. **Luminance keying** — non-background layers are keyed to remove canvas color, producing clean alpha
5. **Alpha composite** — layers are composited in order to produce the final artwork

![Layered exploded view](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/readme/layered_exploded.png)
*Layer decomposition: paper, distant mountains, forest, calligraphy, composite*

### Serial-First Style Anchoring

The first layer generates serially as a style anchor. Its raw RGB output becomes the visual reference (`style_ref`) for all subsequent layers, which generate in parallel. This is Defense 3 from v0.14 — without it, each layer would independently interpret "Chinese xieyi style" and you would get five different visual interpretations in the same artwork.

### The Prompt Builder

The core of layer generation is `build_anchored_layer_prompt()` in [`src/vulca/layers/layered_prompt.py`](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/src/vulca/layers/layered_prompt.py#L47). This function wraps the plan's regeneration prompt in four mandatory anchor blocks: canvas, content (with negative list), spatial, style.

```python
@dataclass(frozen=True)
class LayerPromptResult:
    """Prompt + negative prompt pair for a layer."""
    prompt: str
    negative_prompt: str


def build_anchored_layer_prompt(
    layer: LayerInfo,
    *,
    anchor: TraditionAnchor,
    sibling_roles: list[str],
    position: str = "",
    coverage: str = "",
    english_only: bool = False,
) -> str | LayerPromptResult:
```

The function has two code paths, controlled by `english_only`:

**When `english_only=False`** (Gemini path): Returns a structured multi-section string with `[CANVAS]`, `[CONTENT]`, `[SPATIAL]`, `[STYLE]`, and `[USER INTENT]` blocks. Gemini's LLM-based encoder can parse these sections and follow the instructions.

```python
blocks = [
    "[CANVAS]",
    f"The image MUST be drawn on {canvas_description}.",
    f"The background MUST be the pure canvas color {anchor.canvas_color_hex},",
    "with absolutely no other elements, textures, shading, or borders.",
    "",
    "[CONTENT — exclusivity]",
    "This image ONLY contains the element specified in USER INTENT.",
    f"Do NOT include any of: {others_text}.",
    "",
    "[SPATIAL]",
    f"MUST occupy {pos}, covering approximately {cov} of the canvas area.",
    "",
    "[STYLE]",
    style_keywords,
    "",
    "[USER INTENT]",
    user_intent,
]
```

**When `english_only=True`** (ComfyUI/SDXL path): Returns a `LayerPromptResult` with a flat, CLIP-friendly prompt under 70 tokens and a separate `negative_prompt`. This is the path that took the most engineering to get right. More on why in section 5.

```python
if english_only:
    parts = [user_intent, style_keywords, f"on {canvas_description}"]
    pos = position or ""
    if pos:
        parts.append(pos)
    prompt = ", ".join(p for p in parts if p)
    negative = ", ".join(others) if others else ""
    return LayerPromptResult(prompt=prompt, negative_prompt=negative)
```

### CJK-Aware Prompt Handling

VULCA accepts prompts in Chinese, Japanese, and Korean. When the target provider has the `multilingual_prompt` capability (Gemini), CJK text passes through natively. When the provider does not have that capability (ComfyUI/SDXL with CLIP), VULCA strips CJK characters and falls back to English equivalents:

```python
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")

def _strip_cjk_parenthetical(text: str) -> str:
    """Strip CJK parenthetical annotations, e.g. 'cooked silk (熟绢)' -> 'cooked silk'."""
    return _CJK_PAREN_RE.sub("", text).strip()
```

So `vulca create "水墨山水" -t chinese_xieyi --provider comfyui` works — VULCA translates the prompt for CLIP behind the scenes.

---

## 4. Deep Dive: Making SDXL Work Locally

This is where things got interesting. Two traps nearly derailed the local ComfyUI path.

### Trap 1: The ANCHOR Hallucination

Our structured layer prompts originally used section headers like `[CANVAS ANCHOR]`, `[STYLE ANCHOR]`, and `[CONTENT ANCHOR]`. The word "ANCHOR" was there to signal to the LLM that these were fixed constraints, not suggestions.

SDXL's CLIP encoder is not an LLM. It is a text encoder that treats every token as content. When it saw "ANCHOR", it interpreted it as a request to paint an anchor — the nautical kind.

The result: literal ship anchors appearing on rice paper backgrounds in Chinese ink wash paintings. Misty mountains with a ship anchor in the corner. Bamboo forests with an anchor hovering over them.

The fix was trivial once diagnosed. Rename the headers to `[CANVAS]`, `[STYLE]`, `[CONTENT]`, `[SPATIAL]`. No word that could be interpreted as visual content.

Commit: [`b168178`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/b168178) — `fix(layers): remove ANCHOR from prompt headers — SDXL paints literal anchors`

The lesson: CLIP-based models do not have a concept of "metadata" or "instructions" in a prompt. Every token is content. If your prompt engineering uses structured headers, every header word will influence the generated image.

### Trap 1b: The 77-Token CLIP Ceiling

Fixing the anchor hallucination revealed a second, subtler problem. Our structured prompt — even without "ANCHOR" — was 120+ tokens. CLIP truncates at 77 tokens. The actual subject description ("misty mountains after spring rain") was buried past the 77-token boundary and never reached the encoder.

Gallery images (simple prompts, ~30 tokens) worked perfectly. Layered generation (structured prompts, 120+ tokens) produced generic, unfocused results. The debugging was confusing because the same code path worked for simple creates but failed for layered creates.

The fix: the `english_only` branch in `build_anchored_layer_prompt()`. Instead of a structured multi-section prompt, VULCA builds a flat, subject-first prompt under 70 tokens:

```
misty mountains after spring rain, traditional brushwork, ink wash, on aged xuan paper
```

Plus a separate `negative_prompt` field (other layer roles to avoid). The subject comes first so it is guaranteed to be within CLIP's 77-token window.

Commit: [`74f9952`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/74f9952) — `fix(layers): CLIP-aware prompt compression for SDXL — flat <70 token prompt`

The `LayerPromptResult` dataclass was added specifically for this:

```python
@dataclass(frozen=True)
class LayerPromptResult:
    """Prompt + negative prompt pair for a layer."""
    prompt: str
    negative_prompt: str
```

The structured string (Gemini path) returns a single `str`. The CLIP path returns a `LayerPromptResult` with both positive and negative prompts separated. The caller checks `isinstance(result, LayerPromptResult)` to decide which ComfyUI workflow nodes to populate.

### Trap 2: PyTorch MPS — A Version Minefield

With prompt engineering fixed, we hit the hardware layer. SDXL generation via ComfyUI on Apple Silicon (MPS backend) with PyTorch 2.11.0 produces black (all-zero, ~4KB) or noise (~2MB random pixels) images.

Key observations that made this hard to diagnose:

- KSampler diffusion runs to completion — 20 steps, progress bars, no errors
- VAEDecode output is corrupt despite successful sampling
- `--force-fp32` does NOT fix it — this is a correctness bug, not a precision issue

Three compounding PyTorch MPS bugs cause the failure:

**Bug 1: SDPA Non-Contiguous Tensor Regression** ([pytorch/pytorch#163597](https://github.com/pytorch/pytorch/issues/163597))

Introduced in PyTorch 2.8.0. MPS SDPA kernels produce wildly incorrect results when given non-contiguous tensors. SDXL's cross-attention performs transpose operations that create non-contiguous views, feeding garbage embeddings into the U-Net. Error magnitude: ~34.0 vs normal ~0.000006.

**Bug 2: Conv2d Chunk Correctness Bug** ([pytorch/pytorch#169342](https://github.com/pytorch/pytorch/issues/169342))

Affects PyTorch 2.9.0+. The `chunk() -> conv()` pattern produces correct results only for the first batch element. Single-image generation (batch=1) is unaffected. Multi-image batch workflows will hit it.

**Bug 3: Metal Kernel Migration Regressions** ([pytorch/pytorch#155797](https://github.com/pytorch/pytorch/issues/155797))

PyTorch 2.10-2.11 introduced additional MPS regressions during internal operator migrations. Identical symptoms reported on M3 Ultra via [ComfyUI#10681](https://github.com/Comfy-Org/ComfyUI/issues/10681).

### Why VAEDecode Is the Failure Point

The VAE decoder is uniquely vulnerable:
- Uses Conv2d with large channel counts (hit by Bug 2)
- Uses GroupNorm with float16 inputs (NaN propagation)
- Single-pass decoder with no self-correction like iterative KSampler
- Intermediate values explode to 9.5e+25, GroupNorm cannot recover, output is all-zero or random

### The Version Matrix

| PyTorch Version | SDXL on MPS | Notes |
|---------|-------------|-------|
| 2.4.1 | Working | Last fully validated version |
| 2.5.x | Degraded | Memory +50%, speed -60% |
| 2.6.x | Partial | Some SDPA issues, `--force-fp32` can help |
| 2.7.x | Partial | Similar to 2.6 |
| 2.8.0 | Broken | SDPA non-contiguous bug introduced |
| **2.9.0** | **Working** | **Sweet spot**: pre-Metal migration, SDPA bug masked by ComfyUI's attention slicing |
| 2.10.0 | Broken | Black images on M3 Ultra |
| 2.11.0 | Broken | Black/noise on Apple Silicon |

### The Fix

```bash
# In ComfyUI venv
cd ~/dev/ComfyUI
./venv/bin/pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0
./venv/bin/python main.py --listen 0.0.0.0 --port 8188
```

Pin `torch==2.9.0`. That is the entire fix. We wrote a [complete Apple Silicon MPS + ComfyUI/SDXL Compatibility Guide](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/docs/apple-silicon-mps-comfyui-guide.md) that covers diagnosis, workarounds (CPU VAE, force-fp32), environment variables, and verification steps.

The guide is at [`docs/apple-silicon-mps-comfyui-guide.md`](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/docs/apple-silicon-mps-comfyui-guide.md) in the repo.

---

## 5. Inpainting and Layer Editing

Once you have layers, you can edit them individually without regenerating the entire artwork.

![Inpaint comparison](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/readme/inpaint_comparison.png)

```bash
# Redraw a specific layer with a new instruction
vulca layers redraw ./layers/ --layer sky -i "warm golden sunset"

# Region-based inpaint on the composite
vulca inpaint art.png --region "the sky" --instruction "stormy clouds"
```

The inpaint path uses the same provider architecture. ComfyUI receives an inpaint workflow with a mask, Gemini receives the image + mask + instruction as a multipart prompt. The same `capabilities` system determines prompt formatting.

---

## 6. What's Working, What's Next

### Current State (v0.15.1)

- All 13 traditions generating locally on Apple Silicon via ComfyUI + SDXL
- Full E2E pipeline validated: intent parsing, VLM planning, per-layer generation, keying, composite
- 8 E2E phase tests passing in 2.4 seconds (mock mode)
- CJK prompts working end-to-end with automatic CLIP compression
- PNG response validation catches corrupt MPS output
- Structured layer generation with serial-first style anchoring

### The Commit Trail

The local provider path was stabilized across these commits:

- [`b168178`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/b168178) — remove ANCHOR from prompt headers
- [`42e0e3d`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/42e0e3d) — skip keying for background layers
- [`fdc0e45`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/fdc0e45) — validate ComfyUI PNG response
- [`74f9952`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/74f9952) — CLIP-aware prompt compression
- [`e840496`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/e840496) — MPS compatibility guide
- [`485067e`](https://github.com/vulca-org/vulca-visual-control-sdk/commit/485067e) — v0.15.1 release

### Roadmap

- **Gemini cloud path**: Currently blocked on free-tier billing limits (image generation returns `limit: 0`). Text + VLM vision work. Once billing is enabled, Gemini becomes the zero-setup cloud alternative.
- **SAM3 text-prompted segmentation**: Replace luminance keying with SAM3 for cleaner layer extraction.
- **Web UI / Gradio demo**: A browser-based interface for non-CLI users.

---

## 7. Get Started

### 5-Minute Local Setup

```bash
# 1. Install VULCA
pip install vulca

# 2. Install ComfyUI (if you don't have it)
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
python -m venv venv
./venv/bin/pip install -r requirements.txt
# CRITICAL: pin PyTorch for Apple Silicon
./venv/bin/pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0

# 3. Download SDXL checkpoint
# Place sd_xl_base_1.0.safetensors in ComfyUI/models/checkpoints/

# 4. Start ComfyUI
./venv/bin/python main.py --listen 0.0.0.0 --port 8188

# 5. Install Ollama + Gemma 4 (for VLM evaluation)
brew install ollama
ollama pull gemma4
```

```bash
# 6. Generate and evaluate
export VULCA_IMAGE_BASE_URL=http://localhost:8188
export VULCA_VLM_MODEL=ollama_chat/gemma4

vulca create "Misty mountains after spring rain" \
  -t chinese_xieyi --provider comfyui -o art.png

vulca evaluate art.png -t chinese_xieyi --mode reference
```

### Python API

```python
import vulca

# Evaluate any image
result = await vulca.aevaluate(
    "artwork.png",
    tradition="chinese_xieyi",
    mode="reference",
)

# Access individual dimension scores
print(f"L1 Visual: {result.l1}")
print(f"L5 Philosophy: {result.l5}")
print(f"Overall: {result.score}")
```

### What VULCA Is

VULCA is an open-source SDK for AI-native cultural art creation. It brings cultural intelligence to AI art generation. 13 traditions, each with its own L1-L5 scoring rubric, terminology, and taboos.

It is built on peer-reviewed research (EMNLP 2025 Findings), tested against 7,410 annotated samples (VULCA-Bench), and runs entirely on your local machine if you want it to.

### What VULCA Is Not

- Not a ComfyUI plugin. ComfyUI is one of several image providers.
- Not a Midjourney alternative. VULCA does not host image generation — it orchestrates it.
- Not a wrapper around any single model. Swap ComfyUI for Gemini (or your own provider) with one config change.

### Links

- **GitHub**: [https://github.com/vulca-org/vulca-visual-control-sdk](https://github.com/vulca-org/vulca-visual-control-sdk)
- **PyPI**: [https://pypi.org/project/vulca/](https://pypi.org/project/vulca/)
- **MPS Guide**: [`docs/apple-silicon-mps-comfyui-guide.md`](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/docs/apple-silicon-mps-comfyui-guide.md)
- **Research**: [VULCA Framework (EMNLP 2025 Findings)](https://aclanthology.org/2025.findings-emnlp/) | [VULCA-Bench (arXiv)](https://arxiv.org/abs/2601.07986)

[![PyPI](https://img.shields.io/pypi/v/vulca.svg)](https://pypi.org/project/vulca/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/vulca/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/LICENSE)

If this resonates, [star us on GitHub](https://github.com/vulca-org/vulca-visual-control-sdk). Try it, break it, tell us what failed — [issues welcome](https://github.com/vulca-org/vulca-visual-control-sdk/issues).

If you use VULCA in research, please cite:

```bibtex
@inproceedings{vulca2025,
  title={VULCA: A Framework for Cultural Art Evaluation},
  booktitle={Findings of the Association for Computational Linguistics: EMNLP 2025},
  year={2025}
}
```

![Tradition grid](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/assets/demo/v3/readme/tradition_grid.png)
*13 traditions. One SDK. Your machine.*
