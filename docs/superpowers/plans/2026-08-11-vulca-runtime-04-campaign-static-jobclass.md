# VULCA Campaign Static JobClass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete `campaign-static-creative-production-release.v1` from approved business brief to genuinely generated and adapted static campaign assets, independent evaluation, bounded repair, deterministic package, human release, exact DeliveryReceipt and inert MemoryCandidates—with no routine operator handoff into a competitor UI.

**Architecture:** Freeze a versioned competitor Capability Coverage Ledger, compile one bounded campaign template into exact Cell versions, use the canonical SDK for generation/editing/composition/adaptation/evaluation/technical validation, and keep policy, artifact lineage, repair, package, delivery and memory authority in the platform. Every mock test proves mechanics only; separate opt-in provider and human-review evidence controls Pilot claims.

**Tech Stack:** Canonical `vulca` capability wheel, FastAPI/SQLAlchemy Job runtime, Temporal activities/workflows, YAML JobClass templates, Pillow-backed deterministic Cells, pytest, real-provider opt-in harness, HTML/JSON human review packet.

## Global Constraints

- Before any Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute platform work in `/Users/yhryzy/dev/vulca-platform`; execute any SDK correction uncovered by compatibility tests in the canonical `vulca` repository with a new SDK version and repeat Plan 01's convergence gate.
- Task 1 is the required novelty-and-coverage kill test. Pause for a user `GO_VERTICAL`, `REFRAME_VERTICAL` or `KILL_VERTICAL` decision before Tasks 2–7.
- The selected responsibility includes every chain stage. A generation-only, review-only, or packaging-only success does not pass.
- A manual copy/paste or export/import through Adobe, Canva, Recraft, TapNow, Photoroom, The Brief or another creative UI is a `MISSING` route.
- External APIs may be `ADAPTED` Cells when VULCA owns state, authority, retries, evidence, exceptions and delivery.
- Initial evidence qualifier is `UNPROVEN`. Code existence does not justify `BETTER` or `EXCLUSIVE`.
- Human release remains mandatory. The JobClass must not call public publishing APIs.
- One bounded repair cycle is the MVP maximum. A second quality failure becomes an explicit exception.
- Rights and policy checks validate declared evidence and rules; they do not invent licences or offer legal conclusions.
- No paid provider call occurs without an explicit spend approval and cap at execution time.

---

### Task 1: Freeze the commercial coverage and novelty gate

**Files:**

- Create: `docs/product/campaign-static/competitor-source-lock.yaml`
- Create: `docs/product/campaign-static/coverage-gate.md`
- Create: `wenxin-backend/app/job_runtime/job_classes/__init__.py`
- Create: `wenxin-backend/app/job_runtime/job_classes/coverage.py`
- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_static_coverage_v0.yaml`
- Create: `wenxin-backend/tests/test_campaign_static_coverage.py`

**Official source lock, refreshed before implementation:**

| Product | Official source | Capabilities to verify |
|---|---|---|
| Adobe GenStudio for Performance Marketing | `https://business.adobe.com/products/genstudio/performance-marketing.html` and `/brand-compliance.html` | brief/campaign context, copy and creative variants, brand/channel/accessibility checks, review/approval, asset reuse, activation |
| Canva Enterprise | `https://www.canva.com/learn/canva-pro-vs-canva-enterprise/` | AI generation/editing, resize, Brand Kits, locked templates, comments/versioning, tiered approvals, DAM/integrations, publish |
| Recraft | `https://www.recraft.ai/docs/support-and-faq/FAQ` and `/docs/api-reference/getting-started` | raster/vector generation, custom brand styles/colours, editing, mockups, background removal, vectorisation, exports |
| TapNow | `https://docs.tapnow.ai/en/docs/agent/tapnow-agent` and `/en/docs/canvas/explore-the-canvas` | context reading, planning, generation/editing, batch work, revisions, templates, delivery preparation, canvas orchestration |
| Photoroom API | `https://www.photoroom.com/api` and `https://docs.photoroom.com/` | high-volume image generation/editing, background, relight, reposition/resize, composition, image QA |
| The Brief, formerly Creatopy | `https://www.thebrief.ai/create/advertisement/` | templates, brand customisation, Smart Resize, bulk variants/editing, exports, automation and publication support |

Also freeze two cheap/no-Agent baselines:

1. `ONE_SHOT_PROVIDER`: the same approved image provider receives the brief once; a human selects, resizes, checks and packages outputs.
2. `TEMPLATE_SCRIPT`: deterministic Pillow/ImageMagick template composition and resize with no planning, model evaluation, repair, authority or evidence runtime.

**Coverage row schema:**

```yaml
- id: generation.primary_visual
  chain_stage: produce
  routine: Generate one content-bearing primary visual from the accepted brief
  required: true
  baseline_refs:
    - product: Adobe GenStudio for Performance Marketing
      source_ids: [adobe-core]
  route: MISSING
  capability_ref: null
  evidence_qualifiers: [UNPROVEN]
  evidence_refs: []
  operator_escape_required: true
```

The v0 ledger must contain at least these exact row IDs:

```text
intake.brief_contract
intake.source_rights
plan.creative_direction
plan.production_plan
generation.primary_visual
edit.source_asset
compose.copy_layout
adapt.channel_formats
adapt.batch_variants
brand.style_application
review.technical
review.rights_policy
review.visual_semantic
review.brand
repair.bounded
decision.human_approval
package.naming_manifest
delivery.destination_write
delivery.receipt_reconciliation
evidence.end_to_end_lineage
recovery.restart_resume
control.model_portability
control.local_private_data
learning.governed_memory_candidate
```

- [ ] **Step 1: Write the failing ledger schema and completeness tests**

  Tests reject duplicate IDs, unknown source IDs, invalid route/qualifier combinations, `operator_escape_required=false` with `MISSING`, absent required rows and any `BETTER`/`EXCLUSIVE` claim without an evidence reference.

- [ ] **Step 2: Refresh each current official page and write the source lock**

  Record `retrieved_on`, canonical URL, exact capability statement in paraphrase, availability qualifier such as “coming soon”, and source hash. Do not copy long marketing passages. If a capability is unclear, mark it `UNKNOWN`, not absent.

- [ ] **Step 3: Run the current-state coverage audit**

  Map current canonical SDK/platform capabilities, not planned code, into v0. Existing durable runtime features from Plans 01–03 may be `NATIVE + UNPROVEN`; unimplemented campaign production rows remain `MISSING`.

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_campaign_static_coverage.py
  python -m app.job_runtime.job_classes.coverage \
    audit app/job_runtime/job_classes/campaign_static_coverage_v0.yaml
  ```

  Expected: schema tests pass; audit exits 2 and prints the exact required `MISSING` rows. Exit 2 is the correct pre-implementation state.

- [ ] **Step 4: Write the three-part strategic gate**

  `coverage-gate.md` must separate:

  - **Already covered/commercialised:** isolated generation, editing, brand templates/styles, resize/batch variants, approvals, DAM/activation and canvas workflows are crowded capabilities.
  - **Still unsolved for this selected boundary:** dependable queue ownership across interchangeable tools, explicit authority, restart/reconciliation, exact end-to-end evidence, local/private operation and governed memory are not established by the compared routine configurations.
  - **Potential VULCA differentiation:** better operating performance on one declared metric plus responsibility for the complete bounded queue; this remains a hypothesis until comparative evidence exists.

  Name the strongest baseline for each row and the cheapest test capable of killing the residual hypothesis.

- [ ] **Step 5: Pause for the user decision**

  Present the audit counts and request one exact decision:

  - `GO_VERTICAL`: continue because the responsibility residual remains worth testing;
  - `REFRAME_VERTICAL`: narrow/change the JobClass or metric before implementation;
  - `KILL_VERTICAL`: stop material investment.

  Do not continue on a prior generic “continue”; this gate is based on newly refreshed precedents.

- [ ] **Step 6: Commit only after `GO_VERTICAL`**

  ```bash
  git add docs/product/campaign-static wenxin-backend/app/job_runtime/job_classes wenxin-backend/tests/test_campaign_static_coverage.py
  git commit -m "docs: freeze campaign capability coverage gate"
  ```

---

### Task 2: Register the static JobClass, packs and bounded RunPlan compiler

**Files:**

- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_static_v1.yaml`
- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_cross_media_v1.yaml`
- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_static.py`
- Create: `wenxin-backend/app/services/job_runtime/job_classes.py`
- Create: `wenxin-backend/app/services/job_runtime/seed_job_runtime.py`
- Create: `wenxin-backend/tests/fixtures/campaign_static/packs/organization.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/packs/brand.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/packs/policy.json`
- Create: `wenxin-backend/tests/test_campaign_static_compiler.py`
- Create: `wenxin-backend/tests/test_jobclass_seed.py`

**Static template metadata:**

```yaml
key: campaign-static-creative-production-release
version: "1"
template_id: campaign-static-creative-production-release.v1
authority_ceiling: EXECUTE
human_release_required: true
max_repair_runs: 1
allowed_delivery_kinds: [LOCAL_FOLDER]
required_eval_specs:
  - campaign-static-technical.v1
  - campaign-static-rights-policy.v1
  - campaign-static-visual-semantic.v1
execution_binding_refs:
  deterministic: local-static-cells.v1
  primary_generation: campaign-primary-image.v1
  visual_evaluator: campaign-independent-vlm.v1
```

**Compiled step order:**

```text
creative_plan
source_edit?                  # only when an authorised source asset and edit instruction exist
generate_primary
compose_master
adapt_{format_key}            # one per declared format, maximum 12
technical_validate_{format_key}
rights_policy_validate
visual_semantic_evaluate
brand_evaluate
repair_primary?               # conditional, creates Run attempt 2 and artifact v+1
revalidate_repaired?
package_delivery_set
wait_human_release
deliver_exact_package
propose_memory_candidates
```

The compiler may expand only the declared format list and one conditional repair branch. It may select only exact capability versions and execution-binding keys declared in the template and immutable JobSpec. It must bind the independent evaluator before generation output exists; `primary_generation` and `visual_evaluator` must resolve to different provider/model identities, while deterministic Cells use the declared local binding.

The cross-media template is registered with status `SHADOW_ONLY`, authority ceiling `SHADOW`, and its own ledger containing `MISSING` motion/audio rows. It cannot inherit static authority or Pilot status.

- [ ] **Step 1: Write failing seed and compiler tests**

  Test stable RunPlan hash, exact step keys/dependencies, maximum 12 formats, optional source-edit branch, evaluator binding before output, independent generation/evaluation providers, spend sum, human-release step and cross-media authority isolation.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_campaign_static_compiler.py tests/test_jobclass_seed.py
  ```

  Expected: failure because templates/compiler/seed are absent.

- [ ] **Step 3: Implement idempotent seed and pure compiler**

  Seed one development Organization and its Pack versions only when `VULCA_JOB_RUNTIME_SEED=development`; tests call the seed explicitly. Production never invents customer packs. Store YAML content hashes on JobClass/EvalSpec/Ledger records.

- [ ] **Step 4: Run compiler, plan-validation and seed tests**

  ```bash
  python -m pytest -q tests/test_campaign_static_compiler.py tests/test_jobclass_seed.py tests/test_run_plan_validation.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit JobClass contracts**

  ```bash
  git add wenxin-backend/app/job_runtime/job_classes wenxin-backend/app/services/job_runtime/job_classes.py wenxin-backend/app/services/job_runtime/seed_job_runtime.py wenxin-backend/tests/fixtures/campaign_static/packs wenxin-backend/tests/test_campaign_static_compiler.py wenxin-backend/tests/test_jobclass_seed.py
  git commit -m "feat: compile bounded campaign static jobs"
  ```

---

### Task 3: Produce a primary visual, composed master and exact channel variants

**Files:**

- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_static_contracts.py`
- Create: `wenxin-backend/app/services/job_runtime/campaign_static_production.py`
- Modify: `wenxin-backend/app/job_runtime/activities.py`
- Modify: `wenxin-backend/app/job_runtime/workflows.py`
- Create: `wenxin-backend/tests/test_campaign_static_production.py`
- Create: `wenxin-backend/tests/test_campaign_static_lineage.py`

**Required canonical capabilities:**

```text
vulca.image.generate/1.0.0
vulca.image.edit/1.0.0
vulca.image.compose_static/1.0.0
vulca.image.adapt_static/1.0.0
```

The creative-plan activity emits `creative-plan.json` as an ArtifactVersion bound to JobSpec, BrandPack, PolicyPack and template hashes. The primary generation invocation contains the approved message, audience, CTA, visual direction, prohibited elements and authorised references. It must retain actual provider/model/version/session, latency, cost and input hashes.

Composition applies approved headline/body/CTA, logo, colours, font and safe-area rules to the generated/edited visual. Adaptation produces one immutable child ArtifactVersion for every exact requested format. Parent version IDs form an unbroken lineage from accepted inputs to package.

- [ ] **Step 1: Write failing mock production and lineage tests**

  Test a genuinely content-bearing fake PNG moves through primary → composed master → three format variants; dimensions and text zones match contracts; optional source asset calls edit before composition; no-source input skips edit without skipping generation; every child names parent hashes; duplicate activities do not invoke a Cell twice.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_campaign_static_production.py tests/test_campaign_static_lineage.py
  ```

  Expected: failure because production service/contracts are absent.

- [ ] **Step 3: Implement production activities through the canonical adapter**

  Do not call `vulca.acreate`, Pillow or provider SDKs directly from platform services. Every visual operation resolves the exact Capability manifest and runs through `VulcaSdkCapabilityAdapter` plus the Plan 03 activity/grant path.

- [ ] **Step 4: Advance the immutable coverage ledger**

  Copy v0 to `campaign_static_coverage_v1.yaml`; update only implemented rows to `NATIVE` or `ADAPTED`, set `operator_escape_required=false`, retain `UNPROVEN`, and add test/commit evidence references. Never edit v0.

- [ ] **Step 5: Run production, activity and coverage tests**

  ```bash
  python -m pytest -q \
    tests/test_campaign_static_production.py \
    tests/test_campaign_static_lineage.py \
    tests/test_capability_activities.py \
    tests/test_campaign_static_coverage.py
  ```

  Expected: all tests pass; coverage audit still exits 2 only for later review/package/learning rows.

- [ ] **Step 6: Commit production path**

  ```bash
  git add wenxin-backend/app/job_runtime wenxin-backend/app/services/job_runtime/campaign_static_production.py wenxin-backend/tests/test_campaign_static_production.py wenxin-backend/tests/test_campaign_static_lineage.py
  git commit -m "feat: produce campaign masters and variants"
  ```

---

### Task 4: Add independent evaluation, deterministic policy gating and one repair Run

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/campaign_static_evaluation.py`
- Create: `wenxin-backend/app/services/job_runtime/policy_gate.py`
- Create: `wenxin-backend/app/services/job_runtime/repairs.py`
- Modify: `wenxin-backend/app/job_runtime/activities.py`
- Modify: `wenxin-backend/app/job_runtime/workflows.py`
- Create: `wenxin-backend/tests/test_campaign_static_evaluation.py`
- Create: `wenxin-backend/tests/test_campaign_static_repair.py`
- Create: `wenxin-backend/tests/test_policy_gate.py`

**Evaluation stack:**

1. `vulca.image.validate_static/1.0.0` checks decode, format, dimensions, colour mode, alpha policy, safe area and package naming inputs.
2. Platform rights/policy validator checks exact source rights references, provider data policy, prohibited terms/elements and destination authority.
3. `vulca.image.evaluate/1.0.0` runs with `tradition="brand_design"`, skills `brand` and `audience`, and a VLM provider/model different from primary generation.
4. Deterministic brand checks compare declared logo, font, colours, copy and CTA to the BrandPack.
5. Policy Gate interprets all required reports; executor/evaluator cannot set approval state.

**Gate outcomes:**

- all hard reports PASS → Artifact `EVALUATED`, request human release decision;
- one repairable FAIL and repair budget available → new Run attempt, new artifact version, same bound evaluators;
- ABSTAIN, evaluator conflict, rights/policy FAIL, unrepairable FAIL or second quality FAIL → `WAITING_DECISION` with exact exception owner and safe options.

- [ ] **Step 1: Write failing anti-gaming, abstention and repair tests**

  Prove evaluator bindings precede output, generation provider cannot evaluate, missing required report cannot pass, ABSTAIN never averages into PASS, repair creates Run attempt 2 and ArtifactVersion v+1, rejected v1 remains immutable, and a second failure does not loop.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_campaign_static_evaluation.py tests/test_campaign_static_repair.py tests/test_policy_gate.py
  ```

  Expected: failure because evaluation/gate/repair services are absent.

- [ ] **Step 3: Implement structured reports and deterministic gate**

  Every report stores exact artifact hash, channel, EvalSpec/evaluator/model versions, dimension results, hard failures, uncertainty, evidence references and bounded repair hints. Do not store hidden reasoning.

- [ ] **Step 4: Advance the ledger immutably**

  Create `campaign_static_coverage_v2.yaml`, update review/brand/repair rows to their implemented routes, preserve `UNPROVEN`, and attach test evidence.

- [ ] **Step 5: Run evaluation and workflow tests**

  ```bash
  python -m pytest -q \
    tests/test_campaign_static_evaluation.py \
    tests/test_campaign_static_repair.py \
    tests/test_policy_gate.py \
    tests/test_run_plan_validation.py \
    tests/test_campaign_static_coverage.py
  ```

  Expected: all tests pass; no test treats a model score as release authority.

- [ ] **Step 6: Commit evaluation and repair**

  ```bash
  git add wenxin-backend/app/job_runtime wenxin-backend/app/services/job_runtime/campaign_static_evaluation.py wenxin-backend/app/services/job_runtime/policy_gate.py wenxin-backend/app/services/job_runtime/repairs.py wenxin-backend/tests/test_campaign_static_evaluation.py wenxin-backend/tests/test_campaign_static_repair.py wenxin-backend/tests/test_policy_gate.py
  git commit -m "feat: evaluate and repair campaign artifacts"
  ```

---

### Task 5: Build the delivery package and inert MemoryCandidates

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/packages.py`
- Create: `wenxin-backend/app/services/job_runtime/memory.py`
- Modify: `wenxin-backend/app/job_runtime/activities.py`
- Modify: `wenxin-backend/app/job_runtime/workflows.py`
- Modify: `wenxin-backend/app/api/v1/jobs.py`
- Create: `wenxin-backend/app/api/v1/memory_candidates.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Create: `wenxin-backend/tests/test_campaign_package.py`
- Create: `wenxin-backend/tests/test_memory_candidates.py`

**Deterministic package contents:**

```text
{job_id}/
  assets/{format_key}.{png|jpg|webp}
  manifest.json
  eval-reports.json
  delivery-notes.md
```

`manifest.json` includes Job/JobSpec/RunPlan/Artifact/EvalSpec hashes, media metadata, lineage, human DecisionRecord ID and package SHA-256. ZIP entry order, timestamps and compression settings are fixed so identical inputs produce identical bytes.

Memory extraction may propose only:

- approved brand preference;
- recurrent workflow routing lesson;
- evidenced failure-prevention rule;
- evaluator-calibration candidate;
- operational policy suggestion.

Each candidate names exact Jobs, artifacts, reports, decision/events, scope, owner, rights/data classification, confidence and expiry. It starts `PROPOSED`; no workflow may read it until an authorised decision moves it to `ACTIVE`.

- [ ] **Step 1: Write failing reproducible-package and inert-memory tests**

  Test byte-identical packages, safe names/path traversal rejection, exact hash in ReleaseToken/receipt, no rejected artifact in package, candidate evidence completeness, no cross-organization read, no automatic promotion and revocation taking effect on future reads.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_campaign_package.py tests/test_memory_candidates.py
  ```

  Expected: failure because package/memory services are absent.

- [ ] **Step 3: Implement package activity and memory decision API**

  Package before release, wait for exact human approval, then use Plan 03's ReleaseToken/reconciliation path. Generate MemoryCandidates after completion, rejection, repair or override; candidate creation never changes policy or prompts.

- [ ] **Step 4: Create the final unproven implementation ledger**

  Create `campaign_static_coverage_v3.yaml`. Every required row must now be `NATIVE` or `ADAPTED`, `operator_escape_required=false`, and have implementation/test references. Evidence qualifiers remain `UNPROVEN` until Task 7.

- [ ] **Step 5: Run package, release, memory and coverage tests**

  ```bash
  python -m pytest -q \
    tests/test_campaign_package.py \
    tests/test_memory_candidates.py \
    tests/test_release_tokens.py \
    tests/test_delivery_reconciliation.py \
    tests/test_campaign_static_coverage.py
  python -m app.job_runtime.job_classes.coverage \
    audit app/job_runtime/job_classes/campaign_static_coverage_v3.yaml
  ```

  Expected: tests and audit exit 0; audit reports zero required `MISSING`, zero `BETTER` and zero `EXCLUSIVE` evidence.

- [ ] **Step 6: Commit package and governed memory**

  ```bash
  git add wenxin-backend/app wenxin-backend/tests/test_campaign_package.py wenxin-backend/tests/test_memory_candidates.py
  git commit -m "feat: package deliver and learn from campaign jobs"
  ```

---

### Task 6: Prove the complete vertical mechanically with a Golden corpus

**Files:**

- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/01-no-source-social.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/02-product-source-social.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/03-multi-format-launch.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/04-high-contrast-brand.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/05-long-copy.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/06-authorised-edit.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/07-repairable-technical-fail.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/08-repairable-visual-fail.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/09-rights-block.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/10-policy-block.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/11-evaluator-abstain.json`
- Create: `wenxin-backend/tests/fixtures/campaign_static/jobs/12-delivery-conflict.json`
- Create: `wenxin-backend/tests/test_campaign_static_golden.py`
- Create: `wenxin-backend/tests/temporal/test_campaign_static_e2e.py`
- Create: `wenxin-backend/scripts/run_campaign_static_golden.py`

Each fixture declares expected terminal/pre-release state, expected exception, provider-call ceiling, repair count, artifact count, format dimensions, required event types and whether release is permitted.

- [ ] **Step 1: Write the failing parameterised Golden test**

  The mock capability provider returns deterministic but content-bearing PNGs and programmable evaluation outcomes. For all 12 cases, assert no undocumented service intervention, exact state/event lineage, bounded calls/repair, package/receipt semantics and inert memory.

- [ ] **Step 2: Run and verify initial failures**

  ```bash
  python -m pytest -q tests/test_campaign_static_golden.py
  ```

  Expected: failing cases expose missing fixture handling or workflow branches; fix production code only where the declared contract is violated.

- [ ] **Step 3: Drive every case green without fixture-specific branches**

  Do not key runtime behavior on fixture/job names. Convert each failure into a generic contract, policy, Cell, evaluator, exception or reconciliation rule.

- [ ] **Step 4: Run the real Temporal end-to-end mechanics test**

  ```bash
  python -m pytest -q -m temporal tests/temporal/test_campaign_static_e2e.py
  python scripts/run_campaign_static_golden.py --provider mock --report /tmp/vulca-campaign-golden.json
  ```

  Expected: all 12 cases match declared outcomes; eligible Jobs complete only after simulated authorised human decisions; blocked cases spend nothing after their blocking gate.

- [ ] **Step 5: Run the entire JobClass test set**

  ```bash
  python -m pytest -q \
    tests/test_campaign_static_coverage.py \
    tests/test_campaign_static_compiler.py \
    tests/test_campaign_static_production.py \
    tests/test_campaign_static_lineage.py \
    tests/test_campaign_static_evaluation.py \
    tests/test_campaign_static_repair.py \
    tests/test_campaign_package.py \
    tests/test_memory_candidates.py \
    tests/test_campaign_static_golden.py
  ```

  Expected: all tests pass. The report must label provider/evaluator outputs `MOCK` and must not mark the JobClass Pilot-ready.

- [ ] **Step 6: Commit the mechanical Golden corpus**

  ```bash
  git add wenxin-backend/tests/fixtures/campaign_static wenxin-backend/tests/test_campaign_static_golden.py wenxin-backend/tests/temporal/test_campaign_static_e2e.py wenxin-backend/scripts/run_campaign_static_golden.py
  git commit -m "test: cover the complete campaign job vertical"
  ```

---

### Task 7: Run the opt-in real-provider and strongest-cheap-baseline evidence gate

**Files:**

- Create: `wenxin-backend/tests/fixtures/campaign_static/real-provider-corpus.yaml`
- Create: `wenxin-backend/tests/test_campaign_static_real_provider.py`
- Create: `wenxin-backend/scripts/run_campaign_static_baseline.py`
- Create: `wenxin-backend/scripts/build_campaign_static_review_packet.py`
- Create: `wenxin-backend/app/job_runtime/job_classes/campaign_static_thresholds_v1.yaml`
- Create after authorised run: `docs/product/campaign-static/evidence/real-provider-run.json`
- Create after authorised human review: `docs/product/campaign-static/evidence/human-review.json`
- Create after comparison: `wenxin-backend/app/job_runtime/job_classes/campaign_static_coverage_v4.yaml`

**Predeclared real evidence thresholds:**

- 8 representative, non-customer, rights-cleared briefs; 3 fixed formats per brief;
- generation and independent evaluator providers differ;
- maximum 200 USD cents provider spend per Job and 1,600 USD cents for the full run;
- maximum 1 repair Run and 2 paid generation/edit calls per Job;
- technical/package/delivery integrity: 8/8;
- policy incident or hidden manual artifact edit: 0;
- human release recommendation: at least 6/8 without an unrecorded rescue;
- compared with `ONE_SHOT_PROVIDER`, VULCA must either improve human-approved Job rate by at least 15 percentage points, or reduce measured hands-on minutes by at least 50% while remaining within 5 percentage points of baseline approval rate;
- `EXCLUSIVE` may be assigned only within the evaluated baseline configurations and only when restart recovery, exact authority/evidence, delivery reconciliation or governed memory is directly demonstrated and the comparison configuration lacks that responsibility.

- [ ] **Step 1: Write the opt-in guard test before any provider run**

  The real-provider test must skip unless all are present:

  ```text
  VULCA_REAL_PROVIDER_APPROVED=true
  VULCA_REAL_PROVIDER_APPROVAL_REF=user-approved-campaign-static-real-provider-v1
  VULCA_REAL_PROVIDER_MAX_CENTS=1600
  required provider credentials
  ```

  The harness refuses a higher cap, redacts secrets and writes actual spend after every call.

- [ ] **Step 2: Request explicit spend/data approval**

  Before setting the guard values, show the user the eight fixture summaries, provider/evaluator destinations, data sent, maximum 1,600 USD cents, output location and stop command. Do not infer approval from specification acceptance.

- [ ] **Step 3: Run VULCA and both cheap baselines on the same corpus**

  ```bash
  python -m pytest -q -m real_provider tests/test_campaign_static_real_provider.py
  python scripts/run_campaign_static_baseline.py \
    --corpus tests/fixtures/campaign_static/real-provider-corpus.yaml \
    --baseline one-shot-provider \
    --output docs/product/campaign-static/evidence/one-shot-provider.json
  python scripts/run_campaign_static_baseline.py \
    --corpus tests/fixtures/campaign_static/real-provider-corpus.yaml \
    --baseline template-script \
    --output docs/product/campaign-static/evidence/template-script.json
  ```

  Expected: outputs and receipts are complete; no comparative claim is made before human review.

- [ ] **Step 4: Build a blinded human review packet and stop for human decisions**

  ```bash
  python scripts/build_campaign_static_review_packet.py \
    --vulca docs/product/campaign-static/evidence/real-provider-run.json \
    --baseline docs/product/campaign-static/evidence/one-shot-provider.json \
    --output docs/product/campaign-static/evidence/review-packet.html
  ```

  Randomise system labels and retain the key separately. Human decisions record acceptance, reason, hands-on minutes and whether any rescue occurred. AI-produced labels remain draft and cannot populate `human-review.json` as confirmed evidence.

- [ ] **Step 5: Compute the gate without cherry-picking**

  Include all eight predeclared Jobs. Create v4 from v3; add `BETTER` and `EXCLUSIVE` only to rows whose exact thresholds pass and attach immutable evidence hashes. If no better metric or no exclusive responsibility passes, keep qualifiers `UNPROVEN` and return `REFRAME` or `KILL`.

- [ ] **Step 6: Run the final coverage audit**

  ```bash
  python -m app.job_runtime.job_classes.coverage \
    audit app/job_runtime/job_classes/campaign_static_coverage_v4.yaml \
    --require-no-missing \
    --require-better 1 \
    --require-exclusive 1
  ```

  Expected for a passing vertical: exit 0. Otherwise the command exits 3 and prints the failed evidence gate; do not relabel it as success.

- [ ] **Step 7: Commit only evidence that actually exists**

  ```bash
  git add wenxin-backend/tests/test_campaign_static_real_provider.py wenxin-backend/tests/fixtures/campaign_static/real-provider-corpus.yaml wenxin-backend/scripts/run_campaign_static_baseline.py wenxin-backend/scripts/build_campaign_static_review_packet.py wenxin-backend/app/job_runtime/job_classes/campaign_static_thresholds_v1.yaml
  git add docs/product/campaign-static/evidence wenxin-backend/app/job_runtime/job_classes/campaign_static_coverage_v4.yaml
  git commit -m "test: gate campaign vertical against real baselines"
  ```

  If the authorised run or human review has not occurred, commit only the harness/threshold files in a separate commit and leave evidence/v4 absent.

---

## Plan 04 completion gate

- [ ] The refreshed strategic decision is `GO_VERTICAL`.
- [ ] `campaign-static-creative-production-release.v1` covers brief, plan, real generation, edit/adapt, independent review, repair, package, human release, delivery receipt and MemoryCandidates.
- [ ] No required v4 coverage row is `MISSING`; routine operation does not require a competitor UI.
- [ ] Real-provider provenance exists and is not confused with mock mechanics.
- [ ] Human-confirmed comparison passes at least one `BETTER` threshold and one bounded `EXCLUSIVE` responsibility test, or the plan exits honestly as `REFRAME`/`KILL`.
- [ ] Cross-media remains separately `SHADOW_ONLY` and inherits no authority.
- [ ] No public deployment, paid Pilot, queue ownership or role-replacement claim has been made.

Plan 05 may be implemented against v3 mechanics while Task 7 evidence is pending. Plan 06 cannot declare Internal Pilot Ready until Task 7 and its own recovery/deployment gates pass.
