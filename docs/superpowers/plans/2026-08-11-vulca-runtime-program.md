# VULCA Accountable Runtime Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the approved VULCA product constitution into one deployable, restart-safe creative-production runtime whose first sellable JobClass owns approved business input through generated static campaign assets, independent evaluation, human release, delivery receipt, and governed MemoryCandidates.

**Architecture:** Keep `vulca` as the only Capability SDK and `vulca-platform` as the only customer product and Job runtime. Build one typed contract across SDK capabilities, platform Job state, Temporal workflows, append-only business evidence, and the queue-first React control surface. Complete one vertical C before composing C into D, while representing the full company chain in the canonical domain from day one.

**Tech Stack:** Python 3.11/3.12, dataclasses and protocols in `vulca`, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL, Temporal Python SDK 1.30.0, local content-addressed artifact storage, React 19, TypeScript 5.8, Vite 7, Vitest 4, Playwright.

## Global Constraints

- In every implementation shell, first run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`. The current unversioned `python3` is 3.14.4 and is not the program interpreter.
- The approved specification at `docs/superpowers/specs/2026-08-11-vulca-accountable-creative-organization-runtime-design.md` is the product constitution. If an implementation choice conflicts with it, stop and amend the plan before changing product code.
- Product code changes span two repositories. Execute each task in the repository named by that task and never combine cross-repository files in one commit.
- `vulca` owns Capability contracts and implementations. It must not own Organizations, Jobs, customer authentication, release decisions, or product navigation.
- `/Users/yhryzy/dev/vulca-platform` owns Organizations, Jobs, durable workflow state, business evidence, artifacts, release, delivery, the customer UI, and operating claims. It must not contain or package a second `vulca` implementation.
- The first activated JobClass is exactly `campaign-static-creative-production-release.v1`.
- The routine path is brief → contract → plan → real generation → edit/adapt → independent evaluation → bounded repair or exception → package → human release → destination reconciliation → DeliveryReceipt → inert MemoryCandidates.
- No required routine row in the JobClass Capability Coverage Ledger may remain `MISSING` at Pilot acceptance.
- Pilot acceptance additionally requires at least one predeclared `BETTER` operating metric and one evidence-backed `EXCLUSIVE` responsibility advantage.
- Human release is mandatory. No task in this program authorises autonomous public publishing.
- A mock provider proves mechanics only. Real generation provenance and representative output evidence are separate Pilot gates.
- Temporal history is execution infrastructure, not VULCA business evidence. Every business-significant action must still append an `EvidenceEvent`.
- No probabilistic component may mint its own `StepGrant`, choose away a required evaluator, approve its own artifact, issue a `ReleaseToken`, or infer rights, spend, data use, destination, or release authority.
- Legacy Workspace records remain read-only or are explicitly migrated. New runtime code must not write new `ReviewItem` execution state.
- Illustrative demo/replay state, local test results, and Pilot evidence must remain technically and visually distinct.
- Do not publish, deploy, send outreach, or claim customer adoption while executing these plans unless the user separately authorises that action.

---

## 1. Canonical program boundary

### 1.1 Repository ownership

| Repository | Canonical responsibility | Program plans |
|---|---|---|
| `/Users/yhryzy/.codex/worktrees/02e5/vulca` | Capability manifests, invocation/result envelopes, registry, canonical generation/edit/composition/adaptation/validation/evaluation Cells, SDK compatibility contract | Plan 01 |
| `/Users/yhryzy/dev/vulca-platform` | Product data spine, workflow runtime, authority, artifact/evidence storage, first JobClass, control center, deployment and Pilot evidence | Plans 01–06 |

At execution start, record the exact SHA of both checkouts in the first implementation commit message. The plan was written against:

- SDK branch `codex/vulca-accountable-runtime-design`, beginning at `3bbecb4c` before these plan documents;
- platform branch `codex/vulcaart-v8-production`, beginning at `f65b0a87`.

If either checkout has moved, run the plan's targeted discovery commands again and adjust only paths or dependency versions that actually changed. Do not silently reinterpret the product contract.

The current SDK checkout is `0.23.1`. Adding the new Capability contract changes its public package surface, so the implementation target is `0.24.0`; do not mutate and redistribute `0.23.1` under the same version. The platform stores an exact SDK source commit and wheel SHA-256 in `wenxin-backend/vulca-sdk.lock.json`, pins `vulca==0.24.0`, and installs only a wheel that matches that lock. Publishing or pushing the new SDK remains a separate external action requiring user authority; local implementation may build and verify the wheel from the SDK checkout.

### 1.2 One canonical interface chain

```text
JobIntakeRequest
  -> immutable JobSpec
  -> immutable RunPlan/StepSpec
  -> scoped StepGrant
  -> idempotent GrantAttempt
  -> CapabilityInvocation
  -> CapabilityResult + content hashes/provider receipt
  -> ArtifactVersion
  -> EvalReport
  -> DecisionRecord
  -> ReleaseToken
  -> DeliveryReceipt
  -> MemoryCandidate
```

Every arrow is a typed, versioned boundary. JobSpec freezes approved execution/evaluator bindings; StepSpec refers to them by key; GrantAttempt records each bounded paid attempt. No frontend state, hidden chat context, provider response, or Temporal event substitutes for these records.

### 1.3 Canonical ID, JSON, and time rules

- Product IDs are lowercase prefixes plus UUID4 hex: `org_`, `orgpack_`, `brand_`, `policy_`, `unit_`, `jobclass_`, `ledger_`, `job_`, `jobspec_`, `run_`, `runplan_`, `step_`, `grant_`, `grantattempt_`, `artifact_`, `artifactver_`, `eval_`, `decision_`, `release_`, `receipt_`, `event_`, `memory_`, `trust_`.
- Database ID columns are `String(64)`. `OrganizationMembership.actor_id` stores `str(User.id)` so SQLite string IDs and PostgreSQL UUID IDs share one API contract.
- API JSON uses camelCase aliases. Python code and database columns use snake_case.
- All timestamps are timezone-aware UTC ISO 8601 at API boundaries and timezone-aware database timestamps internally.
- Immutable payload hashes use UTF-8 JSON sorted by key with separators `(',', ':')`, no NaN, then SHA-256.
- Artifact hashes are SHA-256 over exact bytes. A logical `Artifact` may have many immutable `ArtifactVersion` rows.
- Currency spend is integer minor units plus ISO currency; never floating-point money.

### 1.4 Canonical state values

```python
class JobState(StrEnum):
    RECEIVED = "RECEIVED"
    NEEDS_INPUT = "NEEDS_INPUT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    WAITING_DECISION = "WAITING_DECISION"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RunState(StrEnum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    AUTHORIZED = "AUTHORIZED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class StepState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_RETRY = "WAITING_RETRY"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"

class ArtifactState(StrEnum):
    DRAFT = "DRAFT"
    CANDIDATE = "CANDIDATE"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"

class DeliveryStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    CONFLICT = "CONFLICT"

class DecisionAction(StrEnum):
    APPROVE_RELEASE = "APPROVE_RELEASE"
    REQUEST_REPAIR = "REQUEST_REPAIR"
    BLOCK = "BLOCK"
    CANCEL = "CANCEL"
```

State transitions occur only through `app/job_runtime/state_machine.py` and append an EvidenceEvent in the same database transaction.

### 1.5 API contract

The first customer API is authenticated and single-tenant-per-deployment:

| Method and path | Contract |
|---|---|
| `POST /api/v1/jobs` | Require `Idempotency-Key`; compile intake to `Job` and immutable `JobSpec`; return existing Job for an identical duplicate |
| `GET /api/v1/jobs` | Filter by state, JobClass, due date, and exception status; stable cursor pagination |
| `GET /api/v1/jobs/{jobId}` | Return current state, milestones, exact versions, artifacts, evaluations, exception, delivery and evidence summary |
| `POST /api/v1/jobs/{jobId}/inputs` | Supply an explicitly missing/approval-required field and create `JobSpec v+1` |
| `POST /api/v1/jobs/{jobId}/decisions` | Record one authorised decision over exact hashes/versions and signal the workflow |
| `POST /api/v1/jobs/{jobId}/cancel` | Cancel execution and revoke unconsumed grants |
| `GET /api/v1/jobs/{jobId}/events` | Return the customer-safe append-only causal history |
| `GET /api/v1/job-classes` | Return activated JobClasses and Pilot status |
| `GET /api/v1/job-classes/{jobClassId}/coverage` | Return versioned coverage rows, route, evidence qualifier and baseline references |
| `POST /api/v1/memory-candidates/{candidateId}/decisions` | Approve, reject, revoke or expire a candidate within membership authority |

The API must never return private chain-of-thought. Developer detail is structured plan, call, grant, evaluator, retry, cost and receipt data.

### 1.6 Artifact store contract

```python
@dataclass(frozen=True)
class StoredArtifact:
    sha256: str
    byte_count: int
    media_type: str
    storage_uri: str

class ArtifactStore(Protocol):
    async def put_bytes(
        self,
        *,
        organization_id: str,
        data: bytes,
        media_type: str,
    ) -> StoredArtifact: ...

    async def read_bytes(self, *, storage_uri: str) -> bytes: ...

    async def verify(self, *, storage_uri: str, sha256: str) -> bool: ...
```

The local implementation writes atomically under:

```text
${VULCA_ARTIFACT_ROOT}/{organization_id}/{sha256[0:2]}/{sha256}
```

Logical names, provenance, parent versions, and customer-visible metadata belong in PostgreSQL, not in the storage path.

### 1.7 Workflow driver contract

```python
@dataclass(frozen=True)
class JobWorkflowInput:
    job_id: str
    job_spec_id: str
    run_id: str
    run_plan_id: str

@dataclass(frozen=True)
class JobWorkflowResult:
    job_id: str
    final_state: str
    delivery_receipt_id: str | None

class WorkflowDriver(Protocol):
    async def start_job(self, value: JobWorkflowInput) -> str: ...
    async def signal_decision(self, workflow_id: str, decision_id: str) -> None: ...
    async def cancel_job(self, workflow_id: str, reason: str) -> None: ...
```

Temporal workflow code performs no network, provider, file, secret, or database I/O. Those operations are activities, and activity inputs carry only stable IDs or bounded serialisable values.

---

## 2. Dependency-ordered plan package

Execute the files in this exact order unless a plan's explicit gate stops the program:

1. [Plan 01 — Canonical SDK convergence](2026-08-11-vulca-runtime-01-canonical-sdk-convergence.md)
2. [Plan 02 — Job data spine](2026-08-11-vulca-runtime-02-job-data-spine.md)
3. [Plan 03 — Durable workflow runtime](2026-08-11-vulca-runtime-03-durable-workflow-runtime.md)
4. [Plan 04 — Campaign static JobClass](2026-08-11-vulca-runtime-04-campaign-static-jobclass.md)
5. [Plan 05 — Job Control Center](2026-08-11-vulca-runtime-05-job-control-center.md)
6. [Plan 06 — Pilot evidence and operating gates](2026-08-11-vulca-runtime-06-pilot-evidence-gates.md)

Plans 04 and 05 may run in parallel only after Plan 03's workflow acceptance spike passes and Plan 02's API schemas are frozen. Plan 06 begins only after Plans 04 and 05 pass their own gates.

### Program gates

| Gate | Required evidence | Stop condition |
|---|---|---|
| G0 — one SDK | Platform imports the locked canonical `vulca==0.24.0` wheel; provenance test proves no vendored copy | Any production path still copies/imports the vendored SDK or cannot reproduce the locked wheel |
| G1 — one Job truth | Duplicate intake, immutable versions, append-only evidence and read-only legacy adapter pass | New execution state is written into `ReviewItem` or browser storage |
| G2 — durable kernel | Synthetic workflow survives worker restart, bounded failure, cancellation, signal wait and delivery reconciliation | Temporal cannot meet the semantics within the declared local operating envelope; choose `REFRAME` before broad runtime code |
| G3 — full vertical | One static campaign travels from brief to receipt and MemoryCandidate without routine competitor-UI escape | Any required coverage row is `MISSING`, or generation/delivery is manually relayed |
| G4 — usable control | Authenticated operator completes intake, exception, exact release and receipt checks without graph/prompt plumbing | Routine work requires DAG authoring, raw provider switching or demo state |
| G5 — Internal Pilot Ready | Frozen representative corpus, real generation provenance, complete evidence, recovery drills, one `BETTER` metric and one `EXCLUSIVE` advantage | Hidden founder rescue, unbounded cost, weak baseline, or missing recovery evidence |
| G6 — Paid Shadow Ready | Signed scope, rights, sponsor, workflow owner, baseline, budget, stop switch and one approved deployment route | No paid bounded queue or no authority owner; choose `REFRAME` or `KILL` |

---

## 3. Current competitor floor for the first ledger

The ledger is not a feature-marketing comparison. It is a versioned set of routine capabilities that the selected JobClass must cover inside VULCA. The initial official-product baselines, refreshed on 2026-08-11, are:

- Adobe GenStudio for Performance Marketing: campaign organisation, copy/creative variants, brand/channel/accessibility checks, approvals, asset repositories and activation integrations.
- Canva Enterprise: AI generation/editing, resize, Brand Kits, locked templates, collaboration, approval, DAM/integration and publishing surfaces.
- Recraft: raster/vector generation, custom brand styles and colours, editing, mockups, background removal, vectorisation and multi-format export.
- TapNow: brief/context interpretation, agent planning, image/video production, selected-node revision, batch processing, delivery preparation, reusable templates and an infinite-canvas workflow.
- Photoroom API: scaled generation/editing, background removal/replacement, relighting, repositioning, resizing, product composition and automated image QA.
- The Brief (formerly Creatopy): ad templates, brand customisation, collaboration, animation/video support, Smart Resize, bulk variants and export/automation surfaces.

The ledger compares capabilities and operating responsibility, not interface resemblance. VULCA may mark a row `ADAPTED` when an external API sits behind a typed Cell and the operator stays inside the VULCA Job. A manual export/import into an external UI is `MISSING`.

---

## 4. One-founder execution envelope

The fastest credible path is a vertical program, not six polished horizontal platforms.

| Workstream | Founder-time estimate | Exit |
|---|---:|---|
| Canonical SDK convergence | 4–7 focused days | G0 |
| Job data spine and API | 8–12 focused days | G1 |
| Temporal acceptance and durable kernel | 8–15 focused days | G2 |
| First static JobClass and Golden corpus | 15–25 focused days | G3 |
| Operator control center | 8–15 focused days, partly parallel with JobClass | G4 |
| Recovery, metrics and Internal Pilot hardening | 10–20 focused days | G5 |

This implies roughly 9–14 full-time founder weeks to Internal Pilot Ready if the current platform foundations remain reusable, followed by customer-specific Shadow work. It is not evidence that a Pilot, deployment, customer, or replacement outcome already exists.

To preserve speed:

- use one intake form and one local-folder delivery adapter;
- use one static campaign JobClass and one bounded repair cycle;
- adapt strong generation/editing providers behind Cells before building native models;
- keep cross-media Shadow-only;
- reject bespoke customer forks until the shared vertical works;
- ship each plan behind its gate rather than polishing public marketing surfaces in parallel.

---

## 5. Specification traceability

| Requirement | Owning implementation and evidence |
|---|---|
| `FR-01` idempotent intake | Plan 02 Task 5; concurrent duplicate API tests |
| `FR-02` JobSpec and missing hard fields | Plan 02 Tasks 3 and 5; compiler plus `NEEDS_INPUT` tests |
| `FR-03` UI-independent durability | Plan 03 Tasks 1, 2 and 6; real-server restart tests |
| `FR-04` bounded RunPlan | Plan 03 Task 3 and Plan 04 Task 2; exact template/compiler tests |
| `FR-05` narrow StepGrants | Plan 03 Task 3; expiry/revocation/scope tests |
| `FR-06` isolated Cells | Plan 01 contract plus Plan 03 Task 4; activity/idempotency tests |
| `FR-07` immutable artifact versions | Plan 02 Task 4 and Plan 04 Tasks 3–4; lineage/repair tests |
| `FR-08` independent evaluation and Policy Gate | Plan 04 Task 4; anti-gaming/abstention tests |
| `FR-09` explicit exceptions | Plan 02 read DTOs and Plan 05 Task 5; API/component/E2E tests |
| `FR-10` release and receipt | Plan 03 Task 5 and Plan 04 Task 5; token/reconciliation/package tests |
| `FR-11` customer/developer evidence views | Plan 02 Task 6 and Plan 05 Tasks 4/6; redaction/UI tests |
| `FR-12` cancellation/revocation/retry/reconciliation | Plan 03 Tasks 3–6 and Plan 06 Task 4; recovery drills |
| `FR-13` separate operating metrics | Plan 06 Task 1; denominator and no-aggregate-score tests |
| `FR-14` bounded TrustDecisions | Plan 06 Task 2; scope/signature/demotion tests |
| `FR-15` complete creative chain in one Job | Plan 04 Task 6; 12-case vertical Golden corpus |
| `FR-16` versioned coverage ledger | Plan 04 Tasks 1–5/7; schema and evidence audits |
| `FR-17` real content generation | Plan 04 Tasks 3 and 7; provider provenance plus human review |
| `FR-18` no competitor-UI handoff | Plan 04 ledger and Plan 05 Task 7; coverage/E2E architecture tests |
| `FR-19` inert governed learning | Plan 04 Task 5 and Plan 05 Task 6; promotion/revocation tests |
| `FR-20` one canonical SDK | Plan 01; wheel lock, provenance and no-vendored-source tests |
| `FR-21` legacy evidence without legacy execution | Plan 02 Task 6 and Plan 05 Task 6; read-only/architecture tests |

Non-functional ownership is equally explicit:

- reliability: Plan 03 and Plan 06 Task 4;
- security/privacy/least privilege: Plans 02–03, Plan 04 rights gates, Plan 06 deployment preflight;
- auditability: Plan 02 evidence spine and Plan 06 signed bundles;
- provider independence: Plan 01 exact Capability contracts, Plan 03 validated fallback rules, Plan 04 independent evaluator binding;
- usability: Plan 05's queue/exception-first frontend and live-backend E2E.

Any implementation pull request must name the relevant FR rows and include their exact verification commands. An FR cannot be marked complete by a plan document, mock screenshot or adjacent subsystem test.

---

## 6. Program-level verification

- [ ] Run all SDK checks from `/Users/yhryzy/.codex/worktrees/02e5/vulca`:

  ```bash
  python -m ruff check src/vulca/capability tests/test_capability_contract.py tests/test_capability_builtin.py tests/test_capability_static.py
  python -m mypy src/vulca/capability
  python -m pytest -q tests/test_capability_contract.py tests/test_capability_builtin.py tests/test_capability_static.py tests/test_backward_compat.py
  ```

  Expected: exit 0; capability registry resolves exact versions; existing public imports remain compatible.

- [ ] Run backend checks from `/Users/yhryzy/dev/vulca-platform/wenxin-backend`:

  ```bash
  python -m pytest -q \
    tests/test_canonical_vulca_sdk.py \
    tests/test_job_domain.py \
    tests/test_job_migrations.py \
    tests/test_job_intake_api.py \
    tests/test_job_runtime_temporal.py \
    tests/test_campaign_static_jobclass.py \
    tests/test_campaign_static_golden.py \
    tests/test_pilot_gates.py
  ```

  Expected: exit 0; no test requires a real provider unless marked `real_provider`; mock tests do not satisfy the real-generation Pilot gate.

- [ ] Run frontend checks from `/Users/yhryzy/dev/vulca-platform/wenxin-moyun`:

  ```bash
  npm run type-check
  npm test -- --run \
    src/__tests__/features/job-control \
    src/__tests__/pages/JobControlCenterPage.test.tsx \
    src/__tests__/routes/platformModules.test.ts
  npm run test:e2e:workspace
  ```

  Expected: exit 0; `/workspace` is protected, live API-backed, and visibly distinct from replay/demo state.

- [ ] Run architecture scans from `/Users/yhryzy/dev/vulca-platform`:

  ```bash
  test ! -d vulca/src/vulca
  test ! -d wenxin-backend/vulca
  ! rg -n "cp -r vulca/src/vulca|./vulca/src/vulca:/app/vulca" .github docker-compose.yml wenxin-backend
  ! rg -n "ReviewItem" wenxin-backend/app/job_runtime wenxin-backend/app/services/job_runtime wenxin-backend/app/api/v1/jobs.py
  ! rg -n "BackgroundTasks" wenxin-backend/app/job_runtime wenxin-backend/app/services/job_runtime wenxin-backend/app/api/v1/jobs.py
  ```

  Expected: every command exits 0.

- [ ] Run the end-to-end local deployment and close/reopen/restart drill defined in Plan 06.

  Expected: the exact Job returns to its prior durable state, completes only after a human decision and verified DeliveryReceipt, and retains all prior artifact versions and EvidenceEvents.

---

## 7. Program completion claim

After all six plans pass, the strongest allowed local claim is:

> VULCA has an Internal-Pilot-ready implementation candidate for one bounded static campaign production and governed-delivery JobClass, with a canonical SDK, durable workflow semantics, queue-first operator UI, complete capability routing, human release, delivery reconciliation, and evidence-controlled learning candidates.

Do not call this a deployed customer system, paid Pilot, owned queue, employee replacement, or whole-company creative operating unit until the corresponding external evidence exists.
