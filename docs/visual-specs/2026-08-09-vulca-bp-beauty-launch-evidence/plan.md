---
slug: 2026-08-09-vulca-bp-beauty-launch-evidence
status: completed
domain: brand_visual
tradition: null
schema_version: "0.1"
generated_by: visual-plan@0.1.0
design_ref: docs/visual-specs/2026-08-09-vulca-bp-beauty-launch-evidence/design.md
created: 2026-08-09
updated: 2026-08-09
---

# VULCA BP Beauty Launch Dual-Evidence Visual Series - Execution Plan

## A. Execution parameters

```yaml
reviewed: true
provider: openai
execution_route: codex_imagegen
model: gpt-image-2
quality: high
target_size: 2560x1440
provider_landscape_size: 1536x1024
output_format: png
seed: 1337
steps: null
cfg_scale: null
max_real_generation_calls: 3
source_asset_policy: generated_brand_neutral
vulca_source_invocation: "PYTHONPATH=src python3 -m vulca.cli"
```

## B. Iteration plan

```yaml
reviewed: true
strategy: bounded_hero_candidates_then_real_evidence
variation_axis: "commercial hero treatment"
seed_list: [1337, 1338]
pixel_candidate_count: 2
final_asset_count: 4
batch_size: 2
final_assets:
  - commercial_hero
  - enterprise_task
  - actual_vulca_run
  - before_layer_target_after
```

## C. Prompt composition

```yaml
reviewed: true
style_treatment: unified
composed_prompts:
  - name: candidate_a_product_restraint
    prompt: |
      Create a premium, brand-neutral commercial beauty campaign master image
      for a fictional lipstick launch. Landscape composition with a safe 16:9
      crop. Place one coherent fictional lipstick product family on the right:
      two precisely designed cylindrical objects with matte warm-ivory lacquer,
      one controlled carmine product accent, restrained ink-black detailing,
      and a very small cobalt-blue structural accent. No logo, no brand name,
      no letters, no numbers, and no readable packaging text. Keep the left
      45 percent quiet and low-detail for later Chinese deck typography.

      Dominant direction: Apple-like restraint, whitespace, product credibility,
      material precision, precise edges, calm reflections, and generous breathing
      room. Secondary direction: Claude-like warmth, calm editorial humanity,
      and soft tonal transitions. Smaller influence: Kimi-like concise AI-product
      sharpness. These are qualities only, not copied brand identity.

      Express China and United Kingdom launch readiness through globally credible
      contemporary editorial styling, not flags, landmarks, porcelain, dragons,
      lanterns, Union Jack motifs, or national-color shorthand. No advertising
      copy, UI panels, dashboards, robots, neon circuitry, fake metrics, fake
      logos, extra products, warped cylinders, microtext, or recognizable beauty
      campaign imitation. Photorealistic premium studio product photography,
      warm ivory background, ink-black structure, carmine accent, sparse cobalt.
  - name: candidate_b_editorial_warmth
    prompt: |
      Create a premium, brand-neutral commercial beauty campaign master image
      for a fictional lipstick launch, landscape with safe 16:9 crop. Keep one
      repeatable fictional lipstick family on the right: two matte warm-ivory
      cylindrical packages, precise cap seams, one carmine lipstick accent,
      restrained ink-black detailing, and a tiny cobalt-blue construction line.
      No logos, words, letters, numbers, or packaging text. Reserve the left
      45 percent as calm negative space for Chinese presentation copy.

      Use Apple-like material credibility and whitespace as the foundation,
      Claude-like warm editorial atmosphere as a stronger emotional layer, and
      a small amount of Kimi-like crisp AI-product energy. Add one subtle folded
      paper or satin plane behind the product and a controlled carmine shadow arc
      to imply a campaign system without adding decoration. Precise cosmetic
      surfaces, stable three-quarter camera angle, believable contact shadows,
      soft daylight-to-studio tonal transition, one unified premium image.

      Culturally neutral and localization-ready for China and the United Kingdom;
      no flags, landmarks, porcelain, dragons, lanterns, Union Jack motifs,
      red-and-gold cliché, generated copy, UI, dashboards, robots, neon, fake
      metrics, fake logos, extra products, distorted cylinders, or imitation of
      a recognizable beauty brand or campaign.
negative_prompt: ""
sketch_integration: ignore
ref_integration: none
```

## D. Gating decisions

```yaml
reviewed: true
thresholds:
  L1: {value: 0.75, source: assumed, gate_class: soft}
  L2: {value: 0.80, source: assumed, gate_class: soft}
  L3: {value: 0.70, source: assumed, gate_class: soft}
  L4: {value: 0.75, source: assumed, gate_class: soft}
  L5: {value: 0.65, source: assumed, gate_class: soft}
user_elevated: []
soft_gate_warn_count: 0
hard_visual_gates:
  - no generated text or logo
  - no unexpected extra product
  - one dominant product family readable within two seconds
  - left copy-safe area remains quiet
  - no recognizable existing beauty trade dress
  - product geometry remains suitable for semantic decomposition
```

## E. Fail-fast budget + rollback

```yaml
reviewed: true
fail_fast_consecutive: 2
rollback_trigger: "unified revision changes protected product geometry, color, camera, or non-target pixels"
rollback_action: "switch to additive edit using VULCA-produced target mask while preserving approved source pixels"
provider_failure_action: "record exact boundary and stop rather than inventing live evidence"
```

## F. Cost ledger

```yaml
reviewed: true
initial_budget:
  max_real_calls: 3
  per_gen_sec: {value: 234, source: derived, confidence: med}
  total_session_sec: {value: 701, source: derived, confidence: low}
actual:
  total_calls: 3
  total_cost_usd: null
  total_wall_time_sec: 70.8
  provider: openai
  model: gpt-image-2
overage_pct: "under budget (-89.9%)"
```

## Results

| iter | seed | variant | image | L1-L5 | weighted | verdict | wall_time | provider | notes |
|---:|---:|---|---|---|---:|---|---:|---|---|
| 0 | 1337 | product restraint | `iters/1337/candidate_a.png` | .92/.90/.75/.86/.65 | .816 | accept-with-warning | 16.3s | GPT Image 2 | Strong product credibility; campaign emotion is restrained. |
| 1 | 1338 | editorial warmth | `iters/1338/candidate_b.png` | .89/.86/.84/.85/.72 | .832 | reject | 17.5s | GPT Image 2 | Rejected: one unexpected extra package. |
| 2 | 1339 | focused correction | `iters/selected/hero_final.png` | .90/.89/.88/.89/.73 | .858 | accept-with-warning | 37.0s | GPT Image 2 | Selected: extra package removed; protected scene retained. |

## Notes

[resume-state] turns_used: 0

[user-override] The user explicitly instructed Codex to complete all remaining work automatically and stop requesting stage-by-stage confirmation. The plan therefore enters `running` without an additional conversational review pause.

[design-hash] `1ca24c4ae96596dbb834ef0c1e55883f322a4152475b1b4df59679a1174eeab5`

[provider-boundary] GPT Image 2 pixels are rendered through the Codex image-generation route because the shell has no OpenAI provider key. Local VULCA source commands must produce the brief, analysis, decomposition, constraint, revision, review, and adoption evidence that is actually shown.

[runtime] The valid source CLI is `PYTHONPATH=src python3 -m vulca.cli`. The stale global `/opt/homebrew/bin/vulca` command is excluded from evidence. Local ComfyUI is offline.

[evidence] Beauty remains a clearly labelled VULCA demonstration, not a customer case.

[review-required] Iter 0 and iter 2 scores are assistant pixel-review drafts. The configured remote VULCA evaluator is rubric-only and the local live VLM is unavailable; no human-confirmed score is claimed.

[hard-visual-gate] Iter 1 rejected because three product units violated the frozen two-unit constraint.

[selection] Iter 2 is the selected commercial hero. It preserves the higher-energy campaign world from iter 1 while removing the redundant back-center package.

[terminal] Three real GPT Image 2 calls completed; two outputs were usable with evidence-bound review warnings and one was rejected by a hard visual constraint.
