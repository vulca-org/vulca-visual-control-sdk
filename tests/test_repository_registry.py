from pathlib import Path

import pytest

from scripts.build_repository_registry import (
    RegistryError,
    build_public_registry,
    derive_sdk_facts,
    load_yaml,
    main,
    render_public_registry,
    validate_public_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = REPO_ROOT / "docs/product/repository-registry.yaml"
PUBLIC_OUTPUT = REPO_ROOT / "docs/product/repository-registry.md"


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
