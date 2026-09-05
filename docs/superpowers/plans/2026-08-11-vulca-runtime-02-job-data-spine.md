# VULCA Job Data Spine Implementation Plan

> **Status: historical (2026-08-11).** On 2026-08-14 VULCA moved Job Runtime ownership to the DSH/Cordis-derived native kernel in `vulca-platform` (see its `docs/product/2026-08-14-vulca-unified-product-prd.md`). The capability contracts in `src/vulca/capability/` (plan 01) remain canonical and are consumed by that kernel as a sidecar; the runtime plans 02–06 in this series are superseded by the platform-side milestones and are kept only as design record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install one immutable, authenticated Job data spine in `vulca-platform` so a request can become a versioned JobSpec, state transitions and artifacts are causally evidenced, duplicate intake is safe, and legacy Workspace records remain readable without becoming a second runtime.

**Architecture:** Add a new `app.job_runtime` domain layer, split SQLAlchemy models by control/execution/output concern, use Pydantic camelCase API contracts, and keep all state transitions plus EvidenceEvents in one database transaction. Store artifact bytes in a local content-addressed store and immutable metadata in PostgreSQL. The Job API owns business truth; Temporal orchestration is attached in Plan 03.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL with SQLite test compatibility, pytest-asyncio, local SHA-256 content-addressed storage.

## Global Constraints

- Before any Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute this plan in `/Users/yhryzy/dev/vulca-platform` after Plan 01 passes.
- Use `app.api.deps.get_current_user` for every Job, decision, evidence and memory endpoint. Guest sessions cannot read or mutate Job state.
- Store `str(current_user.id)` as `actor_id`; do not add a database foreign key to the environment-dependent `User.id` type in this phase.
- `ReviewItem`, browser storage, demo content and Temporal history are not Job truth.
- JobSpec, RunPlan, ArtifactVersion, EvalReport, DecisionRecord, EvidenceEvent and TrustDecision payloads are immutable. Corrections create a new version or event.
- Every accepted state mutation appends an EvidenceEvent in the same database transaction.
- Missing rights, spend, data-use, destination or release authority produces `NEEDS_INPUT` before a workflow/provider call.
- SQLite is for isolated tests only. The migration and index design must remain valid on PostgreSQL.

---

### Task 1: Add canonical domain primitives and transition validation

**Files:**

- Create: `wenxin-backend/app/job_runtime/__init__.py`
- Create: `wenxin-backend/app/job_runtime/enums.py`
- Create: `wenxin-backend/app/job_runtime/ids.py`
- Create: `wenxin-backend/app/job_runtime/hashing.py`
- Create: `wenxin-backend/app/job_runtime/state_machine.py`
- Create: `wenxin-backend/app/schemas/job_common.py`
- Create: `wenxin-backend/tests/test_job_domain.py`

**Required enums:**

- `JobState`, `RunState`, `StepState`, `ArtifactState` using the values frozen in the program plan;
- `DeliveryStatus` and `DecisionAction` using the values frozen in the program plan;
- `EvalVerdict`: `PASS`, `FAIL`, `ABSTAIN`;
- `JobDataMode`: `LIVE`, `SHADOW`, `REPLAY`, `MOCK`;
- `GrantAttemptStatus`: `RESERVED`, `STARTED`, `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `UNKNOWN`;
- `FieldProvenance`: `PROVIDED`, `INFERRED`, `APPROVAL_REQUIRED`;
- `CoverageRoute`: `NATIVE`, `ADAPTED`, `MISSING`;
- `EvidenceQualifier`: `UNPROVEN`, `BETTER`, `EXCLUSIVE`;
- `MemoryStatus`: `PROPOSED`, `APPROVED`, `ACTIVE`, `REJECTED`, `EXPIRED`, `REVOKED`;
- `AuthorityLevel`: `OBSERVE`, `SHADOW`, `DRAFT`, `EXECUTE`, `RELEASE`, `OPTIMIZE`, `OPERATE`.

**Transition API:**

```python
class InvalidTransition(ValueError): ...

def require_job_transition(current: JobState, target: JobState) -> None: ...
def require_run_transition(current: RunState, target: RunState) -> None: ...
def require_artifact_transition(current: ArtifactState, target: ArtifactState) -> None: ...
```

`ApiModel` uses `ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")` so Python remains snake_case and JSON remains camelCase.

- [ ] **Step 1: Write failing ID, hash, alias and transition tests**

  ```python
  def test_ids_are_prefixed_uuid_hex() -> None:
      value = new_id("job")
      assert re.fullmatch(r"job_[0-9a-f]{32}", value)

  def test_canonical_hash_ignores_mapping_order() -> None:
      assert canonical_json_hash({"a": 1, "b": 2}) == canonical_json_hash({"b": 2, "a": 1})

  def test_job_cannot_complete_without_delivering() -> None:
      with pytest.raises(InvalidTransition):
          require_job_transition(JobState.ACTIVE, JobState.COMPLETED)
  ```

  Also test `ApiModel.model_dump(by_alias=True)` emits `jobId`, not `job_id`, rejects an unknown field, and that `new_id("grantattempt")` uses the fixed prefix declared by the program plan.

- [ ] **Step 2: Run and verify the intended failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_job_domain.py
  ```

  Expected: collection fails because the domain modules do not exist.

- [ ] **Step 3: Implement deterministic primitives**

  `canonical_json_hash` must reject NaN/Infinity and serialise with sorted keys, UTF-8 and compact separators. `new_id` accepts only the fixed prefix set from the program plan. Implement transition adjacency maps exactly from specification sections 7.1–7.3.

- [ ] **Step 4: Run targeted tests**

  ```bash
  python -m pytest -q tests/test_job_domain.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit primitives**

  ```bash
  git add wenxin-backend/app/job_runtime wenxin-backend/app/schemas/job_common.py wenxin-backend/tests/test_job_domain.py
  git commit -m "feat: add job runtime domain primitives"
  ```

---

### Task 2: Add canonical SQLAlchemy models and the single Alembic head

**Files:**

- Create: `wenxin-backend/app/models/job_control.py`
- Create: `wenxin-backend/app/models/job_execution.py`
- Create: `wenxin-backend/app/models/job_output.py`
- Modify: `wenxin-backend/app/models/__init__.py`
- Create: `wenxin-backend/alembic/versions/job_runtime_core.py`
- Create: `wenxin-backend/tests/test_job_migrations.py`
- Create: `wenxin-backend/tests/test_job_models.py`

**Migration identity:**

```python
revision = "job_runtime_core"
down_revision = "workspace_typed_core"
```

**Required tables and minimum columns:**

| Table | Required columns and constraints |
|---|---|
| `organizations` | `id`, unique `slug`, `name`, `active`, timestamps |
| `organization_memberships` | `id`, FK `organization_id`, `actor_id`, `role`, `active`; unique `(organization_id, actor_id, role)` |
| `organization_packs` | `id`, FK `organization_id`, `version`, `content_hash`, JSON `payload`, `active`; unique `(organization_id, version)` |
| `brand_packs` | same version/hash pattern plus `rights_ref` |
| `policy_packs` | same version/hash pattern plus `data_policy`, `release_policy`, `learning_policy` JSON |
| `operating_units` | `id`, FK `organization_id`, `key`, `version`, `name`, JSON `job_class_refs`; unique `(organization_id, key, version)` |
| `job_classes` | `id`, FK `organization_id`, `key`, `version`, `status`, `template_ref`, JSON `job_spec_schema`, `activated`; unique `(organization_id, key, version)` |
| `capability_coverage_ledgers` | `id`, FK `organization_id`, FK `job_class_id`, `version`, `content_hash`, JSON `rows`, `frozen_at`; unique `(job_class_id, version)` |
| `eval_specs` | `id`, FK `organization_id`, FK `job_class_id`, `key`, `version`, `content_hash`, JSON `dimensions`, JSON `bindings`, JSON `thresholds`; unique `(job_class_id, key, version)` |
| `jobs` | `id`, FK `organization_id`, FK `job_class_id`, `state`, `data_mode`, `idempotency_key`, `intake_hash`, `requester_id`, nullable `current_job_spec_id`, nullable `workflow_id`, nullable `due_at`, nullable `exception_code`, timestamps; unique `(organization_id, idempotency_key)` |
| `job_specs` | `id`, FK `organization_id`, FK `job_id`, `version`, `payload_hash`, JSON `payload`, JSON `field_provenance`, `hard_fields_complete`, `created_by`, timestamp; unique `(job_id, version)` and `(job_id, payload_hash)` |
| `runs` | `id`, FKs `organization_id`, `job_id`, `job_spec_id`, `state`, `attempt`, nullable `current_run_plan_id`, timestamps; unique `(job_id, attempt)` |
| `run_plans` | `id`, FKs `organization_id`, `job_id`, `job_spec_id`, `run_id`, `version`, `content_hash`, JSON `steps`, JSON `estimated_cost`, timestamp; unique `(run_id, version)` |
| `steps` | `id`, FKs `organization_id`, `job_id`, `run_id`, `run_plan_id`, `step_key`, `capability_id`, `capability_version`, `state`, `attempt`, nullable `grant_id`, timestamps; unique `(run_id, step_key, attempt)` |
| `step_grants` | `id`, FKs `organization_id`, `job_id`, `run_id`, `step_id`, `job_spec_id`, `action`, JSON `scope`, `max_spend_minor`, `currency`, `max_attempts`, nullable unique `bound_invocation_key`, `expires_at`, nullable `revoked_at`, nullable `consumed_at`, `issued_by`, timestamp |
| `step_grant_attempts` | `id`, FKs `organization_id`, `job_id`, `grant_id`, `step_id`, `invocation_key`, `attempt_number`, `status`, `planned_spend_minor`, `actual_spend_minor`, `currency`, nullable `provider_request_id`, nullable `result_hash`, `started_at`, nullable `finished_at`; unique `(grant_id, invocation_key, attempt_number)` |
| `artifacts` | `id`, FKs `organization_id`, `job_id`, `logical_name`, nullable `current_version_id`, timestamp; unique `(job_id, logical_name)` |
| `artifact_versions` | `id`, FKs `organization_id`, `job_id`, `artifact_id`, nullable `run_id`, nullable `step_id`, `version`, `state`, `sha256`, `byte_count`, `media_type`, `storage_uri`, JSON `parent_version_ids`, JSON `provenance`, timestamp; unique `(artifact_id, version)` |
| `eval_reports` | `id`, FKs `organization_id`, `job_id`, `artifact_version_id`, `eval_spec_id`, `eval_spec_version`, `evaluator_id`, `evaluator_version`, `verdict`, JSON `dimensions`, JSON `hard_failures`, nullable `uncertainty`, JSON `evidence_refs`, JSON `repair_hints`, timestamp |
| `decision_records` | `id`, FKs `organization_id`, `job_id`, `artifact_version_id`, `decision`, `actor_id`, JSON `eval_report_ids`, `reason`, timestamp |
| `release_tokens` | `id`, FKs `organization_id`, `job_id`, `job_spec_id`, `artifact_version_id`, `decision_record_id`, `artifact_sha256`, JSON `destination`, `expires_at`, nullable `revoked_at`, nullable `consumed_at`, `issued_by`, timestamp |
| `delivery_receipts` | `id`, FKs `organization_id`, `job_id`, `release_token_id`, `artifact_version_id`, `artifact_sha256`, `status`, `destination_uri`, nullable `external_id`, JSON `details`, `reconciled_at`, timestamp |
| `evidence_events` | `id`, FKs `organization_id`, `job_id`, nullable `run_id`, nullable `step_id`, nullable `grant_id`, nullable `causal_parent_id`, `event_type`, `actor_type`, `actor_id`, `object_type`, `object_id`, nullable `prior_state`, nullable `new_state`, JSON `payload`, `payload_hash`, `cost_minor`, `currency`, timestamp; index `(job_id, created_at, id)` |
| `memory_candidates` | `id`, FKs `organization_id`, `job_id`, nullable `decision_record_id`, `status`, `kind`, JSON `scope`, JSON `evidence_refs`, `proposed_lesson`, `confidence`, nullable `expires_at`, nullable `decided_by`, nullable `decided_at`, timestamp |
| `trust_decisions` | `id`, FKs `organization_id`, `job_class_id`, `action`, `channel`, `risk_tier`, `authority_level`, `status`, JSON `evidence_window`, JSON `thresholds`, JSON `metrics`, JSON `demotion_rules`, `actor_id`, `expires_at`, timestamp |

Use `JSON().with_variant(JSONB, "postgresql")` for JSON columns. IDs are `String(64)`. Every organization-owned parent table has a unique `(organization_id, id)` key, and every organization-owned child uses a composite foreign key `(organization_id, parent_id)` to that key in addition to its primary key. Service queries still filter by `organization_id`; database constraints must reject a child row that names a parent from another tenant. `step_grant_attempts` carries `organization_id`/`job_id` and uses the same composite-reference rule for its grant and step.

- [ ] **Step 1: Write migration graph and model-invariant tests**

  Tests must assert one Alembic head, `job_runtime_core` descends from `workspace_typed_core`, every table exists after `upgrade head`, duplicate `(organization_id, idempotency_key)` fails, an ArtifactVersion insert cannot reuse `(artifact_id, version)`, a GrantAttempt cannot reuse `(grant_id, invocation_key, attempt_number)`, and cross-organization JobSpec/Run/Artifact/EvalReport/Decision/Grant inserts fail at the database boundary.

- [ ] **Step 2: Run against the current migration graph**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_job_migrations.py tests/test_job_models.py
  ```

  Expected: failure because `job_runtime_core` and the model modules are absent.

- [ ] **Step 3: Implement models and migration**

  Define relationships only where they clarify ownership; use `lazy="raise"` on new relationships so API serialization cannot trigger accidental async queries. Do not import or relate to `ReviewItem`.

- [ ] **Step 4: Exercise upgrade and downgrade in a temporary database**

  ```bash
  JOB_RUNTIME_MIGRATION_TMP=$(mktemp -d)
  DATABASE_URL="sqlite+aiosqlite:///${JOB_RUNTIME_MIGRATION_TMP}/migration.db" alembic upgrade head
  DATABASE_URL="sqlite+aiosqlite:///${JOB_RUNTIME_MIGRATION_TMP}/migration.db" alembic current
  DATABASE_URL="sqlite+aiosqlite:///${JOB_RUNTIME_MIGRATION_TMP}/migration.db" alembic downgrade workspace_typed_core
  DATABASE_URL="sqlite+aiosqlite:///${JOB_RUNTIME_MIGRATION_TMP}/migration.db" alembic upgrade head
  python -m pytest -q tests/test_job_migrations.py tests/test_job_models.py
  ```

  Expected: current revision is `job_runtime_core`; downgrade/upgrade and tests succeed without changing legacy tables.

- [ ] **Step 5: Commit schema and migration**

  ```bash
  git add wenxin-backend/app/models wenxin-backend/alembic/versions/job_runtime_core.py wenxin-backend/tests/test_job_migrations.py wenxin-backend/tests/test_job_models.py
  git commit -m "feat: add canonical job runtime schema"
  ```

---

### Task 3: Define strict intake and immutable JobSpec contracts

**Files:**

- Create: `wenxin-backend/app/schemas/job_contracts.py`
- Create: `wenxin-backend/app/schemas/job_execution.py`
- Create: `wenxin-backend/app/schemas/job_outputs.py`
- Create: `wenxin-backend/app/services/job_runtime/__init__.py`
- Create: `wenxin-backend/app/services/job_runtime/contracts.py`
- Create: `wenxin-backend/tests/test_job_contract_compiler.py`

**First intake request:**

```python
class SourceAssetInput(ApiModel):
    uri: str
    sha256: str
    media_type: str
    rights_status: Literal["AUTHORIZED", "APPROVAL_REQUIRED"]
    rights_ref: str | None = None

class OutputFormatInput(ApiModel):
    key: str
    width: int = Field(ge=64, le=8192)
    height: int = Field(ge=64, le=8192)
    media_type: Literal["image/png", "image/jpeg", "image/webp"]

class DeliveryInput(ApiModel):
    kind: Literal["LOCAL_FOLDER"]
    destination_uri: str
    naming_template: str
    receipt_required: Literal[True] = True

class JobIntakeRequest(ApiModel):
    organization_id: str
    job_class_key: Literal["campaign-static-creative-production-release"]
    job_class_version: Literal["1"]
    brief: str = Field(min_length=20, max_length=20_000)
    objective: str = Field(min_length=3, max_length=2_000)
    offer_message: str = Field(min_length=1, max_length=2_000)
    audience: str = Field(min_length=1, max_length=2_000)
    call_to_action: str = Field(min_length=1, max_length=500)
    channels: list[str] = Field(min_length=1, max_length=8)
    formats: list[OutputFormatInput] = Field(min_length=1, max_length=12)
    source_assets: list[SourceAssetInput] = Field(default_factory=list, max_length=20)
    brand_pack_id: str
    brand_pack_version: int = Field(ge=1)
    policy_pack_id: str
    policy_pack_version: int = Field(ge=1)
    max_spend_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    max_attempts: int = Field(ge=1, le=3)
    deadline_at: datetime
    delivery: DeliveryInput
    release_approver_id: str | None
    learning_permission: Literal["PROPOSE_ONLY", "DISABLED"] = "PROPOSE_ONLY"
```

`CompiledJobSpec` adds requester, source references, per-field provenance, resolved JobClass/Pack IDs and content hashes, exact execution-provider and evaluator bindings, risk tier, missing hard fields, escalation owners, retention/data rules and exact delivery contract. Each execution binding has a stable key, provider kind/name, exact model/version, allowlisted options, data-use class and a secret **reference ID**; it never embeds credentials. The compiler may select bindings only from the frozen JobClass plus PolicyPack intersection.

`Job.data_mode` is derived server-side from the active TrustDecision and environment: `SHADOW` is the first JobClass default, `LIVE` requires an authorised bounded execution scope, and `REPLAY`/`MOCK` are rejected by the normal live intake endpoint outside test/replay services.

- [ ] **Step 1: Write failing compiler tests**

  Cover:

  - a complete request compiles deterministically and all hard fields are `PROVIDED`;
  - a source asset with `APPROVAL_REQUIRED` and no rights reference yields `NEEDS_INPUT` with no Run;
  - missing `releaseApproverId` yields `NEEDS_INPUT`;
  - a naive deadline or a path outside the configured delivery root is rejected;
  - unknown JSON fields are rejected rather than silently ignored;
  - a provider/evaluator binding not present in both JobClass and PolicyPack is rejected, and compiled payloads contain only secret reference IDs;
  - the same normalized request has the same `payload_hash`.

- [ ] **Step 2: Run and verify the intended failure**

  ```bash
  python -m pytest -q tests/test_job_contract_compiler.py
  ```

  Expected: collection fails because the schemas/compiler do not exist.

- [ ] **Step 3: Implement pure contract compilation**

  `compile_job_spec(request, context)` must be a pure function. It may normalise descriptive text and channel keys, but it may not infer an approval-required field. It returns `CompiledContract(payload, field_provenance, missing_hard_fields, payload_hash)` and performs no database, provider, file or network I/O.

- [ ] **Step 4: Run contract tests and type checks**

  ```bash
  python -m pytest -q tests/test_job_contract_compiler.py tests/test_job_domain.py
  python -m mypy app/job_runtime app/schemas/job_common.py app/schemas/job_contracts.py app/services/job_runtime/contracts.py
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit schemas and compiler**

  ```bash
  git add wenxin-backend/app/schemas/job_*.py wenxin-backend/app/services/job_runtime wenxin-backend/tests/test_job_contract_compiler.py
  git commit -m "feat: compile strict immutable job specs"
  ```

---

### Task 4: Add transactional EvidenceEvents and content-addressed artifacts

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/evidence.py`
- Create: `wenxin-backend/app/services/job_runtime/artifacts.py`
- Create: `wenxin-backend/app/services/job_runtime/transitions.py`
- Create: `wenxin-backend/tests/test_job_evidence.py`
- Create: `wenxin-backend/tests/test_artifact_store.py`

**Service interfaces:**

```python
async def append_evidence(session: AsyncSession, command: AppendEvidence) -> EvidenceEvent: ...

async def transition_job(
    session: AsyncSession,
    *,
    job: Job,
    target: JobState,
    actor: ActorRef,
    event_type: str,
    payload: dict[str, JsonValue],
) -> EvidenceEvent: ...

class LocalContentAddressedArtifactStore(ArtifactStore): ...
```

`transition_job` validates the transition, changes the row and appends the event without committing; the API/activity transaction commits both. Direct updates/deletes of `EvidenceEvent` are blocked by SQLAlchemy listeners and covered by tests.

- [ ] **Step 1: Write failing atomicity, immutability and CAS tests**

  Prove that a forced EvidenceEvent insert failure rolls back the Job transition, update/delete of an event raises `ImmutableEvidenceError`, identical bytes deduplicate to the same storage URI, corrupt bytes fail `verify`, and a write cannot escape `${VULCA_ARTIFACT_ROOT}`.

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_job_evidence.py tests/test_artifact_store.py
  ```

  Expected: collection fails because the services do not exist.

- [ ] **Step 3: Implement safe event and artifact services**

  Artifact writes use a temporary file in the final directory, `fsync`, and `os.replace`; verify the hash before returning. `storage_uri` uses `cas://{organization_id}/{sha256}` and is resolved only by the store, never by arbitrary path concatenation.

- [ ] **Step 4: Run targeted tests**

  ```bash
  python -m pytest -q tests/test_job_evidence.py tests/test_artifact_store.py tests/test_job_models.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit evidence and artifact services**

  ```bash
  git add wenxin-backend/app/services/job_runtime wenxin-backend/tests/test_job_evidence.py wenxin-backend/tests/test_artifact_store.py
  git commit -m "feat: add immutable evidence and artifact storage"
  ```

---

### Task 5: Implement authenticated idempotent Job intake

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/intake.py`
- Create: `wenxin-backend/app/api/v1/jobs.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Modify: `wenxin-backend/app/core/module_boundaries.py`
- Create: `wenxin-backend/tests/test_job_intake_api.py`
- Modify: `wenxin-backend/tests/test_platform_module_boundaries.py`

**Intake semantics:**

- Header `Idempotency-Key` is required, 8–128 printable ASCII characters.
- Membership roles `SPONSOR`, `WORKFLOW_OWNER` and `OPERATOR` may create Jobs.
- The service locks or atomically inserts on `(organization_id, idempotency_key)`.
- Same key plus same intake hash returns the existing Job with HTTP 200 and does not append another event.
- Same key plus different hash returns HTTP 409 `IDEMPOTENCY_CONFLICT`.
- New complete contract returns HTTP 201 and `READY`; new incomplete contract returns HTTP 201 and `NEEDS_INPUT`.
- The first event is exactly `JOB_RECEIVED`; if incomplete, a second event `JOB_NEEDS_INPUT` records named missing fields.
- This plan does not start a workflow. Plan 03 attaches workflow start only for `READY` Jobs.
- `POST /jobs/{jobId}/inputs` accepts only fields named in the current missing/approval-required set, recompiles the complete payload, creates immutable JobSpec `v+1`, transitions to `READY` only when all hard fields pass, and records `JOB_SPEC_REVISED`. Any prior RunPlan becomes stale and any prior unconsumed StepGrant/ReleaseToken is revoked; old records remain queryable.

- [ ] **Step 1: Write failing API tests with a temporary async SQLite database**

  Override `get_db` and `get_current_user`. Test 401 without auth, 403 without membership, 201 new, 200 identical duplicate, 409 conflicting duplicate, zero provider/workflow calls for `NEEDS_INPUT`, authorised input producing JobSpec v2/`READY`, rejection of unrelated field changes, and stale-grant/token revocation.

  ```python
  assert first.json()["jobId"] == duplicate.json()["jobId"]
  assert await event_count(job_id) == 1
  ```

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_job_intake_api.py tests/test_platform_module_boundaries.py
  ```

  Expected: 404/collection failure because the Job router is absent.

- [ ] **Step 3: Implement service, router and module ownership**

  Register `jobs.router` under `/jobs`. Add `/jobs`, `/job-classes` and `/memory-candidates` to VULCA Core backend prefixes. Use a nested transaction or dialect-safe unique-insert handling so concurrent duplicate requests converge on one row.

- [ ] **Step 4: Run API and OpenAPI tests**

  ```bash
  python -m pytest -q \
    tests/test_job_intake_api.py \
    tests/test_platform_module_boundaries.py \
    tests/test_openapi_contract.py
  ```

  Expected: all tests pass and the OpenAPI request schema uses camelCase fields.

- [ ] **Step 5: Commit Job intake**

  ```bash
  git add wenxin-backend/app/api/v1 wenxin-backend/app/core/module_boundaries.py wenxin-backend/app/services/job_runtime/intake.py wenxin-backend/tests/test_job_intake_api.py wenxin-backend/tests/test_platform_module_boundaries.py
  git commit -m "feat: add idempotent authenticated job intake"
  ```

---

### Task 6: Add Job reads and a strictly read-only legacy Workspace adapter

**Files:**

- Create: `wenxin-backend/app/services/job_runtime/queries.py`
- Create: `wenxin-backend/app/services/job_runtime/legacy_workspace.py`
- Modify: `wenxin-backend/app/api/v1/jobs.py`
- Create: `wenxin-backend/app/api/v1/job_classes.py`
- Modify: `wenxin-backend/app/api/v1/__init__.py`
- Create: `wenxin-backend/tests/test_job_query_api.py`
- Create: `wenxin-backend/tests/test_legacy_workspace_adapter.py`
- Create: `wenxin-backend/tests/test_job_runtime_architecture.py`

**Read contracts:**

- `GET /jobs` returns cursor-paginated `JobSummary` ordered by `(created_at DESC, id DESC)`.
- `GET /jobs/{id}` returns `JobDetail` with current JobSpec, milestones, current artifacts, required evaluations, current exception, release/delivery summary and operating cost; it does not expose private model reasoning.
- `GET /jobs/{id}/events` returns customer-safe events in causal order.
- `GET /job-classes` and `/job-classes/{id}/coverage` read the canonical tables.
- `LegacyWorkspaceAdapter.list_review_refs(organization_id)` returns `LegacyReviewRef` objects with original IDs, decisions, audit references and `source="LEGACY_WORKSPACE_READ_ONLY"`.
- No API in this plan writes canonical Jobs from legacy records; a one-time migration can be planned later if read-only access proves insufficient.

- [ ] **Step 1: Write failing query, tenancy and architecture tests**

  Test that organization A cannot read organization B, events are stable and append-only, legacy reads do not modify any table, and these paths contain no imports or writes involving `ReviewItem`:

  ```text
  app/job_runtime/
  app/services/job_runtime/intake.py
  app/services/job_runtime/queries.py
  app/api/v1/jobs.py
  ```

- [ ] **Step 2: Run and verify failure**

  ```bash
  python -m pytest -q tests/test_job_query_api.py tests/test_legacy_workspace_adapter.py tests/test_job_runtime_architecture.py
  ```

  Expected: tests fail because query endpoints/adapters are absent.

- [ ] **Step 3: Implement explicit eager queries and DTO construction**

  Query all required rows explicitly with organization filters. Do not serialise ORM models directly. Redact provider receipt fields using the same secret-key denylist as Plan 01.

- [ ] **Step 4: Run the complete data-spine suite**

  ```bash
  python -m pytest -q \
    tests/test_job_domain.py \
    tests/test_job_migrations.py \
    tests/test_job_models.py \
    tests/test_job_contract_compiler.py \
    tests/test_job_evidence.py \
    tests/test_artifact_store.py \
    tests/test_job_intake_api.py \
    tests/test_job_query_api.py \
    tests/test_legacy_workspace_adapter.py \
    tests/test_job_runtime_architecture.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit read APIs and legacy boundary**

  ```bash
  git add wenxin-backend/app/api/v1 wenxin-backend/app/services/job_runtime wenxin-backend/tests/test_job_query_api.py wenxin-backend/tests/test_legacy_workspace_adapter.py wenxin-backend/tests/test_job_runtime_architecture.py
  git commit -m "feat: expose canonical job reads and legacy evidence"
  ```

---

## Plan 02 completion gate

- [ ] A complete authenticated intake produces one `READY` Job and immutable JobSpec; missing authority produces `NEEDS_INPUT` before spend.
- [ ] Duplicate intake is idempotent under sequential and concurrent requests.
- [ ] Every state mutation and material write is causally evidenced in the same transaction.
- [ ] Artifact bytes are content-addressed and verified; metadata and lineage are immutable.
- [ ] Alembic has one head and preserves legacy Workspace tables.
- [ ] Legacy Workspace data is readable without new `ReviewItem` execution writes.
- [ ] No workflow durability, generation quality, deployment or customer-use claim has been made.

Only after every item passes may Plan 03 begin.
