"""VULCA Layers — native layered artwork generation and editing (V2)."""
from vulca.layers.types import LayerInfo, LayerResult, LayeredArtwork
from vulca.layers.analyze import analyze_layers, parse_layer_response
from vulca.layers.split import split_extract, split_regenerate, split_vlm, crop_layer, chromakey_white, chromakey_black
from vulca.layers.palette_mask import split_palette, build_palette_mask_prompt, decode_palette_mask
from vulca.layers.composite import composite_layers
from vulca.layers.blend import blend_normal, blend_screen, blend_multiply, blend_overlay, blend_soft_light, blend_darken, blend_lighten, blend_color_dodge, blend_color_burn, blend_layers
from vulca.layers.export import OpenRasterError, export_openraster, export_psd, import_openraster
from vulca.layers.manifest import write_manifest as write_manifest_v2, load_manifest, MANIFEST_VERSION
from vulca.layers.artifact import write_artifact_v3, load_artifact_v3, ARTIFACT_VERSION
from vulca.layers.mask import build_color_mask, apply_mask_to_image
from vulca.layers.prompt import build_analyze_prompt, build_regeneration_prompt, parse_v2_response
from vulca.layers.redraw import redraw_layer, redraw_merged
from vulca.layers.regenerate import build_regenerate_prompt, regenerate_from_composite
from vulca.layers.ops import (
    add_layer, remove_layer, reorder_layer, toggle_visibility,
    lock_layer, merge_layers, duplicate_layer, transform_layer,
)
from vulca.layers.sam import SAM_AVAILABLE
from vulca.layers.sam3 import SAM3_AVAILABLE, sam3_split
from vulca.layers.vlm_mask import generate_vlm_mask, apply_vlm_mask, VLM_MASK_PROMPT
from vulca.layers.transform import apply_spatial_transform, compute_content_bbox, needs_transform
from vulca.layers.plan_prompt import build_plan_prompt, get_tradition_layer_order
from vulca.layers.alpha import ensure_alpha
from vulca.layers.reconstruction import (
    SourceLayeredGenerationResult,
    apply_owned_mask_to_source,
    asource_layered_generate,
    assert_image_edits_endpoint_allowed,
    evaluate_ownership_quality_gates,
    load_reconstruction_contracts,
    normalize_layer_ownership,
    should_use_local_redraw,
    source_layered_generate,
    write_reconstruction_summary,
)

# V1 compat re-exports
from vulca.layers.manifest import load_manifest as load_artwork

__all__ = [
    "LayerInfo", "LayerResult", "LayeredArtwork",
    "analyze_layers", "parse_layer_response",
    "split_extract", "split_regenerate", "split_vlm", "split_palette",
    "build_palette_mask_prompt", "decode_palette_mask",
    "crop_layer", "chromakey_white", "chromakey_black",
    "composite_layers",
    "blend_normal", "blend_screen", "blend_multiply",
    "blend_overlay", "blend_soft_light", "blend_darken", "blend_lighten",
    "blend_color_dodge", "blend_color_burn", "blend_layers",
    "export_psd", "export_openraster", "import_openraster", "OpenRasterError",
    "write_manifest_v2", "load_manifest", "MANIFEST_VERSION",
    "write_artifact_v3", "load_artifact_v3", "ARTIFACT_VERSION",
    "build_color_mask", "apply_mask_to_image",
    "build_analyze_prompt", "build_regeneration_prompt", "parse_v2_response",
    "redraw_layer", "redraw_merged",
    "build_regenerate_prompt", "regenerate_from_composite",
    "add_layer", "remove_layer", "reorder_layer", "toggle_visibility",
    "lock_layer", "merge_layers", "duplicate_layer", "transform_layer",
    "SAM_AVAILABLE",
    "SAM3_AVAILABLE", "sam3_split",
    "generate_vlm_mask", "apply_vlm_mask", "VLM_MASK_PROMPT",
    "load_artwork",
    "build_plan_prompt", "get_tradition_layer_order",
    "ensure_alpha",
    "apply_spatial_transform", "compute_content_bbox", "needs_transform",
    "SourceLayeredGenerationResult",
    "apply_owned_mask_to_source",
    "asource_layered_generate",
    "assert_image_edits_endpoint_allowed",
    "evaluate_ownership_quality_gates",
    "load_reconstruction_contracts",
    "normalize_layer_ownership",
    "should_use_local_redraw",
    "source_layered_generate",
    "write_reconstruction_summary",
]
