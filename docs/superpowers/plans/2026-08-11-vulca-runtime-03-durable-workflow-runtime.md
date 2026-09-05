# VULCA Durable Workflow Runtime Implementation Plan

> **Status: historical (2026-08-11).** On 2026-08-14 VULCA moved Job Runtime ownership to the DSH/Cordis-derived native kernel in `vulca-platform` (see its `docs/product/2026-08-14-vulca-unified-product-prd.md`). The capability contracts in `src/vulca/capability/` (plan 01) remain canonical and are consumed by that kernel as a sidecar; the runtime plans 02–06 in this series are superseded by the platform-side milestones and are kept only as design record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a restart-safe, signal-driven Job runtime that validates plans, issues narrow grants, executes Cells through activities, survives worker loss, reconciles external writes and records VULCA EvidenceEvents independently of workflow history.

**Architecture:** Use Temporal only after an explicit acceptance spike. FastAPI writes business state plus workflow commands to a transactional outbox; a separate worker process dispatches idempotent start/signal/cancel commands and runs deterministic workflows. Temporal workflow code carries stable IDs and control flow only. Database, SDK, provider, artifact, release and evidence work occurs in idempotent activities guarded by StepGrants.

**Tech Stack:** Temporal Python SDK `1.30.0`, Temporal CLI container `temporalio/temporal:1.8.0` for development acceptance only, FastAPI, SQLAlchemy async, Alembic, PostgreSQL, pytest-asyncio, Docker Compose.

## Global Constraints

- Before any Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute this plan in `/Users/yhryzy/dev/vulca-platform` after Plans 01 and 02 pass.
- Task 1 is a Go/Reframe engineering gate. If any required durable semantic cannot be demonstrated within the declared local envelope, stop this plan and write a replacement-engine decision; do not continue Tasks 2–6 by inertia.
- `temporalio/temporal:1.8.0 server start-dev` is a local development/test dependency, not the Pilot production deployment.
- Temporal workflow history does not replace `EvidenceEvent`, `ArtifactVersion`, `DecisionRecord`, `ReleaseToken` or `DeliveryReceipt`.
- Workflow code must not import SQLAlchemy, FastAPI, `vulca`, filesystem/path modules, provider SDKs or secret/config adapters.
- Every activity is idempotent under at-least-once execution. A duplicate activity may return the existing immutable record; it may not repeat a paid or external side effect blindly.
- Provider retry is bounded by the StepSpec, StepGrant, manifest retryable codes, recorded GrantAttempt state and Job resource envelope. An unknown provider outcome is never retried automatically unless the same provider operation has a verified idempotency key or reconciliation route.
- Human release remains mandatory.

---

### Task 1: Run the Temporal acceptance kill test before runtime investment

**Files:**

- Modify: `wenxin-backend/pyproject.toml`
- Modify: `wenxin-backend/requirements.txt`
- Modify: `wenxin-backend/requirements.render.txt`
- Modify: `wenxin-backend/requirements.cloudrun.txt`
- Create: `docker-compose.temporal-dev.yml`
- Create: `wenxin-backend/tests/temporal/__init__.py`
- Create: `wenxin-backend/tests/temporal/acceptance_workflow.py`
- Create: `wenxin-backend/tests/temporal/test_temporal_acceptance.py`
- Create: `wenxin-backend/scripts/check_temporal_acceptance.py`
- Modify: `wenxin-backend/pyproject.toml` pytest markers

Pin `temporalio==1.30.0` in backend metadata and all runtime requirement sets. Add marker:

```toml
"temporal: requires the pinned local Temporal dev service on localhost:7233"
```

The dev compose service is exact:

```yaml
services:
  temporal-dev:
    image: temporalio/temporal:1.8.0
    command: server start-dev --ip 0.0.0.0
    ports:
      - "7233:7233"
      - "8233:8233"
```

The acceptance workflow uses one retrying activity, waits for a decision signal, supports cancellation, and runs a reconciliation activity after a simulated “write happened, receipt persistence did not” failure.

- [ ] **Step 1: Write the failing acceptance suite**

  The suite must prove all six behaviours against a real local server:

  1. workflow start with a stable workflow ID;
  2. an activity fails once with an application retryable error and succeeds exactly once thereafter;
  3. the workflow waits with no worker-side busy loop and resumes from a decision signal;
  4. stopping worker A after a durable checkpoint and starting worker B completes the same workflow without repeating a completed side effect;
  5. cancellation reaches a terminal cancelled state and prevents later activity execution;
  6. an unknown delivery outcome is reconciled by querying exact destination state before any second write.

  Store side-effect call counts in a test-only SQLite file outside Temporal history so replay alone cannot fake the result.

- [ ] **Step 2: Run before installing/configuring Temporal and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q -m temporal tests/temporal/test_temporal_acceptance.py
  ```

  Expected: collection or connection failure because the SDK/service is not installed/configured.

- [ ] **Step 3: Add the exact dependency and start the pinned dev service**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  docker compose -f docker-compose.temporal-dev.yml up -d
  docker compose -f docker-compose.temporal-dev.yml ps
  ```

  Expected: `temporal-dev` is running and ports 7233/8233 are published.

- [ ] **Step 4: Implement and run the acceptance harness**

  ```bash
  cd wenxin-backend
  python scripts/check_temporal_acceptance.py --address localhost:7233 --namespace default
  python -m pytest -q -m temporal tests/temporal/test_temporal_acceptance.py
  ```

  Expected: the script prints one JSON object with all six keys set to `true`; pytest exits 0.

- [ ] **Step 5: Make the explicit engine decision**

  Record one of these exact outcomes in the implementation log:

  - `GO_TEMPORAL`: all six semantics pass and local API/worker operating weight is acceptable;
  - `REFRAME_ENGINE`: one or more semantics fail, required binaries do not work on the target architecture, or the one-founder local deployment weight is unacceptable.

  On `REFRAME_ENGINE`, stop the plan. The replacement proposal must demonstrate the same six semantics; Celery availability or a database queue alone is not equivalence.

- [ ] **Step 6: Commit only after `GO_TEMPORAL`**

  ```bash
  git add docker-compose.temporal-dev.yml wenxin-backend/pyproject.toml wenxin-backend/requirements*.txt wenxin-backend/tests/temporal wenxin-backend/scripts/check_temporal_acceptance.py
  git commit -m "test: validate temporal durability semantics"
  ```

---

### Task 2: Add workflow contracts, transactional command outbox and separate worker

**Files:**

- Create: `wenxin-backend/app/models/job_workflow.py`
- Modify: `wenxin-backend/app/models/__init__.py`
- Create: `wenxin-backend/alembic/versions/job_runtime_workflow.py`
- Create: `wenxin-backend/app/job_runtime/workflow_contracts.py`
- Create: `wenxin-backend/app/job_runtime/workflows.py`
- Create: `wenxin-backend/app/job_runtime/temporal_driver.py`
- Create: `wenxin-backend/app/job_runtime/dispatch.py`
- Create: `wenxin-backend/app/job_runtime/worker.py`
- Modify: `wenxin-backend/pyproject.toml`
- Create: `wenxin-backend/tests/test_workflow_outbox.py`
- Create: `wenxin-backend/tests/test_workflow_determinism.py`
- Create: `wenxin-backend/tests/test_job_worker_entrypoint.py`

**Migration:**

```python
revision = "job_runtime_workflow"
down_revision = "job_runtime_core"
```

**Outbox table:** `workflow_commands`

| Column | Contract |
|---|---|
| `id` | prefixed immutable ID |
| `organization_id`, `job_id` | canonical ownership FKs |
| `command_type` | `START`, `SIGNAL_DECISION`, `CANCEL` |
| `command_key` | stable workflow ID, decision ID or cancel request ID |
| `payload`, `payload_hash` | immutable serialisable command |
| `status` | `PENDING`, `PROCESSING`, `PROCESSED`, `FAILED` |
| `attempts`, `available_at`, `last_error_code` | bounded dispatcher state |
| `lease_owner`, `lease_expires_at` | crash-safe single command ownership |
| timestamps | UTC |

Unique `(job_id, command_type, command_key)` makes API retries safe.

**Workflow contracts:** use the exact `JobWorkflowInput`, `JobWorkflowResult` and `WorkflowDriver` protocol from the program plan. Workflow ID is `vulca-job-{job_id}`; task queue is `vulca-job-runtime-v1`.

- [ ] **Step 1: Write failing outbox, workflow-ID and import-boundary tests**

  Prove a Job transaction and START command commit together, rollback together, duplicate commands collapse, expired dispatcher leases can be reclaimed, and workflow source imports none of the forbidden modules.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_workflow_outbox.py tests/test_workflow_determinism.py tests/test_job_worker_entrypoint.py
  ```

  Expected: failure because workflow model/modules are absent.

- [ ] **Step 3: Implement migration, driver, dispatcher and worker entrypoint**

  Add:

  ```toml
  [project.scripts]
  vulca-job-worker = "app.job_runtime.worker:main"
  ```

  The worker creates one Temporal client, runs one `temporalio.worker.Worker`, and concurrently runs the outbox dispatcher. Graceful shutdown stops claiming commands, finishes/returns the current lease, and shuts down the worker.

- [ ] **Step 4: Run unit and migration tests**

  ```bash
  python -m pytest -q tests/test_workflow_outbox.py tests/test_workflow_determinism.py tests/test_job_worker_entrypoint.py tests/test_job_migrations.py
  ```

  Expected: all tests pass and Alembic has one head at `job_runtime_workflow`.

- [ ] **Step 5: Commit workflow infrastructure**

  ```bash
  git add wenxin-backend/app/models wenxin-backend/alembic/versions/job_runtime_workflow.py wenxin-backend/app/job_runtime wenxin-backend/pyproject.toml wenxin-backend/tests/test_workflow_*.py wenxin-backend/tests/test_job_worker_entrypoint.py
  git commit -m "feat: add durable workflow command outbox"
  ```

---

### Task 3: Validate bounded RunPlans and issue revocable StepGrants

**Files:**

- Create: `wenxin-backend/app/job_runtime/planning.py`
- Create: `wenxin-backend/app/services/job_runtime/authority.py`
- Create: `wenxin-backend/app/services/job_runtime/runs.py`
- Create: `wenxin-backend/tests/test_run_plan_validation.py`
- Create: `wenxin-backend/tests/test_step_grants.py`

**RunPlan shape:**

```python
class StepSpec(ApiModel):
    step_key: str
    capability_id: str
    capability_version: str
    execution_binding_ref: str
    depends_on: list[str]
    input_refs: list[str]
    output_contract: dict[str, JsonValue]
    requested_actions: list[str]
    max_attempts: int
    timeout_seconds: int
    estimated_spend_minor: int
    required_eval_spec_refs: list[str]

class RunPlanSpec(ApiModel):
    job_spec_id: str
    job_spec_hash: str
    template_id: Literal["synthetic-runtime-acceptance.v1", "campaign-static-creative-production-release.v1"]
    steps: list[StepSpec]
```

The initial validator permits only the two approved templates and their declared step-key sets. It rejects arbitrary graph expansion, cycles, missing exact capability versions, a binding reference absent from the immutable JobSpec, a provider/model added by planner output, total spend above JobSpec, absent independent evaluator paths, undeclared side effects and output type mismatches.

- [ ] **Step 1: Write failing validator and grant tests**

  Include stale JobSpec hash, cyclic plan, unknown execution-binding reference, planner-added provider/model/options, generation/evaluation binding collision, spend overflow, missing evaluation, expired grant, revoked grant, wrong action, cross-invocation grant reuse, idempotent duplicate attempt reservation, attempt overflow, cumulative-spend overflow and valid exact-scope cases.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_run_plan_validation.py tests/test_step_grants.py
  ```

  Expected: collection fails because validator/authority services are absent.

- [ ] **Step 3: Implement deterministic validation and grant service**

  ```python
  async def issue_step_grant(
      session: AsyncSession,
      *,
      job_spec: JobSpec,
      run: Run,
      step: Step,
      requested_action: str,
      requested_scope: dict[str, JsonValue],
      actor_id: str,
  ) -> StepGrant: ...

  @dataclass(frozen=True)
  class GrantAttemptAuthorization:
      grant_id: str
      invocation_key: str
      attempt_number: int
      remaining_attempts: int
      remaining_spend_minor: int

  async def reserve_grant_attempt(
      session: AsyncSession,
      *,
      grant_id: str,
      invocation_key: str,
      attempt_number: int,
      action: str,
      scope_hash: str,
      planned_spend_minor: int,
  ) -> GrantAttemptAuthorization: ...

  async def finalize_grant_attempt(
      session: AsyncSession,
      *,
      grant_id: str,
      invocation_key: str,
      attempt_number: int,
      status: Literal["SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "UNKNOWN"],
      actual_spend_minor: int,
      provider_request_id: str | None,
      result_hash: str | None,
  ) -> StepGrant: ...
  ```

  The first reservation atomically binds the grant to one stable `invocation_key`. A duplicate reservation for the same `(grant, invocation, attempt)` returns the existing record; another invocation is rejected. Every attempt and actual charge counts against the caps. Grant issuance/reservation/finalisation append `GRANT_ISSUED`, `GRANT_ATTEMPT_RESERVED`, `GRANT_ATTEMPT_FINALIZED` and terminal `GRANT_CONSUMED`; rejection appends a safe `GRANT_REJECTED` event without recording secrets.

- [ ] **Step 4: Run targeted tests**

  ```bash
  python -m pytest -q tests/test_run_plan_validation.py tests/test_step_grants.py tests/test_job_evidence.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit plan and authority kernel**

  ```bash
  git add wenxin-backend/app/job_runtime/planning.py wenxin-backend/app/services/job_runtime/authority.py wenxin-backend/app/services/job_runtime/runs.py wenxin-backend/tests/test_run_plan_validation.py wenxin-backend/tests/test_step_grants.py
  git commit -m "feat: validate plans and issue scoped grants"
  ```

---

### Task 4: Execute SDK Cells in idempotent activities

**Files:**

- Create: `wenxin-backend/app/job_runtime/activity_contracts.py`
- Create: `wenxin-backend/app/job_runtime/activities.py`
- Modify: `wenxin-backend/app/job_runtime/workflows.py`
- Modify: `wenxin-backend/app/job_runtime/worker.py`
- Create: `wenxin-backend/tests/test_capability_activities.py`
- Create: `wenxin-backend/tests/test_activity_retry_policy.py`

**Activity rule:** a capability activity receives `step_id`, `grant_id` and a stable `invocation_key`, loads canonical records plus the StepSpec's exact JobSpec execution binding, reserves the current Temporal attempt against the bound grant, constructs allowlisted Capability options from that binding, invokes the Plan 01 adapter once, then stores artifact bytes, inserts immutable ArtifactVersions and finalises the GrantAttempt/provider receipt/cost evidence transactionally. The server derives `invocation_key` as the SHA-256 of canonical JSON containing Job/Run/RunPlan/Step IDs, exact Capability ID/version, execution-binding hash, input-reference hashes and output contract; neither planner model nor frontend supplies it. Credentials are resolved separately from the binding's secret reference and never placed in workflow input, invocation, evidence or logs. The activity returns only IDs, hashes, verdict-neutral metadata and retry classification.

```python
@dataclass(frozen=True)
class ExecuteCapabilityActivityInput:
    job_id: str
    run_id: str
    step_id: str
    grant_id: str
    invocation_key: str

@dataclass(frozen=True)
class ExecuteCapabilityActivityResult:
    step_id: str
    artifact_version_ids: tuple[str, ...]
    output: dict[str, JsonValue]
```

- [ ] **Step 1: Write failing idempotency and retry tests**

  Test duplicate activity delivery returns existing ArtifactVersion IDs and invokes the adapter once; a `NOT_STARTED` retryable manifest failure causes bounded Temporal retry; a non-retryable failure stops immediately; a stale `STARTED` attempt or explicit `UNKNOWN` result without verified provider idempotency/reconciliation enters a visible exception and does not call the provider again; max attempt/spend exhaustion stops; cancellation after provider return quarantines late bytes and does not promote them to current artifact.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_capability_activities.py tests/test_activity_retry_policy.py
  ```

  Expected: failure because activity contracts/implementation are absent.

- [ ] **Step 3: Implement activity boundaries and explicit retry mapping**

  Set Temporal activity retry policies from StepSpec; do not wrap all exceptions as retryable. Before every call, persist `GRANT_ATTEMPT_RESERVED`/`STARTED`. On replay, a prior `STARTED` attempt with no conclusive result is an unknown paid outcome: reconcile by provider idempotency/request ID when supported, otherwise transition the Job to `WAITING_DECISION`. Automatic retry requires `side_effect_state=NOT_STARTED` or a verified same-operation idempotency/reconciliation contract. No provider fallback occurs unless the RunPlan contains a separately validated fallback StepSpec and fresh grant.

- [ ] **Step 4: Run unit and real-server activity tests**

  ```bash
  python -m pytest -q tests/test_capability_activities.py tests/test_activity_retry_policy.py tests/test_step_grants.py
  python -m pytest -q -m temporal tests/temporal/test_temporal_acceptance.py
  ```

  Expected: all tests pass; mock adapter call count proves idempotency.

- [ ] **Step 5: Commit activity execution**

  ```bash
  git add wenxin-backend/app/job_runtime wenxin-backend/tests/test_capability_activities.py wenxin-backend/tests/test_activity_retry_policy.py
  git commit -m "feat: execute capability cells as durable activities"
  ```

---

### Task 5: Add signal-driven human decisions and exact delivery reconciliation

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/decisions.py`
- Create: `wenxin-backend/app/services/job_runtime/release.py`
- Create: `wenxin-backend/app/services/job_runtime/reconciliation.py`
- Modify: `wenxin-backend/app/job_runtime/activities.py`
- Modify: `wenxin-backend/app/job_runtime/workflows.py`
- Modify: `wenxin-backend/app/api/v1/jobs.py`
- Create: `wenxin-backend/tests/test_job_decision_api.py`
- Create: `wenxin-backend/tests/test_release_tokens.py`
- Create: `wenxin-backend/tests/test_delivery_reconciliation.py`

**Decision and release semantics:**

- Decision request names exact `artifactVersionId`, artifact hash, required EvalReport IDs and one action: `APPROVE_RELEASE`, `REQUEST_REPAIR`, `BLOCK`, `CANCEL`.
- Actor must hold active `RELEASE_APPROVER` membership for `APPROVE_RELEASE`.
- The API writes `DecisionRecord` and `SIGNAL_DECISION` outbox command in one transaction.
- Workflow deduplicates decision IDs and rejects decisions against stale artifact/evaluation versions.
- `APPROVE_RELEASE` causes an activity to issue a short-lived token for one exact hash and local destination.
- Release adapter writes to a temporary destination file, verifies bytes, then atomically renames.
- If the process fails after rename and before receipt persistence, reconciliation hashes the exact destination. Match creates one DeliveryReceipt; absence permits one idempotent write; conflict enters `WAITING_DECISION` and never overwrites.

- [ ] **Step 1: Write failing authority, stale-decision and unknown-outcome tests**

  Test 403 for a non-approver, 409 for stale hash, expired/revoked/reused token rejection, duplicate decision signal idempotency, exact receipt hash, post-write failure recovery and destination conflict behavior.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_job_decision_api.py tests/test_release_tokens.py tests/test_delivery_reconciliation.py
  ```

  Expected: API/module failures because decision/release services are absent.

- [ ] **Step 3: Implement decision, token, release and reconciliation services**

  A release success transitions Job `ACTIVE → DELIVERING → COMPLETED` only after receipt persistence. Request-repair returns the workflow to a new repair Run; Plan 04 supplies the repair Cell. `BLOCK` leaves a visible terminal business exception and cannot be translated into success by the workflow.

- [ ] **Step 4: Run targeted and Temporal signal tests**

  ```bash
  python -m pytest -q tests/test_job_decision_api.py tests/test_release_tokens.py tests/test_delivery_reconciliation.py
  python -m pytest -q -m temporal tests/temporal/test_temporal_acceptance.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit human release and reconciliation**

  ```bash
  git add wenxin-backend/app/api/v1/jobs.py wenxin-backend/app/job_runtime wenxin-backend/app/services/job_runtime wenxin-backend/tests/test_job_decision_api.py wenxin-backend/tests/test_release_tokens.py wenxin-backend/tests/test_delivery_reconciliation.py
  git commit -m "feat: gate and reconcile exact job delivery"
  ```

---

### Task 6: Wire READY Jobs to the outbox and prove restart-safe synthetic execution

**Files:**

- Modify: `wenxin-backend/app/services/job_runtime/intake.py`
- Modify: `wenxin-backend/app/api/v1/jobs.py`
- Modify: `wenxin-backend/app/api/v1/health.py`
- Create: `wenxin-backend/app/job_runtime/templates/synthetic_runtime_acceptance.py`
- Create: `wenxin-backend/tests/test_job_runtime_api.py`
- Create: `wenxin-backend/tests/temporal/test_job_runtime_restart.py`
- Modify: `wenxin-backend/tests/test_job_runtime_architecture.py`

The synthetic template has deterministic `prepare`, `echo`, `evaluate`, `wait_release`, `deliver` steps and zero provider spend. It exists only to prove runtime semantics; it is never an activated customer JobClass.

- [ ] **Step 1: Write failing API-to-outbox and restart tests**

  Assert `READY` plus a validated RunPlan creates exactly one START command; `NEEDS_INPUT` creates none; API process exit does not affect workflow; worker restart preserves completed step count; cancellation revokes future grants; duplicate start is harmless; health reports database, Temporal connectivity and worker heartbeat separately.

- [ ] **Step 2: Run unit tests and verify failure**

  ```bash
  python -m pytest -q tests/test_job_runtime_api.py tests/test_job_runtime_architecture.py
  ```

  Expected: failure because intake is not wired and the synthetic template/health fields are absent.

- [ ] **Step 3: Implement transactional enqueue and worker heartbeat**

  Add START command only after a Run and validated RunPlan exist. Plan 04 registers the campaign compiler and removes the synthetic template from all customer-facing listings. Add an architecture assertion that `BackgroundTasks` does not appear in Job runtime, Job services or Job API files.

- [ ] **Step 4: Run the restart drill against the real local Temporal service**

  ```bash
  python -m pytest -q tests/test_job_runtime_api.py tests/test_job_runtime_architecture.py
  python -m pytest -q -m temporal tests/temporal/test_job_runtime_restart.py
  ```

  Expected: all tests pass; the same Job/workflow ID completes after replacing worker A with worker B, and every material milestone has one VULCA EvidenceEvent.

- [ ] **Step 5: Run the complete durable-runtime suite**

  ```bash
  python -m pytest -q \
    tests/test_workflow_outbox.py \
    tests/test_workflow_determinism.py \
    tests/test_run_plan_validation.py \
    tests/test_step_grants.py \
    tests/test_capability_activities.py \
    tests/test_activity_retry_policy.py \
    tests/test_job_decision_api.py \
    tests/test_release_tokens.py \
    tests/test_delivery_reconciliation.py \
    tests/test_job_runtime_api.py \
    tests/test_job_runtime_architecture.py
  ```

  Expected: all tests pass.

- [ ] **Step 6: Commit runtime wiring**

  ```bash
  git add wenxin-backend/app wenxin-backend/tests/test_job_runtime_api.py wenxin-backend/tests/test_job_runtime_architecture.py wenxin-backend/tests/temporal/test_job_runtime_restart.py
  git commit -m "feat: run jobs through restart-safe workflow"
  ```

---

## Plan 03 completion gate

- [ ] The acceptance outcome is `GO_TEMPORAL`, backed by the six real-server semantics.
- [ ] API state plus workflow commands commit transactionally; duplicates are idempotent.
- [ ] Workflow code is deterministic and contains no database, provider, SDK, file or secret I/O.
- [ ] Every side effect requires a valid StepGrant and every external write requires reconciliation plus DeliveryReceipt.
- [ ] Synthetic execution survives API closure and worker restart, cancellation and duplicate dispatch.
- [ ] Job runtime code contains no FastAPI `BackgroundTasks` path.
- [ ] The development Temporal server has not been represented as a Pilot production deployment.

Only after every item passes may Plan 04 begin; Plan 05 may begin in parallel once the Plan 02 API DTOs and this plan's workflow states are frozen.
