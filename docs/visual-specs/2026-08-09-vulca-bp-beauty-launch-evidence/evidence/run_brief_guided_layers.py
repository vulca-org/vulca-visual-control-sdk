"""Materialize an evidence-bounded VULCA layer package for the BP demo.

The automatic orchestrated pipeline is unavailable locally because its SAM
checkpoint is missing.  This script therefore turns a human-confirmed target
region into VULCA RGBA layers and a V3 manifest.  It does not claim automatic
semantic detection.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from vulca.layers.manifest import write_manifest
from vulca.layers.mask import apply_mask_to_image
from vulca.layers.types import LayerInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iters" / "1338" / "candidate_b.png"
OUTPUT = ROOT / "evidence" / "manual_layers"


def _soft_mask(size: tuple[int, int], polygons: list[list[tuple[int, int]]]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for polygon in polygons:
        draw.polygon(polygon, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(radius=2.2))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGB")
    width, height = source.size
    if (width, height) != (1672, 941):
        raise RuntimeError(f"Unexpected source dimensions: {width}x{height}")

    # Human-confirmed visible pixels of the redundant back-centre package.
    # The right edge follows the occluding adopted package from y=270 down.
    target_mask = _soft_mask(
        source.size,
        [[
            (1190, 137), (1204, 119), (1248, 113), (1297, 117),
            (1328, 129), (1338, 143), (1335, 269), (1297, 273),
            (1298, 724), (1284, 738), (1224, 739), (1195, 727),
            (1193, 538), (1190, 523),
        ]],
    )

    # Protected product pixels: the adopted open lipstick and right package.
    protected_mask = _soft_mask(
        source.size,
        [
            [
                (1014, 317), (1022, 174), (1041, 142), (1070, 132),
                (1104, 145), (1114, 177), (1114, 315), (1130, 329),
                (1135, 783), (1117, 806), (1011, 806), (994, 784),
                (996, 333),
            ],
            [
                (1296, 294), (1316, 276), (1369, 270), (1421, 278),
                (1446, 295), (1452, 311), (1451, 795), (1433, 817),
                (1320, 817), (1298, 797),
            ],
        ],
    )

    occupied = ImageChops.lighter(target_mask, protected_mask)
    environment_mask = ImageChops.invert(occupied)

    target_mask.save(OUTPUT / "target_mask.png")
    protected_mask.save(OUTPUT / "protected_mask.png")
    environment_mask.save(OUTPUT / "environment_mask.png")

    apply_mask_to_image(source, environment_mask).save(OUTPUT / "environment.png")
    apply_mask_to_image(source, protected_mask).save(OUTPUT / "protected_product.png")
    apply_mask_to_image(source, target_mask).save(OUTPUT / "target_redundant_package.png")

    target_area = 100.0 * sum(target_mask.histogram()[128:]) / (width * height)
    protected_area = 100.0 * sum(protected_mask.histogram()[128:]) / (width * height)
    layers = [
        LayerInfo(
            id="layer_environment",
            name="environment",
            description="Warm ivory studio environment outside the confirmed product regions",
            z_index=0,
            content_type="background",
            semantic_path="background",
            locked=True,
            quality_status="manual_confirmed",
            area_pct=round(100.0 - target_area - protected_area, 2),
        ),
        LayerInfo(
            id="layer_protected_product",
            name="protected_product",
            description="Adopted open lipstick and right closed package; preserve during correction",
            z_index=1,
            content_type="subject",
            semantic_path="subject.protected_product",
            locked=True,
            quality_status="manual_confirmed",
            area_pct=round(protected_area, 2),
            content_bbox={"x": 994, "y": 132, "w": 458, "h": 686},
        ),
        LayerInfo(
            id="layer_target_redundant_package",
            name="target_redundant_package",
            description="Human-confirmed redundant back-centre package selected for removal",
            z_index=2,
            content_type="subject",
            semantic_path="subject.target_redundant_package",
            locked=False,
            quality_status="manual_confirmed",
            area_pct=round(target_area, 2),
            content_bbox={"x": 1190, "y": 113, "w": 148, "h": 627},
            regeneration_prompt="Remove only the redundant back-centre closed package and preserve all locked layers.",
        ),
    ]

    manifest_path = write_manifest(
        layers,
        output_dir=str(OUTPUT),
        width=width,
        height=height,
        source_image=str(SOURCE.relative_to(ROOT)),
        split_mode="brief_guided_manual_mask",
        layerability="partial_manual",
        partial=True,
        warnings=[
            "Automatic orchestrated segmentation stopped because /tmp/sam_vit_l.pth is unavailable.",
            "Target and protected regions were human-confirmed from the enterprise brief; they are not detector outputs.",
        ],
    )
    print(
        {
            "manifest": manifest_path,
            "target_area_pct": round(target_area, 2),
            "protected_area_pct": round(protected_area, 2),
            "split_mode": "brief_guided_manual_mask",
        }
    )


if __name__ == "__main__":
    main()
