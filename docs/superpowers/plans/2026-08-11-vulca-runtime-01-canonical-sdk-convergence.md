# VULCA Canonical SDK Convergence Implementation Plan

> **Status: historical (2026-08-11).** On 2026-08-14 VULCA moved Job Runtime ownership to the DSH/Cordis-derived native kernel in `vulca-platform` (see its `docs/product/2026-08-14-vulca-unified-product-prd.md`). The capability contracts in `src/vulca/capability/` (plan 01) remain canonical and are consumed by that kernel as a sidecar; the runtime plans 02–06 in this series are superseded by the platform-side milestones and are kept only as design record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release-contract the next canonical SDK locally as `vulca==0.24.0`, expose every visual Capability needed by the first static JobClass, lock the platform to an exact source commit and wheel hash, then remove both vendored SDK copies and every build-time copy/mount path.

**Architecture:** Add a dependency-light `vulca.capability` package whose generation Cell calls one resolved `ImageProvider.generate` operation directly, whose bounded edit Cell reuses only the exact-mask/coordinate `ainpaint` paths, and whose evaluation Cell separately wraps `aevaluate`. The package owns exact-version manifests, invocation/result envelopes and a registry, while the platform converts those envelopes into its own Artifact/Evidence records through one adapter. Rename the platform backend distribution so it can install `vulca` without package-name or CLI collisions.

**Tech Stack:** Python dataclasses, `Protocol`, `StrEnum`, SHA-256, pytest, mypy, ruff, Hatchling, FastAPI platform adapter.

## Global Constraints

- Before any Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute SDK tasks in `/Users/yhryzy/.codex/worktrees/02e5/vulca` and platform tasks in `/Users/yhryzy/dev/vulca-platform`.
- Commit changes separately in the repository where they occur.
- Preserve existing `vulca.create`, `vulca.evaluate`, `vulca.inpaint`, MCP and layer APIs.
- Capability results may contain bytes and structured metadata, but no customer Job state, tenant policy or release authority.
- `CapabilityInvocation.options` is populated by the trusted platform from a validated JobSpec execution-binding reference. It must never accept a raw frontend/planner provider name, model or secret.
- A generation Cell calls one `ImageProvider.generate` operation. It must not call the legacy `acreate` pipeline because that pipeline includes internal evaluation/decision stages and would violate the new independent-evaluation boundary.
- A Capability manifest's `NATIVE` maturity means VULCA owns the contract and operational test target; it does not claim the underlying foundation model is owned by VULCA.
- Do not delete either vendored SDK directory until the platform compatibility and import-provenance tests pass against the installed canonical wheel.
- The current published package is `0.23.1`; the new public Capability surface must become `0.24.0`. Never redistribute changed code as `0.23.1`.
- Build and verify `0.24.0` locally. Publishing or pushing it is a separate external action requiring explicit user authority; until then, the platform consumes the exact locally built wheel and cannot claim deployability outside this workspace.

---

### Task 0: Classify every colliding VULCA surface before deletion or extension

**Repository:** `/Users/yhryzy/dev/vulca-platform`

**Files:**

- Create: `docs/product/vulca-runtime-migration-ledger.yaml`
- Create: `scripts/check_runtime_migration_ledger.py`
- Create: `wenxin-backend/tests/test_runtime_migration_ledger.py`

**Ledger states:** `KEEP`, `ADAPT`, `MIGRATE`, `FREEZE`, `REMOVE_LATER`.

Every entry contains `path`, `kind`, `current_truth`, `target_owner`, `disposition`, `blocking_dependency`, `replacement_path`, `verification` and `claim_status`. Prefix entries are allowed only when every tracked descendant has the same disposition and replacement rule.

The initial ledger must classify:

- top-level copied SDK source, tests, assets, scripts and package metadata under `vulca/`;
- backend copied package under `wenxin-backend/vulca/`;
- Docker/CI copy and bind-mount paths;
- legacy Workspace models, migrations, APIs, services, stores, pages, components and E2E tests;
- `/builder`, `/demo`, sample/replay data and acquisition pages;
- authentication, database, Alembic, module-boundary and frontend shell foundations;
- product/README/roadmap documents whose “hands and eyes only”, review-only or non-competition positioning conflicts with the approved constitution.

The required default decisions are:

- copied SDK implementations and build copy/mount paths → `REMOVE_LATER` after the exact wheel/provenance gate;
- a copied asset/script with an active non-SDK consumer → `MIGRATE` to that consumer's canonical directory before parent deletion;
- Job-relevant auth/database/migration/shell foundations → `KEEP` or `ADAPT` with exact target paths;
- old Workspace records/migrations → `KEEP` read-only; old execution UI/services → `FREEZE` after the Job Control Center replaces the route;
- V8 public shell → `KEEP`; illustrative demo data → `FREEZE` as replay and label non-live;
- conflicting strategy documents → `FREEZE` as historical, never silently rewrite their original evidence status.

- [ ] **Step 1: Write the failing coverage validator test**

  The test runs the checker against tracked files and fails on an unclassified scope, an unknown state, `MIGRATE` without replacement/verification, `REMOVE_LATER` without a blocking dependency, or two active paths claiming the same canonical ownership.

- [ ] **Step 2: Run against the current checkout and verify the inventory failure**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform/wenxin-backend
  python -m pytest -q tests/test_runtime_migration_ledger.py
  ```

  Expected: failure because the ledger/checker do not exist.

- [ ] **Step 3: Build the complete ledger from current tracked files and references**

  Use `git ls-files` for inventory and `rg` for active references. Resolve every copied asset/script before assigning its parent directory `REMOVE_LATER`; do not assume an unreferenced-looking binary is safe to delete without the reference scan.

- [ ] **Step 4: Run the no-ambiguity gate**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  python scripts/check_runtime_migration_ledger.py docs/product/vulca-runtime-migration-ledger.yaml
  cd wenxin-backend
  python -m pytest -q tests/test_runtime_migration_ledger.py tests/test_platform_module_boundaries.py
  ```

  Expected: all commands exit 0; the checker prints zero unclassified or multiply-owned surfaces.

- [ ] **Step 5: Commit the convergence ledger**

  ```bash
  git add docs/product/vulca-runtime-migration-ledger.yaml scripts/check_runtime_migration_ledger.py wenxin-backend/tests/test_runtime_migration_ledger.py
  git commit -m "docs: classify legacy vulca product surfaces"
  ```

---

### Task 1: Add the exact-version Capability contract to the canonical SDK

**Files:**

- Create: `src/vulca/capability/__init__.py`
- Create: `src/vulca/capability/types.py`
- Create: `src/vulca/capability/registry.py`
- Create: `tests/test_capability_contract.py`
- Modify: `src/vulca/__init__.py`

**Interfaces:**

```python
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

class CapabilityMaturity(StrEnum):
    NATIVE = "NATIVE"
    ORCHESTRATED = "ORCHESTRATED"
    INTEGRATED = "INTEGRATED"
    UNSUPPORTED = "UNSUPPORTED"

class CapabilityStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

class SideEffectState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class CapabilityManifest:
    capability_id: str
    version: str
    kind: str
    owner: str
    maturity: CapabilityMaturity
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    authority_requirements: tuple[str, ...]
    evaluator_bindings: tuple[str, ...]
    retryable_codes: tuple[str, ...]
    deterministic: bool
    deprecated: bool = False

@dataclass(frozen=True)
class CapabilityInvocation:
    invocation_id: str
    capability_id: str
    capability_version: str
    inputs: dict[str, JsonValue]
    options: dict[str, JsonValue] = field(default_factory=dict)

@dataclass(frozen=True)
class CapabilityArtifact:
    logical_name: str
    media_type: str
    content: bytes
    sha256: str

@dataclass(frozen=True)
class CapabilityResult:
    invocation_id: str
    status: CapabilityStatus
    side_effect_state: SideEffectState
    output: dict[str, JsonValue]
    artifacts: tuple[CapabilityArtifact, ...]
    provider_receipt: dict[str, JsonValue]
    latency_ms: int
    cost_minor: int
    currency: str
    error_code: str | None = None

class Capability(Protocol):
    manifest: CapabilityManifest
    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult: ...
```

`CapabilityArtifact.__post_init__` must reject a hash that does not match `content`. `CapabilityInvocation.__post_init__` validates non-empty exact IDs/versions and recursively rejects credential-bearing keys (`api_key`, `access_token`, `auth_token`, `secret`, `authorization`, `credential`, and keys ending `_api_key`, `_secret`, or `_credential`) in inputs/options; safe `binding_ref` and non-secret controls such as `max_tokens` remain allowed. `CapabilityRegistry.invoke` must resolve that exact pair and reject any mismatch between the invocation and resolved manifest. `CapabilityResult` must require an `error_code` for `FAILED` and forbid it for `SUCCEEDED`; a success requires `COMPLETED`, while a failure is either `NOT_STARTED` or `UNKNOWN`. `UNKNOWN` is never automatically retryable merely because its error code appears in `retryable_codes`.

- [ ] **Step 1: Write the failing contract and registry tests**

  Add tests that prove:

  ```python
  def test_artifact_rejects_wrong_hash() -> None:
      with pytest.raises(ValueError, match="sha256"):
          CapabilityArtifact("hero", "image/png", b"png", "0" * 64)

  def test_registry_requires_exact_version() -> None:
      registry = CapabilityRegistry()
      registry.register(FakeCapability(version="1.0.0"))
      with pytest.raises(CapabilityNotFound, match="1.0.1"):
          registry.resolve("test.echo", "1.0.1")

  def test_registry_rejects_duplicate_id_and_version() -> None:
      registry = CapabilityRegistry()
      registry.register(FakeCapability(version="1.0.0"))
      with pytest.raises(DuplicateCapability):
          registry.register(FakeCapability(version="1.0.0"))

  def test_invocation_rejects_nested_credentials() -> None:
      with pytest.raises(ValueError, match="credential-bearing"):
          CapabilityInvocation(
              invocation_id="inv_test",
              capability_id="test.echo",
              capability_version="1.0.0",
              inputs={},
              options={"provider": {"api_key": "must-not-enter"}},
          )
  ```

- [ ] **Step 2: Run the test and verify the intended failure**

  ```bash
  python -m pytest -q tests/test_capability_contract.py
  ```

  Expected: collection fails with `ModuleNotFoundError: No module named 'vulca.capability'`.

- [ ] **Step 3: Implement immutable contracts, validation and registry**

  Implement `CapabilityRegistry.register`, `resolve` and `invoke`. Resolution must use exact `(capability_id, version)` keys; it must never select “latest” or silently fall back. Implement `sha256_bytes(data: bytes) -> str` and use `hmac.compare_digest` for hash validation.

- [ ] **Step 4: Export only the stable capability surface**

  Export the enums, dataclasses, protocol, registry and errors from `vulca.capability`. Add `CapabilityManifest`, `CapabilityInvocation`, `CapabilityResult`, `SideEffectState` and `CapabilityRegistry` to the root `vulca.__all__` without changing existing exports.

- [ ] **Step 5: Run targeted quality checks**

  ```bash
  python -m ruff check src/vulca/capability tests/test_capability_contract.py
  python -m mypy src/vulca/capability
  python -m pytest -q tests/test_capability_contract.py tests/test_backward_compat.py
  ```

  Expected: all commands exit 0.

- [ ] **Step 6: Commit the SDK contract**

  ```bash
  git add src/vulca/capability src/vulca/__init__.py tests/test_capability_contract.py
  git commit -m "feat: add canonical capability contracts"
  ```

---

### Task 2: Expose the complete first-JobClass visual Cell set

**Files:**

- Create: `src/vulca/capability/builtin.py`
- Create: `src/vulca/capability/runtime.py`
- Create: `src/vulca/capability/static.py`
- Create: `tests/test_capability_builtin.py`
- Create: `tests/test_capability_static.py`
- Modify: `src/vulca/capability/__init__.py`

**Built-in IDs:**

| Capability | Exact ID and version | Existing implementation |
|---|---|---|
| Generate a primary visual | `vulca.image.generate` / `1.0.0` | Exact `ImageProvider.generate` resolved by the provider registry |
| Edit an authorised source region | `vulca.image.edit` / `1.0.0` | `vulca.ainpaint` |
| Compose approved copy and brand elements | `vulca.image.compose_static` / `1.0.0` | New deterministic Pillow Cell |
| Adapt a master to an exact format | `vulca.image.adapt_static` / `1.0.0` | New deterministic Pillow Cell |
| Validate static technical requirements | `vulca.image.validate_static` / `1.0.0` | New deterministic Pillow/file Cell |
| Evaluate a visual independently | `vulca.image.evaluate` / `1.0.0` | `vulca.aevaluate` |

**Injected runtime boundary:**

```python
class CapabilityRuntime(Protocol):
    def image_provider(
        self,
        *,
        provider_name: str,
        binding_ref: str,
        constructor_options: Mapping[str, JsonValue],
    ) -> ImageProvider: ...

    def api_key(self, *, binding_ref: str) -> str: ...
```

The default SDK runtime delegates to existing environment-aware provider construction for backwards-compatible local use. The platform injects a stricter implementation that resolves only approved secret reference IDs. Raw credentials may exist only inside the runtime/provider call stack; they never enter `CapabilityInvocation`, output, receipt, exception text or logs.

`GenerateImageCapability` accepts prompt/intent, tradition, optional subject/reference, width, height, seed, negative prompt, input fidelity, quality and output format. Provider name and approved model/options live in trusted, server-constructed `invocation.options`; provider credentials never enter the invocation. It resolves one `ImageProvider`, invokes `generate` exactly once, decodes `ImageResult.image_b64`, validates the returned media type and records an allowlisted provider/model/request ID/cost/latency receipt. It measures wall-clock latency independently. Convert a reported `cost_usd` with `Decimal(str(value)) * 100` and `ROUND_HALF_UP`; when cost is absent, set `cost_minor=0` and `costKnown=false` instead of fabricating provider cost. It never calls `acreate`, never evaluates the result and never retries internally.

`EvaluateImageCapability` accepts one local image path or base64 string plus intent/tradition. It emits no binary artifact and maps `EvalResult` to JSON-safe output including score, dimensions, rationales, risk, recommendations, latency and cost.

`EditImageCapability` accepts source image, an exact coordinate region or same-size mask, instruction, tradition and explicit reference type. It wraps only the bounded `ainpaint` mask/coordinate path with one variant and fixed selection, reads the selected output bytes, and records source/output hashes and cost without exposing temporary paths as durable storage. Natural-language region detection and multi-variant self-selection are forbidden in this Cell.

`ComposeStaticCapability` accepts a background image, headline, optional body, CTA, logo, font path, palette, layout template and safe-area percentages. It wraps text deterministically with `ImageDraw.textbbox`, preserves the visual outside declared overlay zones, and rejects fonts/logos that do not resolve from authorised invocation inputs.

`AdaptStaticCapability` accepts exact width, height, media type and one of `COVER`, `CONTAIN` or `SMART_CENTER`. It never silently changes dimensions or output media type.

`ValidateStaticCapability` decodes bytes and returns structured PASS/FAIL checks for media type, width, height, colour mode, alpha policy, safe area, maximum byte count and required naming pattern. It does not make a release decision.

- [ ] **Step 1: Write failing adapter tests with no provider calls**

  Inject a fake `CapabilityRuntime` and monkeypatch module-level `ainpaint` and `aevaluate` references. Assert exact forwarding, exactly one provider `generate` call, no `acreate` call/import, base64/path decoding, byte hash, cost conversion to integer USD cents, and that an empty generation/edit result fails with `EMPTY_ARTIFACT` rather than returning success. Assert pre-call validation/provider-construction failures return `FAILED/NOT_STARTED`; timeouts or transport failures without a provider idempotency/reconciliation receipt return `FAILED/UNKNOWN`; valid outputs return `SUCCEEDED/COMPLETED`. Assert the invocation/receipt/error text never contains the fake credential returned by the runtime.

  ```python
  @pytest.mark.asyncio
  async def test_generate_adapter_returns_hashed_png(monkeypatch) -> None:
      provider = SimpleNamespace(
          generate=AsyncMock(
              return_value=ImageResult(
                  image_b64=base64.b64encode(b"png-bytes").decode("ascii"),
                  mime="image/png",
                  metadata={
                      "provider": "mock",
                      "model": "mock-v1",
                      "request_id": "req_test",
                      "cost_usd": 0.04,
                  },
              )
          )
      )
      runtime = FakeCapabilityRuntime(provider=provider, api_key="test-secret-never-record")
      result = await GenerateImageCapability(runtime=runtime).invoke(generate_invocation())
      assert result.status is CapabilityStatus.SUCCEEDED
      assert result.artifacts[0].content == b"png-bytes"
      assert result.cost_minor == 4
      provider.generate.assert_awaited_once()
  ```

- [ ] **Step 2: Write failing deterministic static Cell tests**

  Use generated in-memory images and an authorised temporary font fixture. Assert exact output dimensions/media type, deterministic bytes, text-zone bounds, safe-area validation, alpha policy, corrupt input failure, path traversal rejection and no mutation of source bytes.

- [ ] **Step 3: Run the tests and verify the intended failure**

  ```bash
  python -m pytest -q tests/test_capability_builtin.py tests/test_capability_static.py
  ```

  Expected: collection fails because the built-in/static modules do not exist.

- [ ] **Step 4: Implement all six Cells and a built-in registry factory**

  Add:

  ```python
  def builtin_registry(runtime: CapabilityRuntime | None = None) -> CapabilityRegistry:
      registry = CapabilityRegistry()
      resolved_runtime = runtime or EnvironmentCapabilityRuntime()
      registry.register(GenerateImageCapability(runtime=resolved_runtime))
      registry.register(EditImageCapability(runtime=resolved_runtime))
      registry.register(ComposeStaticCapability())
      registry.register(AdaptStaticCapability())
      registry.register(ValidateStaticCapability())
      registry.register(EvaluateImageCapability(runtime=resolved_runtime))
      return registry
  ```

  Convert exceptions to failed results only for declared adapter/provider failures. Let programming errors propagate so they are not mislabelled as provider failures. Do not include API keys or raw provider payloads in `provider_receipt`. For coordinate editing, pass `count=1` and `select=0`; after reading the selected bytes, remove only wrapper-created temporary inputs/outputs and resolved `vulca-inpaint-*` scratch paths, never caller-owned paths.

- [ ] **Step 5: Run targeted and existing public-API tests**

  ```bash
  python -m ruff check src/vulca/capability tests/test_capability_builtin.py tests/test_capability_static.py
  python -m mypy src/vulca/capability
  python -m pytest -q \
    tests/test_capability_contract.py \
    tests/test_capability_builtin.py \
    tests/test_capability_static.py \
    tests/test_create_hitl.py \
    tests/test_inpaint.py \
    tests/test_evaluate.py \
    tests/test_backward_compat.py
  ```

  Expected: all tests pass; no test performs a paid provider call.

- [ ] **Step 6: Commit the complete visual Cell set**

  ```bash
  git add src/vulca/capability tests/test_capability_builtin.py tests/test_capability_static.py
  git commit -m "feat: expose campaign production capability cells"
  ```

---

### Task 3: Prove the canonical SDK wheel and import surface

**Files:**

- Create: `tests/test_capability_wheel.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write a wheel-content test**

  Build the wheel into a pytest temporary directory, inspect it with `zipfile`, and assert it contains:

  ```text
  vulca/capability/__init__.py
  vulca/capability/types.py
  vulca/capability/registry.py
  vulca/capability/builtin.py
  vulca/capability/runtime.py
  vulca/capability/static.py
  ```

  Also assert `importlib.metadata.version("vulca") == vulca.__version__ == "0.24.0"` when installed from the wheel and that all six exact capability IDs resolve.

- [ ] **Step 2: Run the test before CI wiring**

  ```bash
  python -m pytest -q tests/test_capability_wheel.py
  ```

  Expected: the test fails until its isolated wheel-install fixture and exports are complete.

- [ ] **Step 3: Complete package metadata and CI targets**

  Change the package version from `0.23.1` to `0.24.0`. Update the package description so it describes the canonical Capability SDK rather than “hands + eyes, not the brain”, without claiming the Job runtime lives in this repository. Add all capability tests and the mypy path to the existing CI job.

- [ ] **Step 4: Run pre-commit build and distribution checks**

  ```bash
  python -m build
  python -m pytest -q tests/test_capability_wheel.py tests/test_capability_builtin.py tests/test_capability_static.py tests/test_package.py
  python -m pip check
  ```

  Expected: `vulca-0.24.0` sdist/wheel build; tests and dependency check exit 0. This pre-commit wheel is verification only and must not be used as the platform lock artifact.

- [ ] **Step 5: Commit wheel verification**

  ```bash
  git add pyproject.toml .github/workflows/ci.yml tests/test_capability_wheel.py
  git commit -m "test: verify canonical capability wheel"
  ```

- [ ] **Step 6: Rebuild from the clean committed tree and record the lock inputs**

  ```bash
  test -z "$(git status --porcelain --untracked-files=no)"
  python -m build --outdir dist
  git rev-parse HEAD
  shasum -a 256 dist/vulca-0.24.0-py3-none-any.whl
  ```

  Expected: the checkout is clean, the commit is exactly 40 lowercase hex characters, and the wheel hash is exactly 64 lowercase hex characters. These two emitted values are the only inputs permitted for Task 4's SDK lock. Do not publish or push without separate authority.

---

### Task 4: Remove the platform package-name collision and pin the canonical SDK

**Repository:** `/Users/yhryzy/dev/vulca-platform`

**Files:**

- Modify: `wenxin-backend/pyproject.toml`
- Modify: `wenxin-backend/requirements.txt`
- Modify: `wenxin-backend/requirements.render.txt`
- Modify: `wenxin-backend/requirements.cloudrun.txt`
- Create: `wenxin-backend/vulca-sdk.lock.json`
- Create: `scripts/build_locked_vulca_sdk.py`
- Create: `wenxin-backend/tests/test_canonical_vulca_sdk.py`

**Required metadata changes:**

Set `[project].name = "vulca-platform-backend"`, retain current backend dependencies and append exact dependency `vulca==0.24.0`. Set `[tool.hatch.build.targets.wheel].packages = ["app"]`.

`vulca-sdk.lock.json` contains four keys and no others: `repository` fixed to `https://github.com/vulca-org/vulca-visual-control-sdk`, `version` fixed to `0.24.0`, `commit` matching `^[0-9a-f]{40}$` from the completed SDK Task 3 checkout, and `wheelSha256` matching `^[0-9a-f]{64}$` from the completed SDK Task 3 wheel. `build_locked_vulca_sdk.py lock` writes the actual values and refuses a dirty SDK checkout.

Remove the platform's `vulca = "vulca.cli:main"` script. Plan 03 adds a separate `vulca-job-worker` script owned by `app`, not by the SDK package.

- [ ] **Step 1: Write dependency-pin and isolated-wheel smoke tests**

  ```python
  def test_backend_metadata_pins_canonical_sdk() -> None:
      metadata = tomllib.loads(Path("pyproject.toml").read_text())
      assert metadata["project"]["name"] == "vulca-platform-backend"
      assert "vulca==0.24.0" in metadata["project"]["dependencies"]

  def test_installed_wheel_exposes_required_capabilities(tmp_path) -> None:
      completed = subprocess.run(
          [sys.executable, "-c", ISOLATED_IMPORT_SCRIPT],
          cwd=tmp_path,
          env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
          check=False,
          capture_output=True,
          text=True,
      )
      assert completed.returncode == 0, completed.stderr
  ```

  `ISOLATED_IMPORT_SCRIPT` must assert version `0.24.0` and exact resolution of all six Task 2 capability IDs. The test also validates the lock's version, 40-character commit, 64-character wheel hash and the installed wheel hash. Running from `tmp_path` intentionally proves the installed distribution while the copied directories still exist; Task 5 proves normal platform import provenance after deleting them.

- [ ] **Step 2: Run against the current checkout and verify the collision**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_canonical_vulca_sdk.py
  ```

  Expected: the metadata test fails because the backend distribution is still named `vulca`, does not pin `vulca==0.24.0`, and has no SDK lock.

- [ ] **Step 3: Rename the distribution, remove package/script collision and pin all runtime requirement sets**

  Replace `vulca>=0.11.0` with `vulca==0.24.0` in Cloud Run requirements and add the same exact pin to the two other runtime requirement sets. Do not add a floating Git branch or unverified path dependency to production files. Generate the lock from the committed SDK checkout and its built wheel.

- [ ] **Step 4: Install the exact locked local wheel and rerun**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  python scripts/build_locked_vulca_sdk.py lock \
    --sdk /Users/yhryzy/.codex/worktrees/02e5/vulca \
    --wheel /Users/yhryzy/.codex/worktrees/02e5/vulca/dist/vulca-0.24.0-py3-none-any.whl
  python scripts/build_locked_vulca_sdk.py install \
    --sdk /Users/yhryzy/.codex/worktrees/02e5/vulca
  cd wenxin-backend
  python -m pytest -q tests/test_canonical_vulca_sdk.py tests/test_vulca_integration.py
  ```

  Expected: both metadata and isolated-wheel capability tests pass, and the installed wheel hash equals the lock. Normal platform import provenance is intentionally tested in Task 5. If the SDK commit is not published or pushed, record `LOCAL_DISTRIBUTION_ONLY`; that blocks external deployment but not local implementation.

- [ ] **Step 5: Commit passing metadata and isolated-wheel tests**

  ```bash
  git add wenxin-backend/pyproject.toml wenxin-backend/requirements*.txt wenxin-backend/vulca-sdk.lock.json scripts/build_locked_vulca_sdk.py wenxin-backend/tests/test_canonical_vulca_sdk.py
  git commit -m "build: pin platform to canonical vulca sdk"
  ```

---

### Task 5: Remove vendored SDKs and every copy/mount path

**Repository:** `/Users/yhryzy/dev/vulca-platform`

**Files:**

- Delete: `vulca/`
- Delete: `wenxin-backend/vulca/`
- Modify: `docker-compose.yml`
- Modify: `.github/workflows/deploy-gcp.yml`
- Modify: `.github/workflows/deploy-backend-cloudrun.yml`
- Modify: `wenxin-backend/Dockerfile.cloud`
- Modify: `wenxin-backend/Dockerfile.dev`
- Modify: `wenxin-backend/Dockerfile.init`
- Modify: `wenxin-backend/Dockerfile.render`
- Create: `wenxin-backend/tests/test_no_vendored_vulca.py`

- [ ] **Step 1: Add a repository-structure test before deletion**

  The test resolves repository root and fails if either vendored package directory exists, if normal platform import resolves under either directory, or if deployment text contains:

  ```text
  cp -r vulca/src/vulca
  ./vulca/src/vulca:/app/vulca
  COPY vulca/src/vulca
  COPY wenxin-backend/vulca
  ```

- [ ] **Step 2: Run the structure and provenance tests and verify failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_no_vendored_vulca.py tests/test_canonical_vulca_sdk.py
  ```

  Expected: both tests fail on the current copied/mounted implementation paths.

- [ ] **Step 3: Remove the exact resolved directories and copy/mount instructions**

  First run the Task 0 ledger checker and complete every `MIGRATE` entry under the two copied trees. Then delete only `/Users/yhryzy/dev/vulca-platform/vulca` and `/Users/yhryzy/dev/vulca-platform/wenxin-backend/vulca`. Remove the compose bind mount and both workflow copy commands. Update each workflow to check out the exact SDK lock commit into a temporary build directory, build `vulca-0.24.0`, verify the wheel hash with `scripts/build_locked_vulca_sdk.py verify`, and place it in an untracked `wenxin-backend/wheelhouse/` before the Docker build. Each Dockerfile installs requirements with `--find-links=/wheelhouse` and verifies `vulca.__version__ == "0.24.0"` during image build. If the locked commit is not externally reachable, deployment workflows must fail explicitly; they must not fall back to PyPI `0.23.1` or a branch head.

- [ ] **Step 4: Run the full convergence checks**

  ```bash
  cd /Users/yhryzy/dev/vulca-platform
  test ! -d vulca
  test ! -d wenxin-backend/vulca
  python scripts/check_runtime_migration_ledger.py docs/product/vulca-runtime-migration-ledger.yaml --require-removals-complete
  ! rg -n "cp -r vulca/src/vulca|./vulca/src/vulca:/app/vulca|COPY (vulca/src/vulca|wenxin-backend/vulca)" .github docker-compose.yml wenxin-backend
  cd wenxin-backend
  python -m pytest -q \
    tests/test_no_vendored_vulca.py \
    tests/test_canonical_vulca_sdk.py \
    tests/test_vulca_integration.py \
    tests/test_openapi_contract.py
  ```

  Expected: every command exits 0 and `Path(vulca.__file__)` points into site-packages, not the repository.

- [ ] **Step 5: Commit and report the material deletion**

  ```bash
  git add -A vulca wenxin-backend/vulca docker-compose.yml .github/workflows wenxin-backend/tests/test_no_vendored_vulca.py
  git commit -m "refactor: remove vendored vulca implementations"
  ```

  In the implementation handoff, state that the two duplicated package trees were removed and remain recoverable from Git history.

---

### Task 6: Add the sole platform-to-SDK adapter

**Repository:** `/Users/yhryzy/dev/vulca-platform`

**Files:**

- Create: `wenxin-backend/app/job_runtime/__init__.py`
- Create: `wenxin-backend/app/job_runtime/capabilities/__init__.py`
- Create: `wenxin-backend/app/job_runtime/capabilities/provider_runtime.py`
- Create: `wenxin-backend/app/job_runtime/capabilities/vulca_sdk.py`
- Create: `wenxin-backend/tests/test_vulca_sdk_capability_adapter.py`
- Create: `wenxin-backend/tests/test_job_runtime_provider_resolution.py`

**Interface:**

```python
@dataclass(frozen=True)
class PlatformCapabilityResult:
    invocation_id: str
    output: dict[str, JsonValue]
    artifacts: tuple[CapabilityArtifact, ...]
    provider_receipt: dict[str, JsonValue]
    latency_ms: int
    cost_minor: int
    currency: str

class VulcaSdkCapabilityAdapter:
    def __init__(self, registry: CapabilityRegistry) -> None: ...
    def manifest(self, capability_id: str, version: str) -> CapabilityManifest: ...
    async def invoke(self, invocation: CapabilityInvocation) -> PlatformCapabilityResult: ...
```

The adapter converts only SDK envelopes. It does not create Jobs, write artifacts, issue grants, append EvidenceEvents, or choose providers. Those platform concerns are implemented in later plans.

`SettingsCapabilityRuntime` implements the SDK runtime protocol with this fixed initial map: `settings:OPENAI_API_KEY → Settings.OPENAI_API_KEY`, `settings:GOOGLE_API_KEY → Settings.GOOGLE_API_KEY`, `settings:GEMINI_API_KEY → Settings.GEMINI_API_KEY`, and `mock:none → no credential`. It rejects an unknown reference, an empty credential for a non-mock binding and arbitrary environment-variable names. Plan 04 may select only the subset approved by the frozen JobClass/PolicyPack; adding another reference requires a config, policy and test change.

- [ ] **Step 1: Write failing exact-version and error-mapping tests**

  Assert that the adapter resolves the exact manifest, invokes once, preserves bytes and receipt, and raises `CapabilityExecutionError(code, retryable, side_effect_state)` for a failed SDK result. `retryable` is true only when the code is in the manifest's retryable set **and** `side_effect_state is NOT_STARTED`; an `UNKNOWN` result remains non-retryable here and is routed to Plan 03 reconciliation/exception handling. Provider-runtime tests prove allowed/unknown/empty secret references and scan captured logs/errors/receipts for the fake credential.

- [ ] **Step 2: Run the test and verify the intended failure**

  ```bash
  cd wenxin-backend
  python -m pytest -q tests/test_vulca_sdk_capability_adapter.py tests/test_job_runtime_provider_resolution.py
  ```

  Expected: collection fails because the platform adapter module is absent.

- [ ] **Step 3: Implement the narrow adapter**

  Reject any invocation whose ID/version differs from the resolved manifest. Never resolve a provider fallback here. Redact receipt keys matching `api_key`, `token`, `secret`, `authorization`, or `credential`, case-insensitively. Preserve `side_effect_state` on the typed execution error so the workflow layer cannot accidentally retry an unknown paid outcome.

- [ ] **Step 4: Run adapter, provenance and module-boundary checks**

  ```bash
  python -m pytest -q \
    tests/test_vulca_sdk_capability_adapter.py \
    tests/test_job_runtime_provider_resolution.py \
    tests/test_canonical_vulca_sdk.py \
    tests/test_no_vendored_vulca.py \
    tests/test_platform_module_boundaries.py
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit the platform adapter**

  ```bash
  git add wenxin-backend/app/job_runtime wenxin-backend/tests/test_vulca_sdk_capability_adapter.py wenxin-backend/tests/test_job_runtime_provider_resolution.py
  git commit -m "feat: add canonical sdk capability adapter"
  ```

---

## Plan 01 completion gate

- [ ] The locked `vulca==0.24.0` wheel exposes all six exact-version visual capabilities without breaking existing APIs.
- [ ] Platform distribution is named `vulca-platform-backend` and packages only `app`.
- [ ] Both vendored SDK directories and all copy/mount paths are gone.
- [ ] Platform imports the installed canonical distribution and one adapter is the only new SDK integration path.
- [ ] No Job, authority, release or customer-state object has been added to the SDK.

Only after every item passes may Plan 02 begin.
