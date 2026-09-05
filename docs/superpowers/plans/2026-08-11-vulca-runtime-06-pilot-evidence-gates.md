# VULCA Pilot Evidence and Operating Gates Implementation Plan

> **Status: historical (2026-08-11).** On 2026-08-14 VULCA moved Job Runtime ownership to the DSH/Cordis-derived native kernel in `vulca-platform` (see its `docs/product/2026-08-14-vulca-unified-product-prd.md`). The capability contracts in `src/vulca/capability/` (plan 01) remain canonical and are consumed by that kernel as a sidecar; the runtime plans 02–06 in this series are superseded by the platform-side milestones and are kept only as design record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the completed static JobClass into an honestly gated Internal-Pilot candidate, then define the separate deployment, baseline, authority and paid-queue evidence required for Paid Shadow and bounded Draft/Execute operation.

**Architecture:** Compute operating metrics from canonical Job/Evidence records, evaluate explicit predicates rather than a trust score, cryptographically sign scoped TrustDecisions, auto-demote on drift/change/incidents, package the local UI/API/worker/PostgreSQL/artifact system with explicit Temporal profiles, and prove backup/recovery/reconciliation before any customer operating claim.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Temporal, PostgreSQL, Docker Compose, local content-addressed storage, Ed25519 signatures via `cryptography`, pytest, Playwright, JSON evidence bundles and Markdown runbooks.

## Global Constraints

- Before any Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute this plan in `/Users/yhryzy/dev/vulca-platform` after Plans 01–05 pass their implementation gates.
- Internal Pilot, Paid Shadow, Draft/Execute, `OWNED` and `REPLACED` are separate evidence states. Never infer a later state from an earlier one.
- Development Temporal (`server start-dev`) may support local engineering and the Internal-Pilot test composition. Paid Shadow preflight must reject it.
- Choosing managed or self-hosted production Temporal is an explicit deployment/data/operations decision. This plan must not describe the archived auto-setup compose example as production-ready.
- Customer raw assets, briefs, credentials and evidence bundles are never committed to either repository.
- Mock, replay, screenshots, local QA and AI-assisted review labels cannot populate human-confirmed or customer-confirmed fields.
- Human release remains mandatory and authority ceiling remains `EXECUTE` for the first Pilot.
- `REPLACED` requires counterfactual labour-capacity evidence and is outside this implementation plan.
- No outreach, deployment to a customer, package publication or external send is authorised by this plan alone.

---

### Task 1: Compute separate operating metrics and immutable gate evaluations

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/metrics.py`
- Create: `wenxin-backend/app/services/job_runtime/pilot_gates.py`
- Create: `wenxin-backend/app/schemas/pilot_evidence.py`
- Create: `wenxin-backend/app/api/v1/pilot_evidence.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Create: `wenxin-backend/tests/test_operating_metrics.py`
- Create: `wenxin-backend/tests/test_pilot_gates.py`

**Metrics remain separate:**

```python
@dataclass(frozen=True)
class OperatingMetrics:
    representative_jobs: int
    eligible_jobs: int
    completed_jobs: int
    first_pass_accepted_jobs: int
    human_interventions: int
    human_hands_on_seconds: int
    cycle_seconds_p50: int
    cycle_seconds_p95: int
    sla_breaches: int
    provider_cost_minor: int
    human_cost_minor: int
    cost_per_accepted_job_minor: int | None
    policy_incidents: int
    release_incidents: int
    duplicate_delivery_incidents: int
    successful_recoveries: int
    failed_recoveries: int
    reconciliation_unknowns: int
    input_distribution_hash: str
    provider_set_hash: str
    evaluator_set_hash: str
```

`PilotGateEvaluation` stores exact Job IDs, time window, corpus/version hashes, threshold version, each predicate/result, evidence references, evaluator code version and one decision: `GO`, `REFRAME` or `KILL`. It never emits a composite trust score.

**Internal Pilot Ready thresholds:**

- Plan 04 v4 coverage: zero required `MISSING`, at least one evidenced `BETTER`, at least one bounded `EXCLUSIVE`;
- three consecutive complete 12-case mock Golden runs with expected state/side-effect outcomes;
- one authorised 8-case real-provider run with human-confirmed results meeting Plan 04 thresholds;
- evidence completeness, artifact hash integrity and exact delivery integrity: 100%;
- high-severity policy/release/duplicate-delivery incidents: 0;
- every retry, repair, intervention and manual action recorded;
- restart, cancellation, grant revocation, backup/restore and unknown-outcome reconciliation drills: all pass;
- no production/customer/adoption evidence required or implied.

- [ ] **Step 1: Write failing metric and gate tests**

  Test denominator rules, blocked/precondition Jobs, first-pass versus eventual acceptance, intervention time, cost per accepted Job, percentile calculation, incident separation, missing evidence, a false `BETTER` row, and `GO` only when every required predicate passes.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_operating_metrics.py tests/test_pilot_gates.py
  ```

  Expected: collection fails because metrics/gate services are absent.

- [ ] **Step 3: Implement event-derived metrics and immutable evaluations**

  Derive metrics from Job/Evidence/Decision/Receipt records; do not accept client-supplied totals. Store exact query filters and corpus hashes with each evaluation. API access requires `SPONSOR` or `WORKFLOW_OWNER` membership.

- [ ] **Step 4: Run tests and API contract checks**

  ```bash
  python -m pytest -q tests/test_operating_metrics.py tests/test_pilot_gates.py tests/test_openapi_contract.py
  ```

  Expected: all tests pass and no field named `trustScore` or `overallScore` exists.

- [ ] **Step 5: Commit metrics and gates**

  ```bash
  git add wenxin-backend/app/services/job_runtime/metrics.py wenxin-backend/app/services/job_runtime/pilot_gates.py wenxin-backend/app/schemas/pilot_evidence.py wenxin-backend/app/api/v1 wenxin-backend/tests/test_operating_metrics.py wenxin-backend/tests/test_pilot_gates.py
  git commit -m "feat: compute explicit pilot operating gates"
  ```

---

### Task 2: Sign scoped TrustDecisions and auto-demote on drift or incidents

**Files:**

- Create: `wenxin-backend/alembic/versions/job_runtime_trust_signatures.py`
- Modify: `wenxin-backend/app/models/job_output.py`
- Create: `wenxin-backend/app/services/job_runtime/trust.py`
- Create: `wenxin-backend/app/schemas/trust.py`
- Create: `wenxin-backend/app/api/v1/trust.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Create: `wenxin-backend/tests/test_trust_decisions.py`
- Create: `wenxin-backend/tests/test_trust_demotion.py`

**Migration:**

```python
revision = "job_runtime_trust_signatures"
down_revision = "job_runtime_workflow"
```

Add `threshold_version`, `pilot_gate_evaluation_id`, `payload_hash`, `signature_algorithm`, `signing_key_id`, `signature`, `supersedes_id`, `revoked_at` and `revocation_reason` to `trust_decisions`.

**Trust scope:**

```text
JobClass × Action × Channel × RiskTier
```

The signed payload includes Organization, JobClass/ledger/template/pack/evaluator/provider versions, exact scope, authority level, evidence window, predicates, expiry and demotion rules. Private signing keys come from a file/secret path outside Job data and logs.

**Automatic demotion:**

- high-severity policy, release or duplicate-delivery incident → immediate `SHADOW`;
- provider, evaluator, BrandPack, PolicyPack, JobClass template or coverage-ledger hash change → immediate `SHADOW` pending replay;
- quality/SLA/intervention/cost predicate fails in two consecutive complete windows → `SHADOW`;
- reconciliation unknown remains past SLA → `SHADOW` for destination action;
- expiry or explicit revocation → no authority;
- no automatic re-promotion; a new signed decision is required.

- [ ] **Step 1: Write failing signature, scope and demotion tests**

  Test canonical payload bytes, valid/invalid signature, wrong key, expired decision, action/channel/risk mismatch, provider change, incident, two-window drift, one-window noise, explicit revocation and inability to exceed `EXECUTE`.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_trust_decisions.py tests/test_trust_demotion.py
  ```

  Expected: failure because migration/service/API are absent.

- [ ] **Step 3: Implement signer/verifier and demotion monitor**

  Use Ed25519. Store only public key ID and signature in the database. Emit append-only `TRUST_GRANTED`, `TRUST_DEMOTED`, `TRUST_REVOKED` events. Every authority check verifies current signature, scope, version hashes and expiry.

- [ ] **Step 4: Run migration and trust tests**

  ```bash
  python -m pytest -q tests/test_job_migrations.py tests/test_trust_decisions.py tests/test_trust_demotion.py tests/test_step_grants.py
  ```

  Expected: all tests pass and Alembic has one head at `job_runtime_trust_signatures`.

- [ ] **Step 5: Commit signed trust controls**

  ```bash
  git add wenxin-backend/alembic/versions/job_runtime_trust_signatures.py wenxin-backend/app/models/job_output.py wenxin-backend/app/services/job_runtime/trust.py wenxin-backend/app/schemas/trust.py wenxin-backend/app/api/v1 wenxin-backend/tests/test_trust_decisions.py wenxin-backend/tests/test_trust_demotion.py
  git commit -m "feat: sign and demote scoped trust decisions"
  ```

---

### Task 3: Package an explicit internal deployment and gate the Pilot Temporal profile

**Files:**

- Create: `deploy/job-runtime/docker-compose.internal.yml`
- Create: `deploy/job-runtime/env.internal.example`
- Create: `deploy/job-runtime/README.md`
- Create: `scripts/vulca_runtime.py`
- Create: `scripts/check_job_runtime_preflight.py`
- Create: `wenxin-backend/tests/test_job_runtime_deployment.py`
- Create: `wenxin-backend/tests/test_pilot_temporal_profile.py`
- Modify: `docker-compose.yml` only to point legacy developers to the new explicit composition; do not silently replace existing services

**Internal composition:**

```text
frontend
api
job-worker
postgresql
temporal-dev             # INTERNAL_ONLY profile
artifact volume
delivery volume
```

`scripts/vulca_runtime.py` provides `preflight`, `up`, `status`, `stop`, `backup`, `restore-check` and `drill` subcommands. `stop` preserves volumes; no command deletes data.

**Temporal profiles:**

- `development`: pinned CLI development server, accepted only for tests/Internal Pilot engineering;
- `managed`: externally managed production Temporal endpoint with TLS/namespace/API-key configuration and a data-policy decision proving workflow payloads contain only opaque IDs/control metadata;
- `self_hosted`: separately operated production Temporal Server using maintained official samples/Helm, schema management, TLS, backup, metrics and upgrade runbook.

Paid Shadow preflight rejects `development`. It accepts `managed` or `self_hosted` only after the corresponding operational checklist passes. Do not embed archived `auto-setup` examples as Pilot infrastructure.

- [ ] **Step 1: Write failing compose/preflight/profile tests**

  Test pinned images, separate API/worker commands, PostgreSQL use, artifact/delivery volumes, no secret defaults, no public provider ingress, `development` rejection for paid Shadow, required TLS for managed, and required schema/backup/metrics evidence for self-hosted.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_job_runtime_deployment.py tests/test_pilot_temporal_profile.py
  ```

  Expected: failure because deployment files/preflight are absent.

- [ ] **Step 3: Implement the internal composition and safe control CLI**

  UI/API health, worker heartbeat, Temporal connectivity, PostgreSQL migration head, artifact root writability, delivery allowlist, SDK lock/version and signing public key must all pass before `up` reports ready. Credentials remain environment/file-secret references.

- [ ] **Step 4: Start and inspect the internal composition**

  ```bash
  python scripts/vulca_runtime.py preflight --profile internal
  python scripts/vulca_runtime.py up --profile internal
  python scripts/vulca_runtime.py status --profile internal
  ```

  Expected: status reports each component and explicitly labels Temporal `development / INTERNAL_ONLY`.

- [ ] **Step 5: Run deployment tests**

  ```bash
  python -m pytest -q tests/test_job_runtime_deployment.py tests/test_pilot_temporal_profile.py
  ```

  Expected: all tests pass.

- [ ] **Step 6: Record the paid-Pilot engine decision before external deployment**

  Choose one with the user and data owner:

  - `GO_MANAGED_TEMPORAL`: metadata-only managed service is accepted under the customer data policy;
  - `GO_SELF_HOSTED_TEMPORAL`: production server operations, TLS, schema, backup, monitoring and upgrade ownership are accepted;
  - `REFRAME_DEPLOYMENT`: neither route is acceptable; Paid Shadow remains blocked.

- [ ] **Step 7: Commit internal deployment tooling**

  ```bash
  git add deploy/job-runtime scripts/vulca_runtime.py scripts/check_job_runtime_preflight.py wenxin-backend/tests/test_job_runtime_deployment.py wenxin-backend/tests/test_pilot_temporal_profile.py docker-compose.yml
  git commit -m "feat: package the internal job runtime"
  ```

---

### Task 4: Prove backup, restore, restart, revocation and reconciliation

**Files:**

- Create: `scripts/job_runtime_backup.py`
- Create: `scripts/job_runtime_restore_check.py`
- Create: `scripts/job_runtime_recovery_drill.py`
- Create: `docs/ops/job-runtime-backup-restore.md`
- Create: `docs/ops/job-runtime-incident-response.md`
- Create: `wenxin-backend/tests/test_job_runtime_backup.py`
- Create: `wenxin-backend/tests/temporal/test_job_runtime_recovery_drill.py`

**Backup bundle:**

```text
backup-{utc_timestamp}/
  postgres.dump
  artifact-manifest.json
  evidence-export.json
  deployment-lock.json
  backup-manifest.json
```

`backup-manifest.json` hashes every file and records schema head, SDK lock, JobClass/Pack/ledger versions and encryption status. Customer Pilot backups must use an approved encrypted destination; the repository contains only scripts and synthetic test bundles.

**Required drills:**

1. API process stop/restart while Job runs;
2. worker A stop and worker B resume;
3. database restart after committed checkpoint;
4. provider retry then bounded failure;
5. Job cancellation and late provider result quarantine;
6. grant and TrustDecision revocation;
7. write-before-receipt crash and destination reconciliation;
8. backup restore into a fresh isolated composition with artifact/evidence hash verification.

- [ ] **Step 1: Write failing backup and recovery tests**

  Test manifest hashes, missing artifact detection, schema/version mismatch, restore into a different empty database/volume, no overwrite of live deployment, and all eight drill outcomes/events.

- [ ] **Step 2: Run unit tests and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_job_runtime_backup.py
  ```

  Expected: failure because scripts/contracts are absent.

- [ ] **Step 3: Implement safe backup/restore-check tooling**

  Restore check always creates a new explicitly named temporary composition and refuses the active database/artifact paths. It verifies every content hash and Job/event count before success. Cleanup remains a separate explicit command.

- [ ] **Step 4: Run all recovery drills**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  python scripts/vulca_runtime.py drill --profile internal --suite all
  cd wenxin-backend
  python -m pytest -q tests/test_job_runtime_backup.py
  python -m pytest -q -m temporal tests/temporal/test_job_runtime_recovery_drill.py
  ```

  Expected: all eight drills pass and produce one machine-readable result file with exact Job/Event/Receipt IDs.

- [ ] **Step 5: Commit recovery tooling**

  ```bash
  git add scripts/job_runtime_backup.py scripts/job_runtime_restore_check.py scripts/job_runtime_recovery_drill.py docs/ops/job-runtime-backup-restore.md docs/ops/job-runtime-incident-response.md wenxin-backend/tests/test_job_runtime_backup.py wenxin-backend/tests/temporal/test_job_runtime_recovery_drill.py
  git commit -m "test: prove job runtime recovery and restore"
  ```

---

### Task 5: Build evidence bundles and the claim-permission gate

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/evidence_bundle.py`
- Create: `wenxin-backend/app/services/job_runtime/claim_permissions.py`
- Create: `wenxin-backend/app/api/v1/claim_permissions.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Create: `scripts/export_pilot_evidence.py`
- Create: `wenxin-backend/tests/test_pilot_evidence_bundle.py`
- Create: `wenxin-backend/tests/test_claim_permissions.py`
- Create: `wenxin-moyun/src/features/job-control/components/ClaimStatus.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/OperatingMetrics.tsx`
- Modify: `wenxin-moyun/src/pages/JobEvidencePage.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/ClaimStatus.test.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/OperatingMetrics.test.tsx`

**Claim states:**

```text
DEMO
PILOT
ASSISTED
AUTOMATED
OWNED
REPLACED
```

Permission is predicate-based:

- local mock/replay → `DEMO` only;
- signed bounded customer Pilot agreement plus actual paid run → `PILOT` for exact scope;
- task usefulness with human primary → `ASSISTED`;
- stable repeated task execution with human controlling flow → `AUTOMATED`;
- continuous real queue against SLA/cost/quality/risk with humans handling exceptions → `OWNED`;
- counterfactual proof that measurable human capacity was removed while the same queue remained served → `REPLACED`.

The first implementation must mechanically cap allowed claims at `DEMO` until external evidence records exist, and at `AUTOMATED` while human release controls the flow. No marketing string can override the gate.

- [ ] **Step 1: Write failing bundle integrity and claim-boundary tests**

  Test evidence bundle hashes/signature, redaction, customer-data exclusion from repository paths, mock cannot become Pilot, sender-side activity cannot prove customer use, paid agreement alone cannot prove operation, human release prevents `OWNED`, and no local evidence can produce `REPLACED`.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_pilot_evidence_bundle.py tests/test_claim_permissions.py
  ```

  Expected: failure because bundle/claim services are absent.

- [ ] **Step 3: Implement signed bundles and claim predicates**

  Export only customer-safe structured records and referenced hashes. Keep private/raw exports outside repository roots. Add UI text that says what is proven, what is not proven and which exact evidence is missing for the next state. `OperatingMetrics` reads the server-derived metrics endpoint and renders queue coverage, first-pass acceptance, intervention/hands-on time, cycle/SLA, cost, incidents, recovery and drift as separate values; it computes no aggregate trust score.

- [ ] **Step 4: Run backend/frontend claim tests**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_pilot_evidence_bundle.py tests/test_claim_permissions.py
  cd ../wenxin-moyun
  npm test -- --run src/__tests__/features/job-control/ClaimStatus.test.tsx src/__tests__/features/job-control/OperatingMetrics.test.tsx
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit evidence and claim gates**

  ```bash
  git add wenxin-backend/app/services/job_runtime/evidence_bundle.py wenxin-backend/app/services/job_runtime/claim_permissions.py wenxin-backend/app/api/v1 scripts/export_pilot_evidence.py wenxin-backend/tests/test_pilot_evidence_bundle.py wenxin-backend/tests/test_claim_permissions.py wenxin-moyun/src/features/job-control/components/ClaimStatus.tsx wenxin-moyun/src/features/job-control/components/OperatingMetrics.tsx wenxin-moyun/src/pages/JobEvidencePage.tsx wenxin-moyun/src/__tests__/features/job-control/ClaimStatus.test.tsx wenxin-moyun/src/__tests__/features/job-control/OperatingMetrics.test.tsx
  git commit -m "feat: gate operating claims with signed evidence"
  ```

---

### Task 6: Define and evaluate the paid Shadow operating transfer

**Files:**

- Create: `docs/product/pilot/campaign-static-pilot-contract.md`
- Create: `docs/product/pilot/customer-qualification.md`
- Create: `docs/product/pilot/baseline-protocol.md`
- Create: `docs/product/pilot/shadow-runbook.md`
- Create: `docs/product/pilot/go-reframe-kill.md`
- Create: `scripts/check_paid_shadow_readiness.py`
- Create: `wenxin-backend/tests/test_paid_shadow_readiness.py`

**Required Pilot contract fields:**

- exact JobClass/ledger/template/Pack versions;
- named Executive Sponsor, Workflow Owner, release approver and exception owners;
- one intake and one delivery route;
- representative queue definition and capped Job Capacity;
- provider/human spend allowance and overage rule;
- rights, privacy, retention and learning policy;
- frozen baseline method and success thresholds;
- Shadow/no-production-effect statement;
- stop switch, incident route and data return/deletion;
- fixed paid amount and payment status;
- exclusions: arbitrary work, unlimited connectors, customer fork, autonomous publish, cross-customer learning and replacement promise.

**Paid Shadow readiness predicates:**

- Internal Pilot Ready evaluation is `GO`;
- production Temporal decision is `GO_MANAGED_TEMPORAL` or `GO_SELF_HOSTED_TEMPORAL` and its profile preflight passes;
- real signed agreement/payment evidence exists;
- both sponsor and workflow owner are named and confirmed;
- representative prior/live queue and human/process baseline are frozen;
- authorised rights/data/destination and release owner exist;
- budget, stop switch, backup and incident route pass;
- Shadow cannot write to production destination;
- no customer assets/evidence are stored in Git.

- [ ] **Step 1: Write failing readiness tests from the protocol**

  Use synthetic records to test every missing field independently, unpaid agreement, development Temporal, no baseline, no rights, absent workflow owner, production-effect Shadow and stale Internal Pilot evidence.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_paid_shadow_readiness.py
  ```

  Expected: failure because checker/protocol files are absent.

- [ ] **Step 3: Implement deterministic readiness checker and documents**

  ```bash
  python scripts/check_paid_shadow_readiness.py --evidence-dir /absolute/customer-safe/evidence-dir
  ```

  Exit codes are exact: 0 `GO`, 2 `REFRAME`, 3 `KILL`, 4 invalid/unverifiable evidence. The checker prints eligible, missing, stale and contradictory predicates separately.

- [ ] **Step 4: Run the synthetic readiness suite**

  ```bash
  python -m pytest -q tests/test_paid_shadow_readiness.py tests/test_pilot_gates.py tests/test_claim_permissions.py
  ```

  Expected: all tests pass. No real company is named or implied.

- [ ] **Step 5: Commit Pilot product and checker**

  ```bash
  git add docs/product/pilot scripts/check_paid_shadow_readiness.py wenxin-backend/tests/test_paid_shadow_readiness.py
  git commit -m "docs: define paid shadow operating transfer"
  ```

---

### Task 7: Run the Internal Pilot gate and hand off the next external decision

**Files:**

- Create after actual internal runs: `docs/product/campaign-static/evidence/internal-pilot-evaluation.json`
- Create after actual internal runs: `docs/product/campaign-static/evidence/internal-pilot-summary.md`
- Modify only if evidence supports it: `wenxin-backend/app/job_runtime/job_classes/campaign_static_coverage_v4.yaml`

- [ ] **Step 1: Verify every prerequisite with fresh commands**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform/wenxin-backend
  python -m pytest -q \
    tests/test_campaign_static_golden.py \
    tests/test_operating_metrics.py \
    tests/test_pilot_gates.py \
    tests/test_trust_decisions.py \
    tests/test_trust_demotion.py \
    tests/test_job_runtime_backup.py \
    tests/test_pilot_evidence_bundle.py \
    tests/test_claim_permissions.py
  python -m pytest -q -m temporal \
    tests/temporal/test_job_runtime_restart.py \
    tests/temporal/test_campaign_static_e2e.py \
    tests/temporal/test_job_runtime_recovery_drill.py
  ```

  Expected: all tests pass.

- [ ] **Step 2: Run three consecutive mechanical corpora without code/config changes**

  ```bash
  python scripts/run_campaign_static_golden.py --provider mock --repeat 3 --fail-on-intervention --report /tmp/vulca-campaign-golden-3x.json
  ```

  Expected: all 36 declared outcomes match; no hidden manual rescue.

- [ ] **Step 3: Verify authorised real-provider and human-review evidence**

  Confirm Plan 04 Task 7 files exist, hashes match, eight jobs are complete, human-confirmed fields were entered by an authorised reviewer and thresholds were not changed after output inspection. If absent, the gate is `REFRAME: real evidence missing`, not GO.

- [ ] **Step 4: Run recovery and internal deployment checks**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  python scripts/vulca_runtime.py preflight --profile internal
  python scripts/vulca_runtime.py drill --profile internal --suite all
  ```

  Expected: all component/recovery checks pass; profile remains labelled `INTERNAL_ONLY`.

- [ ] **Step 5: Evaluate and sign the exact Internal Pilot decision**

  ```bash
  cd wenxin-backend
  python -m app.services.job_runtime.pilot_gates evaluate \
    --job-class campaign-static-creative-production-release.v1 \
    --thresholds app/job_runtime/job_classes/campaign_static_thresholds_v1.yaml \
    --output ../docs/product/campaign-static/evidence/internal-pilot-evaluation.json
  ```

  Expected: one of `GO`, `REFRAME`, `KILL`, with every predicate and evidence hash. A `GO` permits only the claim in the program plan: Internal-Pilot-ready implementation candidate.

- [ ] **Step 6: Write the summary without upgrading evidence status**

  `internal-pilot-summary.md` must state checkout SHAs, environment, corpus and provider/evaluator versions, coverage counts, better/exclusive evidence, metrics, incidents, recovery results, limitations and next decision.

- [ ] **Step 7: Commit internal evidence only if it actually exists and contains no customer/private data**

  ```bash
  git add docs/product/campaign-static/evidence/internal-pilot-evaluation.json docs/product/campaign-static/evidence/internal-pilot-summary.md
  git commit -m "docs: record campaign internal pilot decision"
  ```

  If the gate has not been run, do not create or commit these files.

---

## Plan 06 completion gate

- [ ] Operating metrics and predicates are reproducible from canonical evidence and are not collapsed into one trust score.
- [ ] TrustDecisions are signed, scoped, expiring, revocable and automatically demoted on declared triggers.
- [ ] Internal composition starts safely, is visibly non-production and survives all recovery drills.
- [ ] Paid Shadow rejects development Temporal and remains blocked until one explicit production profile passes.
- [ ] Backup/restore verifies database, artifact and evidence hashes in a fresh isolated composition.
- [ ] Claim permissions cap current evidence honestly; local completion cannot yield customer, `OWNED` or `REPLACED` claims.
- [ ] The Internal Pilot decision is an actual `GO`, `REFRAME` or `KILL`, not assumed from test success.
- [ ] A real paid Shadow run remains a separate externally authorised action with agreement, payment, baseline, rights, owners and deployment evidence.

If the final result is `GO`, the next action is to qualify and sell one fixed-scope paid Shadow Pilot while keeping product work on this same JobClass. If `REFRAME`, improve only the failed Cell/evaluator/contract/UX/deployment predicate. If `KILL`, stop broad creative-runtime investment and preserve the evidence for a narrower product decision.
