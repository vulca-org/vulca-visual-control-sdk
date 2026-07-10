# Repository Registry Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic public repository registry with leak-resistant validation, plus an explicitly generated local private supplement for private repositories and worktrees.

**Architecture:** A public YAML file is the committed authoring source. A Python generator validates the source, derives the SDK version and MCP tool count from code, and renders the committed Markdown registry. The same generator accepts explicit private input/output paths, but default execution never reads outside the repository or inspects Git/GitHub state.

**Tech Stack:** Python 3.11+, `PyYAML`, `tomllib`, `pytest`, Markdown, GitHub Actions

**Design reference:** `docs/superpowers/specs/2026-07-10-repository-registry-governance-design.md`

---

## File Map

- Create `scripts/build_repository_registry.py`: schema validation, safety checks, derived facts, rendering, and CLI.
- Create `tests/test_repository_registry.py`: unit and integration tests for public and private registry behavior.
- Create `docs/product/repository-registry.yaml`: public-safe authoring source for public Vulca repositories.
- Create `docs/product/repository-registry.md`: deterministic generated public registry.
- Modify `README.md`: link the public registry from Support.
- Modify `.github/workflows/ci.yml`: add an explicit generated-registry drift check.
- Create `~/.vulca/repository-registry.private.yaml`: local-only private source.
- Create `~/.vulca/repository-registry.private.md`: local-only generated private registry.

## Task 1: Public schema, safety validation, and derived facts

**Files:**
- Create: `scripts/build_repository_registry.py`
- Create: `tests/test_repository_registry.py`

- [ ] **Step 1: Write failing tests for public validation and code-derived facts**

Create `tests/test_repository_registry.py` with these initial tests:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_repository_registry import (
    RegistryError,
    derive_sdk_facts,
    validate_public_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def _public_registry() -> dict:
    return {
        "schema_version": 1,
        "verified_on": "2026-07-10",
        "policy": "Only repositories already public on GitHub may appear here.",
        "repositories": [
            {
                "id": "vulca-sdk",
                "name": "vulca",
                "owner": "vulca-org",
                "visibility": "public",
                "role": "sdk",
                "lifecycle": "canonical",
                "canonical_for": ["Python SDK", "CLI", "MCP server"],
                "sync_direction": "private-development-source -> public repository",
                "version_source": "pyproject.toml",
                "release_channels": ["GitHub tag", "PyPI"],
                "public_url": "https://github.com/vulca-org/vulca",
                "notes": "Public execution-layer source.",
            }
        ],
    }


def test_derive_sdk_facts_reads_current_code():
    facts = derive_sdk_facts(ROOT)
    assert facts["sdk_version"] == "0.23.1"
    assert facts["mcp_tool_count"] == 23


def test_validate_public_registry_accepts_public_record():
    validate_public_registry(_public_registry())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("local_path", "/Users/example/dev/vulca"),
        ("remote_url", "git@github.com:example/private.git"),
        ("notes", "read credentials from .env.local"),
        ("notes", "token ghp_1234567890abcdef"),
    ],
)
def test_validate_public_registry_rejects_private_or_sensitive_content(field: str, value: str):
    data = _public_registry()
    data["repositories"][0][field] = value
    with pytest.raises(RegistryError, match="public-safety violation"):
        validate_public_registry(data)


def test_validate_public_registry_does_not_echo_secret_value():
    data = _public_registry()
    secret = "github_pat_11AA_sensitive_value"
    data["repositories"][0]["notes"] = secret
    with pytest.raises(RegistryError) as exc_info:
        validate_public_registry(data)
    assert secret not in str(exc_info.value)


def test_validate_public_registry_rejects_duplicate_ids():
    data = _public_registry()
    data["repositories"].append(dict(data["repositories"][0]))
    with pytest.raises(RegistryError, match="duplicate repository id"):
        validate_public_registry(data)


def test_validate_public_registry_rejects_unknown_lifecycle():
    data = _public_registry()
    data["repositories"][0]["lifecycle"] = "experimental"
    with pytest.raises(RegistryError, match="unsupported lifecycle"):
        validate_public_registry(data)
```

- [ ] **Step 2: Run the focused test module and confirm the expected import failure**

Run:

```bash
pytest tests/test_repository_registry.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'scripts.build_repository_registry'`.

- [ ] **Step 3: Implement the public validator and fact derivation**

Create `scripts/build_repository_registry.py` with this foundation:

```python
#!/usr/bin/env python3
"""Build public and explicitly requested private Vulca repository registries."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from pathlib import Path
import re
import sys
import tomllib
from typing import Any

import yaml


ROLES = {"sdk", "plugin", "adapter", "research", "website", "legacy"}
LIFECYCLES = {"canonical", "active-supporting", "historical", "migrated", "archived"}
PRIVATE_FIELDS = {
    "local_path",
    "remote_url",
    "default_branch",
    "current_branch",
    "head",
    "ahead",
    "behind",
    "worktree_state",
    "sensitivity",
    "release_boundary",
    "sync_relationship",
    "cleanup_priority",
    "recommended_action",
}
REQUIRED_PUBLIC_FIELDS = {
    "id",
    "name",
    "owner",
    "visibility",
    "role",
    "lifecycle",
    "canonical_for",
    "sync_direction",
    "version_source",
    "release_channels",
    "public_url",
    "notes",
}
SECRET_KEY_RE = re.compile(r"(password|token|api[_-]?key|secret|credential|oauth)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(
    r"(ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+)"
)
FORBIDDEN_VALUE_RE = re.compile(
    r"(^/Users/|^/home/|^[A-Za-z]:[\\]|file://|ssh://|git@|localhost|127\.0\.0\.1|\.env(?:\.|$)|sessions?/|credentials?)",
    re.IGNORECASE,
)


class RegistryError(ValueError):
    """Raised when a registry cannot be rendered safely."""


def _walk(value: Any, path: str = "root") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")
    else:
        yield path, value


def _fail_safely(category: str, path: str) -> None:
    raise RegistryError(f"public-safety violation ({category}) at {path}")


def _validate_public_safety(data: Mapping[str, Any]) -> None:
    for path, value in _walk(data):
        key = path.rsplit(".", 1)[-1]
        if key in PRIVATE_FIELDS:
            _fail_safely("private field", path)
        if isinstance(value, str):
            if SECRET_KEY_RE.search(key):
                _fail_safely("credential-like key", path)
            if SECRET_VALUE_RE.search(value):
                _fail_safely("credential-like value", path)
            if FORBIDDEN_VALUE_RE.search(value):
                _fail_safely("local or private value", path)


def derive_sdk_facts(root: Path) -> dict[str, str | int]:
    pyproject_path = root / "pyproject.toml"
    mcp_path = root / "src/vulca/mcp_server.py"
    if not pyproject_path.is_file():
        raise RegistryError("missing derived-fact source: pyproject.toml")
    if not mcp_path.is_file():
        raise RegistryError("missing derived-fact source: src/vulca/mcp_server.py")
    with pyproject_path.open("rb") as handle:
        pyproject = tomllib.load(handle)
    version = pyproject.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise RegistryError("pyproject.toml is missing project.version")
    tool_count = mcp_path.read_text(encoding="utf-8").count("@mcp.tool()")
    if tool_count < 1:
        raise RegistryError("src/vulca/mcp_server.py has no @mcp.tool() registrations")
    return {"sdk_version": version, "mcp_tool_count": tool_count}


def validate_public_registry(data: Mapping[str, Any], private_data: Mapping[str, Any] | None = None) -> None:
    _validate_public_safety(data)
    if data.get("schema_version") != 1:
        raise RegistryError("schema_version must be 1")
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RegistryError("repositories must be a non-empty list")
    ids: set[str] = set()
    urls: set[str] = set()
    private_names = _private_repository_denylist(private_data) if private_data else set()
    for record in repositories:
        if not isinstance(record, Mapping):
            raise RegistryError("repository record must be an object")
        missing = REQUIRED_PUBLIC_FIELDS - set(record)
        if missing:
            raise RegistryError(f"repository {record.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        repo_id = str(record["id"])
        if repo_id in ids:
            raise RegistryError(f"duplicate repository id: {repo_id}")
        ids.add(repo_id)
        url = str(record["public_url"])
        if url in urls:
            raise RegistryError(f"duplicate public URL: {url}")
        urls.add(url)
        if record["visibility"] != "public":
            _fail_safely("non-public visibility", f"repositories.{repo_id}.visibility")
        if record["role"] not in ROLES:
            raise RegistryError(f"unsupported role for {repo_id}: {record['role']}")
        if record["lifecycle"] not in LIFECYCLES:
            raise RegistryError(f"unsupported lifecycle for {repo_id}: {record['lifecycle']}")
        expected_url = f"https://github.com/{record['owner']}/{record['name']}"
        if url != expected_url:
            raise RegistryError(f"non-canonical public URL for {repo_id}")
        if record["lifecycle"] == "canonical" and not record["canonical_for"]:
            raise RegistryError(f"canonical repository {repo_id} requires canonical_for")
        if record["lifecycle"] == "migrated" and not record["notes"]:
            raise RegistryError(f"migrated repository {repo_id} requires a migration note")
        if record["lifecycle"] == "archived" and record["release_channels"]:
            raise RegistryError(f"archived repository {repo_id} cannot have active release channels")
        full_name = f"{record['owner']}/{record['name']}".casefold()
        if full_name in private_names or url.casefold() in private_names:
            _fail_safely("private denylist match", f"repositories.{repo_id}")


def _private_repository_denylist(data: Mapping[str, Any] | None) -> set[str]:
    if not data:
        return set()
    values: set[str] = set()
    for record in data.get("github_repositories", []):
        if record.get("visibility") != "private":
            continue
        if record.get("full_name"):
            values.add(str(record["full_name"]).casefold())
        if record.get("url"):
            values.add(str(record["url"]).casefold())
    return values
```

- [ ] **Step 4: Run the focused tests and confirm green**

Run:

```bash
pytest tests/test_repository_registry.py -q
```

Expected: `9 passed`.

- [ ] **Step 5: Commit the validator foundation**

```bash
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: add repository registry validation"
```

## Task 2: Public source, deterministic renderer, and generated document

**Files:**
- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`
- Create: `docs/product/repository-registry.yaml`
- Create: `docs/product/repository-registry.md`

- [ ] **Step 1: Add failing rendering and committed-output tests**

Append to `tests/test_repository_registry.py`:

```python
import yaml

from scripts.build_repository_registry import load_yaml, render_public_registry


PUBLIC_SOURCE = ROOT / "docs/product/repository-registry.yaml"
PUBLIC_OUTPUT = ROOT / "docs/product/repository-registry.md"


def test_render_public_registry_is_deterministic():
    data = _public_registry()
    facts = {"sdk_version": "0.23.1", "mcp_tool_count": 23}
    first = render_public_registry(data, facts)
    second = render_public_registry(data, facts)
    assert first == second
    assert "SDK version | `0.23.1`" in first
    assert "MCP tools | `23`" in first


def test_committed_public_registry_is_valid_and_current():
    data = load_yaml(PUBLIC_SOURCE)
    validate_public_registry(data)
    rendered = render_public_registry(data, derive_sdk_facts(ROOT))
    assert PUBLIC_OUTPUT.read_text(encoding="utf-8") == rendered


def test_public_registry_lists_only_public_visibility():
    data = yaml.safe_load(PUBLIC_SOURCE.read_text(encoding="utf-8"))
    assert {record["visibility"] for record in data["repositories"]} == {"public"}
```

- [ ] **Step 2: Run the new tests and confirm they fail on missing renderer/source**

Run:

```bash
pytest tests/test_repository_registry.py -q
```

Expected: collection or test failure because `load_yaml`, `render_public_registry`, and the public registry files do not exist.

- [ ] **Step 3: Add the public YAML source**

Create `docs/product/repository-registry.yaml` with this exact public-safe inventory:

```yaml
schema_version: 1
verified_on: "2026-07-10"
policy: >-
  Only repositories already public on GitHub may appear as records. Private
  development sources may be described only as unnamed synchronization inputs.
repositories:
  - id: vulca-sdk
    name: vulca
    owner: vulca-org
    visibility: public
    role: sdk
    lifecycle: canonical
    canonical_for:
      - Python SDK
      - command-line interface
      - MCP server and tool registrations
      - agent skill source
    sync_direction: private development source -> public release repository
    version_source: pyproject.toml and Git tag
    release_channels: [GitHub tag, PyPI]
    public_url: https://github.com/vulca-org/vulca
    notes: Public execution-layer source; code-derived facts are rendered below.
  - id: vulca-plugin
    name: vulca-plugin
    owner: vulca-org
    visibility: public
    role: plugin
    lifecycle: canonical
    canonical_for:
      - Claude Code plugin package
      - Gemini CLI extension package
      - Codex marketplace package
    sync_direction: vulca-org/vulca -> vulca-org/vulca-plugin
    version_source: plugin metadata and GitHub Release
    release_channels: [GitHub Release]
    public_url: https://github.com/vulca-org/vulca-plugin
    notes: Distribution package; it must track the public SDK package shape.
  - id: comfyui-vulca
    name: comfyui-vulca
    owner: vulca-org
    visibility: public
    role: adapter
    lifecycle: canonical
    canonical_for:
      - ComfyUI custom nodes
    sync_direction: vulca-org/vulca -> vulca-org/comfyui-vulca
    version_source: pyproject.toml and Git tag
    release_channels: [GitHub Release, ComfyUI Manager]
    public_url: https://github.com/vulca-org/comfyui-vulca
    notes: Public ComfyUI adapter; SDK compatibility must be reviewed before release.
  - id: vulca-bench
    name: VULCA-Bench
    owner: yha9806
    visibility: public
    role: research
    lifecycle: active-supporting
    canonical_for:
      - public VULCA-Bench repository snapshot
    sync_direction: private research source -> public research snapshot
    version_source: dataset release metadata
    release_channels: [GitHub, Hugging Face]
    public_url: https://github.com/yha9806/VULCA-Bench
    notes: Public benchmark snapshot; research submission state is governed separately.
  - id: vulca-framework
    name: VULCA-Framework
    owner: yha9806
    visibility: public
    role: research
    lifecycle: active-supporting
    canonical_for:
      - public tri-tier evaluation framework snapshot
    sync_direction: private research source -> public research snapshot
    version_source: repository revision
    release_channels: [GitHub]
    public_url: https://github.com/yha9806/VULCA-Framework
    notes: Public research implementation; it is not the product SDK.
  - id: emnlp2025-vulca
    name: EMNLP2025-VULCA
    owner: yha9806
    visibility: public
    role: research
    lifecycle: historical
    canonical_for:
      - EMNLP 2025 framework implementation history
    sync_direction: none
    version_source: repository revision
    release_channels: []
    public_url: https://github.com/yha9806/EMNLP2025-VULCA
    notes: Historical paper implementation retained for reproducibility.
  - id: vulca-emnlp2025-site
    name: VULCA-EMNLP2025
    owner: yha9806
    visibility: public
    role: website
    lifecycle: historical
    canonical_for:
      - historical immersive exhibition site
    sync_direction: none
    version_source: repository revision
    release_channels: []
    public_url: https://github.com/yha9806/VULCA-EMNLP2025
    notes: Historical exhibition surface; it is not the current product platform.
  - id: vulca-exhibition
    name: vulca-exhibition
    owner: yha9806
    visibility: public
    role: website
    lifecycle: migrated
    canonical_for:
      - pre-migration exhibition history
    sync_direction: yha9806/vulca-exhibition -> yha9806/VULCA-EMNLP2025
    version_source: not-applicable
    release_channels: []
    public_url: https://github.com/yha9806/vulca-exhibition
    notes: Migrated to the public VULCA-EMNLP2025 repository in 2025.
  - id: claude-skills-vulca
    name: claude-skills-vulca
    owner: yha9806
    visibility: public
    role: legacy
    lifecycle: archived
    canonical_for:
      - historical VULCA-specific Claude agents and skills
    sync_direction: none
    version_source: not-applicable
    release_channels: []
    public_url: https://github.com/yha9806/claude-skills-vulca
    notes: Archived; current public skill sources live in vulca-org/vulca and vulca-plugin.
```

- [ ] **Step 4: Implement YAML loading, public rendering, and the default CLI**

Append these functions and CLI behavior to `scripts/build_repository_registry.py`:

```python
DEFAULT_PUBLIC_SOURCE = Path("docs/product/repository-registry.yaml")
DEFAULT_PUBLIC_OUTPUT = Path("docs/product/repository-registry.md")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"unable to load registry source: {path}") from exc
    if not isinstance(data, dict):
        raise RegistryError(f"registry root must be an object: {path}")
    return data


def _repository_table(records: list[Mapping[str, Any]]) -> list[str]:
    lines = [
        "| Repository | Role | Lifecycle | Canonical for | Sync direction | Release channels |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        repository = f"[{record['owner']}/{record['name']}]({record['public_url']})"
        canonical_for = "; ".join(record["canonical_for"])
        channels = ", ".join(record["release_channels"]) or "None"
        lines.append(
            f"| {repository} | `{record['role']}` | `{record['lifecycle']}` | "
            f"{canonical_for} | {record['sync_direction']} | {channels} |"
        )
    return lines


def render_public_registry(data: Mapping[str, Any], facts: Mapping[str, str | int]) -> str:
    records = list(data["repositories"])
    groups = [
        ("Canonical public product repositories", {"canonical"}),
        ("Active supporting repositories", {"active-supporting"}),
        ("Historical, migrated, and archived repositories", {"historical", "migrated", "archived"}),
    ]
    lines = [
        "# Vulca Public Repository Registry",
        "",
        "<!-- Generated by scripts/build_repository_registry.py. Edit repository-registry.yaml. -->",
        "",
        f"**Verified on:** {data['verified_on']}",
        "",
        str(data["policy"]),
        "",
        "## Code-derived SDK facts",
        "",
        "| Fact | Value | Source |",
        "| --- | --- | --- |",
        f"| SDK version | `{facts['sdk_version']}` | `pyproject.toml` |",
        f"| MCP tools | `{facts['mcp_tool_count']}` | `src/vulca/mcp_server.py` |",
        "",
    ]
    for heading, lifecycles in groups:
        selected = [record for record in records if record["lifecycle"] in lifecycles]
        lines.extend([f"## {heading}", "", *_repository_table(selected), ""])
    lines.extend(
        [
            "## Authority and maintenance",
            "",
            "- Embedded or copied SDK/plugin directories are not authoritative unless named above.",
            "- A registry entry does not imply test, release, deployment, or public-readiness status.",
            "- Update `repository-registry.yaml`, regenerate this file, and run the registry tests together.",
            "- Private repository identities, local paths, worktrees, and cleanup state belong only in the local private supplement.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_PUBLIC_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source = args.source if args.source.is_absolute() else root / args.source
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        data = load_yaml(source)
        validate_public_registry(data)
        rendered = render_public_registry(data, derive_sdk_facts(root))
        if args.check:
            if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
                raise RegistryError(
                    "generated public registry is stale; run python scripts/build_repository_registry.py"
                )
        else:
            _write_if_changed(output, rendered)
    except RegistryError as exc:
        print(f"repository registry error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Generate the public Markdown and run focused verification**

Run:

```bash
python scripts/build_repository_registry.py
python scripts/build_repository_registry.py --check
pytest tests/test_repository_registry.py -q
git diff --check
```

Expected: generator and `--check` exit `0`; all registry tests pass; `docs/product/repository-registry.md` is created; `git diff --check` prints nothing.

- [ ] **Step 6: Commit the public registry**

```bash
git add docs/product/repository-registry.yaml docs/product/repository-registry.md scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: add public repository registry"
```

## Task 3: Explicit private supplement support

**Files:**
- Modify: `scripts/build_repository_registry.py`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Add failing tests for private validation, rendering, and denylisting**

Append to `tests/test_repository_registry.py`:

```python
from scripts.build_repository_registry import render_private_registry, validate_private_registry


def _private_registry() -> dict:
    return {
        "schema_version": 1,
        "verified_on": "2026-07-10",
        "github_repositories": [
            {
                "id": "private-platform",
                "full_name": "example/private-platform",
                "url": "https://github.com/example/private-platform",
                "visibility": "private",
                "lifecycle": "active-supporting",
                "sensitivity": "restricted",
                "release_boundary": "human release owner required",
                "recommended_action": "keep private",
            }
        ],
        "local_sources": [
            {
                "repository_id": "private-platform",
                "local_path": "/Users/example/dev/private-platform",
                "current_branch": "main",
                "head": "1234abcd",
                "worktree_state": "clean",
                "cleanup_priority": "none",
            }
        ],
        "worktrees": [],
    }


def test_private_registry_renders_only_when_explicitly_supplied():
    data = _private_registry()
    validate_private_registry(data)
    rendered = render_private_registry(data)
    assert "example/private-platform" in rendered
    assert "/Users/example/dev/private-platform" in rendered


def test_private_registry_rejects_secret_values_without_echoing_them():
    data = _private_registry()
    secret = "ghp_private_value_123"
    data["github_repositories"][0]["recommended_action"] = secret
    with pytest.raises(RegistryError) as exc_info:
        validate_private_registry(data)
    assert secret not in str(exc_info.value)


def test_private_denylist_blocks_public_record():
    public = _public_registry()
    public["repositories"][0]["owner"] = "example"
    public["repositories"][0]["name"] = "private-platform"
    public["repositories"][0]["public_url"] = "https://github.com/example/private-platform"
    with pytest.raises(RegistryError, match="private denylist match"):
        validate_public_registry(public, _private_registry())


def test_missing_requested_private_source_does_not_change_public_output(tmp_path: Path):
    public_source = tmp_path / "public.yaml"
    public_output = tmp_path / "public.md"
    public_source.write_text(yaml.safe_dump(_public_registry(), sort_keys=False), encoding="utf-8")
    marker = "unchanged public output\n"
    public_output.write_text(marker, encoding="utf-8")
    result = main(
        [
            "--source",
            str(public_source),
            "--output",
            str(public_output),
            "--private-source",
            str(tmp_path / "missing-private.yaml"),
            "--private-output",
            str(tmp_path / "private.md"),
        ]
    )
    assert result == 1
    assert public_output.read_text(encoding="utf-8") == marker
```

Add `main` to the existing import list from `scripts.build_repository_registry`.

- [ ] **Step 2: Run the private-focused tests and confirm the missing functions fail**

Run:

```bash
pytest tests/test_repository_registry.py -q
```

Expected: collection fails because `render_private_registry` and `validate_private_registry` are not defined.

- [ ] **Step 3: Implement private schema validation and rendering**

Add these constants and functions to `scripts/build_repository_registry.py`:

```python
PRIVATE_VISIBILITIES = {"public", "private", "local-only"}
SENSITIVITIES = {"public", "internal", "restricted"}
WORKTREE_STATES = {"clean", "modified", "untracked", "mixed"}
CLEANUP_PRIORITIES = {"none", "low", "medium", "high"}


def validate_private_registry(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise RegistryError("private schema_version must be 1")
    for path, value in _walk(data):
        key = path.rsplit(".", 1)[-1]
        if isinstance(value, str):
            if SECRET_KEY_RE.search(key) or SECRET_VALUE_RE.search(value):
                raise RegistryError(f"private registry credential-like content at {path}")
    repositories = data.get("github_repositories")
    local_sources = data.get("local_sources")
    worktrees = data.get("worktrees")
    if not isinstance(repositories, list):
        raise RegistryError("github_repositories must be a list")
    if not isinstance(local_sources, list):
        raise RegistryError("local_sources must be a list")
    if not isinstance(worktrees, list):
        raise RegistryError("worktrees must be a list")
    repository_ids: set[str] = set()
    for record in repositories:
        repo_id = str(record.get("id", ""))
        if not repo_id or repo_id in repository_ids:
            raise RegistryError("private repository IDs must be present and unique")
        repository_ids.add(repo_id)
        if record.get("visibility") not in PRIVATE_VISIBILITIES:
            raise RegistryError(f"unsupported private visibility for {repo_id}")
        if record.get("lifecycle") not in LIFECYCLES:
            raise RegistryError(f"unsupported private lifecycle for {repo_id}")
        if record.get("sensitivity") not in SENSITIVITIES:
            raise RegistryError(f"unsupported sensitivity for {repo_id}")
    for record in [*local_sources, *worktrees]:
        repo_id = str(record.get("repository_id", ""))
        if repo_id not in repository_ids and repo_id != "local-vulca-jobs":
            raise RegistryError(f"unknown repository_id in local record: {repo_id}")
        state = record.get("worktree_state")
        if state not in WORKTREE_STATES:
            raise RegistryError(f"unsupported worktree_state for {repo_id}")
        priority = record.get("cleanup_priority")
        if priority not in CLEANUP_PRIORITIES:
            raise RegistryError(f"unsupported cleanup_priority for {repo_id}")


def render_private_registry(data: Mapping[str, Any]) -> str:
    lines = [
        "# Vulca Private Repository Supplement",
        "",
        f"**Verified on:** {data['verified_on']}",
        "",
        "> Local-only operational inventory. Never commit this document to a public repository.",
        "",
        "## GitHub repositories",
        "",
        "| Repository | Visibility | Lifecycle | Sensitivity | Release boundary | Recommended action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in data["github_repositories"]:
        lines.append(
            f"| {record['full_name']} | {record['visibility']} | {record['lifecycle']} | "
            f"{record['sensitivity']} | {record['release_boundary']} | {record['recommended_action']} |"
        )
    lines.extend(
        [
            "",
            "## Local repository sources",
            "",
            "| Repository ID | Path | Branch | HEAD | State | Cleanup |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in data["local_sources"]:
        lines.append(
            f"| {record['repository_id']} | `{record['local_path']}` | `{record['current_branch']}` | "
            f"`{record['head']}` | {record['worktree_state']} | {record['cleanup_priority']} |"
        )
    lines.extend(
        [
            "",
            "## Additional worktrees",
            "",
            "| Repository ID | Path | Branch | HEAD | State | Cleanup |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in data["worktrees"]:
        lines.append(
            f"| {record['repository_id']} | `{record['local_path']}` | `{record['current_branch']}` | "
            f"`{record['head']}` | {record['worktree_state']} | {record['cleanup_priority']} |"
        )
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Make private generation validate before any public write**

Add these two arguments to `build_parser` before its `return parser` line:

```python
    parser.add_argument("--private-source", type=Path)
    parser.add_argument("--private-output", type=Path)
```

Then replace the body of `main` with this ordering so a missing or invalid requested private source cannot partially update public output:

```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source = args.source if args.source.is_absolute() else root / args.source
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        data = load_yaml(source)
        private_data: dict[str, Any] | None = None
        private_rendered: str | None = None
        private_output: Path | None = None
        if bool(args.private_source) != bool(args.private_output):
            raise RegistryError("--private-source and --private-output must be supplied together")
        if args.private_source:
            private_data = load_yaml(args.private_source.expanduser())
            validate_private_registry(private_data)
            private_rendered = render_private_registry(private_data)
            private_output = args.private_output.expanduser()
        validate_public_registry(data, private_data)
        rendered = render_public_registry(data, derive_sdk_facts(root))
        if args.check:
            if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
                raise RegistryError(
                    "generated public registry is stale; run python scripts/build_repository_registry.py"
                )
            if private_output and (
                not private_output.is_file()
                or private_output.read_text(encoding="utf-8") != private_rendered
            ):
                raise RegistryError("generated private registry is stale; rerun with private arguments")
        else:
            _write_if_changed(output, rendered)
            if private_output and private_rendered is not None:
                _write_if_changed(private_output, private_rendered)
    except RegistryError as exc:
        print(f"repository registry error: {exc}", file=sys.stderr)
        return 1
    return 0
```

- [ ] **Step 5: Run focused tests and public drift check**

Run:

```bash
pytest tests/test_repository_registry.py -q
python scripts/build_repository_registry.py --check
git diff --check
```

Expected: all registry tests pass; public `--check` exits `0`; `git diff --check` prints nothing.

- [ ] **Step 6: Commit private-support code without private data**

```bash
git add scripts/build_repository_registry.py tests/test_repository_registry.py
git commit -m "feat: support private repository supplement"
```

## Task 4: Populate and render the local private supplement

**Files:**
- Create outside Git: `~/.vulca/repository-registry.private.yaml`
- Create outside Git: `~/.vulca/repository-registry.private.md`

- [ ] **Step 1: Read the local private bootstrap plan before touching private data**

Run:

```bash
test -f ~/.vulca/repository-registry-private-bootstrap-plan.md
sed -n '1,260p' ~/.vulca/repository-registry-private-bootstrap-plan.md
```

Expected: the local plan exists and contains the exact read-only discovery commands, private repository identities, local source paths, worktree paths, policy mappings, and completeness checks. None of that operational data appears in this public plan.

- [ ] **Step 2: Create the private YAML with the complete identified repository set**

Follow `~/.vulca/repository-registry-private-bootstrap-plan.md` exactly. It contains the private identity set, current local source paths, additional worktree paths, lifecycle and sensitivity policy map, read-only refresh commands, and required completeness counts. Use `apply_patch` for both local file creations; do not copy any of those operational values into tracked files, shell history, or the public generated Markdown.

- [ ] **Step 3: Render the private Markdown explicitly**

Run:

```bash
python scripts/build_repository_registry.py \
  --private-source ~/.vulca/repository-registry.private.yaml \
  --private-output ~/.vulca/repository-registry.private.md
```

Expected: exit `0`; both public and private Markdown are current; no Git operation is performed.

- [ ] **Step 4: Verify private completeness and public isolation**

Run:

```bash
python scripts/build_repository_registry.py \
  --check \
  --private-source ~/.vulca/repository-registry.private.yaml \
  --private-output ~/.vulca/repository-registry.private.md
rg -c '^  - id:' ~/.vulca/repository-registry.private.yaml
rg -c '^  - repository_id:' ~/.vulca/repository-registry.private.yaml
git status --short
```

Expected: `--check` exits `0`; the first count is `16`; the second count is at least `27` (8 local sources plus 19 additional worktrees); Git status shows no private files and no unexpected changes.

Do not commit the two files under `~/.vulca`.

## Task 5: Public discoverability and CI drift gate

**Files:**
- Modify: `README.md:Support section`
- Modify: `.github/workflows/ci.yml:test job`
- Modify: `tests/test_repository_registry.py`

- [ ] **Step 1: Add a failing integration test for README and CI wiring**

Append to `tests/test_repository_registry.py`:

```python
def test_registry_is_linked_from_readme_and_checked_in_ci():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "docs/product/repository-registry.md" in readme
    assert "python scripts/build_repository_registry.py --check" in ci
```

- [ ] **Step 2: Run the integration test and confirm failure**

Run:

```bash
pytest tests/test_repository_registry.py::test_registry_is_linked_from_readme_and_checked_in_ci -q
```

Expected: failure because neither README nor CI contains the registry command/link.

- [ ] **Step 3: Link the public registry from README Support**

Add this bullet in the README Support section after the Plugin bullet:

```markdown
- **Repository registry:** [`docs/product/repository-registry.md`](docs/product/repository-registry.md) — public source-of-truth map for canonical, supporting, migrated, and archived Vulca repositories
```

- [ ] **Step 4: Add an explicit CI drift check**

In `.github/workflows/ci.yml`, add this step after `Lint` and before the full test suite:

```yaml
      - name: Repository registry drift check
        run: python scripts/build_repository_registry.py --check
```

- [ ] **Step 5: Run focused and full relevant verification**

Run:

```bash
python scripts/build_repository_registry.py --check
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git diff --check
```

Expected: registry check exits `0`; all registry tests pass; Ruff exits `0`; `git diff --check` prints nothing.

- [ ] **Step 6: Commit discoverability and CI integration**

```bash
git add README.md .github/workflows/ci.yml tests/test_repository_registry.py
git commit -m "ci: enforce repository registry drift check"
```

## Task 6: Final verification and handoff

**Files:**
- Verify all files changed by Tasks 1-5

- [ ] **Step 1: Run the complete registry verification**

```bash
python scripts/build_repository_registry.py --check
python scripts/build_repository_registry.py \
  --check \
  --private-source ~/.vulca/repository-registry.private.yaml \
  --private-output ~/.vulca/repository-registry.private.md
pytest tests/test_repository_registry.py -q
ruff check scripts/build_repository_registry.py tests/test_repository_registry.py
git diff --check
```

Expected: every command exits `0`.

- [ ] **Step 2: Run the broader CI-equivalent test command if the environment has installed dev extras**

```bash
pytest tests/ \
  --ignore=tests/test_cli_layers_retry.py \
  --ignore=tests/test_layered_mock_fallback.py \
  --ignore=tests/test_layered_partial_e2e.py \
  --ignore=tests/test_layered_strict_mode.py \
  --ignore=tests/vulca/layers/test_apply_alpha_assert.py \
  --ignore=tests/vulca/pipeline/nodes/test_layer_generate_capability_routing.py \
  --ignore=tests/vulca/providers/test_capabilities.py \
  --ignore=tests/vulca/scripts/test_migrate_overlap_resolution.py \
  --ignore=tests/test_organism_phase2.py \
  --ignore=tests/test_providers.py \
  --ignore=tests/test_decompose_smoke.py \
  --ignore=tests/test_tool_color_gamut.py \
  --ignore=tests/vulca/layers/test_image_loader.py \
  --ignore=tests/vulca/scripts/test_evfsam_common_uses_image_loader.py \
  --ignore=tests/vulca/scripts/test_evfsam_prompt_schema.py \
  --ignore=tests/test_import_cop_helper.py \
  --ignore=tests/test_import_cop_subprocess.py \
  --ignore=tests/test_unload_models.py \
  --ignore=tests/vulca/scripts/test_claude_orchestrated_pipeline.py \
  -q
```

Expected: exit `0`. If required extras are unavailable, report the exact dependency failure and retain the focused registry verification as the completed task-specific gate.

- [ ] **Step 3: Confirm branch history and cleanliness**

```bash
git log --oneline --decorate -6
git status --short --branch
```

Expected: the design commit and four implementation commits are visible; no tracked or untracked project changes remain.

- [ ] **Step 4: Run an independent diff review, then address only registry-scoped findings**

```bash
gemini-agent diff-review --smart-diff
```

Expected: the review receives the current branch diff. Ignore unrelated pre-existing SAM, provider, or mypy findings; fix registry correctness, leak prevention, determinism, tests, or documentation findings before handoff.

---

## Expected Commit Sequence

1. `feat: add repository registry validation`
2. `feat: add public repository registry`
3. `feat: support private repository supplement`
4. `ci: enforce repository registry drift check`

The local private YAML and Markdown are never staged or committed.
