import subprocess
from pathlib import Path

import pytest

from scripts.build_repository_registry import (
    CommandResult,
    RegistryError,
    SubprocessRunner,
    build_public_registry,
    classify_status,
    derive_sdk_facts,
    git_command,
    load_yaml,
    load_private_seeds,
    main,
    parse_worktree_porcelain,
    private_seed_denylist,
    recommend_action,
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
