import subprocess
from pathlib import Path

import pytest

from scripts.build_repository_registry import (
    CommandResult,
    RegistryError,
    SubprocessRunner,
    build_public_registry,
    derive_sdk_facts,
    load_yaml,
    load_private_seeds,
    main,
    private_seed_denylist,
    render_public_registry,
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
