# Changelog

## v0.24.1 (2026-09-05)

First published release of the 0.24 line. Adds the canonical `vulca.capability`
contract layer that the vulca-platform native DSH runtime consumes as its
Python sidecar. Versions 0.24.0 and 0.24.1 were bumped on the development
branch in August 2026 without a PyPI release; this release is byte-identical
to the wheel vulca-platform has vendored since 2026-08-14.

### Added

- `vulca.capability`: exact-version capability contracts (`CapabilityManifest`,
  `CapabilityInvocation`, `CapabilityResult`, `CapabilityRegistry`,
  `SideEffectState`, `CapabilityStatus`, `CapabilityArtifact`), envelope and
  result-integrity validation, and a `builtin_registry` exposing the campaign
  static-creative production cells `vulca.image.generate`, `vulca.image.edit`,
  `vulca.image.evaluate`, `vulca.image.adapt_static`,
  `vulca.image.compose_static` and `vulca.image.validate_static`, all at
  `1.0.0`. The core contract types are re-exported from the package root.
- `vulca.providers.price_schedule`: frozen OpenAI image price schedule
  `openai.image.pricing@2026-08-14` with `estimate_openai_image_cost` for
  reservation ceilings, re-exported from `vulca.providers`.
- OpenAI provider: `gpt-image-2-2026-04-21` model binding, configurable
  `timeout` and `max_retries`, and explicit rejection of unsupported image
  formats.
- CI: capability release gate (`mypy src/vulca/capability`, the
  contract/wheel/builtin/static test files) and `pip check`; the build front
  end and back end are pinned to `build==1.4.3` and `hatchling==1.31.0` so the
  wheel is reproducible.

### Fixes

- Preserved the unreadable-crop error contract in `vulca.inpaint` and the
  studio inpaint phase.
- Hardened capability contract validation, result integrity and envelope edge
  cases; locked the exact capability dataclass contracts in tests.

### Docs

- Added the 2026-08-11 accountable creative organization runtime design and
  plan series, marked historical: Job Runtime ownership moved to the
  vulca-platform native DSH kernel on 2026-08-14, and the capability contracts
  (plan 01) remain canonical.

### Verification

- `python -m mypy src/vulca/capability`: no issues found in 6 source files.
- Capability release gate (`tests/test_capability_contract.py`,
  `tests/test_capability_builtin.py`, `tests/test_capability_static.py`):
  195 passed.
- `tests/test_capability_wheel.py` (two `--no-isolation` builds must hash
  identically): passed.
- Wheel built from this tree with `hatchling==1.31.0` / `build==1.4.3` has
  SHA-256 `7304658e4459a1a6d9c582113a4b7c0b181883e3a9bd0871da07ca2ce3536f9d`,
  identical to `wenxin-backend/wheelhouse/vulca-0.24.1-py3-none-any.whl` in
  vulca-platform.
- `twine check` on wheel and sdist: passed.

## v0.23.1 (2026-05-11)

Patch release for the NB2/Gemini masked-edit adapter.

### Fixes

- Rendered RGBA edit masks as visible black/white coordinate masks before
  sending them to Gemini/NB2 image-edit calls, while preserving the public
  `inpaint_with_mask` API contract.
- Tightened the Gemini adapter prompt so the visible mask is treated as edit
  guidance, not output content.

### Verification

- Focused redraw/provider suite: 143 passed, 5 warnings.
- `ruff check src/vulca/providers/gemini.py tests/test_gemini_image_size.py`:
  passed.
- `git diff --check`: passed.

## v0.23.0 (2026-05-01)

First public PyPI release after v0.19.0. This release bundles the v0.20-v0.22
redraw hardening work, visual workflow skills, remote MCP profiles, platform
distribution docs, cultural-term benchmark tooling, and hosted provider SDK
aliases.

### Highlights

- Added `/visual-discovery`, `/visual-brainstorm`, `/visual-spec`,
  `/visual-plan`, and `/evaluate` skill surfaces for agent-native visual
  workflows.
- Added remote-safe MCP profile support via `vulca-mcp-remote` for hosted
  clients such as ChatGPT-style remote MCP integrations.
- Added target-aware redraw hardening: source-context edit mattes, generated
  evidence gating, local quality gates, route/geometry advisory fields, and
  target mask refinement helpers.
- Added cultural-term efficacy benchmark tooling, including real-provider
  opt-in and signal-strengthening checks.
- Added provider SDK image aliases:
  `gemini-tools` / `nb2-tools` for Google GenAI tool-backed image calls, and
  `openai-responses` for the OpenAI Responses API image generation tool.
- Added `vulca[providers]` optional dependency group for hosted provider SDKs.
- Refreshed README install pins from `0.17.11` to `0.23.0`.

### Compatibility

- Existing `vulca[mcp]` installs continue to work.
- Hosted provider SDKs remain optional; install `vulca[providers]` only when
  using Gemini/OpenAI hosted backends directly.
- `layers_redraw` keeps backward-compatible defaults while surfacing new route,
  model, quality, and advisory controls for advanced callers.

## v0.21.0 workstream (bundled into v0.23.0 — redraw recontract)

v0.20.1 fixed the hidden model/quality plumbing bug, but dogfood still
showed a deeper design flaw: sparse layers were being edited as
full-canvas images, then post-cropped back to the original alpha. For tiny
or fragmented subjects, that loses the visual evidence the model needs.

### Fix

- Added explicit provider edit capability routing so `gpt-image-2` no
  longer relies on maskless `/v1/images/edits`.
- Replaced full-canvas sparse redraw with padded bbox crop redraw for
  single sparse subjects and bounded per-component redraw for fragmented
  sparse subjects.
- Added a gpt-image-2-safe `route="img2img"` shim that sends a full-canvas
  all-edit mask instead of a maskless edit request.
- Added local quality gates that warn on alpha expansion and large white
  block failures without hard-failing v0.21 outputs.
- `layers_redraw` MCP responses now include route/geometry/quality
  advisory fields such as `redraw_route`, `route_chosen`, `area_pct`,
  `geometry_redraw_route`, `bbox_fill`, `component_count`, and
  `quality_gate_passed`.

### Verification

- Local redraw contract tests cover provider capabilities, wire-level
  model/quality params, gpt-image-2 masked-edit behavior, crop/per-instance
  routing, quality gates, and MCP advisory output.
- The real-provider gate now includes a skip-by-default v0.21 comparison:
  crop route vs full-canvas gpt-image-2-safe control for
  `flower_cluster_c`. It only runs with `--run-real-provider` and
  `OPENAI_API_KEY`.

## v0.20.1 workstream (bundled into v0.23.0 — pre-merge correction)

Pre-merge audit on PR #20 caught that v0.20's ship-gate evidence was
attributed to the wrong OpenAI model. Correcting before merge so the
release notes do not ship a false claim.

### What was wrong

`layers_redraw` (and `redraw_merged`) called `get_image_provider("openai")`
without a `model` kwarg. `OpenAIImageProvider.__init__` defaults to
`model="gpt-image-1"` (`src/vulca/providers/openai_provider.py:147`). The
v0.20 spec, plan.md, CHANGELOG entry, and real-provider ship-gate test
header all stated "gpt-image-2 high" — but every actual API call used
`gpt-image-1` default quality. The 24 OpenAI calls across Phase 2,
fixture 1 (3×), fixture 2 (1×), and G5 carousel (9×) all ran on the
wrong model.

The "80× white-pixel improvement" reported in v0.20 fixture 1 is real
but mis-attributed: it is the *inpaint-vs-img2img on gpt-image-1*
delta, NOT the gpt-image-2 high outcome the docs claimed.

The Scottish 2026-04-25 carousel slide-4 RIGHT (`lanterns_after.png`)
genuinely ran on gpt-image-2 because it was authored via `generate_image`
MCP with explicit `model="gpt-image-2"` — that tool exposes a `model`
kwarg. `layers_redraw` did not.

### How it slipped past 4 review rounds

Three validation layers never intersected at the boundary:
- **Spec/CHANGELOG** validated intended policy
- **Provider unit tests** validated endpoint capability with explicitly
  constructed `OpenAIImageProvider(model="gpt-image-2")`
- **Real-provider integration tests** asserted pixel-level outcomes
  (hue, saturation, white-pixel fraction) but **never inspected the
  HTTP form-data sent to OpenAI**

No reviewer ran `git grep "gpt-image-2" src/vulca/layers/redraw.py` —
which would have returned only comments, not arguments. The bug-shape
was a 5-second `git grep` away from detection. Process audit at
[reviewer round 4](docs/superpowers/specs/2026-04-27-v0.20-mask-aware-redraw-routing-design.md)
fully diagnosed.

### Fix

- `redraw_layer` and `redraw_merged` now accept `model`, `quality`,
  `input_fidelity`, `output_format` kwargs (matching the pattern in
  `generate_image` MCP). Plumbed through `provider.model = model` and
  `provider.generate(quality=...)` / `inpaint_with_mask(quality=...)`.
- `OpenAIImageProvider.inpaint_with_mask` now accepts and forwards
  `quality` / `input_fidelity` / `output_format` form-data fields,
  routed through `_drop_unsupported_params` so per-model capability
  matrices are honored automatically.
- `layers_redraw` MCP tool exposes the same kwargs; v0.18.x callers
  without these kwargs continue to land on the provider default
  (gpt-image-1) — bit-identical backward compat.
- `regenerate_from_composite` (`src/vulca/layers/regenerate.py`) gets
  the same kwarg surface, AND a separate latent bug fixed: it was
  silently injecting `GOOGLE_API_KEY` into every provider construction
  via `api_key=api_key or os.environ.get("GOOGLE_API_KEY", "")` — that
  fallback is removed; provider self-resolves from its own env var.
- 4 deeper studio/phase call sites (`concept.py`, `scout.py`,
  `generate.py`, `pipeline/nodes/generate.py`) get `TODO(v0.21)`
  annotations marking the silent default. Deep plumbing through the
  studio orchestrator is v0.21 scope.

### New safeguard — wire-level invocation contract test

`tests/test_layers_redraw_wire_contract.py` (5 tests). Replaces
`httpx.AsyncClient` with a recording wrapper that captures the outbound
POST form-data. Asserts:

- `data["model"] == "gpt-image-2"` when caller passes that model
- `data["quality"] == "high"` when caller passes that quality
- Default omission lands on provider default (currently gpt-image-1)
- `input_fidelity` is silently dropped for gpt-image-2 (capability table
  marks it unsupported) but kept for gpt-image-1.5

This is the exact failure mode that 4 review rounds missed. Per
reviewer round-4's safeguard recommendation: convert soft prose claims
into hard runtime assertions on the HTTP boundary.

### Ship-gate re-run on real gpt-image-2 high

**Fixture 1 (IMG_6847 flower_cluster_c, single-region 3.3% area)** — 3/3 PASS:

| run | hue | L | pct_white_like |
|---|---|---|---|
| v0.20.0 (gpt-image-1 default, mis-attributed) | 79° / 79° / 154° | 0.82 / 0.87 / 0.85 | 67% / 72% / 72% |
| **v0.20.1 (gpt-image-2 high, corrected)** | **62° / 83° / 61°** | **0.79 / 0.78 / 0.79** | **65% / 66% / 64%** |

`gpt-image-2 high` is materially MORE deterministic than `gpt-image-1
default`: hue range tightens from 75° spread to 22°. All 3 v0.20.1
runs land squarely in the `[60°, 90°]` white-flower hue band that the
original spec's calibrated criteria specified before we had to relax
to `pct_white_like` only because of the hidden gpt-image-1 variance.

**Fixture 2 (Scottish lanterns multi-instance, 8% area)** — PASS:
- Structural: 18 connected components preserved (≥5 required)
- Per-component cinnabar criterion: 4 components meet hue ∈ [0°, 50°]
  ∪ [330°, 360°] AND S > 0.4 (≥4 of 6 required)

The originally claimed "PASSED both fixtures" ship-gate evidence (8
calls, ~$0.48) is preserved on disk at
`docs/visual-specs/2026-04-27-ipad-cartoon-roadside/decompose/pass3/v0_20_ship_gate/`
but now correctly labeled as gpt-image-1 default-quality results.

The v0.20.1 ship-gate (4 calls so far + G5 carousel re-run pending)
is the canonical evidence for v0.20 + v0.20.1 combined claim.

### Backward compat

All v0.20.0 callers without `model` kwarg get the same model as before
(provider default) → bit-identical. The new kwargs are opt-in. No API
break.

## v0.20.0 (superseded by v0.20.1)

Mask-aware redraw routing for `layers_redraw`. Fixes the wrong-subject color/shape drift
on alpha-sparse layers surfaced by the IMG_6847 iPad-cartoon dogfood (2026-04-27) and the
γ Scottish row-of-6-lanterns case (2026-04-25, `feedback_cream_flat_reference_limit`).

### Ship-gate result

Both real-provider fixtures PASSED on OpenAI gpt-image-2 high (2026-04-27):

- **Fixture 1 (IMG_6847 flower_cluster_c, single-region 3.3% area)**: 3/3 runs passed
  calibrated criteria (L > 0.6 AND pct_white_like > 30%). Empirical results: hue
  79°/79°/154°, L 0.82/0.87/0.85, pct_white_like 67/72/72%. Compare legacy: hue 101°
  L=0.44 pct_white=0.1% — **80× improvement in white-pixel fraction**.
- **Fixture 2 (Scottish lanterns multi-instance, 8% area, 6+ disconnected blobs)**:
  PASSED with **explicit `route="inpaint"`**. ≥5 connected components preserved + ≥4
  components met cinnabar-red criteria (hue ∈ [0°, 50°] ∪ [330°, 360°] AND S > 0.4).
  Scottish 2026-04-25 had documented this case as a v0.18 limitation requiring
  `generate_image` workaround (`feedback_cream_flat_reference_limit`); v0.20 closes
  it via mask-aware redraw, but **note**: the lantern row-of-N geometry has
  ~0.6 bbox_fill which sits above the auto-routing threshold (0.5), so the
  predicate does NOT auto-trigger inpaint. Users on row-of-N multi-instance
  layouts must opt in via `route="inpaint"` until v0.21 (where the predicate
  may incorporate connected-component count). Single-region sparse layers
  (e.g. IMG_6847 flower_cluster_c at 3.3% area, bbox_fill 0.7) DO auto-trigger
  via `area_pct < 5%`.

Total ship-gate cost ~$0.48 (8 OpenAI gpt-image-2 high calls; one round of metric
recalibration after first batch revealed hue acceptance band was over-fit).

Spec: `docs/superpowers/specs/2026-04-27-v0.20-mask-aware-redraw-routing-design.md`. Reviewed
in 4 rounds (codex GPT-5.4 ×2, superpowers:code-reviewer ×2).

### Fix

**Sparse-alpha layers now route through OpenAI mask-aware editing.**

`layers_redraw` previously sent every layer to `/v1/images/edits` *without a mask file* —
unmasked img2img. The model freely painted the whole canvas, then `preserve_alpha=True`
post-cropped to the original sparse bbox. For sparse subjects (<5% area or fragmented
multi-instance), the model had no spatial cue for "where the subject is", so the crop
yielded whatever the model painted at those pixel locations — green leaves, brown ground,
multi-color banners — instead of the requested cartoon subject.

Concrete drift evidence (alpha-mask-filtered pixel stats from
`docs/visual-specs/2026-04-27-ipad-cartoon-roadside/execution_log.md`):

| layer | original | redrawn (legacy) | drift |
|---|---|---|---|
| flower_cluster_c (3.3% area) | hue 74° L=0.38 (white-on-green) | hue 101° L=0.44 | white→green leaves |
| yellow_truck (0.68% area) | hue 57° (yellow) | hue 151° L=0.54 | yellow→green abstract |
| red_car (2.58% area, half-occluded) | dark red | hue 354° + 95 unique color buckets | shape collapse to multi-color flag |

The `inpaint_with_mask` primitive existed since v0.17.14 but wasn't wired to `layers_redraw`.
v0.20 wires it.

### New `route` kwarg on `layers_redraw`

```python
mcp__vulca__layers_redraw(
    artwork_dir=...,
    layer="flower_cluster_c",
    instruction="cartoon white wildflowers",
    provider="openai",
    route="auto",   # NEW: "auto" (default) | "img2img" | "inpaint"
)
```

- `"auto"` (default): route sparse-alpha layers (`area_pct < 5%` OR `bbox_fill < 0.5` against
  the true bounding box) through `inpaint_with_mask` when the provider is capable
  (`hasattr(..., "inpaint_with_mask")`). Dense layers and incapable providers stay on
  legacy img2img bit-identically.
- `"img2img"`: force the legacy unmasked path (v0.18.x parity).
- `"inpaint"`: force the mask-aware path. Falls back to img2img with a warning when the
  provider lacks `inpaint_with_mask`.

The capability gate covers all current providers without `inpaint_with_mask`
(`mock`, `gemini`, `comfyui`); only `openai` (gpt-image-*) supports the mask-aware path
today.

### Mask + image dimension handling (B8)

Source layers larger than OpenAI's edit-supported sizes (e.g. 4032×3024 IMG_6847 source)
are aspect-preserving downsampled to 1024-class size (`{1024×1024, 1024×1536, 1536×1024}`)
along with their mask before the API call. The model's response is upsampled back to the
original canvas via `_fit_into_canvas`; `preserve_alpha=True` re-applies the
**original-canvas** alpha (not the resized one) so output alpha is bit-identical to source.
Quality cost: model output is at ~1024-class then upsampled — soft edges visible only at
pixel-peeping zoom. v0.21 will revisit if tile-based super-resolution proves needed.

### Mask polarity invariant pinned

Constructed mask must satisfy: where source alpha > 0 (subject), mask alpha = 0 (EDIT
zone); where source alpha == 0 (empty), mask alpha = 255 (PRESERVE zone). This is
OpenAI's `/v1/images/edits` convention. Hard binary {0, 255} only — no GaussianBlur
(intermediate values are undefined behavior). Pinned by
`tests/test_layers_redraw_mask_aware.py::test_mask_polarity_invariant_pins_v2_to_v2_1_bug`.

### Deferred to v0.21

- `redraw_merged` retains v0.18 behavior (unmasked img2img). The `blend_layers` union
  alpha makes the same fix conceptually wrong for merged subjects — needs separate
  redesign. The new `route` kwarg is **ignored** on the merge path.
- Typed advisory in tool return payload (`{sparse_detected, route_used, hint}`).
  v0.20 surfaces routing decisions only via INFO-level log lines:
  `[layers_redraw] layer=X sparse=true area_pct=3.3 bbox_fill=0.65 route_chosen=inpaint provider=OpenAIImageProvider`

### Backward compat

- All v0.18.x callers without a `route` kwarg get `route="auto"` → dense behavior is
  bit-identical (predicate gates the change), sparse behavior is fixed.
- All non-OpenAI providers fall back to legacy img2img via the capability gate.
- `background_strategy="cream"` retained as the legacy workaround for
  `route="img2img"`. Made redundant by `route="auto"` for sparse layers.
- v0.17.x verbatim parity: `in_place=True, background_strategy="transparent",
  preserve_alpha=False, route="img2img"`.

### Tests

- `tests/test_layers_redraw_mask_aware.py` — 14 unit tests: sparsity predicate (true bbox
  including multi-instance corner-spread), RGBA mask polarity invariant + hard binary,
  capability fallback (auto/inpaint/explicit-img2img), 4032×3024 dimension round-trip,
  B7 deferral pin.
- `tests/test_layers_redraw_mask_aware_real_provider.py` — 3 real-provider ship-gate tests
  behind `@pytest.mark.real_provider`. Cost ceiling ~$0.24 per full run. Two acceptance
  fixtures: IMG_6847 flower_cluster_c (single-region 3.3%, hue [30°,90°] AND L>0.6 AND
  pct_white_like>5%, 3× variance ≥2/3 pass) and Scottish lanterns (multi-instance, ≥5
  components + ≥4/6 components matching gongbi cinnabar+gold criteria).
- 37/37 pre-existing `tests/test_layers_redraw.py`, `tests/test_layers_v2_redraw.py`,
  `tests/test_inpaint_mask.py` continue to pass — backward-compat verified.

## v0.19.0 (2026-04-27)

Two diagnostic improvements to the orchestrated detection pipeline surfaced by a
7-entity dogfood run on IMG_6847.jpg. Neither changes detection behavior — only
the **reporting** of misses is improved so callers can take targeted recovery
actions instead of guessing. See `feedback_dogfood_surfaces_design_bugs.md`.

### Fixes

**FIX P0 — Person path: distinguish chain-zero from rank-exceeded**

Before v0.19, when the person chain (YOLO + DINO fallback) returned fewer
detections than there were person-class entities in the plan, all remaining
entities were silently reported as `reason: no_detection_after_chain` — even
when the chain *did* return some detections. In the IMG_6847 case, the chain
returned 1 detection for 2 person-entities; `yellow_truck` (rank=0) was
correctly detected, but `red_car` (rank=1) showed the same `attempts` field as
`yellow_truck` and `reason: no_detection_after_chain`, giving no indication that
the chain *had* found a person — just not a second one.

New reason codes emitted from the person loop:

| Condition | Reason | Extra fields |
|-----------|--------|--------------|
| Chain returned 0 detections | `chain_returned_zero` | — |
| Chain returned N < K detections for K entities | `rank_exceeded_chain_pool` | `entities_in_chain_pool: N`, `this_entity_rank: K-1` |

The `attempts` field (chain-level summary) is unchanged and still present on all
person-miss records.

**FIX P2 — Object path: distinguish dino-zero from below-threshold**

`detect_all_bboxes` now returns a three-key dict instead of a bare assigned-dict:

```python
{
    "assigned":   dict[label, tuple | list],  # pre-v0.19 shape, unchanged
    "near_miss":  dict[label, list[(bbox, score, phrase)]],  # NEAR_MISS_FLOOR ≤ score < effective_threshold
    "nms_drops":  dict[label, list[(bbox, score, phrase)]],  # above threshold but lost within-label NMS
}
```

A new module constant `NEAR_MISS_FLOOR = 0.05` sets the lower bound for
diagnostic capture. DINO is called at `min(effective_threshold, 0.05)` so
candidates the caller's threshold would have missed are still returned as
diagnostics without being assigned.

In the object-loop missed-branch, the reason now distinguishes three states:

| Condition | Reason | Extra fields |
|-----------|--------|--------------|
| DINO found candidates below threshold | `dino_below_threshold` | `near_miss_candidates: [{bbox, conf, phrase}, ...]` (top 5) |
| Candidate passed threshold but lost NMS | `dropped_by_within_label_nms` | `nms_drop_candidates: [...]` (top 5) |
| DINO returned nothing (true zero) | `dino_not_matched` | — |

In the IMG_6847 case, `wildflower_clusters` (threshold=0.18) would now report
`reason: dino_below_threshold` with `near_miss_candidates` showing the actual
scores (e.g., 0.10), letting the user lower threshold to 0.10 to recover.

The `multi_instance_no_detection` quality flag now fires for both
`dino_not_matched` and `dino_below_threshold` (neither has an assigned bbox),
but NOT for `dropped_by_within_label_nms` (that is an NMS artefact, not a
detection gap).

**BREAKING (detect_all_bboxes callers):** All callers that previously read
`result[label]` directly must now read `result["assigned"][label]`. Updated
callers: `detect_bbox`, `detect_all_bboxes_tiled` (internal), and
`detect_all_bboxes_upscaled` (internal). The tiled and upscaled paths do not
yet propagate `near_miss`/`nms_drops` (they emit empty dicts); this is
documented with `TODO(v0.20)` comments.

**Migration recipe** — to find all impacted call sites in your codebase:

```bash
grep -rn 'detect_all_bboxes(' --include='*.py' .
# inspect each match: replace `result[label]` → `result["assigned"][label]`
# new diagnostic keys are optional: result["near_miss"], result["nms_drops"]
```

`detect_bbox` (the legacy single-label wrapper) preserves its return shape
`(bbox, score)` — no migration needed for that wrapper's callers.

### Tests added

10 new regression tests in `tests/vulca/scripts/test_v0_19_detection_diagnostics.py`:
- `TestPersonChainReasonCodes::test_person_rank_exceeded_chain_pool`
- `TestPersonChainReasonCodes::test_person_chain_returned_zero`
- `TestPersonChainReasonCodes::test_person_chain_full_match`
- `TestObjectDiagnosticReasonCodes::test_object_dino_below_threshold`
- `TestObjectDiagnosticReasonCodes::test_object_dino_below_threshold_multi_instance_flag`
- `TestObjectDiagnosticReasonCodes::test_object_dino_not_matched_true_zero`
- `TestObjectDiagnosticReasonCodes::test_object_dino_not_matched_multi_instance_flag`
- `TestObjectDiagnosticReasonCodes::test_object_dropped_by_within_label_nms`
- `TestObjectDiagnosticReasonCodes::test_near_miss_candidates_capped_at_5`
- `TestDetectAllBboxesReturnShape::test_detect_all_bboxes_returns_three_keys`

Existing tests in `tests/test_layers_v2_split.py` updated to use the new
three-key return shape.

### Pre-ship review summary

Both reviewers (fresh codex GPT-5.4 + superpowers Claude) cross-validated the
diff at SHA 94e6147c. Both flagged the same P1 (the `id(d)` set comparison for
NMS-drop tracking — fragile against `_nms_bboxes` internal refactor) and the
test-count nit. Both fixed in this release on top of 94e6147c. Other P2 items
(joint-pass threshold side-effect surfacing, tiled path diagnostic
suppression flag, test boundary tightening, NEAR_MISS_FLOOR migration to
`src/vulca/_segment.py`) deferred to v0.20 backlog.

## v0.18.0 (2026-04-26)

Two paired changes that close the largest hand-cuts surfaced by the γ Scottish carousel (2026-04-25): `layers_redraw` defaults flipped to the safe path (no more silent in-place overwrite + no more alpha-sparse hallucination by default), and `layers_split` orchestrated mode grew first-class multi-instance support so a "row of 6 lanterns" plan no longer collapses into one fragmented union mask.

The migration is two-tier for callers who relied on the legacy `layers_redraw` behavior: most users only need to add `in_place=True` to keep their file-overwriting workflow; the small minority who depended on the legacy `transparent` background passthrough plus alpha drop must add all three kwargs (`in_place=True`, `background_strategy="transparent"`, `preserve_alpha=False`) for byte-identical v0.17.x parity. Everything else is additive.

### Breaking changes

`layers_redraw` defaults flipped — three parameters now choose the safe path by default:

| Parameter             | v0.17.x default       | v0.18.0 default               |
|-----------------------|-----------------------|-------------------------------|
| Output path           | in-place overwrite    | `<layer>_redrawn.png` (input untouched) |
| `background_strategy` | `"transparent"`       | `"cream"`                     |
| `preserve_alpha`      | `False`               | `True`                        |

A new parameter `in_place: bool = False` is the explicit opt-out for callers who need the legacy in-place write. Most users only need this single kwarg — pass `in_place=True` to keep your v0.17.x file-overwriting workflow while inheriting the new safer `background_strategy="cream"` and `preserve_alpha=True` defaults (which improve, not regress, output quality on alpha-sparse layers).

To restore v0.17.x behavior **byte-for-byte** (rare; required only if you depended on the legacy `transparent` background passthrough plus alpha drop):

```python
layers_redraw(
    artwork_dir, layer="lanterns", instruction="...",
    in_place=True,
    background_strategy="transparent",
    preserve_alpha=False,
)
```

**Why**: v0.17.14 introduced the opt-in defenses (`background_strategy="cream"`, `preserve_alpha=True`, `output_layer_name`) but left legacy as the default — making the trap (silent input destruction + scene hallucination on alpha-sparse layers) the path of least resistance. The γ Scottish Part 2 showcase confirmed the trap is easy to fall into even when the implementer knew about it. v0.18 makes the safe path the default; the unsafe path requires explicit opt-out. See commit `7679b488` (kwarg + 3-way path resolution) and `9631adf2` (atomic default flip).

> Note: `layers_redraw(merge=True, layers="a,b,...")` does **not** yet honor the `in_place` kwarg — only the single-layer path. The merge path always writes the merged result to a new file. Tracked for v0.18.1+.

### Added

`layers_split` orchestrated mode now supports multi-instance entities. Plan JSON entities accept an optional `multi_instance: true` flag. When set, Grounding DINO returns up to 8 bboxes for that label (instead of top-1) and SAM segments each independently. The orchestrator emits N flat sibling layers named `<label>_0..N-1` sorted by DINO `det_score` descending (the ordering is fixed at NMS time in `_nms_bboxes` before SAM runs, so SAM scores do not influence sibling order).

```json
{
  "entities": [
    { "name": "lanterns", "label": "red paper lantern", "multi_instance": true }
  ]
}
```

(The schema key is `entities` on the `Plan` model; some prior design docs used `object_entities` informally — the actual `Plan.from_file()` JSON path is `entities`.)

Edge cases:

- DINO returns 0 bboxes → 0 layers emitted; manifest carries `quality_flags: ["multi_instance_no_detection"]`.
- DINO returns exactly 1 bbox → 1 layer named `<label>` (no `_0` suffix); manifest carries `quality_flags: ["multi_instance_degraded"]`. The keystone naming contract: `_0` suffix means "instance 0 of N≥2"; never "lone instance".
- DINO returns >8 bboxes → top-8 by score retained, rest dropped.
- `z_index` of subsequent entities in the plan is auto-pushed by `(N-1)` so the multi-instance fan-out doesn't collide downstream.

Closes the multi-instance gap deferred from v0.17.13. The plan JSON schema extension is additive; existing plans without `multi_instance` are byte-for-byte unaffected. See commits `c82880dd` (detection-layer multi_instance), `ae6471fe` (orchestrator wire + I-1 fail-fast), `bdc9d32e` (entity-loop refactor).

### Limitation: tiled / upscaled detection paths

`layers_split` orchestrated mode raises `NotImplementedError` early when `multi_instance: true` is requested **and** the input image triggers DINO's tiled or upscaled path (extreme aspect ratio, or dimensions outside the standard window). The error message is actionable: it tells the user to either disable `multi_instance` for that image or pre-crop to a non-extreme aspect ratio. Forwarding `multi_instance` kwargs through the tiled/upscaled wrappers is v0.18.1+ scope.

### Internal

- New `src/vulca/_segment.py` module hosts pure-Python NMS helpers (`_iou`, `_nms_bboxes`) extracted from `scripts/claude_orchestrated_pipeline.py` so they can be unit-tested without `import torch` (mirrors the v0.17.14 hotfix discipline for `_quality_gate`).
- New fixture `tests/fixtures/multi_instance/lanterns_6.jpg` (440×700, ≈86 KB) — γ Scottish lanterns crop, anchored as the multi-instance regression baseline.
- New `l4_local` pytest marker for local-only model-weight tests; CI skips automatically via `pytest.importorskip("torch")`. The pre-existing `real_provider` and `local_provider` markers are also now registered in `pyproject.toml`, eliminating `PytestUnknownMarkWarning` noise on every run.

## v0.17.15 (2026-04-26)

Maintenance release. Pure internal hardening — no API changes, no user-visible behavior changes. Two items closed from the v0.17.14-CI-hotfix backlog plus one GitHub deprecation tracker.

### Changed
- `tests/test_quality_gate.py`: migrated `test_person_path_invokes_compute_quality_flags` from string-grep (`Path.read_text() + str.index()`) to `ast.parse()` walk. Same invariant (the person loop in `process()` must contain a `Call` to `compute_quality_flags`), but structurally rigorous — comments and string literals containing the function name no longer satisfy the assertion. Closes the codex P2 from the 2026-04-26 v0.17.14-CI-hotfix review.
- `.github/workflows/ci.yml`: bump `actions/checkout@v4 → @v5` and `actions/setup-python@v5 → @v6`. GitHub will force Node.js 24 default on Actions runners 2026-06-02 and remove Node 20 entirely 2026-09-16; v4/v5 are Node-20-pinned. v5/v6 are the first majors that support Node 24.

### Notes
- `compute_quality_flags` was extracted to `vulca._quality_gate` in the post-tag CI hotfix during v0.17.14 (commit `b5088caa`, 2026-04-26) — see retro entry below.

## v0.17.14 (2026-04-25)

5-patch surgical release surfaced from the 2026-04-25 parallel `superpowers:code-reviewer` + `codex:codex-rescue` review of the γ Scottish carousel. Carousel slide-4 mask-edit can now be reproduced via native MCP calls.

### Added
- `inpaint_artwork(mask_path=...)` native overload via OpenAI `/v1/images/edits`; Gemini and ComfyUI fail-loud when given a mask.
- `layers_redraw` recontract: opt-in `output_layer_name` (no longer overwrites input by default), `background_strategy=cream|white|sample_median|transparent` (defends against alpha-sparse hallucination), `preserve_alpha`, provider-aware `api_key`, aspect-preserving fit.
- `layers_paste_back`: new MCP glue verb for compositing edited layers onto base raster.
- person-path quality gate (mirrors the v0.17.13 DINO-object fix; both paths now go through `compute_quality_flags`).
- `layers_composite` non-destructive default.

### Fixed (post-tag CI hotfix, 2026-04-26 — commit `b5088caa`)
- Master CI red after `v0.17.14` tag: `tests/test_quality_gate.py` imported `scripts/claude_orchestrated_pipeline.py` (which has top-level `import torch`) → CI doesn't install torch → pytest collection ImportError → exit 2. Pure helper extracted to `vulca._quality_gate` (decompose-internal, underscore-prefixed); `cop.py` keeps its in-module name via re-export so the two internal call sites resolve unchanged. Test imports the new module directly.

## v0.17.13 (2026-04-25)

Transparency fix surfaced from the same γ Scottish dogfood session as v0.17.12. Parallel `superpowers:code-reviewer` + `codex` review of the orchestrated decompose pipeline found that the DINO-object path was missing the SAM-quality gate that the hint-entity path had. Result: low-confidence detections (`sam_score < 0.70`, `bbox_fill < 0.30`) were silently marked `status: "detected"` and overall `success_rate: 1.0` — leaving calling agents with no signal to inspect the bad mask. Real-world impact: the `lanterns` entity in our dogfood plan returned a mask of building structure (sam_score 0.609, bbox_fill 0.256) but reported success.

### Fixed
- `scripts/claude_orchestrated_pipeline.py`: extract DINO-object quality gate into `compute_quality_flags()` helper; mirror the hint-path semantics (`empty_mask`, `low_sam_score`, `low_bbox_fill`, `mask_outside_bbox`) onto the DINO branch. Low-confidence object detections now correctly downgrade to `status: "suspect"` with `quality_flags: [...]`, and the overall manifest status cascades to `"partial"` when any object is suspect (mirroring existing behavior for hint-entity suspects).

### Added
- `tests/test_quality_gate.py`: 8 regression tests pinning the gate's threshold calibration (sam_score 0.70, bbox_fill 0.30, inside_ratio 0.60, pct 0.05) against the γ Scottish 9-entity baseline. 8 clean entities pass at sam ≥ 0.93 / fill ≥ 0.55; lanterns (sam 0.609 / fill 0.256) flips to suspect. Future refactors must update this test explicitly to change the gate.

### Notes
- The underlying multi-instance segmentation gap (single-bbox-per-label structural limit in `detect_all_bboxes`) is **not** fixed here — that's `v0.18` scope. v0.17.13 only fixes the transparency bug so the gap is now visible to callers instead of silent.

## v0.17.12 (2026-04-25)

Bugfix rollup from γ Scottish showcase Part 1 session findings.

### Fixed
- openai_provider: gate `input_fidelity` / `quality` / `output_format` by per-model capability (#12) — `gpt-image-2` GA rejected `input_fidelity` while Vulca was sending it unconditionally
- openai_provider: capture actual `cost_usd` from `response.usage` (#12); log at info level when a model has no pricing entry instead of silently returning None
- openai_provider: normalize `quality` vocabulary across model families — DALL-E-3 receives `"standard"`/`"hd"` while gpt-image-* keeps `"high"`/`"auto"`/`"medium"`/`"low"` (post-review)
- prompting: `compose_prompt_from_design` now handles `tradition: null` (a valid resolved-design state) and reads frozen `C.tradition_tokens` from the artifact when present rather than re-deriving from the live registry (post-review)
- mcp_server: `compose_prompt_from_design` MCP wrapper raises an actionable error when given a relative path that doesn't resolve against the server CWD (post-review)
- `[sam]` extra: pulls `segment-anything` + `timm>=1.0` so the orchestrated decompose pipeline imports cleanly; see `docs/INSTALL-RECIPE.md`

### Added
- MCP tool `compose_prompt_from_design` (#13) — expose Vulca's structured prompt-composition value standalone for non-MCP consumers
- `evaluate_artwork` `mode="rubric_only"` (#14) — agent-native scoring without VLM backend dependency
- `evaluate_artwork` `vlm_model` runtime kwarg (#15) — bypass `VULCA_VLM_MODEL` env + MCP restart for runtime provider switching

## v0.17.11 — 2026-04-23

**Honesty + quality-of-life patch.** Driven by today's (2026-04-23) dogfooding of the Scottish-Chinese fusion showcase + parallel codex + superpowers:code-reviewer product audits. User feedback: "我们的产品好不好？使用起来有bug吗？深度调研一下". The review surfaced real silent-data-loss bugs (ref_type), missing UX questions (Style-Treatment), weak error messages, over-claims in README / BP, and hygiene gaps. This release addresses all of them.

### Added
- **`.claude/skills/visual-brainstorm/SKILL.md`** — **Style-Treatment 7th question-bank dimension** (mandatory, no skip): `additive` (photo preserved, elements painted as distinct objects on top) / `unified` (whole image transformed) / `collage` (visible cut-outs) / `wash` (global style filter). Fixes the UX gap where the gpt-image-1.5 smoke test produced a whole-image painterly overlay when the user wanted additive treatment — the 6-dim question bank simply didn't ask about style application mode. See commit `69dbd5d1`.
- **`.claude/skills/visual-brainstorm/SKILL.md`** — `proposal.md` frontmatter now carries `style_treatment` (7 → 8 fields).
- **`.claude/skills/visual-spec/SKILL.md`** — Phase 1 step 8 validates `proposal.frontmatter.style_treatment ∈ {"additive", "unified", "collage", "wash"}` (Err #4); Phase 3 C.prompt derivation reads `style_treatment` and writes corresponding `negative_prompt` constraints (`additive` → excludes "global painterly filter, unified style wash, photo-texture loss"; `wash` / `unified` → inverse); S4 invariant extended to cover `C.style_treatment` immutability across session.

### Changed
- **Provider error messages normalized** for user-readability — codex 2026-04-23 audit flagged raw low-level errors across 3 providers. Commit `437f4dc0`:
  - `src/vulca/providers/gemini.py:190-234` — classifies empty `response.candidates` into quota-exhaustion vs content-policy vs generic via `prompt_feedback.block_reason` inspection. Provides remediation URL (aistudio.google.com) for the free-tier quota case.
  - `src/vulca/providers/openai_provider.py:148-200` — added user-facing messages for 402 (billing), 400 content-policy, 429 rate-limit on top of the existing 403 Org-verify path. `_is_retryable` extended so 429 RuntimeError stays retryable via string-match (fragile; flagged for v0.17.12 hardening).
  - `src/vulca/providers/comfyui.py:136-153, 219-226` — execution-error extractor surfaces the first meaningful message from `status.messages` list + points to the ComfyUI server console; invalid-image hint explains the likely checkpoint/VAE failure mode.
- **`README.md`** — "Try it in 60 seconds" section retitled to "Quick start" with explicit time breakdown: ~1 min if Claude Code + `uv` already installed, ~5-10 min from scratch. Honest vs aspirational. Commit `856ce54c`.
- **`docs/bp/2026-04-23-vulca-bp/sections/05_competition.tex` §5.4** — "壁垒强度与持续性" moat language softened: "24 个月以上难以复制" → "12 个月以上需专门投入", replaced absolute phrasing with honest "竞品雇 3 位文化顾问一个季度可以追赶一种传统; 追赶 13 种 + 学术认同需要更长周期". Superpowers reviewer: "formal correctness fragile in practice; honest wording more credible to sophisticated readers". Commit `856ce54c`.
- **`.gitignore`** — added `/gen_*.png`, `/gen_*.jpg` (75 files were polluting repo root, never committed) + `tmp-shipgate-*/` (ship-gate artifacts from prior versions). Commit `856ce54c`.

### Removed
- **BREAKING**: `create_artwork.ref_type` parameter removed from MCP tool signature (`src/vulca/mcp_server.py:92-123`). The parameter was declared but never forwarded to the underlying `generate_image` call — callers who set it were silently ignored (silent data loss per codex audit). Rather than wire it through (scope creep), the semantic space is now covered by the `Style-Treatment` dimension in `/visual-brainstorm`. Callers that passed `ref_type` must remove the kwarg; no behavior regression (the value had no effect anyway). Commit `5bf4b1ca`.
  - **SDK-level `ref_type`** in `src/vulca/create.py` + `cli.py` + `studio/phases/{concept,generate}.py` is **unchanged in this release** — only the MCP tool surface was cleaned. Deeper SDK cleanup deferred to v0.18+.

### Fixed
- **`src/vulca/mcp_server.py:578-602`** — `layers_split.plan` parameter now documented in the Args block (previously declared in signature but absent from docstring). Commit `5bf4b1ca`.
- **`src/vulca/mcp_server.py:769-787`** — `layers_edit` docstring: split the compressed `visible` + `locked` line into two separate entries with explicit operation linkage. Commit `5bf4b1ca`.
- **`.claude/skills/decompose/SKILL.md:140`** and **`docs/superpowers/specs/2026-04-20-plugin-sync-and-readme-refresh-design.md:283-285`** — replaced hardcoded `/Users/yhryzy/` maintainer paths with `<vulca-repo-root>` placeholders. Commit `5bf4b1ca`.

### Tests + ship-gate
- Full repo: **1920 passed**, 12 pre-existing baseline failures unchanged (cv2-missing + mock mime-type + layered pipeline edges). **Zero regressions** from any of the 4 v0.17.11 commits.

### Known follow-ups deferred to v0.17.12
- **`/visual-plan` Phase 3 `C.style_treatment` plumb**: the new `style_treatment` field is persisted in design.md but `/visual-plan` does NOT yet read it in Phase 3 prompt composition. Until v0.17.12 lands, the field is "declared but inert" for image generation — it only informs `/visual-spec` C.prompt's `negative_prompt`. Downstream propagation to the execution loop is the v0.17.12 target.
- `openai_provider._is_retryable` uses fragile string-match (`"rate limit hit" in str(exc).lower()`) to preserve 429 retryability after RuntimeError normalization. Robust solution: custom exception subclass + attribute-based classification. v0.17.12.
- SDK-level `create_artwork.ref_type` cleanup (mirrors the MCP-surface removal done here).

### Dogfooding-driven origin
Per 2026-04-23 session memory `feedback_dogfood_showcase_through_triad.md`: this is the 5th same-day ship driven entirely by real dogfooding (Scottish-Chinese fusion showcase run, paused at /visual-spec Phase 2 F-calibration). User feedback "这种类似的问题很严重 很卡手" (previous session) and the style-framing bug in the gpt-image-1.5 smoke test (this session) drove the changes.

## v0.17.10 — 2026-04-23

This release bundles **v0.17.9** (previously unshipped) with **v0.17.10**. Both surfaced from dogfooding the /visual-plan showcase on 2026-04-23 — real user corrections drove both fixes.

### Added (from v0.17.9 OpenAI gpt-image-2 support)
- `OpenAIImageProvider` now accepts `model="gpt-image-2"` (released 2026-04-21), unlocking the `/v1/images/edits` high-fidelity mode required for reference-preserving image fusions.
- New kwargs plumbed through MCP `generate_image` + `OpenAIImageProvider.generate` + `ImageProvider` Protocol:
  - `input_fidelity: "high" | "low"` — preserves reference composition (edits endpoint only)
  - `quality: "low" | "medium" | "high" | "auto"`
  - `output_format: "png" | "webp" | "jpeg"`
- Size set extended with portrait + landscape: `(1024, 1536)`, `(1536, 1024)` in addition to prior DALL-E 3 sizes.
- Friendly error detection on OpenAI 403 with `"organization must be verified"` message — raises `RuntimeError` with remediation URL + 15-min propagation note instead of raw HTTP error.
- `tests/test_generate_image_extended_signature.py` gains 3 new test cases (`TestGptImage2Signature`) covering signature shape + plumbing + kwarg absence.

### Added (v0.17.10 skill-design alignment)
- **`.claude/skills/using-vulca-skills/SKILL.md`** — new meta-skill (≈50 lines) that establishes auto-invoke discipline for the brainstorm→spec→plan triad. Modeled on `superpowers:using-superpowers`. Includes intent-routing table, finalize vocabulary normalization, red-flag checklist.
- **`.claude/settings.json`** — SessionStart hook (`matcher: "startup|clear|compact"`) preloads `using-vulca-skills/SKILL.md` so the agent matches user intent without requiring explicit slash commands.
- **`.claude-plugin/plugin.json`** — distributable plugin manifest for `vulca-org/vulca-plugin` repo (v0.17.10).
- **`hooks/hooks.json`** — mirror-ready hook config for distributed plugin. Uses `${CLAUDE_PLUGIN_ROOT}` to load meta-skill from the plugin's own skills directory.

### Changed
- **3 skill descriptions rewritten** from descriptive "Triggers: /slash-command" to imperative "Use when X / You MUST use this before X" — matches Superpowers' auto-invoke-friendly pattern. Without this, Claude Code's intent-matching heuristic over-interpreted "Triggers:" as slash-only gating. Affected files:
  - `.claude/skills/visual-brainstorm/SKILL.md`
  - `.claude/skills/visual-spec/SKILL.md`
  - `.claude/skills/visual-plan/SKILL.md`
- Each skill also gained a new `## Triggers` body section documenting (a) slash command, (b) Chinese aliases, (c) intent auto-match phrases, (d) skip conditions. Chinese triggers preserved as aliases (not dropped); just moved out of the description field.
- **Finalize vocabulary normalized** across the 3 skills:
  - Brainstorm/Spec: 5-word set `finalize / done / ready / lock it / approve` (brainstorm previously had only 4; `approve` added)
  - Plan: `accept all` exact-match stays (stricter because it triggers real cost-incurring pixel calls)
- **Plan cap-hit prompt** corrected — was asking `"Turn cap reached. finalize or deep review?"` but the actual gate requires `accept all`. Now: `"Turn cap reached. 'accept all' or 'deep review'?"` (2 occurrences fixed for internal consistency).

### Dogfooding-driven surface discoveries
Both of this release's changes came from real dogfooding work 2026-04-23:
- **v0.17.9**: attempting to run /visual-plan Phase 3 with gpt-image-2 on a real Scottish street photo revealed `OpenAIImageProvider` was hardcoded to `gpt-image-1` without `input_fidelity` support.
- **v0.17.10**: user observation — "Vulca skills require slash commands while Superpowers auto-invoke" — triggered a systemic audit (codex + superpowers:code-reviewer parallel) that surfaced the description-wording + meta-skill + SessionStart-hook gaps.

Memory `feedback_dogfood_showcase_through_triad.md` captures the rule: user-facing showcases MUST use the triad, not one-off scripts. Memory `feedback_parallel_review_discipline.md` remains the validation pattern.

### Known follow-ups deferred to v0.18+
- Protocol body compression across the 3 SKILL.md files (currently 200-430 lines each vs Superpowers' peers at 60-170 lines). Superpowers code-reviewer flagged this as "long bodies dilute their own descriptions." Not blocking auto-invoke fix; scope creep risk now.
- Cross-skill factoring of shared Err matrices + invariants — superpowers reviewer warned against this for shared-dep reasons. Monitor only.

## v0.17.8 — 2026-04-23

### Fixed
- **`src/vulca/mcp_server.py` — MCP `generate_image` wrapper now forwards
  `provider.ImageResult.metadata` to the tool caller via the new
  `"metadata"` return-dict key.** v0.17.6 landed mock-provider echo of
  `seed / steps / cfg_scale / negative_prompt` into `ImageResult.metadata`,
  but the MCP wrapper only extracted `cost_usd` and dropped the rest —
  meaning agents could never observe kwargs round-trip. Surfaced by
  /visual-plan Layer C v2 live ship-gate 2026-04-23. Backward-compat:
  `"metadata"` key is always present (non-conditional), empty dict when
  provider returned None.
- **`src/vulca/_version.py` 0.15.1 → 0.17.8** — fixes stale `__version__`
  drift. `pyproject.toml` had been bumped since v0.15.1 but the module
  attribute wasn't. `python -c "import vulca; print(vulca.__version__)"`
  now reports the true PyPI version.

### Changed
- `.claude/skills/visual-plan/SKILL.md` — 12 clarity-gap patches folded in
  from v0.17.7 Layer C v2 (8) + v0.17.5 simulated Layer B (5) minus 1
  covered by the `_version.py` fix:
  - **Err #16 handoff variant split** from user-interrupt (variant 9 added).
    §Handoff is now 9 variants (was 8), distinguishing content-guard abort
    from user-triggered abort for downstream grep users.
  - **`evaluate_artwork` dimensions shape** pin — Phase 3 pseudocode now
    explicitly documents the mock flat-float vs live nested-dict contract
    with unwrap recipe.
  - **MCP metadata agent-hint** — Phase 3 pseudocode notes that mock
    provider echoes all 4 MCP kwargs into `gen_result["metadata"]` for
    round-trip verification.
  - **Iter `<K>` semantic** — new paragraph in §Handoff clarifying that
    `aborted` variants 7-9 use K as the iter_idx that WOULD have run (not
    the last-successful iter); `<N>/<M>` numerator in `partial` variants =
    `len(jsonl)` not K.
  - **Phase 1 step 1 slug path convention** — rejects `/`-containing and
    absolute-path slugs as malformed (Err #1).
  - **Phase 1 step 2 traceback guard** — catch `FileNotFoundError` /
    `PermissionError` and emit Err #1 verbatim BEFORE any Python traceback.
  - **Phase 1 step 3 Err #3 + fresh-lockfile interaction** — documents
    the mid-run crash scenario (fires Err #11, correct per S5 letter).
  - **Phase 1 step 4 stale-lock K=0 rule** — explicit semantic:
    K = `len(completed_iters)` where completed = jsonl rows with
    `verdict ∈ {accept, reject}`; empty/absent jsonl → K=0.
  - **Phase 1 step 7 FIRST-violation precedence** — if both `tradition`
    (step 6) and `domain` (step 7) invalid, report only the tradition
    violation via Err #4 (step 6 fires first; no concatenation).
  - **Phase 2 step 4 Err #8 + denied-deep-review Write suppression** —
    bolded: turns that mutate neither state nor counter skip the
    Phase 2 step 5 `Write`.
  - **Phase 2 step 5 "compact form" definition** — 1-line summary
    `[unchanged sections: …] turns_used: <N>/<cap>` + full Notes block.
  - **Phase 2 step 2 redundant-Write note** — clarified as symmetry, not
    correctness.
  - **Phase 4 step 4 overage_pct negative formatting** — display rule:
    `< 0` → `"under budget (-<pct>%)"`; `>= 0` → `"+<pct>%"`.

### Added
- `tests/test_generate_image_extended_signature.py` — 2 new cases
  (`test_mcp_wrapper_passes_metadata_through` +
  `test_mcp_wrapper_metadata_backward_compat_empty_dict`) covering the
  MCP wrapper metadata passthrough path that v0.17.6 unit tests missed
  (they tested only the direct-provider layer).

### Non-blocking deferrals
The clarity-gap backlog is now **clear** — all 13 items folded in (8 from
v0.17.7 Layer C v2 + 5 from v0.17.5 simulated B; one absorbed into the
_version.py fix). No open skill-body clarity items.

## v0.17.7 — 2026-04-23

### Added
- `/visual-plan` skill — **3rd and final meta-skill** in the
  `brainstorm → spec → plan → execute` architecture. Completes the triad:
  - `/visual-brainstorm` (v0.17.3/v0.17.4) produces `proposal.md`
  - `/visual-spec` (v0.17.5/v0.17.6) resolves into `design.md`
  - `/visual-plan` (this release) executes → `plan.md` + `iters/*.png` +
    `plan.md.results.jsonl` → terminal artifact `{completed, partial, aborted}`
  See `.claude/skills/visual-plan/SKILL.md` (~413 lines).
  Design spec: `docs/superpowers/specs/2026-04-23-visual-plan-skill-design.md`.
  Implementation plan: `docs/superpowers/plans/2026-04-23-visual-plan-skill.md`
  (1801 lines, 10 tasks, ~100 steps executed across this session).
- 4 phases: Precondition gate + derivation + plan.md draft write → Plan-
  review loop (5-turn cap, inherits `/visual-spec` Phase 4 vocabulary) →
  Execution loop (sequential `seed_list` iter with generate+evaluate+jsonl
  append) → Finalize + optional hygiene.
- 7 invariants S1-S7: pixel-tool ban baseline (S1 with Phase 3 exemption
  whitelist), status-transition discipline (S2), single-run guard (S3),
  `design.md` content-hash immutability (S4 — per-iter re-assert + Err #16
  on drift), lockfile `O_CREAT|O_EXCL` concurrency primitive (S5),
  jsonl append-only recovery authority (S6), plan.md render-artifact only
  (S7).
- 16-row error matrix (`Err #1` through `Err #16`) with verbatim
  `Print exactly:` strings for grep-contract stability.
- 8-variant handoff string set covering the terminal states +
  stale-lock-recovery suffix.
- 57 pytest tripwires across 4 test files (tests/test_visual_plan_parser_invariants.py,
  test_visual_plan_source_gating.py, test_visual_plan_execution_loop.py,
  test_visual_plan_error_matrix.py).

### Ship-gate status
- **Layer A** (pytest tripwires): 57/57 PASS in <30s.
- **Layer B** simulated (3 parallel subagents α/β/γ, 14 cases covering
  P1-P3 positive + resume + concurrent, N1-N10 single-fire errors,
  N11 user_elevated persistence): **14/14 PASS**. See
  `docs/superpowers/plans/visual-plan-ship-gate-log.md`.
- **Layer C** live v2 (2 parallel subagents, 6 gaps / 4 cases covering
  real `generate_image(mock)` + real `evaluate_artwork` + real filesystem
  lockfile + Err #16 design-drift): **4/4 PASS**. See
  `docs/superpowers/plans/visual-plan-live-ship-gate-log.md`.
- Combined: **v1 14/14 + v2 4/4 = 18/18 cases** for non-pixel-heavy surface.
- 13 non-blocking clarity-gap candidates logged for a future v0.17.8
  clarity patch (8 from v2, 5 from v1; most notable: MCP
  `generate_image` drops provider metadata at the wire contract —
  v0.17.6 mock-kwargs echo never reaches the tool caller).

### Dependencies
- Requires v0.17.6 (shipped prior) for `generate_image` MCP extension
  (`seed/steps/cfg_scale/negative_prompt` kwargs) + `schema_version`
  field in `design.md` frontmatter.

## v0.17.6 — 2026-04-23

### Added
- MCP `generate_image` signature extended with 4 new Optional kwargs:
  `seed: int | None`, `steps: int | None`, `cfg_scale: float | None`,
  `negative_prompt: str | None`. Required precondition for `/visual-plan`
  Phase 5 spike execution (ships as v0.17.7). Backward-compatible: all 4
  default to `None`; existing 5-param callers unaffected.
- 4-provider plumbing for the new kwargs:
  - `mock`: echoes non-None values into `ImageResult.metadata` for agent diagnostics.
  - `comfyui`: parameterizes the `KSampler` node (seed/steps/cfg); random-seed
    fallback preserved when `seed=None`.
  - `openai`: `seed/steps/cfg_scale` explicitly ignored (no DALL-E support);
    `negative_prompt` prepended as `"(avoid: ...)"` to main prompt.
  - `gemini`: `negative_prompt` prepended to prompt; `seed` wired to
    `GenerateContentConfig` via `try/except TypeError` for SDK-version tolerance;
    `steps/cfg_scale` ignored (no diffusion sampler).
- `tests/test_generate_image_extended_signature.py` — 8 pytest tripwires for
  signature shape, backward-compat, per-kwarg plumbing, and None-exclusion hygiene.
- `design.md` frontmatter gains `schema_version: "0.1"` (9 canonical fields).
  Legacy pre-v0.17.6 drafts default to `"0.1"` on finalize (additive; no retro-write).
- `RESOLVED_NULL_TRADITION_NO_SPIKE_MD` 7-section fixture + 3 new schema-invariants
  tests (11 total, up from 8).

### Changed
- `.claude/skills/visual-spec/SKILL.md` — 10 clarity-gap patches from the v0.17.5
  Layer B simulated ship-gate (9/9) + Layer C live ship-gate v2 (4/4):
  - Err #9 Notes template wording normalized (`unreachable` → `unreadable`).
  - Err #5 / #6 classifier tightened with content-semantic keyword regexes
    (integration-layer vs per-call failure distinction); pipes unescaped.
  - Multiplier table gains bare-`sdxl` row with host-detect resolution rules.
  - Phase 3.A `recommended_providers` phantom key replaced with `pipeline_variant`
    real reference.
  - Phase 3.C `tradition_tokens` shape clarified (`list[dict]` from `.terminology`,
    not flat string list) + concat recipe provided.
  - D1 example weights annotated as illustrative-only; mechanical-copy rule
    re-emphasized.
  - Phase 4 `accept all` branch documents the finalize-Write-absorbs-bump
    exception to the `Write`-pairs-with-every-`turns_used`-change rule.
  - Phase 2 Err #3 resume behavior specified: trust the draft's `F` block,
    do NOT re-calibrate mock latency.
  - §Produced artifact documents all 3 section-count cases (9/8/7) including
    the collapsed `tradition: null` + no-spike shape.
- `tests/test_visual_spec_schema_invariants.py` fixture realigned to SKILL.md's
  canonical 9-field frontmatter set (resolves gap #4: prior fixture was
  vacuously testing itself against divergent field names).
- `ImageProvider` Protocol (`src/vulca/providers/base.py`) updated to match the
  4 concrete providers' new kwargs.

### Fixed
- Pre-v0.17.6 drift between `src/vulca/providers/base.py` Protocol and concrete
  provider signatures (was type-checker surface bug, not runtime).

## v0.17.5 — 2026-04-21

### Added
- `/visual-spec` skill — meta-skill #2 of the `brainstorm → spec → plan` architecture.
  Turns a `proposal.md` (with `status: ready` from `/visual-brainstorm`) into a resolved
  `design.md` that `/visual-plan` will consume. 6 phases (precondition gate → F
  calibration → 7-dimension derivation → derive-then-review loop → optional spike →
  finalize), 9-error matrix, 6 skill bans (S1-S6), 5-word finalize vocabulary
  (superset of brainstorm's 4).
  Design spec: `docs/superpowers/specs/2026-04-21-visual-spec-skill-design.md`.
  Implementation plan: `docs/superpowers/plans/2026-04-21-visual-spec-skill.md`.
  See `.claude/skills/visual-spec/SKILL.md` (~414 lines).
- `tests/test_visual_spec_d1_registry_copy.py` + `tests/test_visual_spec_schema_invariants.py`
  + `tests/test_visual_spec_source_confidence_matrix.py` — Layer A pytest tripwires
  (22 cases, ~2s run). Assert D1 byte-identity with `get_tradition_guide().weights`,
  design.md frontmatter + section + triple-form invariants, per-dim source/confidence
  tag allowability.
- Fenced YAML blocks in `design.md` carry `{value, source, confidence}` metadata on
  D2/F numeric fields (epistemic humility machine-readable for `/visual-plan` downstream).
- F cost budget uses per-session calibration (`mock × multiplier` by default, or
  user-supplied `--budget-per-gen`); never hardcoded values. Unknown-provider fallback
  rule requires user intervention.

## v0.17.4 — 2026-04-21

### Changed
- `/visual-brainstorm` skill — 3 small clarifications to the `proposal.md` contract,
  surfaced by the 2026-04-21 live ship-gate v2 (see
  `docs/superpowers/plans/visual-brainstorm-live-ship-gate-log.md`):
  - Frontmatter schema tightened — "exactly 7 fields, no additional keys, no
    YAML comments inside the `---` fence".
  - §Opening turn 2 resume path (`status: draft`) — explicit rules: skip the A2
    solicited-sketch question; bump `updated:` to today on re-finalize;
    `created:` unchanged.
  - §Error matrix #1 — refusal phrase promoted to `Print exactly:` per §Handoff
    convention so downstream tooling can reliably grep for it.

### Added
- `scripts/tool_audit.py` v2 — `--provider-mode {mock,real}`, `--real-provider`,
  `--max-images` flags; silent-error-as-PASS bug fixed (error-dict returns now
  FAIL); 4 stale-signature kwargs corrected.
- `tests/test_visual_brainstorm_discovery_integration.py` — 12 pytest cases
  (list_traditions / search_traditions / get_tradition_guide) acting as durable
  tripwire for registry churn. Runs in ~2.5 s.
- `docs/tools-readiness-matrix.md` — §2 (mock audit, 9/9 surface valid), §2.1
  stratified gate interpretation, §2.2 (ComfyUI real-pipeline audit, 9/9 with
  latency anchors), §2.3 gate decision GREEN.
- `docs/superpowers/plans/visual-brainstorm-live-ship-gate-log.md` — v2 live
  ship-gate, 5/5 integration cases PASS under real tools + real filesystem.

## v0.17.3 — 2026-04-21

### Added
- `/visual-brainstorm` skill — guide fuzzy visual intent into reviewable
  proposal.md (OpenSpec-aligned partial). Zero-pixel, Discovery-metadata-only.
  Scoped to 2D illustrative/editorial domains (7 enum values). Conditional
  L1-L5 rubric for tradition-bearing projects.
  See `.claude/skills/visual-brainstorm/SKILL.md`.

## [0.17.2] - 2026-04-20

### SAM2 macOS / non-CUDA compatibility

- **Fix default SAM2 checkpoint ID** (`src/vulca/layers/sam.py`): the default `checkpoint` fallback was `"sam2.1_hiera_small"`, not a valid HuggingFace Hub ID. `SAM2ImagePredictor.from_pretrained` rejected it, so any caller invoking `sam_split` without explicit `checkpoint=` crashed on load. Corrected to the canonical HF ID `"facebook/sam2.1-hiera-small"` and exposed as the module constant `DEFAULT_SAM2_CHECKPOINT`.
- **Route SAM2 around its hard-coded CUDA assumption** (`src/vulca/layers/sam.py`): upstream `sam2.build_sam.build_sam2*` calls `.cuda()` unconditionally, crashing on macOS and any host without a CUDA runtime. Added `_sam2_device()` (cuda → cpu; MPS intentionally excluded — SAM2 does not reliably support the MPS backend as of 2026-04-20) and `_patch_sam2_build_to_device()` which idempotently wraps `build_sam2`, `build_sam2_hf`, and `build_sam2_video_predictor` to inject a `device=` kwarg when callers do not supply one. Explicit device kwargs from callers still win. Apple Silicon users now fall back to CPU instead of hitting a `.cuda()` RuntimeError.
- **New offline tests** (`tests/test_sam_device.py`): 8 unit tests cover the checkpoint constant, device-selection behavior under present/missing torch and cuda, monkey-patch idempotency + explicit-kwarg-preservation invariants, and the existing `ImportError` contract from 0.17.1. All tests run without sam2 installed.

Discovered in the emoart T1.6.a decompose smoke immediately after 0.17.1 shipped; both bugs had workarounds in emoart's smoke script but were not fixed in Vulca until now.

## [0.17.1] - 2026-04-20

### Packaging fix

- **Remove nonexistent `segment-anything-2` PyPI dep** (`pyproject.toml`): the `sam` and `layers-full` extras declared `segment-anything-2>=0.1`, a package that does not exist on PyPI. `pip install vulca[sam]` / `pip install vulca[layers-full]` failed with a resolver error. Meta does not publish SAM2 to PyPI — install separately via `pip install git+https://github.com/facebookresearch/sam2.git`. The `sam` extras now pulls only `torch`, `numpy`, `Pillow`; `layers-full` keeps `rembg` + `transformers` + `torch`.
- **Actionable `sam_split` ImportError** (`src/vulca/layers/sam.py`): runtime error now instructs the two-step install path when `sam2` is not importable, so users hitting `vulca layers split --mode sam` without SAM2 see the correct command instead of the stale `pip install vulca[sam]` hint.

## [0.15.1] - 2026-04-13

### README major revision — local-first narrative

- **12-section restructure** — tightened from ~15 fuzzy sections to 12 clean sections (694 lines, down from 758). Local stack (ComfyUI + Ollama) presented as default path, Gemini as alternative.
- **v3 gallery images** — hero area and traditions section now use real E2E-generated images (SDXL on Apple Silicon MPS) instead of v2 placeholder assets.
- **Edit + Inpaint merged** into one section with provider-agnostic callout (v0.15 feature).
- **Self-Evolution** collapsed into Architecture section's `<details>` block.
- **Provider capability matrix** added to Architecture (generate/inpaint/layered/multilingual per provider).
- **`make-readme-assets.py`** — new script produces 5 display-quality composite images from v3 artifacts.

### SDXL generation fixes (4 bugs)

- **CLIP-aware prompt compression** (`layers/layered_prompt.py`): `build_anchored_layer_prompt()` now returns a flat subject-first prompt (<70 tokens) with separate `negative_prompt` for CLIP-based providers (ComfyUI/SDXL). Structured multi-section format preserved for Gemini. Root cause: SDXL CLIP's 77-token limit caused garbage embeddings from 120+ token structured prompts.
- **ANCHOR hallucination fix** (`layers/layered_prompt.py`): Prompt section headers renamed from `[CANVAS ANCHOR]`/`[STYLE ANCHOR]` to `[CANVAS]`/`[STYLE]`. SDXL was painting literal ship anchors.
- **Background keying guard** (`layers/layered_generate.py`): `generate_one_layer()` now skips luminance keying for `content_type="background"` layers, preventing white canvas from becoming transparent.
- **ComfyUI PNG validation** (`providers/comfyui.py`): Rejects responses under 1KB or without PNG magic bytes.

### Apple Silicon MPS compatibility guide

- **New document:** `docs/apple-silicon-mps-comfyui-guide.md` — comprehensive guide for running SDXL on Apple Silicon via ComfyUI. Documents 3 PyTorch MPS backend regressions (SDPA non-contiguous tensors, Conv2d chunk correctness, Metal kernel migrations) that cause black/noise images on PyTorch 2.10-2.11. Solution: pin `torch==2.9.0`.

## [0.15.0] - 2026-04-12

### E2E Phases 2-7 Full Wiring

All 8 E2E demo phases now run end-to-end on the local stack (ComfyUI + Ollama/Gemma 4, Apple Silicon MPS). Previously only phases 1, 3, 8 were wired.

**5 new runner phases** (`scripts/generate-e2e-demo.py`):
- **Phase 2 — Layered Create:** Generates multi-layer artwork via the `LAYERED` pipeline template. Validates manifest, composite, per-layer RGBA PNGs.
- **Phase 4 — Defense 3 Showcase:** Side-by-side comparison of layered generation with vs. without serial-first style-ref anchoring (`disable_style_ref` toggle). Both variants produce composites.
- **Phase 5 — Edit / Layer Redraw:** Loads Phase 2 artifact via `load_manifest()`, redraws a non-background layer, recomposites with `composite_layers()`.
- **Phase 6 — Inpaint:** Region-based inpainting on a Phase 1 gallery image, now provider-agnostic (was Gemini-only).
- **Phase 7 — Studio:** Brief-driven auto-mode session via `asyncio.to_thread(run_studio, ...)` with 900s timeout for MPS.

### Core library fixes

- **CJK-aware `build_anchored_layer_prompt()`** (`layers/layered_prompt.py`): New `english_only: bool` parameter strips CJK characters from canvas descriptions, style keywords, sibling roles, own role, and user intent before sending to CLIP-based providers. Three helpers: `_strip_cjk_parenthetical`, `_is_ascii_latin`, `_strip_cjk_chars`.
- **Provider capability: `multilingual_prompt`** (`providers/gemini.py`): Gemini declares CJK-native prompt support; ComfyUI omits it → triggers `english_only=True` automatically via `LayerGenerateNode`.
- **VLM English output instruction** (`layers/plan_prompt.py`): `PlanLayersNode` now instructs the VLM to produce all `regeneration_prompt` values in English, regardless of user input language.
- **ComfyUI `raw_prompt` support** (`providers/comfyui.py`): `raw_prompt=True` kwarg skips the auto-appended tradition suffix, matching Gemini's existing mechanism.
- **`disable_style_ref` toggle** (`layers/layered_generate.py`): When `True`, all layers generate in parallel without cross-layer style reference (bypasses serial-first split entirely). Used by Phase 4.
- **`ainpaint` provider parameter** (`inpaint.py`, `studio/phases/inpaint.py`): Removed hardcoded `"gemini"` provider. New `provider: str = "gemini"` parameter threaded through to `InpaintPhase.repaint()`.

### Phase 3 public API migration

- `run_phase3_evaluate` now uses the public `vulca.aevaluate()` instead of the private `vulca._vlm.score_image()`. Zero remaining references to the private API in the runner.

## [0.14.1] - 2026-04-12

### Local provider pipeline robustness

- **Gemma 4 JSON parse fallbacks** (`_parse.py`): `parse_llm_json` now handles two Gemma-class drift modes observed in live Phase 3 eval runs — (a) each L-dimension wrapped in its own `{...}` block separated by commas, and (b) a hybrid shape wrapping 5 pseudo-objects plus a bare trailing `risk_flags` key. Both collapse to a flat object via regex pre-pass; array-merge as a second safety net. Captured ~54% parse-failure rate → 0% on the same gallery.
- **Ollama max_tokens starts at 8192** (`_vlm.py`): Local Ollama models (especially Gemma 4) consistently overflow the cloud-conservative 3072 default on the L1-L5 scoring schema. New `_LOCAL_DEFAULT_MAX_TOKENS=8192` skips the wasted first attempt for local models; cloud models keep the 3072 default + escalation loop.
- **`VULCA_VLM_DEBUG_DUMP` env var** (`_vlm.py`): optional directory path for offline diagnosis of VLM parse failures — dumps raw text + extracted `<scoring>` + `finish_reason` + usage + `max_tokens_used` per call. Pure diagnostic, never affects control flow.
- **KSampler seed randomization** (`providers/comfyui.py`): each `generate()` call now draws its own `secrets.randbelow(2**63)` seed instead of reusing a fixed one, preventing ComfyUI's prompt cache from deduplicating intentional re-runs of the same prompt.

### Release infrastructure

- **Sdist size fix** (`pyproject.toml`): `[tool.hatch.build.targets.sdist]` now excludes `/assets`, `/docs`, `/tests`, `/scripts`, and CI/cache dirs from the source distribution. Prior sdist was 218 MB (blowing past the PyPI 100 MB limit) because hatch was including the full `assets/demo/v2/` master layer PNGs and GIFs. New sdist is ~270 KB. Wheel is unchanged (330 KB, src/vulca/ only).

### E2E runner experimental scaffolding

Dev-only enhancements to `scripts/generate-e2e-demo.py` (not shipped in the wheel). Produced by the prompt engineering experiment documented in `docs/superpowers/specs/2026-04-11-prompt-engineering-experiment-design.md`:

- `TRADITION_PROMPTS` evolved from `list[tuple]` to `list[dict]` with optional `negative` field.
- `negative_prompt` plumbed through `run_phase1_gallery` to the ComfyUI provider.
- `EXPERIMENTAL_PROMPT_OVERRIDES` map + `_validate_experimental_overrides()` startup validator.
- Three composable CLI flags: `--traditions <csv>` (filter to subset, fail-fast on unknown), `--gallery-subdir <name>` (scope Phase 1 output + report to an isolated subdir, baseline untouched), `--seeds-per-tradition <name>:<count>,...` (multi-seed with `_seedN` filename suffix).
- Per-work-item override resolution inside the gallery loop, including `suppress_tradition_suffix` handling to bypass the provider's auto-appended `, {tradition} style` suffix when running experimental overrides.

### Experiment artifacts (committed but not shipped in the wheel)

- `assets/demo/v3/gallery-promptfix/` — 5 PNGs from Stage 1 of the prompt engineering experiment (3 gongbi seeds + xieyi + japanese_traditional) validating that English-first prompts + negative prompts + suppressed auto-suffix rescue SDXL subject fidelity for `chinese_gongbi: 工笔牡丹` (which baseline rendered as yet another mountain landscape).
- `assets/demo/v3/e2e-report-gallery-promptfix.json` — scoped run report with full rubric metadata.
- `assets/demo/v3/gemini-vlm-rescore.json` — Gemini 2.5 Flash second-opinion rescore of all 8 images (3 baselines + 5 experimental) on the same 4-criterion rubric, corroborating the experiment outcome.

### Investigation / memory

- Gemini API billing diagnosis: confirmed the current shared API key is on free tier, which has `limit: 0` for ALL image generation models (`gemini-2.5-flash-image`, `gemini-3-pro-image-preview`, `gemini-3.1-flash-image-preview`, Imagen 4 family). Text and VLM vision work normally. Recorded in `memory/project_gemini_api_billing.md` for future diagnosis.

## [0.14.0] - 2026-04-09

### Defense 3 — A-path Reference Image Fidelity
- **Serial-first orchestration:** First layer generates serially (with optional user reference image), its raw RGB output becomes `style_ref` for remaining parallel layers. Cross-layer style consistency without requiring a user-provided reference.
- **Style anchoring:** Remaining layers receive the first layer's output as `reference_image_b64` via `asyncio.gather`, ensuring visual coherence across the composition.
- **Graceful degradation:** If first layer fails, remaining layers proceed without reference (same as v0.13 behavior). Corrupt cached files logged and skipped.
- **Cache-hit fallback:** When first layer is a cache hit (`raw_rgb_bytes=None`), reads cached RGBA, converts to RGB, and uses that as `style_ref`.
- **Pipeline integration:** `_generate_layers_native` resolves reference from context with priority chain (top-level `reference_image_b64` > `composite_b64` > `image_b64` > `node_params`). Legacy B-path unified with same resolution chain.
- **`LayerOutcome.raw_rgb_bytes`:** New field preserves pre-keyed RGB bytes on fresh generation for accurate style reference derivation.
- **SCHEMA_VERSION "0.14":** Layer cache from v0.13 is invalidated on first run.

### Infra
- **mypy advisory config:** 96/135 modules checked, 39 overridden. `pyproject.toml` `[tool.mypy]`.
- **Test baseline cleanup:** 18 pre-existing failures repaired (importorskip guards, flaky event-loop fix, stale release test removed).
- **Retry exception map:** `docs/retry-exception-map.md` documents the two-layer retry architecture and worst-case 12-call amplification.

### Code quality
- `_apply_alpha` accepts numpy array directly (eliminates redundant PIL decode cycle).
- Empty plan guard before resource allocation.
- Pillow 13 deprecation fix (`mode=` parameter removed from `Image.fromarray`).

### Tests
- 18 new tests in `test_layered_style_ref.py` covering serial ordering, style_ref passthrough, user reference chaining, graceful degradation, single-layer plans, cache-hit fallback, empty plans, RGB normalization.

## [0.13.3] - 2026-04-09

### Cleanup Sweep
- **`_call_provider_with_retry`:** Extracted from `generate_one_layer` as standalone function with retry budget, jitter backoff, and exception classification.
- **`_obtain_validation_report`:** Extracted validation/sidecar logic into standalone function with three-branch flow (sidecar hit, sidecar miss, fresh validation).
- **`provider_capabilities()` lookup:** New function in `vulca.providers` for coarse capability inspection without instantiating providers.
- **`ImageProvider.capabilities`** defaults to `frozenset()` on the Protocol.
- **Mock literal elimination:** All `"mock"` string comparisons in pipeline replaced with `"raw_rgba" in capabilities` checks.
- **ValidationReport sidecar round-trip test:** Contract test for serialize/deserialize cycle.

## [0.13.2] - 2026-04-08

### A-path Hardening (P2 Cleanup)

#### Correctness
- `_apply_alpha` asserts shape match between RGB and alpha (no silent resize).
- `LayerCache.put` atomic via `tempfile + os.replace` (no partial writes on crash).
- Tier-2 keying loader wraps `ModuleNotFoundError`/`AttributeError` → `ValueError`.
- `AssertionError`/`TypeError` propagate out of `layered_generate` orchestration (not silently converted to `generation_failed`).

#### Performance
- **Validation sidecar cache:** `<key>.report.json` stored alongside keyed PNGs. Cache hits skip `validate_layer_alpha` entirely.
- **Cache write reuse:** `cache.put` reads disk bytes from `rgba_img.save(out_path)` instead of re-encoding through PIL.

#### Retry
- In-process retry budget=2 (3 total attempts) with full-jitter backoff `random.uniform(0, 0.5 * 2**attempt)`.
- `AssertionError`/`TypeError`/`asyncio.CancelledError` propagate immediately (not retried).
- `LayerFailure.reason` is now `Literal["generation_failed", "validation_failed"]`.

#### Provider capabilities
- `ImageProvider.capabilities: frozenset[str]` — real providers declare `{'raw_rgba'}`, mock declares `frozenset()`.
- `_provider_supports_native` queries capabilities (no `"mock"` string match).

#### Manifest & retry polish
- `layer_extras` whitelist (8 keys, raises on unknown).
- `retry_layers` preserves non-validation manifest warnings and drops stale validation warnings for retried layers.

## [0.13.1] - 2026-04-08

### Fixes (codex review nice-to-haves from v0.13.0)
- **ChromaKeying linear RGB**: distance is now computed in linear RGB (sRGB gamma-decoded) instead of on raw sRGB bytes. Subject separation on colored canvases is now perceptually consistent with the docstring.
- **`_box_blur` vectorization**: replaced the Python per-pixel integral-image loop with full-frame numpy slicing. 512×512 box blur now runs in single-digit ms instead of seconds.
- **`_despill` gating**: no longer erodes alpha on solid interior. Only pixels in the soft-edge band (0.02 < alpha < 0.98) that are close to the background color get attenuated (up to 50% by default).

### Test coverage
- `test_chroma_operates_in_linear_rgb_not_srgb` pins the gamma-decode behavior.
- `test_box_blur_matches_reference_and_is_fast` checks output against a naive per-pixel reference AND enforces a 0.5s budget on 512×512.
- `test_despill_preserves_solid_interior` asserts solid opaque interior stays at alpha >= 0.999 and the edge band still attenuates.

## [0.13.0] - 2026-04-08

### Layered Generation — A-path (generation-time alpha)
- **New keying subsystem** (`vulca.layers.keying`): hand-rolled sRGB→LAB, `CanvasSpec` + `KeyingStrategy` protocol, tier-0 luminance keying (the WOW unlock for ink wash), tier-1 chroma + Delta-E keying, strategy registry.
- **Validation** (`vulca.layers.validate`): coverage / position-IoU / emptiness checks with structured warnings.
- **Tradition config +5 fields**: `layerability`, `canvas_color`, `canvas_description`, `style_keywords`, `key_strategy` rolled out to all 13 traditions. `chinese_xieyi` is the hero case.
- **Anchored layered prompt builder** with canvas / content-exclusivity / spatial / style anchors.
- **Layered generation library** (`vulca.layers.layered_generate`): `generate_one_layer` + concurrent `layered_generate` with semaphore-bounded orchestration and partial-failure non-blocking semantics.
- **Per-artifact sidecar cache** (`.layered_cache/`) keyed on provider + model + prompt + canvas + schema version.
- **Pipeline dispatch**: `LayerGenerateNode` routes native traditions through the new library (A-path). Split / discouraged traditions keep the v0.12 VLM-mask path.
- **Spatial metadata passthrough**: `plan_layers` forwards VLM `position`/`coverage` onto `LayerInfo` for the anchored prompt.

### B-path matting
- `soften_mask` with feather + optional `cv2.ximgproc.guidedFilter` + despill (pure-numpy fallback).
- `apply_vlm_mask` now softens the alpha channel on save for B-path edge quality.

### Manifest v3
- New top-level fields: `generation_path` (a / b), `layerability`, `partial`, `warnings`, plus per-layer extras (`source`, `cache_hit`, `attempts`, `validation`).
- `CompositeNode` writes `manifest.json` alongside `artifact.json` for every LAYERED run.

### CLI
- `vulca create --layered` gains `--no-cache`, `--strict`, `--max-layers` and a proper output directory.
- `vulca layers retry <dir> [--layer NAME | --all-failed]` — re-run failed layers through `layered_generate` with cache reuse.
- `vulca layers cache clear <dir>` — drop the sidecar cache.
- `discouraged` tradition warning on `--layered` (stderr or interactive y/N prompt).

### MCP
- New tools: `vulca_layered_create`, `vulca_layers_retry`.

### Tests
- Unit tests for every keying tier, validation, anchored prompt, cache, `generate_one_layer`, orchestration, manifest v3.
- E2E tests: A-path on chinese_xieyi (mock) and partial-failure on a flaky provider.
- Gated golden test (`--run-real-provider`) comparing 16-bin alpha histograms against a baseline JSON.

### Notes
- Defense 3 (reference image conditioning) is interface-only in v0.13; full implementation deferred to v0.14 per spec.
- No separate in-process counter module — telemetry lives in the manifest via `cache_hit` / `attempts` / `validation` per-layer extras.

## [0.12.0] - 2026-04-07

### Layer Primitives — Spatial + Opacity + Blend Modes
- **LayerInfo spatial fields**: `x`, `y`, `width`, `height`, `rotation` (percentage-based, resolution-independent), `content_bbox` (auto-computed pixel coords)
- **`opacity` field now affects compositing**: 0.0–1.0 alpha multiplier applied during blend
- **Spatial transform engine** (`transform.py`): apply rotation + spatial coords to layer images, with content_bbox tracking
- **`transform_layer` operation**: programmatic layer transform via SDK
- **MCP `layers_transform` tool**: agent-driven spatial manipulation
- **CLI `vulca layers transform`** subcommand
- **6 new blend modes**: `overlay`, `soft_light`, `darken`, `lighten`, `color_dodge`, `color_burn` (joined existing `normal`, `screen`, `multiply`)

### New Split Modes — Two Pixel-Precise Methods
- **`split_vlm`** (Gemini-based semantic split):
  - Per-layer BW mask generation via Gemini image model
  - Custom `prompt` parameter on `generate_vlm_mask`
  - Foreground-first exclusive pixel assignment + background fallback (`~assigned`)
  - Degenerate mask detection (std<10) → fallback to color mask
  - **Validated end-to-end**: composite roundtrip diff = 0.00 on hero-shanshui.jpg
  - Best for: stylized art (ink wash, post-impressionist), recognizable objects with details (trees, characters)
- **`split_sam3`** (SAM3 text-prompted segmentation):
  - Uses `transformers.Sam3Processor` + `Sam3Model` (`facebook/sam3`)
  - Direct text prompts from `info.description` — no point-prompt heuristics
  - Pixel-precise multi-instance OR combination for full concept coverage
  - Resize handling (model resolution → original image size)
  - **Validated end-to-end**: composite roundtrip diff = 0.00 on synthetic + shanshui
  - Best for: large structural elements with clear boundaries (mountains, terrain, well-defined subjects)
  - Requires `pip install vulca[sam3]` (transformers ≥ 4.50, torch ≥ 2.0) + CUDA GPU

### CLI / MCP / SDK Wiring
- **CLI**: `vulca layers split --mode {regenerate,extract,sam,vlm,sam3}` (5 modes)
- **MCP**: `layers_split(image_path, mode="vlm"|"sam3", ...)` routes to new modes
- **SDK**: `from vulca.layers import split_vlm, sam3_split, SAM3_AVAILABLE`

### Fixes
- **`gemini.py` mime type detection**: Hardcoded `image/png` caused Gemini to hang on JPEG inputs (90s timeout). Now detects format from magic bytes (JPEG, PNG, GIF, WebP). **Affects all callers of `GeminiImageProvider` with reference images, not just split_vlm**.
- **SAM3 tensor handling**: Fixed `Boolean value of Tensor with no values is ambiguous` error. SAM3 PCS returns `Tensor[N, mask_h, mask_w]`; combine all instances above threshold via OR for full concept coverage.
- **SAM3 resolution handling**: Resize model output (e.g., 288×288) to original image size via PIL NEAREST.
- **`split_vlm` review fixes**: docstring update, dead `io as _io` import removal, `assigned` array passthrough to `build_color_mask` fallback for consistency.
- **Test fixtures**: Replace deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()` to prevent `RuntimeError` in full test suite execution.

### Tests
- **+26 new tests**: `test_v012_split_vlm.py` (14 tests) + `test_v012_split_sam3.py` (12 tests)
- All tests are mock-based (no GPU/API key needed for CI)
- Real-provider validation completed on RTX 2070 + Gemini API: composite roundtrip diff = 0.00

### Optional Dependencies
```toml
sam3 = ["transformers>=4.50", "torch>=2.0", "numpy>=1.24", "Pillow>=10.0"]
```

### Coverage Strategy (3-mode complementarity)
| Concept type | Recommended mode | Reason |
|---|---|---|
| Mountains, terrain, large structures | `sam3` | Pixel-precise, recognizes structural shapes |
| Trees, characters, detailed objects | `vlm` | Semantic understanding, captures fine details |
| Geometric shapes, clear boundaries | `sam3` | Sharp edges |
| Stylized art, abstract brushstrokes | `vlm` | Contextual understanding |
| No GPU + no API key | `extract` | Zero-dep fallback |

These modes are **complementary, not replacements** — use them together via AI Agent orchestration through MCP/CLI.

---

## [0.11.0] - 2026-04-04

### Layer Semantics — Phase 3 Integrity Fixes
- **VLM mask shared module**: Extracted `vlm_mask.py` for two-pass mask generation (used by regenerate mode + LAYERED pipeline)
- **VLM mask fallback**: Use generated image as input (not source) when initial mask fails
- **Public `hex_to_rgb` API**: Color utility now exported
- **Round-trip integrity tests**: `composite(split(img)) ≈ img` validation
- **Empty `dominant_colors` guard**: Preserve transparent layers when VLM cannot identify colors
- **`info.id` as layer_masks key**: Prevent name collision when multiple layers share names
- **SAM medoid point**: Closest pixel to color centroid (not centroid itself, which can fall outside non-convex shapes)
- **VLM mask degenerate rejection**: Reject masks with `std<10` (no useful segmentation signal)
- **SAM point prompts from color centroid**: Compute layer point from `dominant_colors` instead of using image center
- **Deduplication**: Cleaner separation between mask generation and application

### Cleanup
- **Dead code removal**: 76 orphaned files + v0.2.0 vulca copy
- **Broken imports**: Fixed all references to deleted modules
- **6 unreachable prototype subdirs deleted**

---

## [0.10.0] - 2026-04-01

### LAYERED Pipeline — Structured Creation
- **LAYERED template**: PlanLayers -> LayerGenerate (2-node). Agent orchestrates composition, evaluation, and iteration via MCP tools (layers_composite, evaluate_artwork, layers_redraw)
- **PlanLayersNode**: VLM plans layer structure from text intent with tradition layer order knowledge (xieyi, gongbi, japanese, photography)
- **LayerGenerateNode**: Per-layer "full-scene + focus" generation with style anchor + reference conditioning
- **CompositeNode**: Blend layers + write Artifact V3 structured creation document
- **DecideNode enhancement**: Per-layer accept/rerun decisions; only regenerate weak layers in subsequent rounds
- **Artifact V3 format**: V2 superset with cultural_context, per-layer scores, creation history, export_hints
- **Tradition layer orders**: Canonical layer sequences in 5 YAML files, loaded at runtime with Python fallback
- **Entry points**: CLI `--layered`, MCP `layered=True`, SDK `layered=True`

### Export-Time Alpha Processing
- **`alpha.py`**: Chroma key + content_type strategy selection (background=opaque, text=chroma, subject=rembg, effect=sam2)
- **`export_with_alpha()`**: Export layers with transparency based on content type
- **Optional deps**: `pip install vulca[rembg]` for ML background removal, `vulca[layers-full]` for rembg + SAM2

### Fixes
- **CompositeNode**: Use tempdir instead of hardcoded `/tmp/vulca_composite/`
- **LayerGenerateNode**: Fix provider integration (`get_image_provider` + `ImageResult` handling)
- **PlanLayersNode**: Use `gemini-2.5-flash` (not deprecated `gemini-2.0-flash`)
- **README Scenario 2b**: Replace "UI Component Extraction" with "Parallax Hero Sections"

### Architecture Simplification (post-0.10.0)
- **LAYERED template simplified**: 5 nodes → 2 nodes (PlanLayers → LayerGenerate). Agent orchestrates composition via MCP tools (layers_composite, evaluate_artwork, layers_redraw)
- **Alpha extraction separated from blend**: blend.py is pure math, alpha.py handles ML-based extraction via ensure_alpha()
- **Background layer safety**: _build_prompt overrides VLM-planned content for background layers, forcing texture-only generation
- **OpenAI gpt-image-1**: Native transparency support with background:"transparent"

## [0.9.2] - 2026-03-30

### Release Automation + Dead Code Cleanup
- **`scripts/release.sh`**: One-command release (version bump + subtree push x3 + PyPI + GitHub releases x4)
- **Dead code audit**: Removed unused imports, stale references across 12 files

## [0.9.1] - 2026-03-30

### Tool Protocol — Hybrid Pipeline with Algorithmic Nodes
- **VulcaTool protocol**: Unified tool contract with ImageData, VisualEvidence, ToolConfig, ToolRegistry auto-discovery
- **5 algorithmic tools**: WhitespaceAnalyzer (L1), CompositionAnalyzer (L1), ColorGamutChecker (L3), BrushstrokeAnalyzer (L2), ColorCorrect (filter)
- **3 platform adapters**: CLI (`vulca tools`), SDK (`from vulca.tools import`), MCP (`tool_*` auto-registered)
- **Pipeline hybrid execution**: `_resolve_nodes()` falls back to ToolRegistry; EvaluateNode auto-detects algo-covered dimensions
- **CULTURAL_XIEYI template**: generate → whitespace_analyze → color_gamut_check → composition_analyze → evaluate → decide
- **VisualEvidence**: Every tool produces annotated images + confidence scores + structured details
- **`replaces` mechanism**: Tools declare which VLM dimensions they can replace (e.g., `{"evaluate": ["L1"]}`)

## [0.9.0] - 2026-03-29

### Layered Generation
- **VLM layer analysis**: Decompose artwork into semantic layers (background, midground, foreground, detail)
- **Per-layer generation**: Chromakey isolation + independent regeneration per layer
- **Layer composite**: Reassemble layers with bbox offset paste
- **PSD/PNG export**: Export with layer manifest (manifest.json with bbox + bg_color metadata)
- **CLI**: `vulca layers analyze`, `vulca layers export`, `vulca layers composite`
- **MCP**: `analyze_layers`, `layers_composite`, `layers_export`, `layers_evaluate`, `layers_regenerate`

### Inpainting
- **Region-based inpainting**: PIL local blend replaces full regeneration — pixels outside bbox guaranteed unchanged
- **VLM-guided**: Tradition-aware repaint prompts with cultural terminology injection
- **CLI**: `vulca inpaint` command
- **MCP**: `inpaint_artwork` tool
- **SDK**: `vulca.inpaint()` public API

### Hex Color Input
- Palette accepts `#hex` values with strict prompt injection into generation

### ComfyUI Parity
- 11 nodes (up from 8): added Evolution, Traditions, LayersExport nodes
- 18 tests pass

### MCP Parity
- 18 tools (up from 13): added `sync_data`, `layers_*`, `layers_regenerate`

### Testing
- 813 tests (up from 603), strict TDD red-green discipline

## [0.8.0] - 2026-03-29

### Multi-round img2img Iteration (P0-A)
- **Round-to-round reference**: Selected concept from Round N becomes reference for Round N+1 variations
- **Variation strength inference**: Auto-detects strength from NL update keywords (refine=0.2, change=0.4, redo=0.7)
- **Auto-stop suggestion**: Triggers when score >= 85% or converges (< 3% delta for 2 rounds)
- **Round-separated storage**: Concept images saved to `r{N}/concepts/` instead of overwriting

### VLM Analysis Depth (P0-B)
- **Two-phase prompt**: OBSERVE (visual analysis) → EVALUATE (scoring), replacing single-pass scoring
- **Per-dimension observations**: 3-5 factual visual observations per L1-L5 dimension
- **Reference techniques**: Most relevant traditional technique name per dimension (bilingual)
- **Enhanced suggestions**: Now include technique name + how to apply + expected effect
- `max_tokens` increased from 4096 to 6144

### CLI Unification (P0-C)
- **9 unified commands**: evaluate, create, traditions, tradition, evolution, studio, brief, brief-update, concept
- **Click dependency removed**: All commands now use argparse (stdlib)
- `vulca sync` command for cloud data synchronization

### Data Flow (P1-A)
- **LocalEvolver**: Reads `~/.vulca/data/sessions.jsonl` for local evolution
- **Local evolved_context**: VLM reads `~/.vulca/evolved_context.json` before YAML defaults
- **vulca sync**: Push local sessions to cloud, pull aggregated evolved weights (asymmetric)

### Sketch & Reference Upload (P1-B)
- **All entry points**: CLI (`--sketch`, `--reference`, `--ref-type`), SDK, MCP
- **3 reference types**: `style` (color/brushwork only), `composition` (layout only), `full` (both)
- **Dual input mode**: File path or base64 string, auto-detected
- `resolve_image_input()` utility for path/base64 resolution

### Commercial Extra Dimensions (P1-C)
- **Tradition-specific E1-E3**: Up to 3 extra evaluation dimensions per tradition YAML
- **brand_design**: Brand Consistency, Target Audience Fit, Market Differentiation
- **ui_ux_design**: Usability Clarity, Platform Convention, Interaction Affordance
- **photography**: Technical Exposure, Narrative Moment, Print/Screen Readiness
- Extra scores independent from L1-L5 total (displayed separately)

### Testing
- 603 tests (up from 538), strict TDD red-green discipline (15 RED→GREEN cycles)

## [0.7.0] - 2026-03-28

### Selective Pipeline
- **Agent Residuals**: Selective aggregation of agent outputs — only consume what downstream nodes actually need
- **Cultural Engram**: Hash-indexed cultural knowledge retrieval — terminology and taboos injected via REPLACE (not append)
- **Sparse Eval**: BriefIndexer activates only relevant L1-L5 dimensions per Brief, skipped dimensions get baseline scores
- **Quantized Retrieval**: Zero-training session search for few-shot example selection

### Integrity Fixes
- Reset collapsed evolution weights to YAML defaults
- Replace mock return values with proper errors in production paths
- Evolution guard requires 3+ real human feedback entries before evolving
- Full evolution reset: counter, cultures, few-shot, insights

### CLI
- `--residuals` flag for selective agent output aggregation
- `--sparse-eval` flag for Brief-driven dimension activation

### VLM Integration
- Engram fragments REPLACE terminology/taboos instead of appending (prevents prompt bloat)
- Sparse dimensions integrated into VLM scoring prompts

### Testing
- 538 tests (up from 455), strict TDD red-green discipline
- 8 evolution guard boundary cases

## [0.6.0] - 2026-03-25

### Studio Intelligence (Phase 2)
- **LLM Intent Parsing**: `parse_intent_llm()` uses Gemini 2.5 Flash for implicit element extraction (0% -> 84% capture rate)
- **LLM Dynamic Questions**: `generate_questions_llm()` domain-adaptive question generation
- **LLM NL Update**: `parse_nl_update_llm()` complex Chinese instruction parsing (6/10 -> 1/10 fallback)
- **Keyword Extraction**: element/palette/composition regex for Chinese + English
- **Tradition Keywords**: expanded from 8 to 45+ mappings (60% -> 90% detection)
- **Dynamic Questions**: conditional question generation based on Brief state + free-text option
- **Mock Scoring**: hash-based variation by session/round/completeness (0% -> 80% variation)
- **Sketch Upload**: integrated into interactive flow

### Digestion V2 (Phase 3)
- **JsonlStudioStorage**: unified JSONL storage for sessions, artifacts, and signals
- **ArtifactAnalysis**: L1-L5 structured analysis types (L1-L5 dataclasses with serialization)
- **SessionPreferences**: Layer 1 real-time preference accumulation with prompt hints
- **Trajectory Analysis**: Layer 2 mood drift, cultural fidelity, composition preservation
- **Preloader**: Layer 0 pre-session intelligence from history + keyword matching
- **Evolver**: Layer 3 cross-session pattern detection + weight evolution (mock-data-protected)
- **Archiver**: local cold storage for session archival
- **Alembic Migration**: 5-table schema (studio_sessions, artifacts, signals, evolved_patterns, brief_templates)

### Studio Polish (Phase 4)
- **Concept Preview**: shows filename + file size
- **Style Weight Adjustment**: interactive 70/30 input for multi-style
- **Preloader Wired**: Layer 0 suggestions shown at session start

### Testing
- 455 tests (up from 376)
- 10/10 E2E agent test pass rate (up from 0/10)
- Strict TDD red-green commit discipline (44 commits)

## [0.5.0] - 2026-03-24

### Studio Pipeline V2
- Brief-driven creative collaboration (Intent -> Concept -> Generate -> Evaluate -> Refine)
- Natural language Brief updates with deterministic rollback
- Interactive terminal UI (`vulca studio`)
- CLI commands: `vulca brief`, `vulca brief-update`, `vulca concept`
- MCP tools: `studio_create_brief`, `studio_update_brief`, `studio_generate_concepts`, `studio_select_concept`
- ComfyUI custom nodes (5 nodes)

## [0.4.0] - 2026-03-24

### Judge -> Advisor
- Evaluation mode: `strict` | `reference` | `fusion`
- `reference` mode: advisor, not judge
- HITL / custom weights across all 4 entry points (Canvas, CLI, SDK, MCP)

## [0.3.0] - 2026-03-22

### MCP v2 + Provider Refactor
- 6 MCP tools via FastMCP
- Pluggable ImageProvider + VLMProvider protocols
- CLI/SDK/MCP share ONE engine: `vulca.pipeline.execute()`
