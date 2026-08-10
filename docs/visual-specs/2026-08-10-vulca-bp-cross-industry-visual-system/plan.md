---
slug: 2026-08-10-vulca-bp-cross-industry-visual-system
status: completed
domain: brand_visual
tradition: null
schema_version: "0.1"
generated_by: visual-plan@0.1.0
design_ref: docs/visual-specs/2026-08-10-vulca-bp-cross-industry-visual-system/design.md
created: 2026-08-10
updated: 2026-08-10
---

# VULCA BP Cross-Industry Visual System - Execution Plan

## A. Execution parameters

```yaml
reviewed: true
provider: openai
execution_route: codex_imagegen
model: gpt-image-2
quality: high
output_format: png
seed: 3101
steps: null
cfg_scale: null
max_real_generation_calls: 4
```

## B. Iteration plan

```yaml
reviewed: true
strategy: sequential_cross_industry_assets
variation_axis: "asset role"
seed_list: [3101, 3102, 3103, 3104]
variant_count: 4
batch_size: 1
variants:
  - company_cover
  - consumer_product
  - industrial_manufacturing
  - cultural_tourism_localization
```

## C. Prompt composition

```yaml
reviewed: true
composed_prompts:
  - "Industry-neutral enterprise visual-intelligence cover: several kinds of source objects and blank channel formats connected by one precise cobalt control line; right-weighted 16:9 composition; no single vertical dominates."
  - "Premium fictional consumer-product launch: tactile tea or home-product packaging shown as a credible multi-channel campaign system; warm editorial materials; no readable copy or logo."
  - "Precision industrial manufacturing catalog: compact robotic module or machined assembly with stable geometry, material finish, and multiple controlled product views; no people, text, or logo."
  - "Contemporary cultural-tourism localization campaign: a credible coastal heritage destination with modular editorial crops and restrained cross-market adaptability; no flags, token symbols, text, or logo."
negative_prompt: "logo, trademark, readable text, letters, numbers, watermark, fake UI, fake metrics, robot character, glowing brain, neon circuitry, flag, national stereotype, cluttered collage"
```

## D. Gating decisions

```yaml
reviewed: true
thresholds:
  L1: {value: 0.75, source: assumed, gate_class: soft}
  L2: {value: 0.78, source: assumed, gate_class: soft}
  L3: {value: 0.75, source: assumed, gate_class: soft}
  L4: {value: 0.75, source: assumed, gate_class: soft}
  L5: {value: 0.65, source: assumed, gate_class: soft}
user_elevated: []
soft_gate_warn_count: 0
hard_visual_gates:
  - no generated copy or fake branding
  - cover is industry-neutral
  - three scenarios have distinct business roles
  - composition remains legible at presentation distance
```

## E. Fail-fast budget + rollback

```yaml
reviewed: true
fail_fast_consecutive: 2
rollback_trigger: "generated copy, fake branding, category ambiguity, or low-quality subject geometry"
rollback_action: "preserve successful outputs; stop the failed role rather than use a misleading image"
```

## F. Cost ledger

```yaml
reviewed: true
initial_budget:
  max_real_calls: 4
  per_gen_sec: {value: 240, source: derived, confidence: low}
  total_session_sec: {value: 1440, source: derived, confidence: low}
actual:
  total_calls: 4
  total_wall_time_sec: 127.0
  provider: openai
  model: gpt-image-2
overage_pct: "under budget (-91.2%)"
```

## Results

| iter | seed | variant | image | L1-L5 | weighted | verdict | wall_time | provider | notes |
|---:|---:|---|---|---|---:|---|---:|---|---|
| 0 | 3101 | company cover | `iters/3101/company_cover.png` | .92/.91/.90/.88/.78 | .878 | accept | 24.5s | GPT Image 2 | Industry-neutral, right-weighted, copy-safe cover. |
| 1 | 3102 | consumer product | `iters/3102/consumer_product.png` | .90/.91/.89/.86/.73 | .858 | accept | 19.8s | GPT Image 2 | Fictional blank-label consumer campaign system. |
| 2 | 3103 | industrial manufacturing | `iters/3103/industrial_manufacturing.png` | .94/.92/.90/.90/.78 | .888 | accept | 39.5s | GPT Image 2 | Mechanically credible module with consistent detail views. |
| 3 | 3104 | cultural tourism | `iters/3104/cultural_tourism_localization.png` | .91/.88/.90/.87/.75 | .862 | accept | 43.2s | GPT Image 2 | Fictional destination with coherent channel crops and no token symbols. |

## Notes

[user-override] The user explicitly asked Codex to continue and previously authorized automatic completion without stage-by-stage confirmation. The corrected cross-industry plan therefore enters `running`.

[boundary] All generated industries are fictional demonstrations, not customer cases or traction evidence.

[design-hash] `092e43d7381a0fee0f553dc2dd85db4457db5f071df2255eb120d8c6b6d11e63`

[review-required] L1-L5 values are assistant visual-review drafts used for asset selection. They are not VULCA evaluator output or human-confirmed scores.

[ui-evidence] `evidence/prompt-studio-actual-ui.png` is a local screenshot of the source widget with a fictional industrial task payload. It is a product preview, not a reconstructed dashboard or customer session.

[presentation-derivatives] `evidence/prompt-studio-actual-ui-padded.png` only adds a white safety margin around the same local screenshot. `evidence/beauty-target-overlay.png` is a mechanical composite of the existing beauty candidate and human-confirmed target mask, used to make the recorded edit target legible in the BP; neither file adds a customer or outcome claim.

[terminal] Four distinct GPT Image 2 assets completed and passed the hard visual gates. No generated text, fake branding, or single-industry cover was adopted.
