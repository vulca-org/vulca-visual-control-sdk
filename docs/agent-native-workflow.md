# The Agent-Native Workflow

## Why agent-native?

Traditional image SDKs embed an LLM or a single monolithic model and expose a narrow "describe this" or "segment that" surface. The model is a black box, the prompt is hidden behind an API, and steering is limited to whatever knobs the vendor chose to expose.

Vulca takes the opposite position. The agent — Claude Code, a remote Claude via API, or any other capable VLM-driven loop — is the brain. It reads pixels through its own vision, decides what entities exist in an image, and writes a `plan.json`. Vulca is hands and eyes: deterministic pixel math that stitches YOLO, Grounding DINO, SAM, and SegFormer into reproducible layer masks with a quality-audited manifest. No LLM call happens inside the pipeline.

The trade: you pay for one extra agent round trip (API spend, or a local VLM pass) in exchange for a fully inspectable plan, per-entity prompt steering, and the ability to rescue failures by editing JSON instead of fine-tuning weights.

## The contract

**Agent responsibilities.** Read the source image. Enumerate entities you see. For each entity, pick a detector (`yolo`, `dino`, or `sam_bbox`), write a short grounding `label`, assign a `semantic_path`, and — when occlusion or style defeats DINO — add a `bbox_hint_pct` in normalized `[x0, y0, x1, y1]`. After the pipeline runs, read `manifest.json`, check residual area and `quality_flags`, and iterate.

**SDK responsibilities.** Run the detectors. Resolve overlaps hierarchically by `semantic_path` and `order`. Emit a residual layer so "unclaimed" pixels are honest, not hidden. Record per-layer `area_pct`, `bbox`, and flags (`area_ballooned`, `face_parse_skipped`, etc.) that tell the agent when a mask looks wrong.

**plan.json schema** (the fields that matter):

```json
{
  "slug": "your-slug",
  "domain": "portrait_photograph",
  "device": "mps",
  "threshold_hint": 0.2,
  "expand_face_parts": true,
  "entities": [
    {
      "name": "bieber",
      "label": "man with shaved head in pink hoodie singing frontal view",
      "semantic_path": "subject.person[0]",
      "detector": "sam_bbox",
      "bbox_hint_pct": [0.15, 0.05, 0.90, 1.0],
      "order": 0
    }
  ]
}
```

**manifest.json contract.** Every layer reports `area_pct`, `bbox`, `detector`, and `quality_flags`. A `residual` layer captures pixels no entity claimed. If residual area exceeds ~20%, the agent missed something. If a subject has `area_ballooned`, its bbox was too loose.

## Concrete proof: Post #1 Bieber Coachella

Three source photos (baby, teen, adult) run through one pipeline produced 485 layers and 47 showcase images. The interesting moment was the baby photo: SegFormer face parsing returned 6 face parts — the face was small, dark, and blurred by stage lighting.

The rescue was agent-side, not SDK-side. The agent cropped the face region, upscaled 2x, and bumped brightness +20% before feeding the result back through the pipeline with a face-only plan:

```python
from PIL import Image, ImageEnhance
img = Image.open("baby.png")
face = img.crop((0, 180, img.width, 780))
face = face.resize((face.width * 2, face.height * 2))
face = ImageEnhance.Brightness(face).enhance(1.2)
face.save("baby-faceonly.png")
```

The companion plan (`assets/showcase/plans/bieber-baby-faceonly.json`) drops the crowd entity and focuses SegFormer on a clean close-up:

```json
{
  "slug": "bieber-baby-faceonly",
  "expand_face_parts": true,
  "entities": [
    {"name": "bg", "label": "dark concert crowd background", "detector": "dino", "threshold": 0.15},
    {"name": "bieber", "label": "man with shaved head in pink hoodie singing frontal view",
     "detector": "sam_bbox", "bbox_hint_pct": [0.15, 0.05, 0.90, 1.0]},
    {"name": "microphone", "label": "black handheld microphone at mouth",
     "detector": "dino", "threshold": 0.2}
  ]
}
```

SegFormer went from 6 face parts to 10 — eyes, hair, and ears appeared. Zero SDK code changed.

## Concrete proof: Post #2 Trump

The Butler 2024 Evan Vucci photo is 387×258 pixels with four overlapping people plus flag, sky, and striped stage banner — six subjects competing in a tiny frame. A single `sam_bbox` per person returned headless torsos: SAM, given one bbox enclosing head-plus-body, returns only the most-confident connected blob, which on a dark suit against a darker background is always the suit.

The rescue: declare two entities per occluded person — one tight bbox around the head, one around the body — then composite after the run:

```json
{
  "name": "agent_left_head",
  "label": "blonde hair and face of agent",
  "detector": "sam_bbox",
  "bbox_hint_pct": [0.22, 0.38, 0.32, 0.52],
  "order": 5
},
{
  "name": "agent_left_body",
  "label": "dark suit body of agent crouching",
  "detector": "sam_bbox",
  "bbox_hint_pct": [0.18, 0.50, 0.44, 0.88],
  "order": 4
}
```

Post-run compose, three lines:

```python
h = Image.open("agent_left_head.png").convert("RGBA")
b = Image.open("agent_left_body.png").convert("RGBA")
Image.alpha_composite(b, h).save("agent_left.png")
```

Applied to two occluded agents in the Trump photo after two failed single-bbox iterations. No SDK code change.

## Concrete proof: C1 from-zero plan authoring

C1 was a five-image proof: the agent authored plans from scratch by looking at each image, and residual coverage was compared against existing baseline plans.

| Image | Baseline residual | Agent residual | Iters | Verdict |
|---|---|---|---|---|
| american-gothic | 21.45% | 5.8% | 1 | Win — added sky / trees / barn / greenhouse |
| the-scream | 35.97% | 8.7% | 3 | Win — sam_bbox rescued expressionist faces |
| trump-mugshot | 2.14% | 2.1% | 1 | Win — matched + added seal and tie |
| mona-lisa | 41.80% | 79.82% | 1 | Loss — agent missed the chair_parapet |
| starry-night | 2.31% | 14.6% | 3 | Loss — over-decomposition narrowed DINO bboxes |

The `american-gothic` plan (`assets/showcase/plans/american-gothic.json`) enumerates 8 entities — sky, trees, red barn, greenhouse, farmhouse, woman, man, pitchfork — all with DINO labels and explicit `order` on the two people. That breakdown cut residual from 21.45% to 5.8% in a single iteration.

`the-scream` needed three iterations. Iter 1 with naive DINO labels put both figures in the wrong place and a "distant shore" label ate 94% of the canvas. Iter 2 switched to `sam_bbox` with tight hints for the screaming figure and the two background silhouettes. Iter 3 found the z-ordering bug: `foreground.bridge_railing` at 41.7% area was eroding into the screaming figure. The fix was promotion — move the hero to `foreground.person[0]` with `order: 10`:

```json
{
  "name": "screaming_figure",
  "semantic_path": "foreground.person[0]",
  "detector": "sam_bbox",
  "bbox_hint_pct": [0.32, 0.38, 0.58, 0.95],
  "order": 10
}
```

The two losses are more instructive than the wins:

- **mona-lisa** — the agent didn't notice the visible chair / parapet behind Mona Lisa. Post-run residual of 79.82% was the signal to look again, but this was a one-shot run.
- **starry-night** — baseline residual was already 2.31%. Splitting "sky" into sky + moon + stars made DINO return a tighter bbox for each, leaving gaps. Coverage dropped to 14.6%.

Three lessons:

1. When baseline residual is already under 5%, don't over-split.
2. DINO fails on stylized subjects (expressionist faces, painted figures). Switch to `sam_bbox` with a hint.
3. Z-ordering via `semantic_path` and `order` matters more than people expect. Promote heroes to `foreground.person[N]` with `order: 10`.

## Failure modes and rescue patterns

| Symptom | Cause | Fix |
|---|---|---|
| DINO label bbox too tight | Granular label collided with a neighbor entity | Simplify the label, or switch to `sam_bbox` with a hint |
| SAM returns headless torso | Single dominant-blob bias on occluded subject | Head + body split, compose with `alpha_composite` |
| Face parts sparse or stubby | Small face, low contrast, or dark lighting | Agent-side crop + 2x upscale + +20% brightness |
| Hero subject eroded | Overlapping foreground has higher effective z | Promote to `foreground.person[N]` with `order: 10` |
| Entity missed entirely | Agent didn't see it during plan authoring | Check residual > 20% and do a visual diff pass |

## Try it yourself (30 seconds)

```bash
pip install vulca
```

Drop your image into `assets/showcase/originals/your-slug.png` and write a minimal plan:

```bash
cat > assets/showcase/plans/your-slug.json <<'EOF'
{
  "slug": "your-slug",
  "domain": "photograph",
  "device": "mps",
  "threshold_hint": 0.2,
  "expand_face_parts": true,
  "entities": [
    {"name": "background", "label": "blurred stage lights",
     "semantic_path": "background", "detector": "dino", "threshold": 0.2},
    {"name": "subject", "label": "standing person facing camera",
     "semantic_path": "subject.person[0]", "detector": "yolo", "order": 0}
  ]
}
EOF

python3 scripts/claude_orchestrated_pipeline.py your-slug
```

Inspect `assets/showcase/layers_v2/your-slug/manifest.json`. Residual > 20% means you missed an entity. A `quality_flag` of `area_ballooned` or `face_parse_skipped` means the plan needs a tighter `bbox_hint_pct` or a preprocessing pass.

That manifest is the contract. The agent reads it, re-authors the plan, and runs again. The SDK never guesses.

## Links

- Repo: https://github.com/vulca-org/vulca-visual-control-sdk
- Social showcase: Post #1 (Bieber Coachella) and Post #2 (Trump Butler) linked from the README
- Pipeline entry point: `scripts/claude_orchestrated_pipeline.py`
