from pathlib import Path

import pytest

from scripts.build_repository_registry import (
    RegistryError,
    derive_sdk_facts,
    load_yaml,
    validate_public_registry,
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
