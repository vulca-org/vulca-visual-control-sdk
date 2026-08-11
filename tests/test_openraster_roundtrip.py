"""OpenRaster round-trip Effect Pack tests."""

from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image, ImageDraw

from vulca.layers.composite import composite_layers
from vulca.layers.export import (
    OPENRASTER_MIMETYPE,
    OpenRasterError,
    export_openraster,
    import_openraster,
)
from vulca.layers.manifest import load_manifest, write_manifest
from vulca.layers.types import LayerInfo, LayerResult


def _rgba_bytes(path: str | Path) -> bytes:
    with Image.open(path) as image:
        return image.convert("RGBA").tobytes()


def _make_artwork(root: Path) -> tuple[Path, list[LayerResult]]:
    artwork = root / "source-artwork"
    layers_dir = artwork / "layers"
    layers_dir.mkdir(parents=True)
    width, height = 48, 32

    background = Image.new("RGBA", (width, height), (238, 224, 196, 255))
    subject = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(subject).ellipse((11, 5, 35, 29), fill=(65, 105, 160, 230))
    light = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(light).rectangle((2, 2, 18, 10), fill=(255, 210, 80, 180))

    infos = [
        LayerInfo(
            id="layer_background",
            name="paper_base",
            description="Warm paper",
            z_index=10,
            content_type="background",
            visible=True,
            blend_mode="normal",
            opacity=1.0,
            tradition_role="底纸",
        ),
        LayerInfo(
            id="layer_subject",
            name="blue_subject",
            description="Main blue form",
            z_index=20,
            content_type="subject",
            visible=True,
            blend_mode="multiply",
            opacity=0.65,
            semantic_path="subject.main",
            regeneration_prompt="Keep the silhouette.\nPreserve the blue value group.",
        ),
        LayerInfo(
            id="layer_light",
            name="hidden_light",
            description="Optional light",
            z_index=30,
            content_type="effect",
            visible=False,
            blend_mode="screen",
            opacity=0.4,
        ),
    ]
    images = [background, subject, light]
    file_map: dict[str, str] = {}
    results: list[LayerResult] = []
    for position, (info, image) in enumerate(zip(infos, images, strict=True)):
        relative = f"layers/{position:02d}.png"
        path = artwork / relative
        image.save(path)
        file_map[info.id] = relative
        results.append(LayerResult(info=info, image_path=str(path), scores={"L1": 0.8 - position * 0.1}))

    write_manifest(
        infos,
        output_dir=str(artwork),
        width=width,
        height=height,
        split_mode="test-fixture",
        tradition="test-tradition",
        layer_files=file_map,
    )
    composite_layers(results, width=width, height=height, output_path=str(artwork / "composite.png"))
    return artwork, results


def _rewrite_archive(
    source: Path,
    destination: Path,
    replacements: dict[str, bytes],
    *,
    omit: set[str] | None = None,
    renames: dict[str, str] | None = None,
) -> None:
    omitted = omit or set()
    renamed = renames or {}
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(destination, "w", allowZip64=True) as rewritten:
        for original_info in original.infolist():
            if original_info.filename in omitted:
                continue
            payload = replacements.get(original_info.filename, original.read(original_info))
            info = zipfile.ZipInfo(renamed.get(original_info.filename, original_info.filename), date_time=original_info.date_time)
            info.compress_type = original_info.compress_type
            info.external_attr = original_info.external_attr
            rewritten.writestr(info, payload)


def test_openraster_no_edit_roundtrip_preserves_pixels_and_core_metadata(tmp_path: Path) -> None:
    artwork, original_layers = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    exported = export_openraster(str(artwork), str(archive))

    assert Path(exported["export_path"]) == archive
    assert len(exported["ora_sha256"]) == 64
    assert exported["provider"] == "not_applicable"
    with zipfile.ZipFile(archive, "r") as opened:
        infos = opened.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert opened.read("mimetype") == OPENRASTER_MIMETYPE
        assert {"stack.xml", "mergedimage.png", "Thumbnails/thumbnail.png", "vulca.json"}.issubset(opened.namelist())
        stack = ET.fromstring(opened.read("stack.xml"))
        root_stack = next(child for child in stack if child.tag == "stack")
        assert [layer.get("name").split(" [vulca-id:", 1)[0] for layer in root_stack] == [
            "hidden_light",
            "blue_subject",
            "paper_base",
        ]

    imported_dir = tmp_path / "imported"
    imported = import_openraster(str(archive), str(imported_dir))
    assert imported["verification"]["no_edit_roundtrip"] is True
    loaded = load_manifest(str(imported_dir))
    assert [layer.info.id for layer in loaded.layers] == [layer.info.id for layer in original_layers]
    assert [layer.info.name for layer in loaded.layers] == [layer.info.name for layer in original_layers]
    assert [layer.info.z_index for layer in loaded.layers] == [10, 20, 30]
    assert [layer.info.visible for layer in loaded.layers] == [True, True, False]
    assert [layer.info.blend_mode for layer in loaded.layers] == ["normal", "multiply", "screen"]
    assert [layer.info.opacity for layer in loaded.layers] == [1.0, 0.65, 0.4]
    assert loaded.layers[1].info.regeneration_prompt == "Keep the silhouette.\nPreserve the blue value group."
    for before, after in zip(original_layers, loaded.layers, strict=True):
        assert _rgba_bytes(before.image_path) == _rgba_bytes(after.image_path)
    assert _rgba_bytes(artwork / "composite.png") == _rgba_bytes(imported_dir / "composite.png")

    evidence = json.loads((imported_dir / "openraster-roundtrip.json").read_text(encoding="utf-8"))
    assert evidence["verification"]["status"] == "verified-no-edit"
    assert all(layer["pixels_changed"] is False for layer in evidence["layers"])
    assert evidence["provider"] == "not_applicable"


def test_openraster_roundtrips_repository_layered_demo_asset(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parent.parent / "assets" / "demo" / "v2" / "layers-split"
    archive = tmp_path / "repository-demo.ora"
    result = export_openraster(str(source), str(archive))
    assert result["layer_count"] == 6

    imported_dir = tmp_path / "repository-demo-import"
    imported = import_openraster(str(archive), str(imported_dir))
    assert imported["verification"]["no_edit_roundtrip"] is True
    before = load_manifest(str(source))
    after = load_manifest(str(imported_dir))
    assert [layer.info.id for layer in after.layers] == [layer.info.id for layer in before.layers]
    assert [layer.info.name for layer in after.layers] == [layer.info.name for layer in before.layers]
    for source_layer, imported_layer in zip(before.layers, after.layers, strict=True):
        assert _rgba_bytes(source_layer.image_path) == _rgba_bytes(imported_layer.image_path)


def test_openraster_import_records_only_the_edited_layer(tmp_path: Path) -> None:
    artwork, _ = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    export_openraster(str(artwork), str(archive))
    with zipfile.ZipFile(archive, "r") as opened:
        sidecar = json.loads(opened.read("vulca.json"))
        target = next(layer for layer in sidecar["layers"] if layer["id"] == "layer_subject")
        with Image.open(Path(artwork) / "layers" / "01.png") as source_image:
            edited = source_image.convert("RGBA")
        edited.putpixel((12, 6), (250, 20, 30, 255))
        output = io.BytesIO()
        edited.save(output, format="PNG")

    edited_archive = tmp_path / "edited.ora"
    _rewrite_archive(archive, edited_archive, {target["src"]: output.getvalue()})
    imported_dir = tmp_path / "edited-import"
    imported = import_openraster(str(edited_archive), str(imported_dir))
    assert imported["verification"]["no_edit_roundtrip"] is False
    evidence = json.loads((imported_dir / "openraster-roundtrip.json").read_text(encoding="utf-8"))
    changed = {item["id"]: item["pixels_changed"] for item in evidence["layers"]}
    assert changed == {"layer_background": False, "layer_subject": True, "layer_light": False}


def test_openraster_import_uses_layer_markers_when_sidecar_is_removed(tmp_path: Path) -> None:
    artwork, original_layers = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    export_openraster(str(artwork), str(archive))
    stripped = tmp_path / "without-sidecar.ora"
    _rewrite_archive(archive, stripped, {}, omit={"vulca.json"})

    imported_dir = tmp_path / "fallback-import"
    result = import_openraster(str(stripped), str(imported_dir))
    assert result["verification"]["no_edit_roundtrip"] is False
    assert result["warnings"]
    loaded = load_manifest(str(imported_dir))
    assert [layer.info.id for layer in loaded.layers] == [layer.info.id for layer in original_layers]


def test_openraster_reorder_updates_canonical_order_without_losing_ids(tmp_path: Path) -> None:
    artwork, original_layers = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    export_openraster(str(artwork), str(archive))
    with zipfile.ZipFile(archive, "r") as opened:
        stack = ET.fromstring(opened.read("stack.xml"))
        root_stack = next(child for child in stack if child.tag == "stack")
        children = list(root_stack)
        root_stack[:] = list(reversed(children))
        changed_stack = ET.tostring(stack, encoding="utf-8", xml_declaration=True)

    reordered = tmp_path / "reordered.ora"
    _rewrite_archive(archive, reordered, {"stack.xml": changed_stack})
    imported_dir = tmp_path / "reordered-import"
    result = import_openraster(str(reordered), str(imported_dir))
    assert result["verification"]["layer_order_changed"] is True
    loaded = load_manifest(str(imported_dir))
    assert [layer.info.id for layer in loaded.layers] == list(
        reversed([layer.info.id for layer in original_layers])
    )
    assert [layer.info.z_index for layer in loaded.layers] == [10, 20, 30]


def test_openraster_matches_sidecar_metadata_by_id_after_internal_path_change(tmp_path: Path) -> None:
    artwork, _ = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    export_openraster(str(artwork), str(archive))
    with zipfile.ZipFile(archive, "r") as opened:
        sidecar = json.loads(opened.read("vulca.json"))
        subject = next(layer for layer in sidecar["layers"] if layer["id"] == "layer_subject")
        old_src = subject["src"]
        new_src = "data/editor-renamed-subject.png"
        stack = ET.fromstring(opened.read("stack.xml"))
        root_stack = next(child for child in stack if child.tag == "stack")
        target = next(child for child in root_stack if child.get("src") == old_src)
        target.set("src", new_src)
        changed_stack = ET.tostring(stack, encoding="utf-8", xml_declaration=True)

    renamed_archive = tmp_path / "renamed-path.ora"
    _rewrite_archive(
        archive,
        renamed_archive,
        {"stack.xml": changed_stack},
        renames={old_src: new_src},
    )
    imported_dir = tmp_path / "renamed-path-import"
    result = import_openraster(str(renamed_archive), str(imported_dir))
    assert any("metadata matched by stable id" in warning for warning in result["warnings"])
    loaded = load_manifest(str(imported_dir))
    subject_layer = next(layer for layer in loaded.layers if layer.info.id == "layer_subject")
    assert subject_layer.info.regeneration_prompt == "Keep the silhouette.\nPreserve the blue value group."


def test_openraster_rejects_zip_slip_without_creating_destination(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.ora"
    with zipfile.ZipFile(archive, "w") as opened:
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        opened.writestr(mimetype, OPENRASTER_MIMETYPE)
        opened.writestr("../escape.png", b"not-an-image")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(OpenRasterError, match="Unsafe OpenRaster archive path"):
        import_openraster(str(archive), str(destination))
    assert not destination.exists()
    assert not (tmp_path.parent / "escape.png").exists()


def test_openraster_import_never_overwrites_existing_destination(tmp_path: Path) -> None:
    artwork, _ = _make_artwork(tmp_path)
    archive = tmp_path / "layers.ora"
    export_openraster(str(artwork), str(archive))
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(OpenRasterError, match="already exists"):
        import_openraster(str(archive), str(destination))
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_openraster_export_rejects_layer_file_outside_artwork(tmp_path: Path) -> None:
    artwork, _ = _make_artwork(tmp_path)
    outside = tmp_path / "outside.png"
    Image.new("RGBA", (48, 32), (255, 0, 0, 255)).save(outside)
    manifest_path = artwork / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["layers"][0]["file"] = "../outside.png"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(OpenRasterError, match="inside the artwork directory"):
        export_openraster(str(artwork), str(tmp_path / "must-not-exist.ora"))
    assert not (tmp_path / "must-not-exist.ora").exists()


def test_openraster_rejects_excessive_decoded_layer_workload(tmp_path: Path) -> None:
    archive = tmp_path / "oversized-workload.ora"
    stack = b'''<?xml version="1.0" encoding="UTF-8"?>
<image version="0.0.6" w="10000" h="10000"><stack>
<layer name="a [vulca-id:YQ]" src="data/a.png"/>
<layer name="b [vulca-id:Yg]" src="data/b.png"/>
<layer name="c [vulca-id:Yw]" src="data/c.png"/>
</stack></image>'''
    with zipfile.ZipFile(archive, "w") as opened:
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        opened.writestr(mimetype, OPENRASTER_MIMETYPE)
        opened.writestr("stack.xml", stack)

    with pytest.raises(OpenRasterError, match="decoded-pixel safety limit"):
        import_openraster(str(archive), str(tmp_path / "must-not-exist"))


def test_cli_lists_openraster_export_and_import(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    export_help = subprocess.run(
        [sys.executable, "-m", "vulca", "layers", "export", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert export_help.returncode == 0, export_help.stderr
    assert "{png,psd,ora}" in export_help.stdout
    import_help = subprocess.run(
        [sys.executable, "-m", "vulca", "layers", "import-ora", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert import_help.returncode == 0, import_help.stderr
    assert "output_dir" in import_help.stdout
