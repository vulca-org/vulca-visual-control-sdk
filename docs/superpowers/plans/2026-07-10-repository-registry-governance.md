# Repository Registry Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public-safe Vulca repository registry and an explicit, read-only private snapshot workflow without making ordinary feature development depend on volatile repository state.

**Architecture:** `docs/product/repository-registry.yaml` is the stable public source. One standard-library-oriented Python script validates it, derives SDK facts from the checkout, and renders deterministic Markdown. The same script exposes a separately gated private mode that reads a local stable-seed file, discovers Git/worktree state through an injected read-only command runner, and writes timestamped JSON and Markdown outside Git. Public CI runs only deterministic public checks.

**Tech Stack:** Python 3.11+, PyYAML, pytest, `tomllib`, `subprocess`, Git CLI, optional GitHub CLI, GitHub Actions.

---

## File Map

Create:

- `docs/product/repository-registry.yaml` — committed public source of truth.
- `docs/product/repository-registry.md` — generated public reading view.
- `scripts/build_repository_registry.py` — validation, rendering, CLI, and opt-in scanner.
- `tests/test_repository_registry.py` — public safety, determinism, scanner, and CLI tests.

Modify:

- `README.md` — link to the public registry.
- `.github/workflows/ci.yml` — verify only the public registry output.

Maintain outside Git:

- `~/.vulca/repository-registry-seeds.private.yaml` — stable private scan seeds.
- `~/.vulca/repository-registry-snapshot.private.json` — current private machine-readable snapshot.
- `~/.vulca/repository-registry-snapshot.private.md` — current private reading view.
- `~/.vulca/repository-registry-private-bootstrap-plan.md` — local mode-`600` runbook.

Never stage or commit the four local private files.

## Task 1: Public schema, leak checks, and derived facts

**Files:**

- Create: `scripts/build_repository_registry.py`
- Create: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing tests for code-derived facts**

Add tests that create a bounded temporary checkout rather than relying on the real repository:

```python
from pathlib import Path

from scripts.build_repository_registry import derive_sdk_facts


def test_derive_sdk_facts_reads_version_and_mcp_count(tmp_path: Path) -> None:
    (tmp_path / "src/vulca").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "vulca"\nversion = "0.23.1"\n',
        encoding="utf-8",
    )
    (tmp_path / "src/vulca/mcp_server.py").write_text(
        "@mcp.tool()\ndef first():\n    return None\n\n"
        "@mcp.tool()\ndef second():\n    return None\n",
        encoding="utf-8",
    )

    assert derive_sdk_facts(tmp_path) == {
        "sdk_version": "0.23.1",
        "mcp_tool_count": 2,
    }
```

Also test missing `pyproject.toml`, invalid TOML syntax, missing `src/vulca/mcp_server.py`, missing project version, and zero MCP registrations. Each must raise `RegistryError` with the missing relative path or fact, not a generic traceback.

- [ ] **Step 2: Run the focused test and confirm the expected import failure**

Run:

```bash
pytest tests/test_repository_registry.py -q
```

Expected: fail because `scripts.build_repository_registry` does not exist.

- [ ] **Step 3: Add the minimum public validation model**

Implement these names in `scripts/build_repository_registry.py`:

```python
PUBLIC_ROLES = {"sdk", "plugin", "adapter", "research", "website", "legacy"}
PUBLIC_LIFECYCLES = {
    "canonical",
    "active-supporting",
    "historical",
    "migrated",
    "archived",
}
PRIVATE_ONLY_FIELDS = {
    "local_path",
    "local_roots",
    "remote_url",
    "expected_remote",
    "head",
    "current_branch",
    "comparison_ref",
    "ahead",
    "behind",
    "worktree_state",
    "prunable",
    "recommended_action",
    "sensitivity",
    "release_boundary",
}


class RegistryError(ValueError):
    pass
```

Add:

- `load_yaml(path: Path) -> dict[str, object]`
- `walk_values(value: object, field: str = "root") -> Iterator[tuple[str, object]]`
- `derive_sdk_facts(root: Path) -> dict[str, object]`
- `validate_public_registry(data: dict[str, object], private_denylist: set[str] | None = None) -> None`

Validation must enforce:

- top-level `schema_version`, `verified_on`, `policy`, and non-empty `repositories`;
- exactly the public record fields approved in the design;
- unique IDs and unique public URLs;
- public visibility and canonical HTTPS GitHub repository URLs;
- supported role and lifecycle values;
- non-empty `canonical_for` for canonical records;
- a migration note for migrated records;
- no active release channel for archived records;
- no private-only fields at any depth;
- no absolute POSIX/Windows paths, `file://`, SSH Git, localhost, `.env`, credential, session, or private-evidence fragments;
- no credential-like field names or values;
- no match against an optional private denylist.

Safety errors identify the category and field path but never echo a suspected secret value.

- [ ] **Step 4: Add table-driven rejection tests**

Start from one valid record, mutate one property per test, and cover:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("visibility", "private"),
        ("role", "unknown"),
        ("lifecycle", "experimental"),
        ("notes", "/tmp/internal-checkout"),
        ("notes", "git@github.com:example/repository.git"),
        ("notes", "http://localhost:9000/status"),
        ("local_path", "/tmp/internal-checkout"),
    ],
)
def test_public_validation_rejects_unsafe_records(field: str, value: str) -> None:
    data = valid_public_registry()
    data["repositories"][0][field] = value

    with pytest.raises(RegistryError):
        validate_public_registry(data)
```

Add separate tests for duplicate IDs, duplicate URLs, credential-like input without value reflection, canonical-without-authority, migrated-without-note, archived-with-release-channel, and denylist collision.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
```

Expected: all new tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit the verified unit**

```bash
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: validate public repository registry"
```

## Task 2: Public source, deterministic renderer, and default CLI

**Files:**

- Create: `docs/product/repository-registry.yaml`
- Create: `docs/product/repository-registry.md`
- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing renderer and CLI tests**

Add tests for:

- the committed YAML passes validation;
- rendering the same model twice returns identical text;
- the rendered document includes the code-derived SDK version and MCP count;
- the rendered document groups canonical, supporting, historical, migrated, and archived records;
- the committed Markdown equals fresh output;
- `main(["--check"])` returns `0` when current;
- `main(["--check", "--source", str(source), "--output", str(stale_output)])` returns non-zero for a stale output file and does not rewrite it;
- default invocation never expands `~`, reads private seeds, calls Git, or calls GitHub.

Use dependency injection or explicit temporary paths; do not patch the real home directory.

- [ ] **Step 2: Run the renderer tests and confirm they fail**

```bash
pytest tests/test_repository_registry.py -q
```

Expected: failures for missing renderer, CLI, YAML, and generated Markdown.

- [ ] **Step 3: Create the public YAML registry**

Use `schema_version: 1`, `verified_on: 2026-07-10`, policy text from the approved design, and this initial public scope:

| Repository | Role | Lifecycle | Primary authority |
| --- | --- | --- | --- |
| `vulca-org/vulca` | `sdk` | `canonical` | SDK, CLI, MCP, public docs |
| `vulca-org/vulca-plugin` | `plugin` | `canonical` | agent plugin distribution |
| `vulca-org/comfyui-vulca` | `adapter` | `canonical` | ComfyUI adapter distribution |
| `yha9806/VULCA-Bench` | `research` | `active-supporting` | public benchmark artifacts |
| `yha9806/VULCA-Framework` | `research` | `active-supporting` | public framework artifacts |
| `yha9806/EMNLP2025-VULCA` | `research` | `historical` | historical paper artifacts |
| `yha9806/VULCA-EMNLP2025` | `website` | `historical` | historical project website |
| `yha9806/vulca-exhibition` | `legacy` | `migrated` | superseded exhibition surface |
| `yha9806/claude-skills-vulca` | `legacy` | `archived` | archived skill distribution |

Populate every required field with public evidence already verified in the repository audit. Do not add any private repository record, private owner, local path, current branch, HEAD, or worktree status.

- [ ] **Step 4: Implement deterministic rendering**

Implement these exact signatures:

- `render_public_registry(data: dict[str, object], derived_facts: dict[str, object]) -> str`
- `build_public_registry(source: Path, root: Path) -> str`
- `write_if_changed(path: Path, content: str) -> bool`

The renderer must:

- preserve YAML record order within lifecycle sections;
- include policy, authority, sync, version source, release channels, and maintenance guidance;
- insert derived facts only for the canonical SDK record;
- end with exactly one newline;
- include no runtime timestamp;
- validate the completed Markdown before writing.

- [ ] **Step 5: Add the public-default CLI**

`main(argv: Sequence[str] | None = None) -> int` supports:

```text
--source PATH
--output PATH
--check
```

Defaults are the committed YAML and Markdown relative to the repository root. `--check` compares in memory and exits non-zero with the exact regeneration command when stale. It performs no write.

- [ ] **Step 6: Generate and verify the public document**

```bash
python scripts/build_repository_registry.py
python scripts/build_repository_registry.py --check
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git diff --check
```

Expected: the second generator call is clean, focused tests pass, and no whitespace errors appear.

- [ ] **Step 7: Commit the public registry unit**

```bash
git add docs/product/repository-registry.yaml docs/product/repository-registry.md scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: publish repository authority registry"
```

## Task 3: Stable private-seed validation and safe command boundary

**Files:**

- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing private-seed tests**

Use only synthetic identities and temporary paths:

```python
VALID_PRIVATE_SEED = {
    "id": "example-private-platform",
    "full_name": "example/private-platform",
    "visibility": "private",
    "lifecycle": "active-supporting",
    "local_roots": ["/tmp/example repository"],
    "expected_remote": "https://github.com/example/private-platform.git",
    "sensitivity": "internal",
    "release_boundary": "explicit owner approval",
    "sync_relationship": "exports selected public-safe artifacts",
}
```

Verify stable seeds accept the approved fields and reject every volatile field:

```text
observed_at, availability, remote_url, current_branch, head,
comparison_ref, ahead, behind, worktree_state, prunable,
recommended_action
```

Also test duplicate seed IDs, missing roots, invalid visibility/sensitivity, and credential-like values.

- [ ] **Step 2: Write failing safe-runner tests**

Define an injected runner contract and test that:

- arguments are a `Sequence[str]`, never a command string;
- a path containing spaces remains one argument;
- `subprocess.run` receives `shell=False`, `capture_output=True`, `text=True`, `check=False`;
- the default local Git timeout is 10 seconds;
- a timeout becomes a bounded `CommandResult` error category without environment or secret output.
- a missing executable (`FileNotFoundError`) becomes `stderr_category="executable-not-found"` without raising or exposing `PATH`.

- [ ] **Step 3: Implement seed validation and the runner**

Add:

```python
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr_category: str | None = None


class CommandRunner(Protocol):
    def run(self, args: Sequence[str], timeout: int) -> CommandResult:
        raise NotImplementedError
```

Implement `SubprocessRunner.run(args: Sequence[str], timeout: int) -> CommandResult` plus these exact functions:

- `load_private_seeds(path: Path) -> dict[str, object]`
- `validate_private_seeds(data: dict[str, object]) -> None`
- `private_seed_denylist(data: dict[str, object]) -> set[str]`

`SubprocessRunner` must copy the argument sequence into a list and call only:

```python
subprocess.run(
    list(args),
    shell=False,
    capture_output=True,
    text=True,
    timeout=timeout,
    check=False,
)
```

Do not pass `env`, `cwd`, or free-form shell fragments through seed data.

- [ ] **Step 4: Run and commit**

```bash
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: validate private repository scan seeds"
```

## Task 4: Read-only Git and worktree discovery

**Files:**

- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Write parser and classification tests**

Cover:

- clean, modified, untracked, and mixed porcelain status;
- normal, detached, locked, and prunable worktree records;
- worktree paths containing spaces;
- missing and non-repository roots;
- repository with and without an upstream tracking ref;
- remote mismatch;
- command timeout and unreadable repository.

The worktree fixture should resemble:

```text
worktree /tmp/example repository
HEAD 1111111111111111111111111111111111111111
branch refs/heads/main

worktree /tmp/example detached
HEAD 2222222222222222222222222222222222222222
detached
prunable gitdir file points to non-existent location
```

- [ ] **Step 2: Write a temporary-repository integration test**

Create a Git repository under `tmp_path`, configure only local test identity, commit one file, add a local bare remote, establish an upstream, and verify the scanner reports branch, HEAD, remote, clean state, and `ahead=0`/`behind=0` without changing `git status` or refs.

- [ ] **Step 3: Implement fixed read-only Git operations**

Add the allowlist:

```python
ALLOWED_GIT_OPERATIONS = {
    "rev-parse",
    "branch",
    "remote",
    "status",
    "rev-list",
    "worktree",
}
```

Implement these exact signatures:

- `git_command(runner: CommandRunner, root: Path, operation: str, *arguments: str) -> CommandResult`
- `classify_status(porcelain: str) -> str`
- `parse_worktree_porcelain(text: str) -> list[dict[str, object]]`
- `scan_checkout(root: Path, expected_remote: str, runner: CommandRunner) -> dict[str, object]`
- `recommend_action(record: dict[str, object]) -> str`

Only these commands are permitted, each with `git -C <root>` and a 10-second timeout:

```text
git rev-parse --is-inside-work-tree
git rev-parse HEAD
git branch --show-current
git rev-parse --abbrev-ref --symbolic-full-name @{upstream}
git remote get-url origin
git status --porcelain=v1
git rev-list --left-right --count @{upstream}...HEAD
git worktree list --porcelain
```

Do not run `fetch`, `pull`, `checkout`, `switch`, `merge`, `rebase`, `push`, `prune`, `clean`, or delete operations. Treat a missing upstream as `comparison_ref: null`, `ahead: unknown`, and `behind: unknown`.

`recommended_action` is a bounded label such as `none`, `inspect-remote-mismatch`, `review-dirty-worktree`, `review-divergence`, or `review-prunable-record`; it never performs that action.

- [ ] **Step 4: Run and commit**

```bash
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: discover repository worktree state"
```

## Task 5: Timestamped private snapshots and optional GitHub refresh

**Files:**

- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing snapshot tests**

Add tests proving:

- one seed root expands to linked worktrees discovered from porcelain output;
- paths are de-duplicated across seeds and worktree discovery;
- one UTC `observed_at` value is shared by JSON and Markdown;
- JSON and Markdown contain the same record IDs and paths;
- missing roots are recorded rather than raised;
- all validation completes before either output file is replaced;
- public mode never reads private seeds and never invokes the runner;
- `--refresh-github` is the only route that invokes `gh`;
- a failed `gh` call adds bounded unavailable metadata but leaves local discovery intact.

- [ ] **Step 2: Implement snapshot building and rendering**

Implement these exact signatures:

- `github_metadata(full_name: str, runner: CommandRunner) -> dict[str, object]`
- `build_private_snapshot(seeds: dict[str, object], runner: CommandRunner, observed_at: datetime | None = None, refresh_github: bool = False) -> dict[str, object]`
- `render_private_json(snapshot: dict[str, object]) -> str`
- `render_private_markdown(snapshot: dict[str, object]) -> str`

The optional GitHub call is list-based and uses a 30-second timeout:

```text
gh repo view example/private-platform --json visibility,isArchived,defaultBranchRef
```

No GitHub call runs when `refresh_github=False`. The builder must discover worktrees, scan each path once, sort records stably by seed order then path, and validate the complete snapshot before returning it.

- [ ] **Step 3: Extend the CLI with an explicit private mode**

Add:

```text
--snapshot-private
--private-seeds PATH
--private-json PATH
--private-markdown PATH
--refresh-github
```

Rules:

- all three private paths are required with `--snapshot-private`;
- `--private-json`, `--private-markdown`, and `--refresh-github` without `--snapshot-private` are rejected;
- `--private-seeds` may be used without snapshot mode only together with `--check`, where it supplies an additional denylist but performs no Git scan;
- `--refresh-github` requires `--snapshot-private`;
- private paths are expanded only after their explicit flag combination has been validated;
- snapshot mode is separate from public generation; it does not rewrite the public Markdown;
- the public build remains the default behavior when snapshot mode is absent;
- every private seed and output path must resolve outside the repository root, otherwise the command fails before reading or writing it;
- private timestamps are dynamic and never checked by public `--check`;
- create explicitly requested private output parent directories only after seed/snapshot validation;
- write JSON and Markdown only after both are fully rendered and validated.

- [ ] **Step 4: Verify CLI isolation and commit**

```bash
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
python scripts/build_repository_registry.py --check
git diff --check
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: generate private repository snapshots"
```

## Task 6: Bootstrap the local private layer without publishing it

**Files outside Git:**

- Modify: `~/.vulca/repository-registry-private-bootstrap-plan.md`
- Create: `~/.vulca/repository-registry-seeds.private.yaml`
- Create: `~/.vulca/repository-registry-snapshot.private.json`
- Create: `~/.vulca/repository-registry-snapshot.private.md`

- [ ] **Step 1: Rewrite the local runbook around stable seeds**

Use the already audited private/local repository identities and canonical local roots in the mode-`600` runbook. Remove any instruction to maintain a manual list of branches, HEADs, ahead/behind counts, or all linked worktrees.

Document:

- when a seed must change: add, rename, migrate, archive, move, authority change, or release-boundary change;
- when a snapshot should run: before repository-family cleanup, release review, or a fresh governance audit;
- that ordinary commits and new worktrees require no seed edit;
- that `--refresh-github` is optional and networked;
- that all cleanup remains human-reviewed and outside this command.

- [ ] **Step 2: Create the private stable seed file**

Translate the verified local inventory into the approved seed schema. Store one seed per independent repository identity and only canonical local roots. Let `git worktree list --porcelain` discover linked worktrees.

Before generating a snapshot, validate that the seed file contains none of:

```bash
rg -n 'observed_at|availability|remote_url|current_branch|head|comparison_ref|ahead|behind|worktree_state|prunable|recommended_action' \
  ~/.vulca/repository-registry-seeds.private.yaml
```

Expected: no matches.

- [ ] **Step 3: Generate the first no-network snapshot**

```bash
python scripts/build_repository_registry.py \
  --snapshot-private \
  --private-seeds ~/.vulca/repository-registry-seeds.private.yaml \
  --private-json ~/.vulca/repository-registry-snapshot.private.json \
  --private-markdown ~/.vulca/repository-registry-snapshot.private.md
chmod 600 \
  ~/.vulca/repository-registry-private-bootstrap-plan.md \
  ~/.vulca/repository-registry-seeds.private.yaml \
  ~/.vulca/repository-registry-snapshot.private.json \
  ~/.vulca/repository-registry-snapshot.private.md
```

Do not use `--refresh-github` in the bootstrap run.

- [ ] **Step 4: Verify privacy and file agreement**

Run a small read-only verification that parses both YAML and JSON, checks the common snapshot timestamp and record set, and confirms all four local files have mode `600`.

Then run:

```bash
git status --short
git check-ignore -v \
  ~/.vulca/repository-registry-seeds.private.yaml \
  ~/.vulca/repository-registry-snapshot.private.json \
  ~/.vulca/repository-registry-snapshot.private.md || true
```

Expected: no private file appears as a repository change. There is no Git commit for this task.

## Task 7: README discovery and public-only CI gate

**Files:**

- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing integration-policy tests**

Add tests that assert:

- `README.md` links to `docs/product/repository-registry.md`;
- CI runs `python scripts/build_repository_registry.py --check`;
- CI does not contain `--snapshot-private`, `--private-seeds`, `--refresh-github`, or `.vulca`;
- public registry output contains none of the exact private denylist values when a synthetic seed fixture is supplied.

- [ ] **Step 2: Add the public documentation link**

Add one concise bullet to the README support/governance area:

```markdown
- [Repository registry](docs/product/repository-registry.md) — public repository authority, lifecycle, synchronization, and release boundaries.
```

Do not add private snapshot instructions to the public README.

- [ ] **Step 3: Add the deterministic CI step**

After checkout/install and before the broader test suite, add:

```yaml
      - name: Repository registry is current
        run: python scripts/build_repository_registry.py --check
```

This step must not read the home directory, inspect Git worktrees, require `gh`, or access network metadata.

- [ ] **Step 4: Verify and commit**

```bash
python scripts/build_repository_registry.py --check
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git diff --check
git add README.md .github/workflows/ci.yml tests/test_repository_registry.py
git commit -m "ci: enforce public repository registry"
```

## Task 8: Final verification and review

**Files:** all files changed by Tasks 1–7.

- [ ] **Step 1: Re-run the deterministic public checks**

```bash
python scripts/build_repository_registry.py
git diff --exit-code -- docs/product/repository-registry.md
python scripts/build_repository_registry.py --check
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git diff --check
```

Expected: regeneration creates no diff and all focused checks pass.

- [ ] **Step 2: Run the relevant broader repository checks**

```bash
pytest tests/test_package.py tests/test_mcp_server.py tests/test_repository_registry.py -q
ruff check src/ tests/ scripts/build_repository_registry.py
```

If an optional dependency blocks a broader existing test, record the exact missing dependency and retain the passing focused verification. Do not describe blocked checks as passing.

- [ ] **Step 3: Refresh and inspect one private snapshot**

Run the Task 6 command without `--refresh-github`. Confirm:

- missing roots are represented as observations, not fatal errors;
- dirty worktrees are advisory and do not change the public command result;
- linked worktrees were discovered without seed duplication;
- no Git refs, files, worktrees, or remotes changed;
- JSON and Markdown use the same `observed_at` timestamp.

- [ ] **Step 4: Perform an independent diff review**

Review the complete diff for:

- public/private boundary leaks;
- deterministic ordering and timestamps;
- command allowlist and `shell=False` enforcement;
- partial-write behavior;
- accidental private-mode invocation in CI;
- test coverage for paths with spaces, timeouts, and failed GitHub refresh.

Resolve relevant findings, then re-run Steps 1 and 2.

- [ ] **Step 5: Confirm the implementation commit series**

The expected coherent implementation commits are:

1. `feat: validate public repository registry`
2. `feat: publish repository authority registry`
3. `feat: validate private repository scan seeds`
4. `feat: discover repository worktree state`
5. `feat: generate private repository snapshots`
6. `ci: enforce public repository registry`

Do not squash unless the user requests it. Do not push or open a pull request without separate authorization.

## Completion Criteria

- The public YAML and Markdown cover all currently verified public Vulca repositories and expose no private identity or local path.
- SDK version and MCP tool count are derived from code.
- Public generation is deterministic and `--check` detects drift.
- Private seeds contain stable identity/routing facts only.
- Private snapshots are explicit, timestamped, read-only, and outside Git.
- Worktrees are discovered automatically rather than maintained manually.
- Missing/dirty/private state never blocks normal feature CI.
- The scanner has no fetch, checkout, merge, push, prune, clean, or delete path.
- Focused tests, lint, public generation, and diff checks pass before completion is claimed.
