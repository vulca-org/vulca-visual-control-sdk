"""Export layered artwork to delivery and interchange formats."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from PIL import Image

from vulca.layers.artifact import load_artifact_v3
from vulca.layers.blend import blend_layers
from vulca.layers.manifest import write_manifest
from vulca.layers.transform import needs_transform
from vulca.layers.types import LayerInfo, LayerResult


OPENRASTER_MIMETYPE = b"image/openraster"
OPENRASTER_VERSION = "0.0.6"
OPENRASTER_SIDECAR = "vulca.json"
OPENRASTER_EVIDENCE = "openraster-roundtrip.json"
OPENRASTER_OPERATION_VERSION = "openraster-roundtrip/1"
VULCA_ORA_NS = "https://vulcaart.art/ns/openraster/1.0"
MAX_ARCHIVE_ENTRIES = 4096
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_XML_BYTES = 4 * 1024 * 1024
MAX_SIDECAR_BYTES = 8 * 1024 * 1024
MAX_CANVAS_DIMENSION = 32768
MAX_CANVAS_PIXELS = 100_000_000
MAX_TOTAL_LAYER_PIXELS = 256_000_000
MAX_LAYERS = 256
_LAYER_MARKER_RE = re.compile(r"^(?P<name>.*) \[vulca-id:(?P<id>[A-Za-z0-9_-]+)\]$", re.DOTALL)

_BLEND_TO_ORA = {
    "normal": "svg:src-over",
    "multiply": "svg:multiply",
    "screen": "svg:screen",
    "overlay": "svg:overlay",
    "soft_light": "svg:soft-light",
    "darken": "svg:darken",
    "lighten": "svg:lighten",
    "color_dodge": "svg:color-dodge",
    "color_burn": "svg:color-burn",
}
_ORA_TO_BLEND = {value: key for key, value in _BLEND_TO_ORA.items()}


class OpenRasterError(ValueError):
    """Raised when an ORA file cannot preserve the VULCA layer contract."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rgba_sha256(image: Image.Image) -> str:
    rgba = image.convert("RGBA")
    prefix = f"RGBA:{rgba.width}x{rgba.height}\0".encode("ascii")
    return _sha256_bytes(prefix + rgba.tobytes())


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=6)
    return output.getvalue()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _checked_text(value: object, *, field: str, default: str = "", limit: int = 32768) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise OpenRasterError(f"{field} must be text")
    if len(value) > limit or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise OpenRasterError(f"{field} contains unsupported control characters or is too long")
    return value


def _checked_identifier(value: object, *, field: str = "layer id") -> str:
    identifier = _checked_text(value, field=field, limit=512)
    if not identifier:
        raise OpenRasterError(f"{field} must not be empty")
    return identifier


def _encode_layer_id(layer_id: str) -> str:
    return base64.urlsafe_b64encode(layer_id.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_layer_id(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    try:
        payload = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
        return _checked_identifier(payload.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, OpenRasterError) as exc:
        raise OpenRasterError("Invalid VULCA layer-id marker in OpenRaster layer name") from exc


def _marked_layer_name(name: str, layer_id: str) -> str:
    return f"{name} [vulca-id:{_encode_layer_id(layer_id)}]"


def _split_marked_layer_name(name: str) -> tuple[str, str | None]:
    match = _LAYER_MARKER_RE.fullmatch(name)
    if not match:
        return name, None
    return match.group("name"), _decode_layer_id(match.group("id"))


def _checked_canvas(width: object, height: object) -> tuple[int, int]:
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width <= 0
        or height <= 0
        or width > MAX_CANVAS_DIMENSION
        or height > MAX_CANVAS_DIMENSION
        or width * height > MAX_CANVAS_PIXELS
    ):
        raise OpenRasterError("Canvas dimensions are invalid or exceed the OpenRaster safety limit")
    return width, height


def _canvas_from_document(document: dict) -> tuple[int, int]:
    canvas = document.get("canvas")
    if isinstance(canvas, dict):
        return _checked_canvas(canvas.get("width"), canvas.get("height"))
    return _checked_canvas(document.get("width"), document.get("height"))


def _load_png(payload: bytes, *, field: str, expected_size: tuple[int, int] | None = None) -> Image.Image:
    if len(payload) > MAX_MEMBER_BYTES:
        raise OpenRasterError(f"{field} exceeds the per-file safety limit")
    try:
        with Image.open(io.BytesIO(payload)) as opened:
            if opened.format != "PNG":
                raise OpenRasterError(f"{field} must be a PNG image")
            opened.load()
            image = opened.convert("RGBA")
    except OpenRasterError:
        raise
    except Exception as exc:
        raise OpenRasterError(f"{field} is not a readable PNG: {exc}") from exc
    if expected_size is not None and image.size != expected_size:
        raise OpenRasterError(f"{field} has canvas {image.size}; expected {expected_size}")
    return image


def _document_fields(document: dict) -> dict:
    warnings = document.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        warnings = []
    return {
        "split_mode": str(document.get("split_mode", document.get("generation_mode", "")) or ""),
        "generation_path": str(document.get("generation_path", "") or ""),
        "layerability": str(document.get("layerability", "") or ""),
        "partial": bool(document.get("partial", False)),
        "warnings": warnings,
        "tradition": str(document.get("tradition", "") or ""),
    }


def _source_layers(artwork_dir: str) -> tuple[list[LayerResult], int, int, Path, dict]:
    artwork_root = Path(artwork_dir).expanduser().resolve()
    if not artwork_root.is_dir():
        raise OpenRasterError(f"VULCA artwork directory does not exist: {artwork_root}")
    artwork = load_artifact_v3(str(artwork_root))
    document_path = Path(artwork.manifest_path).resolve()
    try:
        document_path.relative_to(artwork_root)
    except ValueError as exc:
        raise OpenRasterError("Canonical VULCA document must be inside the artwork directory") from exc
    try:
        document_bytes = document_path.read_bytes()
        document = json.loads(document_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenRasterError(f"Cannot read canonical VULCA document: {exc}") from exc
    if not isinstance(document, dict):
        raise OpenRasterError("Canonical VULCA document must contain a JSON object")
    width, height = _canvas_from_document(document)
    layers = sorted(artwork.layers, key=lambda layer: layer.info.z_index)
    if not 1 <= len(layers) <= MAX_LAYERS:
        raise OpenRasterError(f"OpenRaster export requires 1-{MAX_LAYERS} layers")
    if width * height * len(layers) > MAX_TOTAL_LAYER_PIXELS:
        raise OpenRasterError("OpenRaster layer workload exceeds the decoded-pixel safety limit")
    ids = [_checked_identifier(layer.info.id) for layer in layers]
    if len(ids) != len(set(ids)):
        raise OpenRasterError("Layer ids must be unique before OpenRaster export")
    z_indices = [layer.info.z_index for layer in layers]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in z_indices):
        raise OpenRasterError("Layer z_index values must be integers")
    if len(z_indices) != len(set(z_indices)):
        raise OpenRasterError("Layer z_index values must be unique before OpenRaster export")
    for layer in layers:
        image_path = Path(layer.image_path).resolve()
        try:
            image_path.relative_to(artwork_root)
        except ValueError as exc:
            raise OpenRasterError(
                f"Layer {layer.info.id} image must stay inside the artwork directory"
            ) from exc
        if not image_path.is_file():
            raise OpenRasterError(f"Layer {layer.info.id} image does not exist: {image_path}")
        layer.image_path = str(image_path)
    return layers, width, height, document_path, {"raw": document_bytes, "data": document}


def _source_layer_record(layer: LayerResult, *, src: str, canvas: tuple[int, int]) -> tuple[dict, bytes]:
    info = layer.info
    _checked_text(info.name, field=f"layer {info.id} name", limit=1024)
    if info.blend_mode not in _BLEND_TO_ORA:
        raise OpenRasterError(f"Layer {info.id} uses unsupported blend mode {info.blend_mode!r}")
    if not isinstance(info.opacity, (int, float)) or isinstance(info.opacity, bool) or not math.isfinite(info.opacity):
        raise OpenRasterError(f"Layer {info.id} opacity must be a finite number")
    if not 0.0 <= float(info.opacity) <= 1.0:
        raise OpenRasterError(f"Layer {info.id} opacity must be between 0 and 1")
    if needs_transform(info):
        raise OpenRasterError(
            f"Layer {info.id} has a VULCA spatial transform; the first ORA Effect Pack only accepts full-canvas layers"
        )
    image_path = Path(layer.image_path)
    try:
        png_payload = image_path.read_bytes()
    except OSError as exc:
        raise OpenRasterError(f"Cannot read layer {info.id}: {exc}") from exc
    image = _load_png(png_payload, field=f"layer {info.id}", expected_size=canvas)
    record = {
        "id": info.id,
        "name": info.name,
        "src": src,
        "z_index": info.z_index,
        "visible": bool(info.visible),
        "opacity": float(info.opacity),
        "blend_mode": info.blend_mode,
        "rgba_sha256": _rgba_sha256(image),
        "png_sha256": _sha256_bytes(png_payload),
        "metadata": asdict(info),
        "scores": _safe_scores(layer.scores),
    }
    return record, png_payload


def export_openraster(artwork_dir: str, output_path: str) -> dict:
    """Export a canonical VULCA Artifact/manifest as a flat OpenRaster archive.

    The source artwork is never mutated. Layer PNGs must already be full-canvas
    and must not use VULCA spatial transforms. Stable ids are stored in a VULCA
    sidecar, an XML extension attribute, and a reversible layer-name marker so
    that editors which discard unknown extension files still preserve identity.
    """
    layers, width, height, document_path, document = _source_layers(artwork_dir)
    canvas = (width, height)
    records: list[dict] = []
    png_members: dict[str, bytes] = {}
    for position, layer in enumerate(layers):
        id_digest = hashlib.sha256(layer.info.id.encode("utf-8")).hexdigest()[:12]
        src = f"data/layer-{position:04d}-{id_digest}.png"
        record, png_payload = _source_layer_record(layer, src=src, canvas=canvas)
        records.append(record)
        png_members[src] = png_payload

    composite = blend_layers(layers, width=width, height=height)
    composite_payload = _png_bytes(composite)
    thumbnail = composite.copy()
    thumbnail.thumbnail((256, 256), Image.Resampling.LANCZOS)
    thumbnail_payload = _png_bytes(thumbnail)

    ET.register_namespace("vulca", VULCA_ORA_NS)
    image_root = ET.Element("image", {"version": OPENRASTER_VERSION, "w": str(width), "h": str(height)})
    stack = ET.SubElement(image_root, "stack")
    for record in reversed(records):  # OpenRaster lists the uppermost layer first.
        layer_element = ET.SubElement(
            stack,
            "layer",
            {
                "name": _marked_layer_name(record["name"], record["id"]),
                "src": record["src"],
                "x": "0",
                "y": "0",
                "opacity": format(record["opacity"], ".12g"),
                "visibility": "visible" if record["visible"] else "hidden",
                "composite-op": _BLEND_TO_ORA[record["blend_mode"]],
            },
        )
        layer_element.set(f"{{{VULCA_ORA_NS}}}id", record["id"])
    stack_payload = ET.tostring(image_root, encoding="utf-8", xml_declaration=True)

    sidecar = {
        "schema_version": 1,
        "kind": "vulca-openraster-roundtrip",
        "operation_version": OPENRASTER_OPERATION_VERSION,
        "created_at": _now(),
        "source_document": document_path.name,
        "source_document_sha256": _sha256_bytes(document["raw"]),
        "canvas": {"width": width, "height": height},
        "source_composite_rgba_sha256": _rgba_sha256(composite),
        "source_layer_order_bottom_to_top": [record["id"] for record in records],
        "document_fields": _document_fields(document["data"]),
        "provider": "not_applicable",
        "model": "not_applicable",
        "prompt": "not_applicable",
        "seed": "not_applicable",
        "cost": "not_applicable",
        "latency": "not_applicable",
        "layers": records,
    }
    sidecar_payload = json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".ora":
        raise OpenRasterError("OpenRaster output_path must end in .ora")
    if destination.exists() and destination.is_dir():
        raise OpenRasterError("OpenRaster output_path points to a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            mimetype_info = zipfile.ZipInfo("mimetype")
            mimetype_info.compress_type = zipfile.ZIP_STORED
            archive.writestr(mimetype_info, OPENRASTER_MIMETYPE)
            archive.writestr("stack.xml", stack_payload, compress_type=zipfile.ZIP_DEFLATED)
            for src, payload in png_members.items():
                archive.writestr(src, payload, compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr("mergedimage.png", composite_payload, compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr("Thumbnails/thumbnail.png", thumbnail_payload, compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr(OPENRASTER_SIDECAR, sidecar_payload, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return {
        "schema_version": 1,
        "operation": "openraster-export",
        "operation_version": OPENRASTER_OPERATION_VERSION,
        "export_path": str(destination),
        "ora_sha256": _sha256_file(destination),
        "source_document": str(document_path),
        "source_document_sha256": sidecar["source_document_sha256"],
        "canvas": sidecar["canvas"],
        "layer_count": len(records),
        "source_composite_rgba_sha256": sidecar["source_composite_rgba_sha256"],
        "provider": "not_applicable",
        "model": "not_applicable",
        "prompt": "not_applicable",
        "seed": "not_applicable",
        "cost": "not_applicable",
        "latency": "not_applicable",
        "layers": [
            {"id": record["id"], "rgba_sha256": record["rgba_sha256"], "png_sha256": record["png_sha256"]}
            for record in records
        ],
    }


def _validate_archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
        raise OpenRasterError("OpenRaster archive has an invalid number of entries")
    if infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
        raise OpenRasterError("OpenRaster mimetype must be the first uncompressed archive entry")
    by_name: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in infos:
        name = info.filename
        if name in by_name:
            raise OpenRasterError(f"OpenRaster archive contains duplicate entry {name!r}")
        if not name or "\x00" in name or "\\" in name or name.startswith("/"):
            raise OpenRasterError(f"Unsafe OpenRaster archive path {name!r}")
        stripped = name[:-1] if name.endswith("/") else name
        parts = stripped.split("/")
        path = PurePosixPath(stripped)
        if not stripped or any(part in {"", ".", ".."} for part in parts) or path.is_absolute() or ":" in parts[0]:
            raise OpenRasterError(f"Unsafe OpenRaster archive path {name!r}")
        if info.flag_bits & 0x1:
            raise OpenRasterError("Encrypted OpenRaster entries are not supported")
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise OpenRasterError("OpenRaster entries must use STORED or DEFLATED compression")
        if info.file_size > MAX_MEMBER_BYTES:
            raise OpenRasterError(f"OpenRaster entry {name!r} exceeds the per-file safety limit")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise OpenRasterError("OpenRaster archive exceeds the uncompressed safety limit")
        by_name[name] = info
    return by_name


def _read_member(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    name: str,
    *,
    limit: int = MAX_MEMBER_BYTES,
) -> bytes:
    info = members.get(name)
    if info is None or info.is_dir():
        raise OpenRasterError(f"Required OpenRaster entry is missing: {name}")
    if info.file_size > limit:
        raise OpenRasterError(f"OpenRaster entry {name!r} exceeds its safety limit")
    payload = archive.read(info)
    if len(payload) != info.file_size:
        raise OpenRasterError(f"OpenRaster entry {name!r} is truncated")
    return payload


def _parse_stack_xml(payload: bytes) -> tuple[int, int, list[dict]]:
    if len(payload) > MAX_XML_BYTES:
        raise OpenRasterError("stack.xml exceeds the XML safety limit")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise OpenRasterError("stack.xml must not contain DTD or entity declarations")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise OpenRasterError(f"stack.xml is invalid XML: {exc}") from exc
    if _local_name(root.tag) != "image":
        raise OpenRasterError("stack.xml root element must be image")
    try:
        width = int(root.get("w", ""))
        height = int(root.get("h", ""))
    except ValueError as exc:
        raise OpenRasterError("stack.xml canvas dimensions must be integers") from exc
    width, height = _checked_canvas(width, height)
    stacks = [child for child in list(root) if _local_name(child.tag) == "stack"]
    if len(stacks) != 1:
        raise OpenRasterError("The first ORA Effect Pack requires exactly one root stack")
    entries: list[dict] = []
    for child in list(stacks[0]):
        if _local_name(child.tag) != "layer":
            raise OpenRasterError("The first ORA Effect Pack supports flat layer stacks only")
        src = _checked_text(child.get("src"), field="OpenRaster layer src", limit=2048)
        if not src.startswith("data/"):
            raise OpenRasterError("OpenRaster layer src must point inside data/")
        try:
            x = int(child.get("x", "0"))
            y = int(child.get("y", "0"))
            opacity = float(child.get("opacity", "1"))
        except ValueError as exc:
            raise OpenRasterError("OpenRaster layer offset or opacity is invalid") from exc
        if x != 0 or y != 0:
            raise OpenRasterError("The first ORA Effect Pack requires full-canvas layers at x=0, y=0")
        if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
            raise OpenRasterError("OpenRaster layer opacity must be between 0 and 1")
        visibility = child.get("visibility", "visible")
        if visibility not in {"visible", "hidden"}:
            raise OpenRasterError(f"Unsupported OpenRaster visibility {visibility!r}")
        composite_op = child.get("composite-op", "svg:src-over")
        if composite_op not in _ORA_TO_BLEND:
            raise OpenRasterError(f"Unsupported OpenRaster composite-op {composite_op!r}")
        marked_name = _checked_text(child.get("name", ""), field="OpenRaster layer name", limit=2048)
        display_name, marker_id = _split_marked_layer_name(marked_name)
        extension_id = child.get(f"{{{VULCA_ORA_NS}}}id")
        if extension_id is not None:
            extension_id = _checked_identifier(extension_id, field="OpenRaster vulca:id")
        if marker_id and extension_id and marker_id != extension_id:
            raise OpenRasterError("OpenRaster layer id marker conflicts with vulca:id")
        entries.append(
            {
                "src": src,
                "name": display_name,
                "marker_id": marker_id,
                "extension_id": extension_id,
                "visible": visibility == "visible",
                "opacity": opacity,
                "blend_mode": _ORA_TO_BLEND[composite_op],
            }
        )
    if not 1 <= len(entries) <= MAX_LAYERS:
        raise OpenRasterError(f"OpenRaster import requires 1-{MAX_LAYERS} flat layers")
    if width * height * len(entries) > MAX_TOTAL_LAYER_PIXELS:
        raise OpenRasterError("OpenRaster layer workload exceeds the decoded-pixel safety limit")
    sources = [entry["src"] for entry in entries]
    if len(sources) != len(set(sources)):
        raise OpenRasterError("OpenRaster layer src values must be unique")
    return width, height, entries


def _parse_sidecar(payload: bytes, *, canvas: tuple[int, int]) -> dict:
    if len(payload) > MAX_SIDECAR_BYTES:
        raise OpenRasterError("VULCA OpenRaster sidecar exceeds the JSON safety limit")
    try:
        sidecar = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenRasterError(f"VULCA OpenRaster sidecar is invalid JSON: {exc}") from exc
    if not isinstance(sidecar, dict) or sidecar.get("kind") != "vulca-openraster-roundtrip":
        raise OpenRasterError("VULCA OpenRaster sidecar has an unsupported contract")
    if sidecar.get("schema_version") != 1:
        raise OpenRasterError("VULCA OpenRaster sidecar schema version is unsupported")
    if sidecar.get("operation_version") != OPENRASTER_OPERATION_VERSION:
        raise OpenRasterError("VULCA OpenRaster sidecar operation version is unsupported")
    sidecar_canvas = sidecar.get("canvas", {})
    if not isinstance(sidecar_canvas, dict) or _checked_canvas(
        sidecar_canvas.get("width"), sidecar_canvas.get("height")
    ) != canvas:
        raise OpenRasterError("VULCA sidecar canvas conflicts with stack.xml")
    layers = sidecar.get("layers")
    if not isinstance(layers, list) or not layers:
        raise OpenRasterError("VULCA sidecar layers must be a non-empty array")
    by_src: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    ids: set[str] = set()
    for item in layers:
        if not isinstance(item, dict):
            raise OpenRasterError("VULCA sidecar layer entries must be objects")
        layer_id = _checked_identifier(item.get("id"))
        src = _checked_text(item.get("src"), field=f"sidecar src for {layer_id}", limit=2048)
        if layer_id in ids or src in by_src:
            raise OpenRasterError("VULCA sidecar layer ids and src values must be unique")
        z_index = item.get("z_index")
        if not isinstance(z_index, int) or isinstance(z_index, bool):
            raise OpenRasterError(f"VULCA sidecar z_index for {layer_id} must be an integer")
        _checked_text(item.get("name", ""), field=f"sidecar name for {layer_id}", limit=1024)
        if not isinstance(item.get("visible"), bool):
            raise OpenRasterError(f"VULCA sidecar visibility for {layer_id} must be boolean")
        opacity = item.get("opacity")
        if (
            not isinstance(opacity, (int, float))
            or isinstance(opacity, bool)
            or not math.isfinite(opacity)
            or not 0.0 <= float(opacity) <= 1.0
        ):
            raise OpenRasterError(f"VULCA sidecar opacity for {layer_id} must be between 0 and 1")
        if item.get("blend_mode") not in _BLEND_TO_ORA:
            raise OpenRasterError(f"VULCA sidecar blend mode for {layer_id} is unsupported")
        rgba_hash = item.get("rgba_sha256")
        if not isinstance(rgba_hash, str) or re.fullmatch(r"[0-9a-f]{64}", rgba_hash) is None:
            raise OpenRasterError(f"VULCA sidecar pixel hash for {layer_id} is invalid")
        if not isinstance(item.get("metadata", {}), dict):
            raise OpenRasterError(f"VULCA sidecar metadata for {layer_id} must be an object")
        ids.add(layer_id)
        by_src[src] = item
        by_id[layer_id] = item
    source_order = sidecar.get("source_layer_order_bottom_to_top")
    if (
        not isinstance(source_order, list)
        or not all(isinstance(value, str) for value in source_order)
        or len(source_order) != len(ids)
        or set(source_order) != ids
    ):
        raise OpenRasterError("VULCA sidecar source layer order does not match its layers")
    for field in ("source_document_sha256", "source_composite_rgba_sha256"):
        value = sidecar.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise OpenRasterError(f"VULCA sidecar {field} is invalid")
    document_fields = sidecar.get("document_fields", {})
    if not isinstance(document_fields, dict):
        raise OpenRasterError("VULCA sidecar document_fields must be an object")
    document_warnings = document_fields.get("warnings", [])
    if not isinstance(document_warnings, list) or not all(isinstance(value, str) for value in document_warnings):
        raise OpenRasterError("VULCA sidecar document warnings must be an array of strings")
    sidecar["layers_by_src"] = by_src
    sidecar["layers_by_id"] = by_id
    return sidecar


def _safe_scores(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, score in value.items():
        if isinstance(key, str) and isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
            result[key] = float(score)
    return result


def _metadata_text(metadata: dict, key: str, *, default: str = "", limit: int = 32768) -> str:
    return _checked_text(metadata.get(key, default), field=f"sidecar metadata {key}", default=default, limit=limit)


def _layer_info_from_import(
    metadata: object,
    *,
    layer_id: str,
    name: str,
    z_index: int,
    visible: bool,
    opacity: float,
    blend_mode: str,
) -> LayerInfo:
    source = metadata if isinstance(metadata, dict) else {}
    dominant = source.get("dominant_colors", [])
    if not isinstance(dominant, list) or not all(isinstance(value, str) for value in dominant):
        dominant = []
    else:
        dominant = [_checked_text(value, field="sidecar dominant color", limit=128) for value in dominant[:256]]
    generation_round = source.get("generation_round", 0)
    if not isinstance(generation_round, int) or isinstance(generation_round, bool):
        generation_round = 0
    area_pct = source.get("area_pct", 0.0)
    if not isinstance(area_pct, (int, float)) or isinstance(area_pct, bool) or not math.isfinite(area_pct):
        area_pct = 0.0
    parent_layer_id = source.get("parent_layer_id")
    if parent_layer_id is not None:
        parent_layer_id = _checked_identifier(parent_layer_id, field="sidecar metadata parent_layer_id")
    bbox = source.get("bbox") if isinstance(source.get("bbox"), dict) else None
    content_bbox = source.get("content_bbox") if isinstance(source.get("content_bbox"), dict) else None
    return LayerInfo(
        name=_checked_text(name, field=f"layer {layer_id} name", limit=1024),
        description=_metadata_text(source, "description"),
        z_index=z_index,
        id=layer_id,
        content_type=_metadata_text(source, "content_type", default="background", limit=256),
        dominant_colors=dominant,
        regeneration_prompt=_metadata_text(source, "regeneration_prompt", limit=131072),
        visible=visible,
        blend_mode=blend_mode,
        bg_color=_metadata_text(source, "bg_color", default="white", limit=64),
        locked=bool(source.get("locked", False)) if isinstance(source.get("locked", False), bool) else False,
        bbox=bbox,
        x=0.0,
        y=0.0,
        width=100.0,
        height=100.0,
        rotation=0.0,
        content_bbox=content_bbox,
        tradition_role=_metadata_text(source, "tradition_role", limit=1024),
        opacity=opacity,
        status=_metadata_text(source, "status", limit=128),
        weakness=_metadata_text(source, "weakness", limit=32768),
        generation_round=generation_round,
        position=_metadata_text(source, "position", limit=4096),
        coverage=_metadata_text(source, "coverage", limit=4096),
        semantic_path=_metadata_text(source, "semantic_path", limit=4096),
        parent_layer_id=parent_layer_id,
        quality_status=_metadata_text(source, "quality_status", default="detected", limit=128),
        area_pct=float(area_pct),
    )


def import_openraster(input_path: str, output_dir: str) -> dict:
    """Import a flat ORA archive into a new canonical VULCA manifest directory.

    The destination must not exist. Import is staged beside the destination and
    promoted with one atomic rename only after the archive, pixels, ids, canvas,
    and metadata have been validated.
    """
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise OpenRasterError(f"OpenRaster input does not exist: {source}")
    destination = Path(output_dir).expanduser().resolve()
    if destination.exists():
        raise OpenRasterError(f"OpenRaster import destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ora_sha256 = _sha256_file(source)

    try:
        archive = zipfile.ZipFile(source, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise OpenRasterError(f"Cannot open OpenRaster archive: {exc}") from exc

    with archive:
        members = _validate_archive_members(archive)
        if _read_member(archive, members, "mimetype", limit=64) != OPENRASTER_MIMETYPE:
            raise OpenRasterError("OpenRaster mimetype content is invalid")
        width, height, top_to_bottom = _parse_stack_xml(
            _read_member(archive, members, "stack.xml", limit=MAX_XML_BYTES)
        )
        canvas = (width, height)
        merged = _load_png(
            _read_member(archive, members, "mergedimage.png"),
            field="mergedimage.png",
            expected_size=canvas,
        )
        thumbnail = _load_png(
            _read_member(archive, members, "Thumbnails/thumbnail.png"),
            field="Thumbnails/thumbnail.png",
        )
        if thumbnail.width > 256 or thumbnail.height > 256:
            raise OpenRasterError("OpenRaster thumbnail must not exceed 256x256")

        sidecar = None
        warnings: list[str] = []
        if OPENRASTER_SIDECAR in members:
            sidecar = _parse_sidecar(
                _read_member(archive, members, OPENRASTER_SIDECAR, limit=MAX_SIDECAR_BYTES),
                canvas=canvas,
            )
        else:
            warnings.append("VULCA sidecar was not preserved; semantic metadata is reduced to stable id markers")

        resolved_top_to_bottom: list[dict] = []
        for entry in top_to_bottom:
            expected = sidecar["layers_by_src"].get(entry["src"]) if sidecar else None
            candidate_ids = [value for value in (entry["marker_id"], entry["extension_id"]) if value]
            if len(set(candidate_ids)) > 1:
                raise OpenRasterError(f"Layer {entry['src']} has conflicting stable VULCA ids")
            if sidecar and expected is None and candidate_ids:
                expected = sidecar["layers_by_id"].get(candidate_ids[0])
                if expected is not None:
                    warnings.append(
                        f"Layer {candidate_ids[0]} changed its internal OpenRaster path; metadata matched by stable id"
                    )
            if expected is not None:
                candidate_ids.append(_checked_identifier(expected.get("id")))
            if not candidate_ids or len(set(candidate_ids)) != 1:
                raise OpenRasterError(f"Layer {entry['src']} does not preserve one stable VULCA id")
            entry["id"] = candidate_ids[0]
            entry["expected"] = expected
            resolved_top_to_bottom.append(entry)

        ids = [entry["id"] for entry in resolved_top_to_bottom]
        if len(ids) != len(set(ids)):
            raise OpenRasterError("Imported OpenRaster layer ids must be unique")
        if sidecar:
            expected_ids = {_checked_identifier(item.get("id")) for item in sidecar["layers"]}
            if set(ids) != expected_ids or len(ids) != len(sidecar["layers"]):
                raise OpenRasterError("OpenRaster layer count or stable ids drifted from the VULCA sidecar")

        bottom_to_top = list(reversed(resolved_top_to_bottom))
        if sidecar:
            z_slots = sorted(int(item.get("z_index")) for item in sidecar["layers"])
            if len(z_slots) != len(set(z_slots)):
                raise OpenRasterError("VULCA sidecar z_index values must be unique")
        else:
            z_slots = list(range(len(bottom_to_top)))

        stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.import-", dir=destination.parent))
        try:
            (stage / "layers").mkdir(parents=True, exist_ok=True)
            layer_results: list[LayerResult] = []
            layer_files: dict[str, str] = {}
            evidence_layers: list[dict] = []
            for position, (entry, z_index) in enumerate(zip(bottom_to_top, z_slots, strict=True)):
                payload = _read_member(archive, members, entry["src"])
                image = _load_png(payload, field=entry["src"], expected_size=canvas)
                layer_id = entry["id"]
                expected = entry["expected"]
                expected_hash = expected.get("rgba_sha256") if isinstance(expected, dict) else None
                actual_hash = _rgba_sha256(image)
                filename = f"layers/{position:04d}_{hashlib.sha256(layer_id.encode('utf-8')).hexdigest()[:12]}.png"
                image.save(stage / Path(filename), format="PNG", compress_level=6)
                metadata = expected.get("metadata") if isinstance(expected, dict) else {}
                info = _layer_info_from_import(
                    metadata,
                    layer_id=layer_id,
                    name=entry["name"],
                    z_index=z_index,
                    visible=entry["visible"],
                    opacity=entry["opacity"],
                    blend_mode=entry["blend_mode"],
                )
                scores = _safe_scores(expected.get("scores")) if isinstance(expected, dict) else {}
                result = LayerResult(info=info, image_path=str(stage / Path(filename)), scores=scores)
                layer_results.append(result)
                layer_files[layer_id] = filename
                metadata_changed = None
                if isinstance(expected, dict):
                    metadata_changed = any(
                        (
                            entry["name"] != expected.get("name"),
                            entry["visible"] != expected.get("visible", True),
                            not math.isclose(entry["opacity"], float(expected.get("opacity", 1.0)), abs_tol=1e-12),
                            entry["blend_mode"] != expected.get("blend_mode"),
                            z_index != expected.get("z_index"),
                        )
                    )
                evidence_layers.append(
                    {
                        "id": layer_id,
                        "file": filename,
                        "before_rgba_sha256": expected_hash,
                        "after_rgba_sha256": actual_hash,
                        "pixels_changed": None if expected_hash is None else actual_hash != expected_hash,
                        "metadata_changed": metadata_changed,
                    }
                )

            document_fields = sidecar.get("document_fields", {}) if sidecar else {}
            if not isinstance(document_fields, dict):
                document_fields = {}
            write_manifest(
                [layer.info for layer in layer_results],
                output_dir=str(stage),
                width=width,
                height=height,
                split_mode=str(document_fields.get("split_mode", "") or ""),
                generation_path=str(document_fields.get("generation_path", "") or ""),
                layerability=str(document_fields.get("layerability", "") or ""),
                partial=bool(document_fields.get("partial", False)),
                warnings=list(document_fields.get("warnings", [])) + warnings,
                layer_files=layer_files,
                tradition=str(document_fields.get("tradition", "") or ""),
            )
            imported_composite = blend_layers(layer_results, width=width, height=height)
            imported_composite.save(stage / "composite.png", format="PNG", compress_level=6)
            composite_hash = _rgba_sha256(imported_composite)
            expected_composite_hash = sidecar.get("source_composite_rgba_sha256") if sidecar else None
            archive_merged_hash = _rgba_sha256(merged)
            imported_order = [layer.info.id for layer in layer_results]
            expected_order = sidecar.get("source_layer_order_bottom_to_top") if sidecar else None
            order_changed = None if expected_order is None else imported_order != expected_order
            no_edit_roundtrip = bool(
                sidecar
                and not order_changed
                and all(item["pixels_changed"] is False for item in evidence_layers)
                and all(item["metadata_changed"] is False for item in evidence_layers)
                and composite_hash == expected_composite_hash
                and archive_merged_hash == expected_composite_hash
            )
            evidence = {
                "schema_version": 1,
                "operation": "openraster-import",
                "operation_version": OPENRASTER_OPERATION_VERSION,
                "created_at": _now(),
                "source_ora": source.name,
                "ora_sha256": ora_sha256,
                "source_document_sha256": sidecar.get("source_document_sha256") if sidecar else None,
                "canvas": {"width": width, "height": height},
                "provider": "not_applicable",
                "model": "not_applicable",
                "prompt": "not_applicable",
                "seed": "not_applicable",
                "cost": "not_applicable",
                "latency": "not_applicable",
                "warnings": warnings,
                "layers": evidence_layers,
                "verification": {
                    "status": "verified-no-edit" if no_edit_roundtrip else "edited-or-metadata-degraded",
                    "no_edit_roundtrip": no_edit_roundtrip,
                    "layer_order_changed": order_changed,
                    "source_composite_rgba_sha256": expected_composite_hash,
                    "imported_composite_rgba_sha256": composite_hash,
                    "archive_mergedimage_rgba_sha256": archive_merged_hash,
                    "archive_mergedimage_matches_imported": archive_merged_hash == composite_hash,
                },
            }
            (stage / OPENRASTER_EVIDENCE).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            stage.replace(destination)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    return {
        "schema_version": 1,
        "operation": "openraster-import",
        "operation_version": OPENRASTER_OPERATION_VERSION,
        "output_dir": str(destination),
        "manifest_path": str(destination / "manifest.json"),
        "composite_path": str(destination / "composite.png"),
        "evidence_path": str(destination / OPENRASTER_EVIDENCE),
        "ora_sha256": ora_sha256,
        "layer_count": len(bottom_to_top),
        "verification": evidence["verification"],
        "warnings": warnings,
    }


def export_psd(
    layers: list[LayerResult],
    *,
    width: int = 1024,
    height: int = 1024,
    output_path: str,
) -> str:
    """Export layers as PNG directory with full-canvas layers + manifest.

    V2: Layers are already full-canvas, so no bbox expansion needed.
    If output_path ends in .psd, creates a PNG directory alongside it.
    If output_path is a directory (or no suffix), uses it directly.
    """
    out = Path(output_path)
    if out.suffix == ".psd":
        png_dir = out.with_suffix("")
    else:
        png_dir = out
    png_dir.mkdir(parents=True, exist_ok=True)

    sorted_layers = sorted(layers, key=lambda l: l.info.z_index)
    for layer in sorted_layers:
        try:
            img = Image.open(layer.image_path).convert("RGBA")
            # V2: layers should already be full-canvas
            # V1 compat: if they're not, expand using bbox if available
            if img.size != (width, height):
                if layer.info.bbox:
                    full = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    x = int(width * layer.info.bbox["x"] / 100)
                    y = int(height * layer.info.bbox["y"] / 100)
                    full.paste(img, (x, y), img)
                    img = full
                else:
                    img = img.resize((width, height), Image.LANCZOS)
            dest = png_dir / f"{layer.info.z_index:02d}_{layer.info.name}.png"
            img.save(str(dest))
        except Exception:
            continue

    manifest = {
        "width": width,
        "height": height,
        "layers": [
            {
                "name": l.info.name,
                "description": l.info.description,
                "file": f"{l.info.z_index:02d}_{l.info.name}.png",
                "z_index": l.info.z_index,
                "blend_mode": l.info.blend_mode,
                "scores": l.scores,
            }
            for l in sorted_layers
        ],
    }
    manifest_path = png_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return str(out)


def export_with_alpha(
    artwork_dir: str,
    output_dir: str,
    method: str = "auto",
) -> list[str]:
    """Export layers with transparency based on content_type."""
    from vulca.layers.artifact import load_artifact_v3
    from vulca.layers.alpha import apply_alpha_to_layer

    artwork = load_artifact_v3(artwork_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    exported = []
    for lr in sorted(artwork.layers, key=lambda l: l.info.z_index):
        try:
            img = Image.open(lr.image_path)
            rgba = apply_alpha_to_layer(img, lr.info, method=method)
            dest = out / f"{lr.info.z_index:02d}_{lr.info.name}.png"
            rgba.save(str(dest))
            exported.append(str(dest))
        except Exception:
            continue
    return exported
