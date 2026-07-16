# dev.to article · English · long-form technical narrative

**Title**: Same `gpt-image-2` API. Two totally different results. The difference is 3 markdown files.

**Tags**: #ai #python #opensource #showdev

---

## TL;DR

We took a Glasgow street photo and tried to add Northern Song gongbi (工笔重彩) painterly elements — red lanterns, Chinese signage, muted-gold trim — without dissolving the photo's existing pixels.

Two paths, same `gpt-image-2`:

1. **Bare API + naive prompt** ("repaint in gongbi style"): the entire image gets washed into a unified painterly filter. Photo gone.
2. **Vulca-mediated structured prompt**: photo anchors preserved, gongbi elements painted INTO the scene as discrete additions.

The difference between path 1 and path 2 is **three markdown files** that an agent produces by walking the brainstorm → spec → plan triad.

This post walks through what that "structured prompt composition" actually is, the silent `input_fidelity` parameter drift we caught between `design.md` and the live `gpt-image-2` GA endpoint (and the `v0.17.12` fix shipped today), and how the same triad evaluates cross-cultural AI generation honestly (including an L2 hard-fail at `0.65` that we surface plus a `user-override-accept` we ALSO record).

> Repo: <https://github.com/vulca-org/vulca-visual-control-sdk>
> Install: `pip install "vulca[mcp]==0.17.14"`

![Same gpt-image-2 API. Two totally different results. The difference is 3 markdown files.](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide1.png)

---

## The setup

Vulca is an MCP-native toolkit for cultural-art generation. The agent owns the brain (proposal → design → plan); the SDK owns the hands and eyes (prompt composition, layer decomposition, L1-L5 scoring). We were dogfooding our own triad on a real-world brief: *"add Chinese gongbi cultural elements to a Scottish street photo, but preserve every photographic anchor"*.

User-supplied source: a Glasgow street with red brick Victorian buildings, a Gothic cathedral spire, Stagecoach buses, a woman in a purple jacket walking — your standard urban photograph.

Target: visible Chinese street culture (lanterns, calligraphy signage, muted-gold trim) painted INTO the scene at gongbi technical fidelity. *Not* a Photoshop filter; closer to a Wang Ximeng (王希孟, c.1096–1119) *Thousand Li of Rivers and Mountains* (《千里江山图》, Northern Song, 1113) palette discipline applied as overlay.

## Path 1 — naive bare API

```bash
curl https://api.openai.com/v1/images/edits \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F "model=gpt-image-2" \
  -F "prompt=Add Chinese gongbi painterly elements to this Glasgow street photo" \
  -F "image=@source.png"
```

Result (slide 1, left): the model produced a unified-wash painterly filter applied to the entire image. Red brick became flat color, building edges softened, photographic detail lost. The output reads as a *style transfer*, not an *additive overlay*. The lanterns are there, but so is everything else, all in the same painterly register.

This is the failure mode you get when "gongbi" is interpreted globally rather than as a discipline applied to specific painted-in elements.

## Path 2 — Vulca-mediated structured prompt

Same `gpt-image-2`. Same source photo. Same intent. The difference is what the prompt looks like by the time it reaches OpenAI.

Vulca's `compose_prompt_from_design()` is a small, deliberately-boring helper: it reads a resolved `design.md` artifact, parses the YAML frontmatter + the `## C. Prompt composition` block, and **concatenates three pieces** in order:

1. `C.base_prompt` — the user-authored prose that names MUST-PRESERVE anchors (Gothic spire, red brick wall, woman in purple jacket, bus, traffic light, sky, distant pedestrians, right-side building silhouette) and ADD-as-gongbi elements (lanterns, calligraphy signage, muted-gold trim, 千里江山图 palette echoes), plus the `style_treatment: additive` discipline clause.
2. `C.tradition_tokens` — terminology copied from the `chinese_gongbi` cultural registry: *meticulous heavy-color painting (工笔重彩) · triple alum nine washes (三矾九染) · plain line drawing (白描) · outline and fill color (勾勒填彩) · boneless technique (没骨法) · court academy painting (院体画)*.
3. `C.color_constraint_tokens` — cinnabar red (朱砂红) · muted gold (泥金) · stone blue (石青) · malachite green (石绿) — and an explicit *forbid: neon saturation, CNY plastic red, cartoon rainbow*.

That's it. The "value" isn't a clever compiler; it's that **the prose, the terminology, and the color discipline are all archived in `design.md`** — version-controlled, reviewable, and reproducible from disk. A new agent two weeks later can call `compose_prompt_from_design("design.md")` and get the same prompt string back. That replayability is what bare-API workflows lose.

`design.md` also asks for `input_fidelity=high` on the OpenAI call. **What actually happened** is documented in `plan.md` Notes `[param-drift]`: `gpt-image-2` GA shipped without `input_fidelity` support and **rejected the parameter outright**. The pre-`v0.17.12` `openai_provider` was sending it unconditionally and would have failed; we caught the drift mid-session, gated the param by per-model capability (issue #12, fixed in `v0.17.12` shipped to PyPI an hour before this post), and re-ran iter 0 **without** `input_fidelity`. The image still succeeded — `style_treatment: additive` plus the prompt-level "do NOT apply unified filter" clause carried preservation discipline through prose alone. The provenance trail is in `plan.md`.

Result (slide 1, right): the lanterns are painted, the calligraphy signage is gongbi 白描 (plain line drawing) on cinnabar panels — but the brick wall, spire, woman in purple jacket, and bus are recognizably the source photograph. The painterly elements read as *intent* (画意), not *filter*.

![Glasgow street + Northern Song gongbi additive overlay — full Vulca-mediated result, openai/gpt-image-2 seed 7](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide2.png)

## Decompose: 1 image → 10 editable semantic layers

```python
mcp_vulca.layers_split(
    image_path="iters/7/gen_bfbbacd2.png",
    output_dir="decompose/iter1",
    mode="orchestrated",
    plan='{"domain":"photograph","entities":[...]}'
)
```

Pipeline: YOLO + Grounding DINO + SAM + SegFormer face-parsing. Returns a manifest with per-entity status, alpha-sparse RGBA layers, and a `residual` layer.

iter1 entities:

All numbers below come from `manifest.json` `detection_report.per_entity[].pct_after_resolve` (the deduplicated area share that resolves overlap to a single owning entity):

| Layer | pct_after_resolve | sam_score | Detector |
|---|---|---|---|
| person | 5.65% | 1.01 | dino (`woman`) |
| lanterns | 8.05% | 0.61 | dino (`row`) |
| sign_top | 1.17% | 0.99 | dino (`red panel calligraphy plaque`) |
| sign_right | 0.47% | 0.97 | dino (`tall vertical golden plaque`) |
| spire | 2.08% | 0.96 | dino (`gothic cathedral spire pointed roof`) |
| bus | 3.59% | 0.98 | dino (`blue double decker bus`) |
| left_buildings | 24.45% | 0.98 | dino (`red brick row`) |
| right_buildings | 7.51% | 0.93 | dino (`cathedral ornate stone facade`) |
| sky | 15.50% | 0.98 | dino (`blue sky upper region`) |
| **9 entities sum** | **68.47%** | | |
| **residual (deduped)** | **31.53%** | | leftover (shadows, awning, road, traffic light) |

`success_rate: 1.0`, no suspect detections, no missed entities. (Note: the `manifest.json` also stores `layers[9].area_pct = 40.69%` for the residual layer using *overlap-permissive* accounting — both numbers are exposed; the deduped 31.53% is the canonical "share of canvas not assigned to any named entity".)

The lanterns layer's `sam_score` is conspicuously low (`0.61` vs the others' 0.93–1.01). That's not a bug — it's the pipeline doing something honest: SAM was given **one bbox** for "row of red paper lanterns" and asked to mask the whole row as a single object. With six dispersed lanterns + tassels + occluding awning ropes, SAM returns a fragmented streak rather than six clean silhouettes. Multi-instance entity detection (per-lantern bbox + NMS-multi-output) is a `v0.18` backlog item; today's pipeline is `1 entity = 1 bbox = 1 mask`. **Slide 3's lanterns thumbnail looks "noisy" because that's the real shape of the mask.**

![1 image → 10 editable semantic layers via YOLO + Grounding DINO + SAM + SegFormer](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide3.png)

A practical workflow note: DINO open-vocabulary detection has a "phrase contamination" failure mode where one entity's label tokens bleed into another entity's matched_phrase. If you ask for both "Chinese calligraphy sign on red panel" and "large Chinese calligraphy signage" in the same plan, DINO may union the bbox into a single region. The defense is: *give each entity a phrase-distinct label*. We renamed `sign_top` to "red panel calligraphy plaque" and `sign_right` to "tall vertical golden plaque" — both detect cleanly.

## Redraw: same layer, two paths

```python
mcp_vulca.layers_redraw(
    artwork_dir="decompose/iter1/",
    layer="lanterns",
    instruction="朱砂 cinnabar saturation +15%, 三矾九染 depth richer, "
                "preserve lantern shapes and tassel positions exactly, "
                "keep gongbi outline-and-fill discipline, no global filter",
    provider="openai",
    tradition="chinese_gongbi",
)
# As of v0.18.0 this writes to `lanterns_redrawn.png` by default
# (non-destructive); the original `lanterns.png` is preserved. Pass
# `in_place=True` to restore the v0.17.x overwrite behavior.
```

`layers_redraw` sends the alpha-sparse layer through `gpt-image-2`'s edit endpoint with the cultural tradition's prompt-composition layer applied. The slide-4-right artifact you see — a four-lantern + spire reinterpretation in full 工笔重彩 with deeper cinnabar saturation and gongbi-canonical line discipline (outline-and-fill, *勾勒填彩*) — was authored via a fresh `generate_image` call seeded by this same gongbi prompt scaffold, **not** the literal `layers_redraw` output above. The native `layers_redraw` path on this row-of-six-lanterns alpha gives a stylistically incoherent result because cream-flat reference loses per-instance geometry (see [`decompose/v0_17_14_native/NOTES.md`](../decompose/v0_17_14_native/NOTES.md) for the v0.17.14 end-to-end MCP run and the v0.18 backlog item). The `layers_redraw` verb still works as documented; the carousel's slide-4-right just exercises the related `generate_image` path for visual coherence. The model approximates the *visual register* of gongbi — but as the L1-L5 scorecard below makes explicit, **single-pass diffusion can't simulate the multi-pass alum-wash physics** of true 三矾九染. The redraw looks gongbi-flavored; it isn't gongbi-correct. Both can be true.

The agent now has two paths for the lanterns layer:

- alpha-isolated original (preservation, composite-friendly)
- gongbi-reinterpreted output (concept exploration, hero asset)

Vulca exposes both paths via MCP. The choosing happens in the agent, not in a static pipeline.

![Same layer, two paths — alpha-isolated lantern silhouettes vs gpt-image-2 + gongbi prompt reinterpretation](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide4.png)

## Honest scoring — `mode="rubric_only"` + agent self-grade

`v0.17.12` shipped a new evaluate mode this morning. Important: it does **not** score the image. It returns the rubric so the **agent** can score:

```python
result = mcp_vulca.evaluate_artwork(
    image_path=".../gen_bfbbacd2.png",
    tradition="chinese_gongbi",
    mode="rubric_only",
)
# result.score == None
# result.rubric == { weights, terminology, taboos, tradition_layers }
# result.score_schema == { L1: null, L2: null, ..., L5: null }
```

`rubric_only` returns the rubric template (L1-L5 weights from `chinese_gongbi.yaml`, six terminology entries, taboos, tradition_layers) and an empty `score_schema`. **No VLM call.** The agent — which already has vision — applies the rubric to the image and fills the scores itself. The split is deliberate: consumer agents already see the pixels; an extra VLM round-trip would be redundant cost. Vulca supplies the rubric; the agent self-grades.

Our agent self-grade for the iter 0 image, recorded verbatim in `plan.md` `## Results`:

| Dim | Weight | Score | Rationale |
|---|---|---|---|
| L1 Visual | 0.15 | 0.78 | Gongbi additions read as deliberate; line discipline visible |
| **L2 Technical** | **0.30** | **0.65 ✗** | 三矾九染 depth shallow; 石青/石绿 under-represented |
| L3 Cultural | 0.25 | 0.72 | 千里江山图 palette intent honored; 朱砂/泥金 read true |
| L4 Critical | 0.15 | 0.75 | Additive treatment honored; photo anchors preserved |
| L5 Philosophical | 0.15 | 0.65 | Cross-cultural intent legible; literati-naming convention borrowed |
| **Weighted** | | **0.702** | |

L2 hard-fails 0.70 because *triple-alum-nine-washes* (三矾九染) is a **multi-pass physical technique** — alum fixative applied between successive translucent washes to build depth and luminosity. A single forward pass through any diffusion model — `gpt-image-2`, `stable-diffusion-xl`, anything — cannot simulate alum-wash layering. **This is a category-level ceiling, not a Vulca regression.** The model approximates the *visual register* of depth; a trained gongbi reviewer will catch the absence of true alum-wash physics instantly.

The strict rubric verdict was `reject`. The maintainer (the human in the loop) decided to **accept for showcase use anyway** — and `plan.md` records BOTH judgments:

- `verdict: reject ✗ → user-override-accept` (the table cell)
- the override reason in the Notes block: *"L2 hard-fail: 三矾九染 depth shallow; 石青/石绿 under-represented. User accepted for showcase use."*

This is the **dual-judgment provenance** pattern. The strict rubric retains technical honesty; the human retains veto. Both are archived. A skeptic running the same pipeline gets the same rubric verdict; a different maintainer might decide to *not* override. The artifact captures both.

`design.md`'s `rollback_trigger` is a separate concern: it fires only when *all 3 main seeds score L1<0.6 OR L3<0.6*. Neither condition was met (L1=0.78, L3=0.72), so the L2 hard-fail surfaces as **honest disclosure**, not as a rollback signal. Different gates for different purposes.

![plan.md verdict trail — L1 0.78, L2 0.65 (hard-fail), L3 0.72, L4 0.75, L5 0.65, weighted 0.702 → strict reject → user-override-accept; both judgments archived](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide5.png)

## The triad — three markdown files

```
docs/visual-specs/2026-04-23-scottish-chinese-fusion/
├── proposal.md              ← /visual-brainstorm output (8K)
├── design.md                ← /visual-spec output (10K)
├── plan.md                  ← /visual-plan output (11K)
├── source.png               ← user-supplied Glasgow photo
├── iters/
│   ├── _baseline_bare/
│   │   └── bare_gpt2_edit.png       ← naive API control
│   └── 7/
│       └── gen_bfbbacd2.png         ← Vulca-mediated
├── decompose/
│   ├── lanterns_before.png          ← alpha-iso (slide 4 left)
│   ├── lanterns_after.png           ← gongbi reinterp (slide 4 right)
│   └── iter1/                       ← 9 entities + residual
└── carousel/                        ← this 6-slide deck
```

![The whole project, in 3 markdown files: proposal.md / design.md / plan.md + a directory of artifacts. Pixels reproducible from markdown. The markdown is the product.](https://raw.githubusercontent.com/vulca-org/vulca-visual-control-sdk/master/docs/visual-specs/2026-04-23-scottish-chinese-fusion/carousel/slide6.png)

Three markdown files lock the entire decision trail:

- `proposal.md` — the user's intent in human terms. Style treatment, anchor list, budget, deadline.
- `design.md` — the technical translation. Provider, model, input_fidelity, prompt composition, L1-L5 weights & thresholds, spike plan, cost budget.
- `plan.md` — the execution flow. Phase order, batch size, evaluation gates, fail-fast rules.

Each file is produced by a `/visual-*` skill (brainstorm / spec / plan), each gated by a finalize handshake (`finalize` / `done` / `ready` / `lock it` / `approve`). The agent doesn't free-form image-generate; it walks the triad.

This is what "agent-mediated prompting" actually means in code. Not magic. A markdown contract.

## Try it

```bash
pip install "vulca[mcp]==0.17.14"
```

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "vulca": {
      "command": "vulca-mcp"
    }
  }
}
```

Then in your Claude Code session, type `/visual-brainstorm` to start a fresh visual project, or `/decompose <image>` to break an existing image into editable layers. The full 22-tool MCP surface is documented in `docs/`.

GitHub: <https://github.com/vulca-org/vulca-visual-control-sdk>

## Closing note

The two images at the top of this post differ by three markdown files. They're not magic; they're version-controllable, reviewable, replayable contracts. If your AI-art workflow today is "type a prompt, hope, retry" — try the markdown-trio approach once. The first time you get the same image back from a fresh agent two weeks later because the markdown is still there, you'll see why.

— shipped today as `vulca==0.17.14`. The v0.17.14 patches make the
`layers_redraw` + `layers_paste_back` *mechanism* fully native: the
`background_strategy="cream"` flag stops the alpha-sparse hallucination
that pre-v0.17.14 tainted redraw of sparse layers, `preserve_alpha=True`
re-applies the source layer's alpha, and `layers_paste_back` is a new
glue verb for compositing an edited layer back into a foreign source
image. **Visual parity** with the slide-4-right artifact specifically is
a different goal: that artifact was authored via `generate_image` with a
gongbi text prompt, not via `layers_redraw` on the lanterns layer alone.
The v0.17.14 patch closes the *out-of-band Python* gap for the canonical
edit-and-paste-back flow; per-instance multi-lantern redraw with full
visual parity remains a v0.18 backlog item. Reproducible MCP-only
validation of the mechanism is archived in
[`decompose/v0_17_14_native/NOTES.md`](../decompose/v0_17_14_native/NOTES.md).
