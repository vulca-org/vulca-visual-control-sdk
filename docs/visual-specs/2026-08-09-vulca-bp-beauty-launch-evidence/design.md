---
slug: 2026-08-09-vulca-bp-beauty-launch-evidence
status: resolved
schema_version: "0.1"
domain: brand_visual
tradition: null
generated_by: visual-spec@0.1.0
proposal_ref: docs/visual-specs/2026-08-09-vulca-bp-beauty-launch-evidence/proposal.md
created: 2026-08-09
updated: 2026-08-09
---

# VULCA BP Beauty Launch Dual-Evidence Visual Series - Technical Design

## A. Provider + generation params

```yaml
reviewed: true
provider: openai                    # source: derived, confidence: high
model_primary: gpt-image-2          # source: user-directed, confidence: high
model_fallback: null                # do not silently downgrade the rendering model
quality: high                       # source: derived, confidence: med
input_fidelity: null                # unsupported path is not claimed
target_size: 2560x1440              # source: copied from proposal, confidence: high
provider_size: 1536x1024            # source: derived, confidence: med
output_format: png
seed: 1337                          # source: assumed, confidence: low; OpenAI may ignore
steps: null                         # OpenAI ignores diffusion-step controls
cfg_scale: null                     # OpenAI ignores CFG controls
candidate_count: 2                  # source: copied from proposal, confidence: high
max_focused_corrections: 1          # source: copied from proposal, confidence: high
source_asset_policy: generated_brand_neutral
execution_boundary: "GPT Image 2 renders pixels; the local VULCA source workflow records brief, constraints, layers, revision, review, and adoption evidence."
```

## B. Composition strategy

```yaml
reviewed: true
strategy: series
variation_axis: "evidence_role: commercial hero -> enterprise task -> actual VULCA run -> control proof"
variant_count: 4
shared_identity: "one fictional lipstick product, one camera family, one carmine shade, one campaign world"
hero_layout: "landscape 16:9; product group on right 55%; quiet negative space on left 45% for Chinese deck copy"
evidence_layout: "large four-state sequence; each state remains legible at presentation distance; no thumbnail grids"
delivery_mapping:
  slide_1: commercial_hero
  slide_3: enterprise_task
  slide_4: actual_vulca_run
  slide_5: before_layer_target_after
```

## C. Prompt composition

```yaml
reviewed: true
style_treatment: unified
base_prompt: |
  Create a premium, brand-neutral commercial beauty campaign master image for a
  fictional lipstick launch. Landscape composition designed to crop safely to
  16:9. Place one coherent fictional lipstick product family on the right side:
  two precisely designed cylindrical objects with matte warm-ivory lacquer,
  one controlled carmine product accent, restrained ink-black detailing, and a
  very small cobalt-blue structural accent. No logo, no brand name, no letters,
  no numbers, and no readable packaging text.

  The product geometry must be simple and repeatable: stable cylinder diameter,
  cap seam, base proportion, carmine shade, camera height, three-quarter angle,
  and soft contact shadow. Use high-end studio material rendering, believable
  cosmetic surfaces, precise edges, calm reflections, and generous breathing
  room. Keep the left 45 percent quiet and low-detail for later Chinese deck
  typography.

  Visual direction weighting: Apple-like restraint, whitespace, product
  credibility, and material precision as the dominant discipline; Claude-like
  warmth, calm editorial humanity, and soft tonal transitions as the secondary
  influence; a smaller amount of Kimi-like concise AI-product sharpness. These
  are directional qualities only, not copied brand identity or trade dress.

  Market context is a China and United Kingdom launch, expressed through
  globally credible contemporary editorial styling and subtle localization
  readiness, not through flags, landmarks, national-color clichés, porcelain,
  dragons, lanterns, Union Jack motifs, or token cultural symbols. The complete
  image should read as one unified premium campaign world.

  Do not create advertising copy, UI panels, floating dashboards, robots,
  glowing brains, neon circuitry, glassmorphism, fake metrics, fake logos,
  extra products, distorted caps, warped cylinders, illegible microtext, or
  recognizable imitation of an existing beauty campaign.
negative_prompt: ""
tradition_tokens: []
color_constraint_tokens:
  - "warm ivory base"
  - "ink black structure"
  - "VULCA cobalt blue used sparingly for control identity"
  - "one lipstick-carmine campaign accent"
  - "no rainbow gradients or generic red-and-gold luxury"
sketch_integration: ignore
ref_integration: listed_in_notes
protected_product_constraints:
  - "cylinder silhouette and diameter"
  - "cap seam and base proportion"
  - "three-quarter camera angle and camera height"
  - "carmine shade and warm-ivory packaging"
  - "soft contact-shadow direction"
  - "no generated text or logo"
derived_asset_rules:
  commercial_hero: "may use generated pixels; label as VULCA demonstration"
  enterprise_task: "compose from the approved hero plus factual brief fields; do not generate fake client evidence"
  actual_vulca_run: "use only artifacts produced by the local VULCA run; no reconstructed interface"
  control_proof: "use actual before, layer/mask, targeted revision, and after artifacts from the same run"
unified_to_additive_fallback: |
  Attempt one unified localized revision first. If any protected product
  constraint fails, preserve the approved hero pixels and switch to an additive
  edit that changes only the selected environment or localization layer.
```

## D2. Thresholds + batch + rollback

```yaml
reviewed: true
L1_threshold:          {value: 0.75, source: assumed, confidence: low}
L2_threshold:          {value: 0.80, source: assumed, confidence: low}
L3_threshold:          {value: 0.70, source: assumed, confidence: low}
L4_threshold:          {value: 0.75, source: assumed, confidence: low}
L5_threshold:          {value: 0.65, source: assumed, confidence: low}
batch_size:            {value: 2, source: derived, confidence: high}
rollback_trigger:      {value: "any hard protected-product failure on the first unified localized revision triggers additive fallback; two consecutive generation failures stop real calls", source: derived, confidence: high}
override_rationale: null
hard_gates:
  generated_text_or_logo_count_max: 0
  unexpected_product_count_max: 0
  product_bbox_iou_min: 0.90
  product_color_delta_e_max: 5.0
  camera_alignment_shift_pct_max: 3.0
  protected_region_change_pct_max_for_additive: 1.0
  slide_evidence_label_min_pt: 20
  slide_evidence_states_max: 4
commercial_readability_gates:
  - "one dominant product subject is readable within two seconds"
  - "left-side copy-safe area remains quiet and uncluttered"
  - "product material and geometry remain believable at full-slide size"
  - "the visual does not resemble a known beauty brand or campaign"
evidence_gates:
  - "slide 4 names the rendering backend and the VULCA workflow boundary"
  - "slide 4 uses actual run artifacts, not mock or reconstructed product screens"
  - "slide 5 shows before, selected semantic layer or mask, targeted change, and after from one chronology"
  - "all beauty imagery is labelled as a VULCA demonstration, not a customer result"
```

## F. Cost budget

```yaml
reviewed: true
per_gen_sec:                  {value: 234, source: derived, confidence: med}
total_session_sec:            {value: 701, source: derived, confidence: low}
fail_fast_consecutive:        {value: 2, source: assumed, confidence: low}
provider_used_for_calibration: mock
provider_multiplier_applied: 10000
mock_calibration_sec: 0.023356
max_real_generation_calls: 3
cost_policy: "two hero candidates plus one focused correction or localized revision; no decorative extra calls before proof assets exist"
```

## Open questions

- `/visual-plan` MUST smoke-test the source invocation `PYTHONPATH=src python3 -m vulca.cli` and record the exact successful command; the stale global `/opt/homebrew/bin/vulca` entry must not be used as evidence.
- `/visual-plan` MUST verify which local VULCA decomposition path can run on the approved GPT Image 2 source asset before claiming an actual semantic-layer result.
- `/visual-plan` MUST preserve the provider boundary in the evidence record if GPT Image 2 is invoked through Codex while VULCA performs brief, decomposition, constraint, and adoption work locally.
- `/visual-plan` SHOULD choose the smallest source-safe set of actual run artifacts that remains legible on slide 4; raw engineering logs belong in the evidence folder, not on the slide.

## Notes

[resume-state] turns_used: 2

[null-tradition] spike skipped — requires tradition-guide weights for judgment.

[calibration] One allowed local mock generation completed in 0.023356 seconds. The OpenAI 10000x multiplier produced a conservative 234-second per-generation budget; the user accepted the derived budget after clarification. No real provider generation ran during `/visual-spec`.

[source] The commercial source asset is intentionally generated and brand-neutral because no approved historical beauty-customer asset was identified. This prevents a hypothetical beauty scenario from being presented as customer traction.

[execution] Unified is the frozen primary treatment copied from the proposal. Additive is a rollback route, not a frontmatter style change: it preserves the approved product pixels if unified localization fails the hard protected-product gates.

[references] Claude, Kimi, and Apple are directional references only, weighted 30/20/50. No proprietary logo, layout, icon, typeface, or trade dress may be copied.
