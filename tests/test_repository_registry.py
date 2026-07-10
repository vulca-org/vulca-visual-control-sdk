import builtins
import importlib.util
import json
import subprocess
import sys
import tomllib
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from scripts.build_repository_registry import (
    CommandResult,
    RegistryError,
    SubprocessRunner,
    build_private_snapshot,
    build_public_registry,
    classify_status,
    derive_sdk_facts,
    git_command,
    github_metadata,
    load_yaml,
    load_private_seeds,
    main,
    parse_worktree_porcelain,
    private_seed_denylist,
    recommend_action,
    render_private_json,
    render_private_markdown,
    render_public_registry,
    scan_checkout,
    validate_private_seeds,
    validate_public_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = REPO_ROOT / "docs/product/repository-registry.yaml"
PUBLIC_OUTPUT = REPO_ROOT / "docs/product/repository-registry.md"
VOLATILE_PRIVATE_FIELDS = (
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
)


def valid_public_registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "verified_on": "2026-07-10",
        "policy": "Only public repository authority belongs in this registry.",
        "repositories": [
            {
                "id": "vulca-sdk",
                "name": "vulca",
                "owner": "vulca-org",
                "visibility": "public",
                "role": "sdk",
                "lifecycle": "canonical",
                "canonical_for": ["SDK", "CLI", "MCP"],
                "sync_direction": "private development source to this public repository",
                "version_source": "pyproject.toml",
                "release_channels": ["PyPI", "GitHub tags"],
                "public_url": "https://github.com/vulca-org/vulca",
                "notes": "Canonical public product surface.",
            }
        ],
    }


def valid_private_seeds(root: str = "/tmp/example repository") -> dict[str, object]:
    return {
        "schema_version": 1,
        "repositories": [
            {
                "id": "example-private-platform",
                "full_name": "example/private-platform",
                "visibility": "private",
                "lifecycle": "active-supporting",
                "local_roots": [root],
                "expected_remote": "https://github.com/example/private-platform.git",
                "sensitivity": "internal",
                "release_boundary": "explicit owner approval",
                "sync_relationship": "exports selected public-safe artifacts",
            }
        ],
    }


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


@pytest.mark.parametrize(
    ("missing_path", "expected"),
    [
        ("pyproject.toml", "pyproject.toml"),
        ("src/vulca/mcp_server.py", "src/vulca/mcp_server.py"),
    ],
)
def test_derive_sdk_facts_reports_missing_sources(
    tmp_path: Path,
    missing_path: str,
    expected: str,
) -> None:
    (tmp_path / "src/vulca").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "vulca"\nversion = "0.23.1"\n',
        encoding="utf-8",
    )
    (tmp_path / "src/vulca/mcp_server.py").write_text(
        "@mcp.tool()\ndef first():\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / missing_path).unlink()

    with pytest.raises(RegistryError, match=expected):
        derive_sdk_facts(tmp_path)


def test_derive_sdk_facts_rejects_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "src/vulca").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    (tmp_path / "src/vulca/mcp_server.py").write_text(
        "@mcp.tool()\ndef first():\n    return None\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="invalid.*pyproject.toml"):
        derive_sdk_facts(tmp_path)


def test_derive_sdk_facts_requires_project_version(tmp_path: Path) -> None:
    (tmp_path / "src/vulca").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "vulca"\n', encoding="utf-8")
    (tmp_path / "src/vulca/mcp_server.py").write_text(
        "@mcp.tool()\ndef first():\n    return None\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="project.version"):
        derive_sdk_facts(tmp_path)


def test_derive_sdk_facts_requires_mcp_registration(tmp_path: Path) -> None:
    (tmp_path / "src/vulca").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "vulca"\nversion = "0.23.1"\n',
        encoding="utf-8",
    )
    (tmp_path / "src/vulca/mcp_server.py").write_text("def first():\n    return None\n", encoding="utf-8")

    with pytest.raises(RegistryError, match="MCP tool registrations"):
        derive_sdk_facts(tmp_path)


def test_load_yaml_requires_a_mapping(tmp_path: Path) -> None:
    source = tmp_path / "registry.yaml"
    source.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(RegistryError, match="mapping"):
        load_yaml(source)


def test_public_validation_accepts_valid_registry() -> None:
    validate_public_registry(valid_public_registry())


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
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0][field] = value

    with pytest.raises(RegistryError):
        validate_public_registry(data)


def test_public_validation_rejects_duplicate_ids_and_urls() -> None:
    data = valid_public_registry()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories.append(dict(repositories[0]))

    with pytest.raises(RegistryError, match="duplicate"):
        validate_public_registry(data)


def test_public_validation_does_not_echo_secret_values() -> None:
    secret = "github_pat_example_value_that_must_not_be_repeated"
    data = valid_public_registry()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["notes"] = secret

    with pytest.raises(RegistryError) as exc_info:
        validate_public_registry(data)

    assert secret not in str(exc_info.value)


def test_public_validation_requires_canonical_authority() -> None:
    data = valid_public_registry()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["canonical_for"] = []

    with pytest.raises(RegistryError, match="canonical_for"):
        validate_public_registry(data)


def test_public_validation_requires_migration_note() -> None:
    data = valid_public_registry()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["lifecycle"] = "migrated"
    repositories[0]["notes"] = ""

    with pytest.raises(RegistryError, match="migration"):
        validate_public_registry(data)


def test_public_validation_rejects_archived_release_channel() -> None:
    data = valid_public_registry()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["lifecycle"] = "archived"

    with pytest.raises(RegistryError, match="release_channels"):
        validate_public_registry(data)


def test_public_validation_rejects_private_denylist_match() -> None:
    data = valid_public_registry()

    with pytest.raises(RegistryError, match="private denylist"):
        validate_public_registry(data, private_denylist={"vulca-org"})


def test_committed_public_registry_is_valid_and_complete() -> None:
    data = load_yaml(PUBLIC_SOURCE)

    validate_public_registry(data)

    repositories = data["repositories"]
    assert isinstance(repositories, list)
    assert len(repositories) == 9
    assert {record["visibility"] for record in repositories} == {"public"}


def test_public_rendering_is_deterministic() -> None:
    data = valid_public_registry()
    facts = {"sdk_version": "0.23.1", "mcp_tool_count": 23}

    assert render_public_registry(data, facts) == render_public_registry(data, facts)


def test_public_rendering_includes_sections_and_derived_facts() -> None:
    rendered = render_public_registry(
        valid_public_registry(),
        {"sdk_version": "0.23.1", "mcp_tool_count": 23},
    )

    assert "# Vulca Public Repository Registry" in rendered
    assert "## Canonical repositories" in rendered
    assert "SDK version: `0.23.1`" in rendered
    assert "MCP tool count: `23`" in rendered
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


def test_public_rendering_places_derived_facts_under_sdk_record() -> None:
    rendered = render_public_registry(
        valid_public_registry(),
        {"sdk_version": "0.23.1", "mcp_tool_count": 23},
    )

    sdk_heading = rendered.index("### [vulca-org/vulca]")
    version_fact = rendered.index("SDK version: `0.23.1`")
    assert sdk_heading < version_fact


def test_committed_markdown_matches_fresh_render() -> None:
    assert build_public_registry(PUBLIC_SOURCE, REPO_ROOT) == PUBLIC_OUTPUT.read_text(encoding="utf-8")


def test_public_cli_check_passes_for_committed_output() -> None:
    assert main(["--check"]) == 0


def test_public_cli_check_rejects_stale_output_without_writing(tmp_path: Path) -> None:
    stale_output = tmp_path / "registry.md"
    stale_output.write_text("stale\n", encoding="utf-8")

    result = main(
        [
            "--check",
            "--source",
            str(PUBLIC_SOURCE),
            "--output",
            str(stale_output),
        ]
    )

    assert result == 1
    assert stale_output.read_text(encoding="utf-8") == "stale\n"


def test_public_cli_does_not_expand_home_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "registry.md"

    def reject_expanduser(path: Path) -> Path:
        raise AssertionError(f"public mode expanded a home path: {path.name}")

    monkeypatch.setattr(Path, "expanduser", reject_expanduser)

    assert main(["--source", str(PUBLIC_SOURCE), "--output", str(output)]) == 0
    assert output.is_file()


def test_private_seed_validation_accepts_stable_fields() -> None:
    validate_private_seeds(valid_private_seeds())


@pytest.mark.parametrize("field", VOLATILE_PRIVATE_FIELDS)
def test_private_seed_validation_rejects_volatile_fields(field: str) -> None:
    data = valid_private_seeds()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0][field] = "unstable"

    with pytest.raises(RegistryError, match="volatile"):
        validate_private_seeds(data)


def test_private_seed_validation_rejects_duplicate_ids() -> None:
    data = valid_private_seeds()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories.append(dict(repositories[0]))

    with pytest.raises(RegistryError, match="duplicate"):
        validate_private_seeds(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("local_roots", []),
        ("visibility", "unknown"),
        ("sensitivity", "unbounded"),
    ],
)
def test_private_seed_validation_rejects_invalid_stable_values(field: str, value: object) -> None:
    data = valid_private_seeds()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0][field] = value

    with pytest.raises(RegistryError):
        validate_private_seeds(data)


def test_private_seed_validation_does_not_echo_secret_values() -> None:
    secret = "github_pat_private_value_that_must_not_be_repeated"
    data = valid_private_seeds()
    repositories = data["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["release_boundary"] = secret

    with pytest.raises(RegistryError) as exc_info:
        validate_private_seeds(data)

    assert secret not in str(exc_info.value)


def test_load_private_seeds_validates_input(tmp_path: Path) -> None:
    source = tmp_path / "seeds.yaml"
    source.write_text(
        "schema_version: 1\nrepositories:\n  - id: incomplete\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError):
        load_private_seeds(source)


def test_private_seed_denylist_contains_private_identity_and_remote() -> None:
    denylist = private_seed_denylist(valid_private_seeds())

    assert "example/private-platform" in denylist
    assert "https://github.com/example/private-platform.git" in denylist
    assert "private-platform" in denylist


def test_subprocess_runner_uses_safe_list_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SubprocessRunner().run(
        ["git", "-C", "/tmp/example repository", "status"],
        timeout=10,
    )

    assert result == CommandResult(returncode=0, stdout="ok\n")
    assert captured["args"] == ["git", "-C", "/tmp/example repository", "status"]
    assert captured["kwargs"] == {
        "shell": False,
        "capture_output": True,
        "text": True,
        "timeout": 10,
        "check": False,
    }


def test_subprocess_runner_rejects_command_strings() -> None:
    with pytest.raises(RegistryError, match="argument list"):
        SubprocessRunner().run("git status", timeout=10)


def test_subprocess_runner_bounds_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["git", "status"], timeout=10, stderr="sensitive")

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    assert SubprocessRunner().run(["git", "status"], timeout=10) == CommandResult(
        returncode=124,
        stderr_category="timeout",
    )


def test_subprocess_runner_bounds_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("PATH and executable details")

    monkeypatch.setattr(subprocess, "run", raise_missing)

    assert SubprocessRunner().run(["git", "status"], timeout=10) == CommandResult(
        returncode=127,
        stderr_category="executable-not-found",
    )


@pytest.mark.parametrize(
    ("porcelain", "expected"),
    [
        ("", "clean"),
        (" M tracked.py\n", "modified"),
        ("?? new.py\n", "untracked"),
        (" M tracked.py\n?? new.py\n", "mixed"),
    ],
)
def test_classify_status(porcelain: str, expected: str) -> None:
    assert classify_status(porcelain) == expected


def test_parse_worktree_porcelain_preserves_paths_and_state() -> None:
    records = parse_worktree_porcelain(
        "worktree /tmp/example repository\n"
        "HEAD 1111111111111111111111111111111111111111\n"
        "branch refs/heads/main\n"
        "locked maintenance\n"
        "\n"
        "worktree /tmp/example detached\n"
        "HEAD 2222222222222222222222222222222222222222\n"
        "detached\n"
        "prunable gitdir file points to non-existent location\n"
    )

    assert records == [
        {
            "local_path": "/tmp/example repository",
            "head": "1111111111111111111111111111111111111111",
            "current_branch": "main",
            "locked": True,
            "prunable": False,
        },
        {
            "local_path": "/tmp/example detached",
            "head": "2222222222222222222222222222222222222222",
            "current_branch": "detached",
            "locked": False,
            "prunable": True,
        },
    ]


class RecordingRunner:
    def __init__(self, result: CommandResult | None = None) -> None:
        self.result = result or CommandResult(returncode=0, stdout="ok\n")
        self.calls: list[tuple[list[str], int]] = []

    def run(self, args: list[str], timeout: int) -> CommandResult:
        self.calls.append((list(args), timeout))
        return self.result


def test_git_command_preserves_path_as_one_argument() -> None:
    runner = RecordingRunner()

    git_command(runner, Path("/tmp/example repository"), "status", "--porcelain=v1")

    assert runner.calls == [
        (["git", "-C", "/tmp/example repository", "status", "--porcelain=v1"], 10)
    ]


@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("fetch", ()),
        ("status", ("--short",)),
        ("rev-parse", ("--git-dir",)),
    ],
)
def test_git_command_rejects_non_allowlisted_operations(
    operation: str,
    arguments: tuple[str, ...],
) -> None:
    with pytest.raises(RegistryError, match="allowlisted"):
        git_command(RecordingRunner(), Path("/tmp/repository"), operation, *arguments)


def _run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def test_scan_checkout_reads_real_repository_without_mutation(tmp_path: Path) -> None:
    root = tmp_path / "repository with spaces"
    remote = tmp_path / "remote.git"
    root.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    _run_git(root, "config", "user.name", "Registry Test")
    _run_git(root, "config", "user.email", "registry-test@example.invalid")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run_git(root, "add", "tracked.txt")
    _run_git(root, "commit", "-m", "initial")
    _run_git(root, "remote", "add", "origin", str(remote))
    _run_git(root, "push", "-u", "origin", "main")
    refs_before = _run_git(root, "show-ref")
    status_before = _run_git(root, "status", "--porcelain=v1")

    record = scan_checkout(root, str(remote), SubprocessRunner())

    assert record["availability"] == "available"
    assert record["current_branch"] == "main"
    assert isinstance(record["head"], str) and len(record["head"]) == 40
    assert record["remote_url"] == str(remote)
    assert record["worktree_state"] == "clean"
    assert record["comparison_ref"] == "origin/main"
    assert record["ahead"] == 0
    assert record["behind"] == 0
    assert record["recommended_action"] == "none"
    assert _run_git(root, "show-ref") == refs_before
    assert _run_git(root, "status", "--porcelain=v1") == status_before


def test_scan_checkout_treats_missing_upstream_as_unknown_not_error(tmp_path: Path) -> None:
    root = tmp_path / "local repository"
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    _run_git(root, "config", "user.name", "Registry Test")
    _run_git(root, "config", "user.email", "registry-test@example.invalid")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run_git(root, "add", "tracked.txt")
    _run_git(root, "commit", "-m", "initial")

    record = scan_checkout(root, None, SubprocessRunner())

    assert record["availability"] == "available"
    assert record["comparison_ref"] is None
    assert record["ahead"] == "unknown"
    assert record["behind"] == "unknown"
    assert record["remote_mismatch"] is False
    assert "error_category" not in record
    assert record["recommended_action"] == "none"


def test_scan_checkout_reports_missing_without_running_git(tmp_path: Path) -> None:
    runner = RecordingRunner()

    record = scan_checkout(tmp_path / "missing", "https://github.com/example/repository.git", runner)

    assert record["availability"] == "missing"
    assert record["recommended_action"] == "review-unavailable-checkout"
    assert runner.calls == []


def test_scan_checkout_reports_non_repository(tmp_path: Path) -> None:
    root = tmp_path / "ordinary directory"
    root.mkdir()

    record = scan_checkout(root, "https://github.com/example/repository.git", SubprocessRunner())

    assert record["availability"] == "not-a-repository"
    assert record["recommended_action"] == "review-unavailable-checkout"


def test_scan_checkout_bounds_git_timeout(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    runner = RecordingRunner(CommandResult(returncode=124, stderr_category="timeout"))

    record = scan_checkout(root, "https://github.com/example/repository.git", runner)

    assert record["availability"] == "not-a-repository"
    assert record["error_category"] == "timeout"


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"availability": "missing"}, "review-unavailable-checkout"),
        ({"availability": "available", "prunable": True}, "review-prunable-record"),
        ({"availability": "available", "remote_mismatch": True}, "inspect-remote-mismatch"),
        ({"availability": "available", "worktree_state": "modified"}, "review-dirty-worktree"),
        ({"availability": "available", "worktree_state": "clean", "ahead": 1}, "review-divergence"),
        ({"availability": "available", "worktree_state": "clean", "ahead": 0, "behind": 0}, "none"),
    ],
)
def test_recommend_action_is_advisory(record: dict[str, object], expected: str) -> None:
    assert recommend_action(record) == expected


def _write_private_seed_file(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_private_snapshot_discovers_and_deduplicates_worktrees(tmp_path: Path) -> None:
    root = tmp_path / "main repository"
    linked = tmp_path / "linked worktree"
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    _run_git(root, "config", "user.name", "Registry Test")
    _run_git(root, "config", "user.email", "registry-test@example.invalid")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run_git(root, "add", "tracked.txt")
    _run_git(root, "commit", "-m", "initial")
    _run_git(root, "remote", "add", "origin", "https://github.com/example/private-platform.git")
    _run_git(root, "worktree", "add", "-b", "feature", str(linked))
    seeds = valid_private_seeds(str(root))
    repositories = seeds["repositories"]
    assert isinstance(repositories, list)
    repositories[0]["local_roots"] = [str(root), str(linked)]
    observed_at = datetime(2026, 7, 10, 12, 30, tzinfo=timezone.utc)

    snapshot = build_private_snapshot(seeds, SubprocessRunner(), observed_at=observed_at)

    records = snapshot["records"]
    assert isinstance(records, list)
    assert snapshot["observed_at"] == "2026-07-10T12:30:00Z"
    assert [record["local_path"] for record in records] == sorted([str(root), str(linked)])
    assert {record["seed_id"] for record in records} == {"example-private-platform"}
    assert all(record["availability"] == "available" for record in records)


def test_private_snapshot_renderers_share_timestamp_and_records(tmp_path: Path) -> None:
    missing = tmp_path / "missing repository"
    snapshot = build_private_snapshot(
        valid_private_seeds(str(missing)),
        SubprocessRunner(),
        observed_at=datetime(2026, 7, 10, 12, 30, tzinfo=timezone.utc),
    )

    json_text = render_private_json(snapshot)
    markdown = render_private_markdown(snapshot)
    parsed = json.loads(json_text)

    assert parsed["observed_at"] == "2026-07-10T12:30:00Z"
    assert "2026-07-10T12:30:00Z" in markdown
    assert parsed["records"][0]["seed_id"] in markdown
    assert parsed["records"][0]["local_path"] in markdown
    assert parsed["records"][0]["availability"] == "missing"


def test_github_metadata_uses_fixed_list_command_and_timeout() -> None:
    runner = RecordingRunner(
        CommandResult(
            returncode=0,
            stdout=(
                '{"visibility":"PRIVATE","isArchived":false,'
                '"defaultBranchRef":{"name":"main"}}\n'
            ),
        )
    )

    metadata = github_metadata("example/private-platform", runner)

    assert runner.calls == [
        (
            [
                "gh",
                "repo",
                "view",
                "example/private-platform",
                "--json",
                "visibility,isArchived,defaultBranchRef",
            ],
            30,
        )
    ]
    assert metadata == {
        "availability": "available",
        "visibility": "private",
        "is_archived": False,
        "default_branch": "main",
    }


def test_private_snapshot_never_calls_github_without_refresh(tmp_path: Path) -> None:
    runner = RecordingRunner()

    snapshot = build_private_snapshot(
        valid_private_seeds(str(tmp_path / "missing")),
        runner,
        observed_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        refresh_github=False,
    )

    assert runner.calls == []
    records = snapshot["records"]
    assert isinstance(records, list) and len(records) == 1
    assert "github" not in records[0]


def test_failed_github_refresh_keeps_local_snapshot(tmp_path: Path) -> None:
    runner = RecordingRunner(CommandResult(returncode=1, stderr_category="command-failed"))

    snapshot = build_private_snapshot(
        valid_private_seeds(str(tmp_path / "missing")),
        runner,
        observed_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        refresh_github=True,
    )

    records = snapshot["records"]
    assert isinstance(records, list) and len(records) == 1
    assert records[0]["availability"] == "missing"
    assert records[0]["github"] == {
        "availability": "unavailable",
        "error_category": "command-failed",
    }


def test_public_cli_never_invokes_subprocess_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_run(*args: object, **kwargs: object) -> CommandResult:
        raise AssertionError("public mode invoked an external command")

    monkeypatch.setattr(SubprocessRunner, "run", reject_run)

    assert main(["--check"]) == 0


def test_private_cli_writes_snapshot_outside_repository(tmp_path: Path) -> None:
    seeds = tmp_path / "private" / "seeds.yaml"
    json_output = tmp_path / "snapshot" / "registry.json"
    markdown_output = tmp_path / "snapshot" / "registry.md"
    _write_private_seed_file(seeds, valid_private_seeds(str(tmp_path / "missing")))

    result = main(
        [
            "--snapshot-private",
            "--private-seeds",
            str(seeds),
            "--private-json",
            str(json_output),
            "--private-markdown",
            str(markdown_output),
        ]
    )

    assert result == 0
    assert json.loads(json_output.read_text(encoding="utf-8"))["records"][0]["availability"] == "missing"
    assert "missing" in markdown_output.read_text(encoding="utf-8")


def test_private_cli_rejects_paths_inside_repository(tmp_path: Path) -> None:
    outside_seed = tmp_path / "seeds.yaml"
    _write_private_seed_file(outside_seed, valid_private_seeds(str(tmp_path / "missing")))
    inside_output = REPO_ROOT / "private-snapshot.json"

    result = main(
        [
            "--snapshot-private",
            "--private-seeds",
            str(outside_seed),
            "--private-json",
            str(inside_output),
            "--private-markdown",
            str(tmp_path / "snapshot.md"),
        ]
    )

    assert result == 2
    assert not inside_output.exists()


def test_private_cli_validates_before_replacing_outputs(tmp_path: Path) -> None:
    invalid_seeds = tmp_path / "invalid.yaml"
    invalid_seeds.write_text("schema_version: 1\nrepositories: []\n", encoding="utf-8")
    json_output = tmp_path / "snapshot.json"
    markdown_output = tmp_path / "snapshot.md"
    json_output.write_text("old json\n", encoding="utf-8")
    markdown_output.write_text("old markdown\n", encoding="utf-8")

    result = main(
        [
            "--snapshot-private",
            "--private-seeds",
            str(invalid_seeds),
            "--private-json",
            str(json_output),
            "--private-markdown",
            str(markdown_output),
        ]
    )

    assert result == 2
    assert json_output.read_text(encoding="utf-8") == "old json\n"
    assert markdown_output.read_text(encoding="utf-8") == "old markdown\n"


def test_readme_links_public_repository_registry() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "[Repository registry](docs/product/repository-registry.md)" in readme


def test_ci_checks_only_public_repository_registry() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python scripts/build_repository_registry.py --check" in workflow
    for forbidden in ("--snapshot-private", "--private-seeds", "--refresh-github", ".vulca"):
        assert forbidden not in workflow


def test_public_render_excludes_synthetic_private_denylist() -> None:
    seeds = valid_private_seeds()
    denylist = private_seed_denylist(seeds)

    rendered = build_public_registry(PUBLIC_SOURCE, REPO_ROOT, private_denylist=denylist)

    assert all(value not in rendered for value in denylist)


def test_registry_script_falls_back_to_tomli_on_python310(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tomli = types.ModuleType("tomli")
    fake_tomli.loads = lambda text: {"project": {"version": "test"}}  # type: ignore[attr-defined]
    real_import = builtins.__import__

    def python310_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "tomllib":
            raise ModuleNotFoundError("simulated Python 3.10")
        if name == "tomli":
            return fake_tomli
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", python310_import)
    module_path = REPO_ROOT / "scripts/build_repository_registry.py"
    spec = importlib.util.spec_from_file_location("registry_python310_probe", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)

    spec.loader.exec_module(module)

    assert module.tomllib is fake_tomli


def test_project_declares_tomli_for_python310() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "tomli>=2.0; python_version < '3.11'" in project["project"]["dependencies"]
