"""Manifest V2 read/write for VULCA layered artwork.

Single source of truth for manifest I/O, replacing the scattered
write_manifest in split.py and load_artwork in edit.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vulca.layers.types import LayerInfo, LayerResult, LayeredArtwork

MANIFEST_VERSION = 3

# v0.13.2 P2 T11: whitelist the keys runtime code is allowed to stash in
# layer_extras. Anything outside this set — including any name that would
# shadow a core LayerInfo field like 'id'/'name'/'z_index' — raises at
# write_manifest time rather than silently clobbering the explicit field.
ALLOWED_LAYER_EXTRAS_KEYS: frozenset[str] = frozenset({
    "source",       # "a" | "legacy"
    "status",       # "ok" | "failed"
    "cache_hit",
    "attempts",
    "canvas_color",
    "key_strategy",
    "reason",       # LayerFailure.reason
    "validation",   # ValidationReport dict
})


def write_manifest(
    layers: list[LayerInfo],
    *,
    output_dir: str,
    width: int,
    height: int,
    source_image: str = "",
    split_mode: str = "",
    generation_path: str = "",
    layerability: str = "",
    partial: bool = False,
    warnings: list | None = None,
    layer_extras: dict[str, dict] | None = None,
    layer_files: dict[str, str] | None = None,
    tradition: str = "",
) -> str:
    """Write manifest V3 JSON to output_dir/manifest.json. Returns path."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    extras = layer_extras or {}
    files = layer_files or {}
    unknown_file_ids = set(files) - {info.id for info in layers}
    if unknown_file_ids:
        raise ValueError(f"layer_files contains unknown layer ids: {sorted(unknown_file_ids)}")
    for layer_id, relative_path in files.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"layer_files[{layer_id!r}] must be a safe relative PNG path")
        normalized = Path(relative_path)
        if (
            normalized.is_absolute()
            or "\\" in relative_path
            or "\x00" in relative_path
            or ".." in normalized.parts
            or (normalized.parts and ":" in normalized.parts[0])
            or normalized.suffix.lower() != ".png"
        ):
            raise ValueError(f"layer_files[{layer_id!r}] must be a safe relative PNG path")
    for lid, extra_dict in extras.items():
        if not isinstance(extra_dict, dict):
            raise ValueError(
                f"layer_extras[{lid!r}] must be a dict, got {type(extra_dict).__name__}"
            )
        for k in extra_dict:
            if k not in ALLOWED_LAYER_EXTRAS_KEYS:
                raise ValueError(
                    f"unknown layer_extras key {k!r} for layer {lid!r}; "
                    f"allowed keys: {sorted(ALLOWED_LAYER_EXTRAS_KEYS)}"
                )

    manifest = {
        "version": MANIFEST_VERSION,
        "width": width,
        "height": height,
        "source_image": source_image,
        "split_mode": split_mode,
        "generation_path": generation_path,
        "layerability": layerability,
        "tradition": tradition,
        "partial": partial,
        "warnings": warnings or [],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "layers": [
            {
                **(extras.get(info.id, {})),
                "id": info.id,
                "name": info.name,
                "description": info.description,
                "z_index": info.z_index,
                "blend_mode": info.blend_mode,
                "content_type": info.content_type,
                "visible": info.visible,
                "locked": info.locked,
                "file": files.get(info.id, f"{info.name}.png"),
                "dominant_colors": info.dominant_colors,
                "regeneration_prompt": info.regeneration_prompt,
                "opacity": info.opacity,
                "x": info.x,
                "y": info.y,
                "width": info.width,
                "height": info.height,
                "rotation": info.rotation,
                "content_bbox": info.content_bbox,
                # v0.13.1 P0.2 — spatial anchor round-trip for retry.
                "position": info.position,
                "coverage": info.coverage,
                # v0.16 multi-layer — dot-notation hierarchical path.
                "semantic_path": info.semantic_path,
                # Phase 1.5+: hierarchical parent pointer + quality signals.
                "parent_layer_id": info.parent_layer_id,
                "quality_status": info.quality_status,
                "area_pct": info.area_pct,
            }
            for info in sorted(layers, key=lambda l: l.z_index)
        ],
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return str(manifest_path)


def load_manifest(artwork_dir: str) -> LayeredArtwork:
    """Load LayeredArtwork from manifest.json. Auto-migrates V1 manifests."""
    d = Path(artwork_dir)
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json in {artwork_dir}")

    manifest = json.loads(manifest_path.read_text())
    version = manifest.get("version", 1)

    layers = []
    for index, item in enumerate(manifest.get("layers", [])):
        if version >= 2:
            # V2: use id and content_type directly
            info = LayerInfo(
                name=item["name"],
                description=item.get("description", ""),
                z_index=item.get("z_index", index),
                id=item.get("id", f"layer_{item['name']}_{index:03d}"),
                content_type=item.get("content_type", "background"),
                dominant_colors=item.get("dominant_colors", []),
                regeneration_prompt=item.get("regeneration_prompt", ""),
                visible=item.get("visible", True),
                blend_mode=item.get("blend_mode", "normal"),
                locked=item.get("locked", False),
                opacity=item.get("opacity", 1.0),
                x=item.get("x", 0.0),
                y=item.get("y", 0.0),
                width=item.get("width", 100.0),
                height=item.get("height", 100.0),
                rotation=item.get("rotation", 0.0),
                content_bbox=item.get("content_bbox"),
                position=item.get("position", "") or "",
                coverage=item.get("coverage", "") or "",
                semantic_path=item.get("semantic_path", ""),
                parent_layer_id=item.get("parent_layer_id"),
                quality_status=item.get("quality_status", "detected"),
                area_pct=item.get("area_pct", 0.0),
            )
        else:
            # V1: migrate — generate id, default content_type, preserve bbox.
            # semantic_path defaults to "" (multi-layer schema didn't exist in
            # V1; legacy content_type remains authoritative).
            name = item.get("name", f"layer_{index:03d}")
            generated_id = f"layer_{name}_{index:03d}"
            info = LayerInfo(
                name=name,
                description=item.get("description", ""),
                z_index=item.get("z_index", index),
                id=generated_id,
                content_type="background",
                dominant_colors=[],
                regeneration_prompt="",
                visible=True,
                blend_mode=item.get("blend_mode", "normal"),
                locked=False,
                bbox=item.get("bbox"),
            )

        image_path = str(d / item.get("file", f"{info.name}.png"))
        scores = item.get("scores", {})
        layers.append(LayerResult(info=info, image_path=image_path, scores=scores))

    composite = str(d / manifest.get("composite", "composite.png"))

    return LayeredArtwork(
        composite_path=composite,
        layers=sorted(layers, key=lambda lr: lr.info.z_index),
        manifest_path=str(manifest_path),
        source_image=manifest.get("source_image", ""),
        split_mode=manifest.get("split_mode", ""),
    )
