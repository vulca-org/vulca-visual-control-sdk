"""Build and validate Vulca repository-governance artifacts."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import yaml


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


def build_public_registry(source: Path, root: Path) -> str:
    """Validate public source and build its generated Markdown."""
    data = load_yaml(source)
    validate_public_registry(data)
    return render_public_registry(data, derive_sdk_facts(root))


def write_if_changed(path: Path, content: str) -> bool:
    """Write ``content`` only when it differs, returning whether a write occurred."""
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _public_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_PUBLIC_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run deterministic public generation or drift checking."""
    args = _public_parser().parse_args(argv)
    try:
        rendered = build_public_registry(args.source, REPOSITORY_ROOT)
    except RegistryError as exc:
        print(f"repository registry error: {exc}", file=sys.stderr)
        return 2

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


if __name__ == "__main__":
    raise SystemExit(main())
