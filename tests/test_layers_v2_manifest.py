"""Tests for manifest V2 read/write and V1 migration."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from vulca.layers.manifest import MANIFEST_VERSION, load_manifest, write_manifest
from vulca.layers.types import LayerInfo, LayeredArtwork


def _make_layer(name: str, z_index: int = 0, **kwargs) -> LayerInfo:
    return LayerInfo(name=name, description=f"{name} layer", z_index=z_index, **kwargs)


def _write_dummy_png(path: str) -> None:
    img = Image.new("RGBA", (64, 64), (128, 64, 32, 255))
    img.save(path)


class TestWriteManifestV2:
    def test_writes_version_2(self, tmp_path):
        layer = _make_layer("mountains", z_index=1)
        path = write_manifest(
            [layer],
            output_dir=str(tmp_path),
            width=1024,
            height=1024,
            source_image="original.png",
            split_mode="regenerate",
        )
        data = json.loads(Path(path).read_text())
        assert data["version"] == 3
        assert data["width"] == 1024
        assert data["source_image"] == "original.png"
        assert data["split_mode"] == "regenerate"

    def test_writes_v2_fields(self, tmp_path):
        layer = _make_layer(
            "mountains",
            z_index=1,
            content_type="background",
            dominant_colors=["#333", "#666"],
            regeneration_prompt="Distant mountain peaks...",
            visible=True,
            locked=False,
        )
        layer.id = "layer_001"  # override for deterministic check
        path = write_manifest(
            [layer],
            output_dir=str(tmp_path),
            width=1024,
            height=768,
        )
        data = json.loads(Path(path).read_text())
        layer_data = data["layers"][0]
        assert layer_data["id"] == "layer_001"
        assert layer_data["content_type"] == "background"
        assert layer_data["dominant_colors"] == ["#333", "#666"]
        assert layer_data["regeneration_prompt"] == "Distant mountain peaks..."
        assert layer_data["visible"] is True
        assert layer_data["locked"] is False
        assert layer_data["file"] == "mountains.png"

    def test_preserves_real_dimensions(self, tmp_path):
        layer = _make_layer("sky", z_index=0)
        path = write_manifest(
            [layer],
            output_dir=str(tmp_path),
            width=768,
            height=512,
        )
        data = json.loads(Path(path).read_text())
        assert data["width"] == 768
        assert data["height"] == 512
        # must not be silently replaced with 1024×1024
        assert data["width"] != 1024
        assert data["height"] != 1024

    def test_returns_path_string(self, tmp_path):
        layer = _make_layer("bg", z_index=0)
        result = write_manifest([layer], output_dir=str(tmp_path), width=256, height=256)
        assert isinstance(result, str)
        assert result.endswith("manifest.json")
        assert Path(result).exists()

    def test_layers_sorted_by_z_index(self, tmp_path):
        layers = [
            _make_layer("fg", z_index=3),
            _make_layer("bg", z_index=0),
            _make_layer("mid", z_index=1),
        ]
        path = write_manifest(layers, output_dir=str(tmp_path), width=512, height=512)
        data = json.loads(Path(path).read_text())
        z_indices = [l["z_index"] for l in data["layers"]]
        assert z_indices == sorted(z_indices)

    def test_created_at_present(self, tmp_path):
        layer = _make_layer("bg", z_index=0)
        path = write_manifest([layer], output_dir=str(tmp_path), width=512, height=512)
        data = json.loads(Path(path).read_text())
        assert "created_at" in data
        assert "T" in data["created_at"]  # ISO 8601

    def test_source_image_defaults_to_empty(self, tmp_path):
        layer = _make_layer("bg", z_index=0)
        path = write_manifest([layer], output_dir=str(tmp_path), width=512, height=512)
        data = json.loads(Path(path).read_text())
        assert data["source_image"] == ""

    def test_split_mode_defaults_to_empty(self, tmp_path):
        layer = _make_layer("bg", z_index=0)
        path = write_manifest([layer], output_dir=str(tmp_path), width=512, height=512)
        data = json.loads(Path(path).read_text())
        assert data["split_mode"] == ""

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "output"
        layer = _make_layer("bg", z_index=0)
        write_manifest([layer], output_dir=str(new_dir), width=512, height=512)
        assert (new_dir / "manifest.json").exists()

    def test_accepts_safe_layer_file_override(self, tmp_path):
        layer = _make_layer("subject", z_index=0, id="stable-subject")
        path = write_manifest(
            [layer],
            output_dir=str(tmp_path),
            width=512,
            height=512,
            layer_files={"stable-subject": "layers/0000_subject.png"},
        )
        data = json.loads(Path(path).read_text())
        assert data["layers"][0]["file"] == "layers/0000_subject.png"

    def test_rejects_unsafe_layer_file_override(self, tmp_path):
        layer = _make_layer("subject", z_index=0, id="stable-subject")
        with pytest.raises(ValueError, match="safe relative PNG path"):
            write_manifest(
                [layer],
                output_dir=str(tmp_path),
                width=512,
                height=512,
                layer_files={"stable-subject": "../escape.png"},
            )


class TestLoadManifestV2:
    def test_load_v2_manifest(self, tmp_path):
        # Create dummy PNG files
        _write_dummy_png(str(tmp_path / "mountains.png"))
        _write_dummy_png(str(tmp_path / "composite.png"))

        manifest = {
            "version": 2,
            "width": 1024,
            "height": 1024,
            "source_image": "original.png",
            "split_mode": "regenerate",
            "created_at": "2026-03-30T12:00:00Z",
            "composite": "composite.png",
            "layers": [
                {
                    "id": "layer_001",
                    "name": "mountains",
                    "description": "distant peaks",
                    "z_index": 1,
                    "blend_mode": "normal",
                    "content_type": "background",
                    "visible": True,
                    "locked": False,
                    "file": "mountains.png",
                    "dominant_colors": ["#333", "#666"],
                    "regeneration_prompt": "Distant mountain peaks...",
                }
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        artwork = load_manifest(str(tmp_path))

        assert isinstance(artwork, LayeredArtwork)
        assert artwork.source_image == "original.png"
        assert artwork.split_mode == "regenerate"
        assert len(artwork.layers) == 1

        layer = artwork.layers[0]
        assert layer.info.id == "layer_001"
        assert layer.info.name == "mountains"
        assert layer.info.description == "distant peaks"
        assert layer.info.z_index == 1
        assert layer.info.content_type == "background"
        assert layer.info.dominant_colors == ["#333", "#666"]
        assert layer.info.regeneration_prompt == "Distant mountain peaks..."
        assert layer.info.visible is True
        assert layer.info.locked is False
        assert layer.image_path.endswith("mountains.png")
        assert artwork.manifest_path.endswith("manifest.json")

    def test_load_v2_manifest_composite_path(self, tmp_path):
        _write_dummy_png(str(tmp_path / "bg.png"))
        _write_dummy_png(str(tmp_path / "composite.png"))

        manifest = {
            "version": 2,
            "width": 512,
            "height": 512,
            "composite": "composite.png",
            "layers": [
                {
                    "id": "layer_bg_000",
                    "name": "bg",
                    "description": "",
                    "z_index": 0,
                    "blend_mode": "normal",
                    "content_type": "background",
                    "visible": True,
                    "locked": False,
                    "file": "bg.png",
                    "dominant_colors": [],
                    "regeneration_prompt": "",
                }
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        artwork = load_manifest(str(tmp_path))
        assert artwork.composite_path.endswith("composite.png")


class TestMigrateV1Manifest:
    def test_migrate_v1_manifest(self, tmp_path):
        _write_dummy_png(str(tmp_path / "sky.png"))
        _write_dummy_png(str(tmp_path / "composite.png"))

        v1_manifest = {
            "version": 1,
            "width": 800,
            "height": 600,
            "layers": [
                {
                    "name": "sky",
                    "description": "sky layer",
                    "file": "sky.png",
                    "bbox": {"x": 0, "y": 0, "w": 100, "h": 50},
                    "z_index": 0,
                    "blend_mode": "normal",
                    "bg_color": "white",
                }
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(v1_manifest))

        artwork = load_manifest(str(tmp_path))

        assert isinstance(artwork, LayeredArtwork)
        assert len(artwork.layers) == 1

        layer = artwork.layers[0]
        # id generated from name + index
        assert layer.info.id == "layer_sky_000"
        # defaults
        assert layer.info.content_type == "background"
        assert layer.info.visible is True
        assert layer.info.locked is False
        assert layer.info.dominant_colors == []
        assert layer.info.regeneration_prompt == ""
        # bbox preserved
        assert layer.info.bbox == {"x": 0, "y": 0, "w": 100, "h": 50}

    def test_migrate_v1_composite_defaults_to_composite_png(self, tmp_path):
        _write_dummy_png(str(tmp_path / "bg.png"))

        v1_manifest = {
            "version": 1,
            "width": 512,
            "height": 512,
            "layers": [
                {
                    "name": "bg",
                    "description": "",
                    "file": "bg.png",
                    "bbox": {"x": 0, "y": 0, "w": 100, "h": 100},
                    "z_index": 0,
                    "blend_mode": "normal",
                }
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(v1_manifest))
        artwork = load_manifest(str(tmp_path))
        # composite field absent → defaults to composite.png
        assert artwork.composite_path.endswith("composite.png")

    def test_migrate_v1_missing_version_treated_as_v1(self, tmp_path):
        _write_dummy_png(str(tmp_path / "bg.png"))

        no_version_manifest = {
            "width": 512,
            "height": 512,
            "layers": [
                {
                    "name": "bg",
                    "description": "",
                    "file": "bg.png",
                    "bbox": {"x": 0, "y": 0, "w": 100, "h": 100},
                    "z_index": 0,
                    "blend_mode": "normal",
                }
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(no_version_manifest))
        artwork = load_manifest(str(tmp_path))
        # No id in original → should be generated
        assert artwork.layers[0].info.id == "layer_bg_000"


class TestMissingManifest:
    def test_missing_manifest_raises(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            load_manifest(str(empty_dir))

    def test_missing_manifest_message_contains_dir(self, tmp_path):
        empty_dir = tmp_path / "no_manifest_here"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="manifest.json"):
            load_manifest(str(empty_dir))


class TestManifestVersionConstant:
    def test_manifest_version_is_2(self):
        assert MANIFEST_VERSION == 3
