"""Distribution and import-provenance checks for the canonical capability SDK."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from zipfile import ZipFile


EXPECTED_CAPABILITIES = {
    ("vulca.image.generate", "1.0.0"),
    ("vulca.image.edit", "1.0.0"),
    ("vulca.image.compose_static", "1.0.0"),
    ("vulca.image.adapt_static", "1.0.0"),
    ("vulca.image.validate_static", "1.0.0"),
    ("vulca.image.evaluate", "1.0.0"),
}

EXPECTED_WHEEL_FILES = {
    "vulca/capability/__init__.py",
    "vulca/capability/types.py",
    "vulca/capability/registry.py",
    "vulca/capability/builtin.py",
    "vulca/capability/runtime.py",
    "vulca/capability/static.py",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_FRONTEND_VERSION = "1.4.3"
BUILD_BACKEND_VERSION = "1.31.0"


def _build_wheel(outdir: Path, environment: dict[str, str]) -> Path:
    outdir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(outdir)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = sorted(outdir.glob("vulca-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_canonical_capability_wheel_contains_isolated_import_surface(tmp_path: Path) -> None:
    assert importlib.metadata.version("build") == BUILD_FRONTEND_VERSION
    assert importlib.metadata.version("hatchling") == BUILD_BACKEND_VERSION

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["build-system"]["requires"] == [f"hatchling=={BUILD_BACKEND_VERSION}"]

    build_environment = os.environ.copy()
    build_environment.pop("PYTHONPATH", None)
    wheel_paths = (
        _build_wheel(tmp_path / "wheel-one", build_environment),
        _build_wheel(tmp_path / "wheel-two", build_environment),
    )
    wheel_bytes = tuple(path.read_bytes() for path in wheel_paths)
    wheel_sha256 = tuple(hashlib.sha256(content).hexdigest() for content in wheel_bytes)
    assert wheel_bytes[0] == wheel_bytes[1]
    assert wheel_sha256[0] == wheel_sha256[1]

    wheel_path = wheel_paths[0]
    with ZipFile(wheel_path) as wheel:
        wheel_members = set(wheel.namelist())
        capability_members = {
            member
            for member in wheel_members
            if member.startswith("vulca/capability/") and not member.endswith("/")
        }
        assert capability_members == EXPECTED_WHEEL_FILES

        wheel_metadata = wheel.read("vulca-0.24.1.dist-info/WHEEL")
        distribution_metadata = wheel.read("vulca-0.24.1.dist-info/METADATA")

    assert b"Generator: hatchling 1.31.0" in wheel_metadata.splitlines()
    parsed_metadata = BytesParser(policy=default).parsebytes(distribution_metadata)
    assert parsed_metadata["Metadata-Version"] == "2.4"
    assert parsed_metadata["Name"] == "vulca"
    assert parsed_metadata["Version"] == "0.24.1"

    install_dir = tmp_path / "installed-wheel"
    install_dir.mkdir()
    install_environment = os.environ.copy()
    install_environment.pop("PYTHONPATH", None)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(install_dir),
            str(wheel_path),
        ],
        cwd=tmp_path,
        env=install_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    probe = """
import importlib.metadata
import json
from pathlib import Path
import sys

install_dir = Path(sys.argv[1]).resolve()
project_root = Path(sys.argv[2]).resolve()
source_dir = project_root / "src"
sys.path.insert(0, str(install_dir))

import vulca
from vulca.capability import builtin_registry

loaded_path = Path(vulca.__file__).resolve()
assert loaded_path.is_relative_to(install_dir), loaded_path
assert not loaded_path.is_relative_to(project_root), loaded_path
assert not loaded_path.is_relative_to(source_dir), loaded_path
assert all(Path(package_path).resolve().is_relative_to(install_dir) for package_path in vulca.__path__)
assert all(
    not (
        Path(entry or ".").resolve().is_relative_to(project_root)
        or Path(entry or ".").resolve().is_relative_to(source_dir)
    )
    for entry in sys.path
), sys.path

registry = builtin_registry()
resolved = sorted(
    (capability.manifest.capability_id, capability.manifest.version)
    for capability in registry._capabilities.values()
)
assert importlib.metadata.version("vulca") == vulca.__version__ == "0.24.1"
assert Path(importlib.metadata.distribution("vulca").locate_file("")).resolve().is_relative_to(install_dir)
assert resolved == sorted([
    ("vulca.image.adapt_static", "1.0.0"),
    ("vulca.image.compose_static", "1.0.0"),
    ("vulca.image.edit", "1.0.0"),
    ("vulca.image.evaluate", "1.0.0"),
    ("vulca.image.generate", "1.0.0"),
    ("vulca.image.validate_static", "1.0.0"),
])
for capability_id, version in resolved:
    capability = registry.resolve(capability_id, version)
    assert capability.manifest.capability_id == capability_id
    assert capability.manifest.version == version

print(json.dumps({"imported_from": str(loaded_path), "capabilities": resolved}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            probe,
            str(install_dir),
            str(PROJECT_ROOT),
        ],
        cwd=tmp_path,
        env=install_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    evidence = json.loads(result.stdout)
    assert Path(evidence["imported_from"]).is_relative_to(install_dir)
    assert set(map(tuple, evidence["capabilities"])) == EXPECTED_CAPABILITIES
