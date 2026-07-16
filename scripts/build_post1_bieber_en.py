"""Build English-language carousel Post #1 — Justin Bieber Coachella 2026.

9 slides at 1080x1440 (3:4) for dev.to / Twitter / GitHub Discussion.

Narrative:
  01 cover
  02 stayed: orig vs subject
  03 stayed: orig vs teal stage
  04 baby: orig vs frontal subject
  05 face anatomy: 6-panel grid
  06 speed-demon: orig vs subject
  07 speed-demon: orig vs red stage
  08 how it works: Claude Code + Vulca attribution
  09 outro stats

English-only sibling of build_xhs_post1_bieber.py. Cross-post helpers live
in xhs_common.py.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from xhs_common import (
    ACCENT, BG_DARK, H, W, WHITE,
    en_locale, fit_cover, make_anatomy_grid, make_compare_slide,
    render_how_slide, render_outro_slide,
)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "assets" / "social" / "post1-bieber-en"
OUT.mkdir(parents=True, exist_ok=True)

LAYERS = REPO / "assets" / "showcase" / "layers_v2"
ORIGS = REPO / "assets" / "showcase" / "originals"

LOC = en_locale()
font = LOC.font

# Shared EN style for how + outro slides (typography differs from CN).
HOW_STYLE = {
    "title_y": 140,
    "brand_size": 64,
    "step_size": 34,
    "step_sub_size": 22,
    "step_y0": 500,
    "step_sub_gap": 52,
    "tag_size": 42,
}
OUTRO_STYLE = {
    "num_y": 240,
    "label_size": 40,
    "label_y": 480,
    "hr_size": 52,
    "hr_y": 670,
    "credit_size": 26,
    "credit_y0": 790,
    "credit_gap": 42,
    "cta_size": 36,
}


def slide_01_cover():
    c = Image.new("RGB", (W, H), BG_DARK)
    orig = Image.open(ORIGS / "bieber-coachella-stayed.png").convert("RGB")
    bg = fit_cover(orig, W, H, centering=(0.5, 0.5))
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    c = Image.alpha_composite(bg.convert("RGBA"), veil).convert("RGB")

    d = ImageDraw.Draw(c)
    f_big = font(84, heavy=True)
    for i, line in enumerate(["I let Claude", "decompose Bieber"]):
        bbox = d.textbbox((0, 0), line, font=f_big)
        tw = bbox[2] - bbox[0]
        y_off = 140 + i * 110
        color = WHITE if i == 0 else ACCENT
        d.text(((W - tw) // 2, y_off), line, fill=color, font=f_big)

    f_sub = font(34, heavy=False)
    sub = "Coachella 2026 - fully automated layer decomposition"
    sbbox = d.textbbox((0, 0), sub, font=f_sub)
    d.text(((W - (sbbox[2] - sbbox[0])) // 2, 390), sub, fill=WHITE, font=f_sub)

    f_small = font(30, heavy=True)
    bottom = "-> swipe for all"
    bbox2 = d.textbbox((0, 0), bottom, font=f_small)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, H - 140, W, H - 60], fill=(0, 0, 0, 180))
    c = Image.alpha_composite(c.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(c)
    d.text(((W - (bbox2[2] - bbox2[0])) // 2, H - 120), bottom,
           fill=ACCENT, font=f_small)
    c.save(OUT / "01-cover.png", quality=95)
    print("[ok] 01-cover.png")


def slide_02_stayed_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "bieber-coachella-stayed.png",
        LAYERS / "bieber-coachella-stayed" / "bieber.png",
        "Subject extracted", "pose 1 / pink",
        "AI isolates the subject", "background removed automatically",
    )
    c.save(OUT / "02-stayed-subject.png", quality=95)
    print("[ok] 02-stayed-subject.png")


def slide_03_stayed_bg():
    c = make_compare_slide(
        LOC,
        ORIGS / "bieber-coachella-stayed.png",
        LAYERS / "bieber-coachella-stayed" / "teal_stage.png",
        "Stage background", "pose 1 / pink",
        "Stage lighting isolated", "teal wash extracted as its own layer",
        layer_use_photo_bg=True,
    )
    c.save(OUT / "03-stayed-bg.png", quality=95)
    print("[ok] 03-stayed-bg.png")


def slide_04_baby_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "bieber-coachella-baby.png",
        LAYERS / "bieber-coachella-baby" / "bieber.png",
        "Frontal pose - subject", "pose 2 / baby",
        "Frontal face, same pipeline", "no prompt tweaks between poses",
    )
    c.save(OUT / "04-baby-subject.png", quality=95)
    print("[ok] 04-baby-subject.png")


def slide_05_face_anatomy():
    """6-panel grid: face-part decomposition from face-only source."""
    parts = [
        ("bieber__skin.png",     "Skin"),
        ("bieber__hair.png",     "Hair"),
        ("bieber__eyebrows.png", "Eyebrows"),
        ("bieber__nose.png",     "Nose"),
        ("bieber__ears.png",     "Ears"),
        ("bieber.png",           "All parts"),
    ]
    make_anatomy_grid(
        LOC, OUT / "05-face-anatomy.png",
        LAYERS / "bieber-baby-faceonly", parts, highlight_idx=len(parts) - 1,
        top_title="Face parts - auto-decomposition",
        top_sub="SegFormer on one face-only crop",
        bot_text="portrait - 12 face layers",
        bot_sub="zero manual annotation",
    )
    print("[ok] 05-face-anatomy.png")


def slide_06_sd_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "bieber-coachella-speed-demon.png",
        LAYERS / "bieber-coachella-speed-demon" / "bieber.png",
        "Subject extracted", "pose 3 / speed demon",
        "Same pipeline - different poses",
        "same SDK across all 3 poses",
    )
    c.save(OUT / "06-sd-subject.png", quality=95)
    print("[ok] 06-sd-subject.png")


def slide_07_sd_bg():
    c = make_compare_slide(
        LOC,
        ORIGS / "bieber-coachella-speed-demon.png",
        LAYERS / "bieber-coachella-speed-demon" / "red_stage.png",
        "Red stage background", "pose 3 / speed demon",
        "Red-lit stage isolated", "same decomposition plan, different palette",
        layer_use_photo_bg=True,
    )
    c.save(OUT / "07-sd-bg.png", quality=95)
    print("[ok] 07-sd-bg.png")


def slide_08_how():
    render_how_slide(OUT / "08-how.png", LOC, {
        "title": "How it works",
        "brand": "Claude Code  +  Vulca",
        "steps": [
            ("(1) Claude looks at the photo",
             "agent reads pixels via vision"),
            ("(2) Claude writes a JSON plan",
             "subject targets + face-parts flags"),
            ("(3) Vulca SDK runs YOLO+DINO+SAM+SegFormer",
             "hierarchical resolve + residual layer"),
            ("(4) Agent checks manifest + quality flags",
             "validates coverage, iterates if needed"),
        ],
        "tag": "Zero manual masking",
        **HOW_STYLE,
    })
    print("[ok] 08-how.png")


def slide_09_outro():
    render_outro_slide(OUT / "09-outro.png", LOC, {
        "layers_label": "layers",
        "hr_main": "47 images - fully automated",
        "credit_lines": [
            "Claude Code directs - Vulca SDK executes",
            "YOLO + DINO + SAM + SegFormer",
            "hierarchical resolve - residual honesty",
        ],
        "cta": "Want more?  Tell me in the comments",
        **OUTRO_STYLE,
    })
    print("[ok] 09-outro.png")


def write_caption_md():
    path = OUT / "caption.md"
    path.write_text("""# English caption pack - Post #1 Bieber

## Version A - Twitter thread hook (<=280 char)

I let Claude decompose Justin Bieber's Coachella 2026 photos - 9 slides showing the full layer breakdown + face anatomy. Claude reads -> writes JSON plan -> Vulca runs YOLO+DINO+SAM+SegFormer -> agent checks flags. Zero manual masking. Thread below.

## Version B - dev.to blog intro (paragraph)

I've been experimenting with an agent-native split for image editing: the LLM is the brain, the SDK is the hands and eyes, and there is no model call inside the library itself. To stress-test it, I pointed Claude Code at three Bieber Coachella 2026 frames and asked for a full layer decomposition - subject, stage background, and face parts. Claude read each photo, wrote a small JSON plan describing the targets, and handed it to the Vulca SDK, which stitched YOLO + Grounding DINO + SAM + SegFormer into a hierarchical resolve with a residual "honesty" layer. The manifest came back to the agent for a quality check before anything was shown to a human. Three poses, one pipeline, 485 layers across the full 47-image showcase, zero manual masking. Source: https://github.com/vulca-org/vulca-visual-control-sdk

## Version C - Show HN title + TLDR

Title: Show HN: I gave Claude Code an image-decomposition SDK and asked it to post to Xiaohongshu

TLDR para 1: Vulca is a small Python SDK that turns an image plus a JSON plan into a stack of PNG layers - subject, individual objects, a per-face-part breakdown, and a residual layer so nothing is hidden. It stitches YOLO, Grounding DINO, SAM and SegFormer behind a single `decompose()` call. No LLM lives inside the SDK.

TLDR para 2: The thesis is agent-native: Claude Code is the brain (reads pixels, writes plans, validates manifests), Vulca is the hands and eyes (runs the pipeline, returns structured evidence). This post is the evidence - nine slides of a fully automated Coachella 2026 Bieber decomposition where the only human step was saying "go". Repo + full showcase linked in comments.
""", encoding="utf-8")
    print("[ok] caption.md")


def write_hashtags_txt():
    path = OUT / "hashtags.txt"
    path.write_text("""# English hashtag bank - Post #1 Bieber - pick 8-12 per surface

## Flagship (broad reach)
#AI
#MachineLearning
#ComputerVision

## Tech stack
#SAM
#SegFormer
#YOLO
#ClaudeCode
#Anthropic

## Genre / community
#OpenSource
#Python
#ImageProcessing
#IndieHackers

## Topical
#JustinBieber
#Coachella2026
""", encoding="utf-8")
    print("[ok] hashtags.txt")


def main():
    slide_01_cover()
    slide_02_stayed_subject()
    slide_03_stayed_bg()
    slide_04_baby_subject()
    slide_05_face_anatomy()
    slide_06_sd_subject()
    slide_07_sd_bg()
    slide_08_how()
    slide_09_outro()
    write_caption_md()
    write_hashtags_txt()
    print(f"\n[ok] 9 slides + caption + hashtags -> {OUT}")


if __name__ == "__main__":
    main()
