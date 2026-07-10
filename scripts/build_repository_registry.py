"""Build and validate Vulca repository-governance artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised through an isolated import probe
    import tomli as tomllib


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
PUBLIC_TOP_LEVEL_FIELDS = {"schema_version", "verified_on", "policy", "repositories"}
PUBLIC_RECORD_FIELDS = {
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
PRIVATE_SEED_TOP_LEVEL_FIELDS = {"schema_version", "repositories"}
PRIVATE_SEED_FIELDS = {
    "id",
    "full_name",
    "visibility",
    "lifecycle",
    "local_roots",
    "expected_remote",
    "sensitivity",
    "release_boundary",
    "sync_relationship",
}
VOLATILE_PRIVATE_FIELDS = {
    "observed_at",
    "availability",
    "remote_url",
    "current_branch",
    "head",
    "comparison_ref",
    "ahead",
    "behind",
    "worktree_state",
    "prunable",
    "recommended_action",
}
PRIVATE_VISIBILITIES = {"public", "private", "local-only"}
PRIVATE_SENSITIVITIES = {"public", "internal", "restricted"}
ALLOWED_GIT_OPERATIONS: dict[str, set[tuple[str, ...]]] = {
    "rev-parse": {
        ("--is-inside-work-tree",),
        ("HEAD",),
        ("--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
    },
    "branch": {("--show-current",)},
    "remote": {("get-url", "origin")},
    "status": {("--porcelain=v1",)},
    "rev-list": {("--left-right", "--count", "@{upstream}...HEAD")},
    "worktree": {("list", "--porcelain")},
}
_CREDENTIAL_FIELD_PATTERN = re.compile(r"(?:token|password|secret|api[-_]?key|credential)", re.IGNORECASE)
_CREDENTIAL_VALUE_PATTERN = re.compile(
    r"(?:github_pat_|gh[pousr]_[A-Za-z0-9]|sk-[A-Za-z0-9]|AIza[0-9A-Za-z_-])",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_PUBLIC_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_SOURCE = REPOSITORY_ROOT / "docs/product/repository-registry.yaml"
DEFAULT_PUBLIC_OUTPUT = REPOSITORY_ROOT / "docs/product/repository-registry.md"


class RegistryError(ValueError):
    """Raised when registry input cannot be validated safely."""


@dataclass(frozen=True)
class CommandResult:
    """Bounded subprocess result that never retains raw stderr."""

    returncode: int
    stdout: str = ""
    stderr_category: str | None = None


class CommandRunner(Protocol):
    """Injectable boundary for fixed read-only external operations."""

    def run(self, args: Sequence[str], timeout: int) -> CommandResult:
        raise NotImplementedError


class SubprocessRunner:
    """Execute list-based commands without a shell and with bounded errors."""

    def run(self, args: Sequence[str], timeout: int) -> CommandResult:
        if isinstance(args, (str, bytes)) or not args or any(not isinstance(arg, str) for arg in args):
            raise RegistryError("command must be a non-empty argument list")
        try:
            completed = subprocess.run(
                list(args),
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(returncode=124, stderr_category="timeout")
        except FileNotFoundError:
            return CommandResult(returncode=127, stderr_category="executable-not-found")
        except OSError:
            return CommandResult(returncode=126, stderr_category="execution-error")

        category = None if completed.returncode == 0 else "command-failed"
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr_category=category,
        )


def load_yaml(path: Path) -> dict[str, object]:
    """Load a YAML mapping and convert parse failures into bounded errors."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"missing YAML source: {path.name}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RegistryError(f"invalid YAML source: {path.name}") from exc
    if not isinstance(loaded, dict):
        raise RegistryError("registry YAML root must be a mapping")
    return loaded


def load_private_seeds(path: Path) -> dict[str, object]:
    """Load and validate a stable private repository seed file."""
    data = load_yaml(path)
    validate_private_seeds(data)
    return data


def walk_values(value: object, field: str = "root") -> Iterator[tuple[str, object]]:
    """Yield leaf values with stable dotted field paths."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_field = f"{field}.{key}"
            yield from walk_values(child, child_field)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from walk_values(child, f"{field}[{index}]")
        return
    yield field, value


def _error(category: str, field: str) -> RegistryError:
    return RegistryError(f"{category} at {field}")


def _validate_public_safety(data: dict[str, object], private_denylist: set[str]) -> None:
    lowered_denylist = {item.casefold() for item in private_denylist if item.strip()}
    for field, value in walk_values(data):
        key = field.rsplit(".", 1)[-1].split("[", 1)[0]
        if key in PRIVATE_ONLY_FIELDS:
            raise _error("private-only field", field)
        if _CREDENTIAL_FIELD_PATTERN.search(key):
            raise _error("credential-like field", field)
        if not isinstance(value, str):
            continue

        stripped = value.strip()
        lowered = stripped.casefold()
        if stripped.startswith("/") or _WINDOWS_ABSOLUTE_PATH.match(stripped):
            raise _error("absolute path", field)
        if lowered.startswith(("file://", "ssh://", "git@")):
            raise _error("non-public URL", field)
        if "localhost" in lowered or "127.0.0.1" in lowered:
            raise _error("localhost reference", field)
        if any(fragment in lowered for fragment in (".env", "private-evidence", "credential-file", "session-file")):
            raise _error("private path fragment", field)
        if _CREDENTIAL_VALUE_PATTERN.search(stripped):
            raise _error("credential-like value", field)
        if any(denied in lowered for denied in lowered_denylist):
            raise _error("private denylist match", field)


def _require_string(record: Mapping[str, object], field: str, record_id: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"record {record_id}: {field} must be a non-empty string")
    return value


def _require_string_list(record: Mapping[str, object], field: str, record_id: str) -> list[str]:
    value = record.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise RegistryError(f"record {record_id}: {field} must be a list of non-empty strings")
    return value


def _validate_private_value_safety(data: dict[str, object]) -> None:
    for field, value in walk_values(data):
        if not isinstance(value, str):
            continue
        if _CREDENTIAL_VALUE_PATTERN.search(value):
            raise _error("credential-like value", field)
        lowered = value.casefold()
        if any(fragment in lowered for fragment in (".env", "credential-file", "session-file")):
            raise _error("forbidden private payload reference", field)


def validate_private_seeds(data: dict[str, object]) -> None:
    """Validate stable private identities while rejecting operational state."""
    _validate_private_value_safety(data)
    if set(data) != PRIVATE_SEED_TOP_LEVEL_FIELDS:
        raise RegistryError("private seed file has invalid top-level fields")
    if data.get("schema_version") != 1:
        raise RegistryError("private seed schema_version must be 1")
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RegistryError("private repositories must be a non-empty list")

    seen_ids: set[str] = set()
    for index, record in enumerate(repositories):
        if not isinstance(record, dict):
            raise RegistryError(f"private seed {index} must be a mapping")
        volatile = set(record) & VOLATILE_PRIVATE_FIELDS
        if volatile:
            raise RegistryError(f"private seed {index} contains volatile fields")
        seed_id = str(record.get("id", f"index-{index}"))
        if set(record) != PRIVATE_SEED_FIELDS:
            raise RegistryError(f"private seed {seed_id} has invalid stable fields")
        seed_id = _require_string(record, "id", seed_id)
        if not _PUBLIC_ID.fullmatch(seed_id):
            raise RegistryError(f"private seed {seed_id}: id must be lowercase kebab-case")
        if seed_id in seen_ids:
            raise RegistryError(f"duplicate private seed id: {seed_id}")
        seen_ids.add(seed_id)

        visibility = _require_string(record, "visibility", seed_id)
        lifecycle = _require_string(record, "lifecycle", seed_id)
        sensitivity = _require_string(record, "sensitivity", seed_id)
        _require_string(record, "release_boundary", seed_id)
        _require_string(record, "sync_relationship", seed_id)
        if visibility not in PRIVATE_VISIBILITIES:
            raise RegistryError(f"private seed {seed_id}: unsupported visibility")
        if lifecycle not in PUBLIC_LIFECYCLES:
            raise RegistryError(f"private seed {seed_id}: unsupported lifecycle")
        if sensitivity not in PRIVATE_SENSITIVITIES:
            raise RegistryError(f"private seed {seed_id}: unsupported sensitivity")

        roots = record.get("local_roots")
        if not isinstance(roots, list) or not roots:
            raise RegistryError(f"private seed {seed_id}: local_roots must be non-empty")
        if any(not isinstance(root, str) or not Path(root).is_absolute() for root in roots):
            raise RegistryError(f"private seed {seed_id}: local_roots must contain absolute paths")

        full_name = record.get("full_name")
        expected_remote = record.get("expected_remote")
        if visibility == "local-only":
            if full_name is not None or expected_remote is not None:
                raise RegistryError(f"private seed {seed_id}: local-only identity must be null")
        else:
            if not isinstance(full_name, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", full_name):
                raise RegistryError(f"private seed {seed_id}: full_name must be owner/repository")
            if not isinstance(expected_remote, str) or not expected_remote.strip():
                raise RegistryError(f"private seed {seed_id}: expected_remote must be a string")


def private_seed_denylist(data: dict[str, object]) -> set[str]:
    """Extract non-public identities that must never appear in public output."""
    validate_private_seeds(data)
    denied: set[str] = set()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    for record in repositories:
        if record["visibility"] == "public":
            continue
        for field in ("id", "full_name", "expected_remote"):
            value = record[field]
            if isinstance(value, str):
                denied.add(value)
        full_name = record["full_name"]
        if isinstance(full_name, str):
            denied.add(full_name.rsplit("/", 1)[-1])
        for root in record["local_roots"]:
            denied.add(root)
            denied.add(Path(root).name)
    return denied


def git_command(
    runner: CommandRunner,
    root: Path,
    operation: str,
    *arguments: str,
) -> CommandResult:
    """Run one fixed read-only Git operation with a 10-second timeout."""
    argument_tuple = tuple(arguments)
    if operation not in ALLOWED_GIT_OPERATIONS or argument_tuple not in ALLOWED_GIT_OPERATIONS[operation]:
        raise RegistryError("Git operation is not allowlisted")
    return runner.run(["git", "-C", str(root), operation, *arguments], timeout=10)


def classify_status(porcelain: str) -> str:
    """Classify porcelain-v1 output without retaining file names."""
    lines = [line for line in porcelain.splitlines() if line]
    if not lines:
        return "clean"
    has_untracked = any(line.startswith("??") for line in lines)
    has_tracked = any(not line.startswith("??") for line in lines)
    if has_untracked and has_tracked:
        return "mixed"
    if has_untracked:
        return "untracked"
    return "modified"


def parse_worktree_porcelain(text: str) -> list[dict[str, object]]:
    """Parse `git worktree list --porcelain` while preserving path spaces."""
    records: list[dict[str, object]] = []
    current: dict[str, object] = {}

    def finish() -> None:
        if not current:
            return
        if "local_path" not in current:
            raise RegistryError("worktree record is missing a path")
        current.setdefault("head", None)
        current.setdefault("current_branch", "detached")
        current.setdefault("locked", False)
        current.setdefault("prunable", False)
        records.append(dict(current))
        current.clear()

    for line in text.splitlines():
        if not line:
            finish()
            continue
        key, separator, value = line.partition(" ")
        if key == "worktree" and separator:
            if current:
                finish()
            current["local_path"] = value
        elif key == "HEAD" and separator:
            current["head"] = value
        elif key == "branch" and separator:
            prefix = "refs/heads/"
            current["current_branch"] = value.removeprefix(prefix)
        elif key == "detached":
            current["current_branch"] = "detached"
        elif key == "locked":
            current["locked"] = True
        elif key == "prunable":
            current["prunable"] = True
    finish()
    return records


def _normalized_remote(remote: str | None) -> str | None:
    if remote is None:
        return None
    normalized = remote.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@") and ":" in normalized:
        host, path = normalized[4:].split(":", 1)
        return f"{host.casefold()}/{path.casefold()}"
    match = re.match(r"https?://([^/]+)/(.+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).casefold()}/{match.group(2).casefold()}"
    return normalized


def recommend_action(record: dict[str, object]) -> str:
    """Return a non-mutating human-review label for an observed checkout."""
    if record.get("prunable") is True:
        return "review-prunable-record"
    if record.get("availability") != "available":
        return "review-unavailable-checkout"
    if record.get("remote_mismatch") is True:
        return "inspect-remote-mismatch"
    if record.get("worktree_state") in {"modified", "untracked", "mixed"}:
        return "review-dirty-worktree"
    if any(isinstance(record.get(field), int) and record[field] > 0 for field in ("ahead", "behind")):
        return "review-divergence"
    if record.get("error_category"):
        return "review-command-error"
    return "none"


def _unavailable_checkout(path: Path, availability: str, error_category: str | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "availability": availability,
        "local_path": str(path),
        "remote_url": None,
        "current_branch": None,
        "head": None,
        "comparison_ref": None,
        "ahead": "unknown",
        "behind": "unknown",
        "worktree_state": "unknown",
        "prunable": False,
        "remote_mismatch": False,
    }
    if error_category:
        record["error_category"] = error_category
    record["recommended_action"] = recommend_action(record)
    return record


def github_metadata(full_name: str, runner: CommandRunner) -> dict[str, object]:
    """Read bounded GitHub repository metadata through an explicit opt-in call."""
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", full_name):
        raise RegistryError("GitHub identity must be owner/repository")
    result = runner.run(
        [
            "gh",
            "repo",
            "view",
            full_name,
            "--json",
            "visibility,isArchived,defaultBranchRef",
        ],
        timeout=30,
    )
    if result.returncode != 0:
        return {
            "availability": "unavailable",
            "error_category": result.stderr_category or "command-failed",
        }
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"availability": "unavailable", "error_category": "invalid-response"}
    if not isinstance(payload, dict):
        return {"availability": "unavailable", "error_category": "invalid-response"}

    default_branch_ref = payload.get("defaultBranchRef")
    default_branch = default_branch_ref.get("name") if isinstance(default_branch_ref, dict) else None
    visibility = payload.get("visibility")
    is_archived = payload.get("isArchived")
    if not isinstance(visibility, str) or not isinstance(is_archived, bool):
        return {"availability": "unavailable", "error_category": "invalid-response"}
    return {
        "availability": "available",
        "visibility": visibility.casefold(),
        "is_archived": is_archived,
        "default_branch": default_branch,
    }


def _snapshot_timestamp(observed_at: datetime | None) -> str:
    value = observed_at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise RegistryError("snapshot observed_at must include a timezone")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _attach_seed_context(
    observed: dict[str, object],
    seed: Mapping[str, object],
    github: dict[str, object] | None,
) -> dict[str, object]:
    record = {
        "seed_id": seed["id"],
        "full_name": seed["full_name"],
        "visibility": seed["visibility"],
        "lifecycle": seed["lifecycle"],
        "expected_remote": seed["expected_remote"],
        "sensitivity": seed["sensitivity"],
        "release_boundary": seed["release_boundary"],
        "sync_relationship": seed["sync_relationship"],
        **observed,
    }
    if github is not None:
        record["github"] = github
    return record


def _validate_private_snapshot(snapshot: dict[str, object]) -> None:
    _validate_private_value_safety(snapshot)
    if set(snapshot) != {"schema_version", "observed_at", "github_refreshed", "records"}:
        raise RegistryError("private snapshot has invalid top-level fields")
    if snapshot.get("schema_version") != 1:
        raise RegistryError("private snapshot schema_version must be 1")
    observed_at = snapshot.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise RegistryError("private snapshot observed_at must be UTC")
    if not isinstance(snapshot.get("github_refreshed"), bool):
        raise RegistryError("private snapshot github_refreshed must be boolean")
    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise RegistryError("private snapshot records must be non-empty")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise RegistryError(f"private snapshot record {index} must be a mapping")
        for field in ("seed_id", "local_path", "availability", "recommended_action"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise RegistryError(f"private snapshot record {index} is missing {field}")


def build_private_snapshot(
    seeds: dict[str, object],
    runner: CommandRunner,
    observed_at: datetime | None = None,
    refresh_github: bool = False,
) -> dict[str, object]:
    """Expand stable seeds into one timestamped, read-only operational snapshot."""
    validate_private_seeds(seeds)
    timestamp = _snapshot_timestamp(observed_at)
    repositories = seeds["repositories"]
    assert isinstance(repositories, list)
    collected: list[tuple[int, dict[str, object]]] = []
    seen_paths: set[str] = set()

    for seed_index, seed in enumerate(repositories):
        full_name = seed["full_name"]
        github = None
        if refresh_github and isinstance(full_name, str):
            github = github_metadata(full_name, runner)

        for root_value in seed["local_roots"]:
            root = Path(root_value)
            root_key = str(root.resolve(strict=False))
            if root_key in seen_paths:
                continue

            root_observed = scan_checkout(root, seed["expected_remote"], runner)
            worktree_metadata: dict[str, dict[str, object]] = {}
            if root_observed["availability"] == "available":
                worktree_result = git_command(runner, root, "worktree", "list", "--porcelain")
                if worktree_result.returncode == 0:
                    for parsed in parse_worktree_porcelain(worktree_result.stdout):
                        parsed_key = str(Path(str(parsed["local_path"])).resolve(strict=False))
                        worktree_metadata[parsed_key] = parsed
                else:
                    root_observed.setdefault(
                        "error_category",
                        worktree_result.stderr_category or "worktree-discovery-failed",
                    )

            candidates: list[tuple[Path, dict[str, object] | None]] = [(root, root_observed)]
            candidates.extend(
                (Path(str(parsed["local_path"])), None)
                for key, parsed in worktree_metadata.items()
                if key != root_key
            )
            for candidate, pre_scanned in candidates:
                path_key = str(candidate.resolve(strict=False))
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                observed = dict(pre_scanned) if pre_scanned is not None else scan_checkout(
                    candidate,
                    seed["expected_remote"],
                    runner,
                )
                parsed = worktree_metadata.get(path_key)
                if parsed is not None:
                    observed["prunable"] = parsed["prunable"]
                    observed["locked"] = parsed["locked"]
                    if observed["head"] is None:
                        observed["head"] = parsed["head"]
                    if observed["current_branch"] is None:
                        observed["current_branch"] = parsed["current_branch"]
                    observed["recommended_action"] = recommend_action(observed)
                collected.append((seed_index, _attach_seed_context(observed, seed, github)))

    records = [record for _, record in sorted(collected, key=lambda item: (item[0], item[1]["local_path"]))]
    snapshot = {
        "schema_version": 1,
        "observed_at": timestamp,
        "github_refreshed": refresh_github,
        "records": records,
    }
    _validate_private_snapshot(snapshot)
    return snapshot


def render_private_json(snapshot: dict[str, object]) -> str:
    """Render the private authority artifact as stable JSON."""
    _validate_private_snapshot(snapshot)
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _markdown_cell(value: object) -> str:
    if value is None:
        return "unknown"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_private_markdown(snapshot: dict[str, object]) -> str:
    """Render a private human reading view from the same snapshot model."""
    _validate_private_snapshot(snapshot)
    lines = [
        "# Vulca Private Repository Snapshot",
        "",
        f"- Observed at: `{snapshot['observed_at']}`",
        f"- GitHub refreshed: `{'yes' if snapshot['github_refreshed'] else 'no'}`",
        "",
        "| Seed | Local path | Availability | Branch | HEAD | Ahead | Behind | State | Action |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    records = snapshot["records"]
    assert isinstance(records, list)
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(record.get(field))
                for field in (
                    "seed_id",
                    "local_path",
                    "availability",
                    "current_branch",
                    "head",
                    "ahead",
                    "behind",
                    "worktree_state",
                    "recommended_action",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "This snapshot is observational. Recommended actions require human review and are never executed here.",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def scan_checkout(
    root: Path,
    expected_remote: str | None,
    runner: CommandRunner,
) -> dict[str, object]:
    """Observe one checkout using only allowlisted read-only Git commands."""
    if not root.exists():
        return _unavailable_checkout(root, "missing")
    if not root.is_dir():
        return _unavailable_checkout(root, "not-a-repository")

    inside = git_command(runner, root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return _unavailable_checkout(root, "not-a-repository", inside.stderr_category)

    head_result = git_command(runner, root, "rev-parse", "HEAD")
    branch_result = git_command(runner, root, "branch", "--show-current")
    remote_result = git_command(runner, root, "remote", "get-url", "origin")
    status_result = git_command(runner, root, "status", "--porcelain=v1")
    upstream_result = git_command(
        runner,
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
    )

    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    remote = remote_result.stdout.strip() if remote_result.returncode == 0 else None
    comparison_ref = upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    ahead: int | str = "unknown"
    behind: int | str = "unknown"
    count_result: CommandResult | None = None
    if comparison_ref:
        count_result = git_command(
            runner,
            root,
            "rev-list",
            "--left-right",
            "--count",
            "@{upstream}...HEAD",
        )
        if count_result.returncode == 0:
            counts = count_result.stdout.split()
            if len(counts) == 2 and all(count.isdigit() for count in counts):
                behind, ahead = (int(counts[0]), int(counts[1]))

    results = (head_result, branch_result, status_result, count_result)
    error_category = next(
        (result.stderr_category for result in results if result is not None and result.stderr_category),
        None,
    )
    record = {
        "availability": "available",
        "local_path": str(root),
        "remote_url": remote,
        "current_branch": branch or "detached",
        "head": head,
        "comparison_ref": comparison_ref,
        "ahead": ahead,
        "behind": behind,
        "worktree_state": classify_status(status_result.stdout) if status_result.returncode == 0 else "unknown",
        "prunable": False,
        "remote_mismatch": _normalized_remote(remote) != _normalized_remote(expected_remote),
    }
    if error_category:
        record["error_category"] = error_category
    record["recommended_action"] = recommend_action(record)
    return record


def validate_public_registry(
    data: dict[str, object],
    private_denylist: set[str] | None = None,
) -> None:
    """Validate the committed registry schema and its public-safety boundary."""
    _validate_public_safety(data, private_denylist or set())
    if set(data) != PUBLIC_TOP_LEVEL_FIELDS:
        raise RegistryError("public registry has invalid top-level fields")
    if data.get("schema_version") != 1:
        raise RegistryError("schema_version must be 1")
    for field in ("verified_on", "policy"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RegistryError(f"{field} must be a non-empty string")

    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RegistryError("repositories must be a non-empty list")

    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, record in enumerate(repositories):
        if not isinstance(record, dict):
            raise RegistryError(f"repository record {index} must be a mapping")
        record_id = str(record.get("id", f"index-{index}"))
        if set(record) != PUBLIC_RECORD_FIELDS:
            raise RegistryError(f"record {record_id}: invalid public record fields")

        record_id = _require_string(record, "id", record_id)
        if not _PUBLIC_ID.fullmatch(record_id):
            raise RegistryError(f"record {record_id}: id must be lowercase kebab-case")
        name = _require_string(record, "name", record_id)
        owner = _require_string(record, "owner", record_id)
        visibility = _require_string(record, "visibility", record_id)
        role = _require_string(record, "role", record_id)
        lifecycle = _require_string(record, "lifecycle", record_id)
        _require_string(record, "sync_direction", record_id)
        _require_string(record, "version_source", record_id)
        public_url = _require_string(record, "public_url", record_id)
        notes = record.get("notes")
        if not isinstance(notes, str):
            raise RegistryError(f"record {record_id}: notes must be a string")
        canonical_for = _require_string_list(record, "canonical_for", record_id)
        release_channels = _require_string_list(record, "release_channels", record_id)

        if record_id in seen_ids or public_url in seen_urls:
            raise RegistryError(f"duplicate repository id or URL at record {record_id}")
        seen_ids.add(record_id)
        seen_urls.add(public_url)

        if visibility != "public":
            raise RegistryError(f"record {record_id}: visibility must be public")
        if role not in PUBLIC_ROLES:
            raise RegistryError(f"record {record_id}: unsupported role")
        if lifecycle not in PUBLIC_LIFECYCLES:
            raise RegistryError(f"record {record_id}: unsupported lifecycle")
        expected_url = f"https://github.com/{owner}/{name}"
        if public_url != expected_url:
            raise RegistryError(f"record {record_id}: public_url must be canonical GitHub HTTPS URL")
        if lifecycle == "canonical" and not canonical_for:
            raise RegistryError(f"record {record_id}: canonical_for is required")
        if lifecycle == "migrated" and not notes.strip():
            raise RegistryError(f"record {record_id}: migration note is required")
        if lifecycle == "archived" and release_channels:
            raise RegistryError(f"record {record_id}: release_channels must be empty when archived")


def derive_sdk_facts(root: Path) -> dict[str, object]:
    """Derive public SDK facts from canonical files in ``root``."""
    pyproject_path = root / "pyproject.toml"
    mcp_server_path = root / "src/vulca/mcp_server.py"

    try:
        pyproject_text = pyproject_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RegistryError("missing source: pyproject.toml") from exc
    try:
        project = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryError("invalid source: pyproject.toml") from exc
    try:
        version = project["project"]["version"]
    except (KeyError, TypeError) as exc:
        raise RegistryError("missing fact: project.version") from exc
    if not isinstance(version, str) or not version.strip():
        raise RegistryError("missing fact: project.version")

    try:
        mcp_server = mcp_server_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RegistryError("missing source: src/vulca/mcp_server.py") from exc
    tool_count = len(re.findall(r"^\s*@mcp\.tool\(", mcp_server, flags=re.MULTILINE))
    if tool_count == 0:
        raise RegistryError("missing fact: MCP tool registrations")

    return {"sdk_version": version, "mcp_tool_count": tool_count}


def _markdown_list(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "none"
    return ", ".join(str(value) for value in values)


def render_public_registry(
    data: dict[str, object],
    derived_facts: dict[str, object],
) -> str:
    """Render a deterministic public reading view in YAML record order."""
    validate_public_registry(data)
    repositories = data["repositories"]
    assert isinstance(repositories, list)

    lines = [
        "# Vulca Public Repository Registry",
        "",
        (
            "> Generated from `docs/product/repository-registry.yaml`; "
            f"authority facts verified on `{data['verified_on']}`."
        ),
        "",
        "## Policy",
        "",
        str(data["policy"]),
        "",
    ]

    sections = (
        ("canonical", "Canonical repositories"),
        ("active-supporting", "Active supporting repositories"),
        ("historical", "Historical repositories"),
        ("migrated", "Migrated repositories"),
        ("archived", "Archived repositories"),
    )
    for lifecycle, heading in sections:
        lines.extend((f"## {heading}", ""))
        records = [record for record in repositories if record["lifecycle"] == lifecycle]
        if not records:
            lines.extend(("_No repositories in this category._", ""))
            continue
        for record in records:
            full_name = f"{record['owner']}/{record['name']}"
            record_lines = [
                f"### [{full_name}]({record['public_url']})",
                "",
                f"- Role: `{record['role']}`",
                f"- Lifecycle: `{record['lifecycle']}`",
                f"- Canonical for: {_markdown_list(record['canonical_for'])}",
                f"- Synchronization: {record['sync_direction']}",
                f"- Version authority: {record['version_source']}",
                f"- Release channels: {_markdown_list(record['release_channels'])}",
            ]
            if record["role"] == "sdk" and record["lifecycle"] == "canonical":
                record_lines.extend(
                    (
                        f"- SDK version: `{derived_facts['sdk_version']}`",
                        f"- MCP tool count: `{derived_facts['mcp_tool_count']}`",
                    )
                )
            record_lines.extend((f"- Boundary note: {record['notes']}", ""))
            lines.extend(record_lines)

    lines.extend(
        (
            "## Maintenance",
            "",
            "1. Edit `docs/product/repository-registry.yaml` only for stable authority or lifecycle changes.",
            "2. Run `python scripts/build_repository_registry.py` to regenerate this document.",
            "3. Run `python scripts/build_repository_registry.py --check` before committing.",
            "",
            "Dynamic branches, commits, worktrees, and local availability are intentionally excluded from this public view.",
        )
    )
    rendered = "\n".join(lines).rstrip() + "\n"
    _validate_public_safety({"rendered": rendered}, set())
    return rendered


def build_public_registry(
    source: Path,
    root: Path,
    private_denylist: set[str] | None = None,
) -> str:
    """Validate public source and build its generated Markdown."""
    data = load_yaml(source)
    validate_public_registry(data, private_denylist=private_denylist)
    return render_public_registry(data, derive_sdk_facts(root))


def write_if_changed(path: Path, content: str) -> bool:
    """Write ``content`` only when it differs, returning whether a write occurred."""
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_PUBLIC_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--snapshot-private", action="store_true")
    parser.add_argument("--private-seeds", type=Path)
    parser.add_argument("--private-json", type=Path)
    parser.add_argument("--private-markdown", type=Path)
    parser.add_argument("--refresh-github", action="store_true")
    return parser


def _private_path_outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return resolved
    raise RegistryError("private seed and snapshot paths must be outside the repository root")


def _run_private_snapshot(args: argparse.Namespace) -> int:
    if args.check:
        raise RegistryError("--check cannot be combined with --snapshot-private")
    required = {
        "--private-seeds": args.private_seeds,
        "--private-json": args.private_json,
        "--private-markdown": args.private_markdown,
    }
    missing = [flag for flag, value in required.items() if value is None]
    if missing:
        raise RegistryError("snapshot mode requires all private seed and output paths")

    seed_path = _private_path_outside_repository(args.private_seeds)
    json_path = _private_path_outside_repository(args.private_json)
    markdown_path = _private_path_outside_repository(args.private_markdown)
    seeds = load_private_seeds(seed_path)
    snapshot = build_private_snapshot(
        seeds,
        SubprocessRunner(),
        refresh_github=args.refresh_github,
    )
    json_content = render_private_json(snapshot)
    markdown_content = render_private_markdown(snapshot)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    write_if_changed(json_path, json_content)
    write_if_changed(markdown_path, markdown_content)
    return 0


def _run_public(args: argparse.Namespace) -> int:
    if args.private_json is not None or args.private_markdown is not None or args.refresh_github:
        raise RegistryError("private output and refresh flags require --snapshot-private")
    denylist = None
    if args.private_seeds is not None:
        if not args.check:
            raise RegistryError("--private-seeds without snapshot mode requires --check")
        seed_path = _private_path_outside_repository(args.private_seeds)
        denylist = private_seed_denylist(load_private_seeds(seed_path))

    rendered = build_public_registry(args.source, REPOSITORY_ROOT, private_denylist=denylist)

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.is_file() else None
        if current != rendered:
            print(
                "repository registry is stale; regenerate with: "
                "python scripts/build_repository_registry.py",
                file=sys.stderr,
            )
            return 1
        return 0

    write_if_changed(args.output, rendered)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run public generation/checking or an explicit private snapshot."""
    args = _parser().parse_args(argv)
    try:
        if args.snapshot_private:
            return _run_private_snapshot(args)
        return _run_public(args)
    except RegistryError as exc:
        print(f"repository registry error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
