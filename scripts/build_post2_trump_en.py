"""Build English-language carousel Post #2 - Donald Trump 3-photo decomposition.

9 slides at 1080x1440 (3:4) for dev.to / Twitter / GitHub Discussion.

Narrative:
  01 cover - shooting photo hook "I let Claude decompose Trump"
  02 Butler 2024 original - full shooting photo
  03 shooting: orig vs Trump subject
  04 shooting multi-subject: Trump hero + 4 side tiles
  05 mugshot: orig vs subject
  06 mugshot face anatomy: 6-panel face-parts grid
  07 portrait: orig vs subject (Oval Office)
  08 how it works: Claude Code + Vulca attribution
  09 outro stats

English-only sibling of build_xhs_post2_trump.py. Cross-post helpers live
in xhs_common.py.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from xhs_common import (
    ACCENT, BG_DARK, H, W, WHITE,
    checker_bg, compose_photo, en_locale, fit_contain, fit_cover,
    make_anatomy_grid, make_compare_slide,
    render_how_slide, render_outro_slide,
)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "assets" / "social" / "post2-trump-en"
OUT.mkdir(parents=True, exist_ok=True)

LAYERS = REPO / "assets" / "showcase" / "layers_v2"
ORIGS = REPO / "assets" / "showcase" / "originals"

LOC = en_locale()
font = LOC.font

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
    orig = Image.open(ORIGS / "trump-shooting.jpg").convert("RGB")
    bg = fit_cover(orig, W, H, centering=(0.5, 0.35))
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    c = Image.alpha_composite(bg.convert("RGBA"), veil).convert("RGB")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 0, W, 440], fill=(0, 0, 0, 170))
    c = Image.alpha_composite(c.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(c)
    f_big = font(84, heavy=True)
    for i, line in enumerate(["I let Claude", "decompose Trump"]):
        bbox = d.textbbox((0, 0), line, font=f_big)
        tw = bbox[2] - bbox[0]
        y_off = 90 + i * 110
        color = WHITE if i == 0 else ACCENT
        d.text(((W - tw) // 2, y_off), line, fill=color, font=f_big)

    f_sub = font(34, heavy=False)
    sub = "Butler 2024 - one news photo, 6 subjects"
    sbbox = d.textbbox((0, 0), sub, font=f_sub)
    d.text(((W - (sbbox[2] - sbbox[0])) // 2, 340), sub, fill=WHITE, font=f_sub)

    f_small = font(30, heavy=True)
    bottom = "-> swipe for all"
    bbox2 = d.textbbox((0, 0), bottom, font=f_small)
    overlay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od2 = ImageDraw.Draw(overlay2)
    od2.rectangle([0, H - 140, W, H - 60], fill=(0, 0, 0, 180))
    c = Image.alpha_composite(c.convert("RGBA"), overlay2).convert("RGB")
    d = ImageDraw.Draw(c)
    d.text(((W - (bbox2[2] - bbox2[0])) // 2, H - 120), bottom,
           fill=ACCENT, font=f_small)
    c.save(OUT / "01-cover.png", quality=95)
    print("[ok] 01-cover.png")


def slide_02_shooting_orig():
    c = compose_photo(ORIGS / "trump-shooting.jpg")
    c = LOC.top_badge(c.convert("RGBA"),
                      "Butler 2024 - original",
                      "news photo / Evan Vucci").convert("RGB")
    c = LOC.bottom_caption(c.convert("RGBA"),
                           "One 387x258 news photo",
                           "6 independent subjects + 2 background elements").convert("RGB")
    c.save(OUT / "02-shooting-orig.png", quality=95)
    print("[ok] 02-shooting-orig.png")


def slide_03_shooting_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "trump-shooting.jpg",
        LAYERS / "trump-shooting" / "trump.png",
        "Subject extracted", "Butler 2024 / shooting",
        "Fist raised, isolated",
        "subject isolated from a chaotic scene",
    )
    c.save(OUT / "03-shooting-subject.png", quality=95)
    print("[ok] 03-shooting-subject.png")


def slide_04_shooting_multi():
    """Trump hero + 4 side tiles: 3 agents + flag."""
    SRC = LAYERS / "trump-shooting"
    c = Image.new("RGB", (W, H), BG_DARK)
    c_rgba = c.convert("RGBA")

    margin_top = 200
    margin_bottom = 220
    margin_x = 40
    gap = 20

    hero_w = W - 2 * margin_x
    hero_h = 500
    bot_y = margin_top + hero_h + gap
    bot_tile_w = (W - 2 * margin_x - 3 * gap) // 4
    bot_tile_h = H - margin_bottom - bot_y

    f_tile = font(26, heavy=True)
    f_tile_small = font(22, heavy=True)

    def draw_tile(panel_rgba, layer_path, label, highlight):
        panel_w_, panel_h_ = panel_rgba.size
        layer = Image.open(layer_path).convert("RGBA")
        bbox = layer.split()[-1].getbbox()
        if bbox is not None:
            layer = layer.crop(bbox)
        fit = fit_contain(layer, panel_w_ - 20, panel_h_ - 70)
        lx = (panel_w_ - fit.width) // 2
        ly = (panel_h_ - 60 - fit.height) // 2 + 10
        panel_rgba.paste(fit, (lx, ly), fit)
        pd = ImageDraw.Draw(panel_rgba)
        outline = ACCENT if highlight else (70, 70, 75)
        pd.rectangle([0, 0, panel_w_ - 1, panel_h_ - 1],
                     outline=outline, width=2)
        pd.rectangle([0, panel_h_ - 60, panel_w_, panel_h_],
                     fill=(10, 10, 12, 230))
        f_use = f_tile if panel_w_ > 300 else f_tile_small
        lbl_bbox = pd.textbbox((0, 0), label, font=f_use)
        lbl_x = (panel_w_ - (lbl_bbox[2] - lbl_bbox[0])) // 2
        pd.text((lbl_x, panel_h_ - 46), label, fill=WHITE, font=f_use)

    hero_panel = checker_bg((hero_w, hero_h)).convert("RGBA")
    draw_tile(hero_panel, SRC / "trump.png",
              "Trump - fist raised, blood on cheek", highlight=True)
    c_rgba.paste(hero_panel, (margin_x, margin_top))

    bottom_tiles = [
        ("agent_left.png",   "Agent - L"),
        ("agent_right.png",  "Agent - R"),
        ("agent_bottom.png", "Agent - B"),
        ("flag.png",         "US flag"),
    ]
    for i, (fname, label) in enumerate(bottom_tiles):
        panel = checker_bg((bot_tile_w, bot_tile_h)).convert("RGBA")
        draw_tile(panel, SRC / fname, label, highlight=False)
        tx = margin_x + i * (bot_tile_w + gap)
        c_rgba.paste(panel, (tx, bot_y))

    c = c_rgba.convert("RGB")
    c = LOC.top_badge(c.convert("RGBA"),
                      "One photo - 6 subjects",
                      "Trump + 3 agents + flag + sky").convert("RGB")
    c = LOC.bottom_caption(c.convert("RGBA"),
                           "Butler 2024 - chaotic scene auto-decomposed",
                           "sam_bbox hints separate overlapping figures").convert("RGB")
    c.save(OUT / "04-shooting-multi.png", quality=95)
    print("[ok] 04-shooting-multi.png")


def slide_05_mugshot_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "trump-mugshot.jpg",
        LAYERS / "trump-mugshot" / "trump.png",
        "Subject extracted", "Fulton County mugshot, 2023",
        "mugshot - 6 face layers",
        "same pipeline, different vibe",
    )
    c.save(OUT / "05-mugshot-subject.png", quality=95)
    print("[ok] 05-mugshot-subject.png")


def slide_06_mugshot_anatomy():
    parts = [
        ("trump__skin.png", "Skin"),
        ("trump__hair.png", "Hair"),
        ("trump__eyes.png", "Eyes"),
        ("trump__nose.png", "Nose"),
        ("trump__lips.png", "Lips"),
        ("trump__ears.png", "Ears"),
    ]
    make_anatomy_grid(
        LOC, OUT / "06-mugshot-anatomy.png",
        LAYERS / "trump-mugshot", parts, highlight_idx=4,
        top_title="Face parts - auto-decomposition",
        top_sub="SegFormer on the booking photo",
        bot_text="mugshot - 6 face layers",
        bot_sub="same SegFormer run, no retraining",
    )
    print("[ok] 06-mugshot-anatomy.png")


def slide_07_portrait_subject():
    c = make_compare_slide(
        LOC,
        ORIGS / "trump-portrait.jpg",
        LAYERS / "trump-portrait" / "trump.png",
        "Oval Office extracted", "portrait, 2025",
        "Third photo, same SDK",
        "no prompt tweaks between photos",
    )
    c.save(OUT / "07-portrait-subject.png", quality=95)
    print("[ok] 07-portrait-subject.png")


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
    path.write_text("""# English caption pack - Post #2 Trump

## Version A - Twitter thread hook (<=280 char)

I let Claude decompose Donald Trump's Butler 2024 photo - one 387x258 news frame, 6 independent subjects (Trump + 3 agents + flag + sky) plus a full face anatomy of the mugshot. Vulca ran YOLO+DINO+SAM+SegFormer. Zero manual masking. Thread below.

## Version B - dev.to blog intro (paragraph)

Second test of the agent-native split: the LLM is the brain, the SDK is the hands and eyes, and there is no model call inside the library itself. I handed Claude Code three Trump photos - the Butler 2024 shooting frame, the 2023 Fulton County mugshot, and a 2025 Oval Office portrait - and asked for a full decomposition. The hard one is Butler: overlapping agents, a clinging flag, a cramped 387x258 news crop. Claude read the photo, wrote a JSON plan with `sam_bbox` hints to separate the overlapping figures, and Vulca stitched YOLO + Grounding DINO + SAM + SegFormer into a hierarchical resolve with a residual "honesty" layer. Six subjects came out cleanly. The manifest went back to the agent for a quality check before anything was surfaced. Three photos, one pipeline, 485 layers across the wider 47-image showcase, zero manual masking. Source: https://github.com/vulca-org/vulca-visual-control-sdk

## Version C - Show HN title + TLDR

Title: Show HN: I gave Claude Code an image-decomposition SDK and asked it to post to Xiaohongshu

TLDR para 1: Vulca is a small Python SDK that turns an image plus a JSON plan into a stack of PNG layers - subject, individual objects, a per-face-part breakdown, and a residual layer so nothing is hidden. It stitches YOLO, Grounding DINO, SAM and SegFormer behind a single `decompose()` call. No LLM lives inside the SDK.

TLDR para 2: The thesis is agent-native: Claude Code is the brain (reads pixels, writes plans, validates manifests), Vulca is the hands and eyes (runs the pipeline, returns structured evidence). The Butler 2024 Trump frame is the stress test - one small chaotic news photo, six overlapping subjects, fully automated. Repo + full showcase linked in comments.
""", encoding="utf-8")
    print("[ok] caption.md")


def write_hashtags_txt():
    path = OUT / "hashtags.txt"
    path.write_text("""# English hashtag bank - Post #2 Trump - pick 8-12 per surface

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
#Trump
#Butler2024
""", encoding="utf-8")
    print("[ok] hashtags.txt")


def main():
    slide_01_cover()
    slide_02_shooting_orig()
    slide_03_shooting_subject()
    slide_04_shooting_multi()
    slide_05_mugshot_subject()
    slide_06_mugshot_anatomy()
    slide_07_portrait_subject()
    slide_08_how()
    slide_09_outro()
    write_caption_md()
    write_hashtags_txt()
    print(f"\n[ok] 9 slides + caption + hashtags -> {OUT}")


if __name__ == "__main__":
    main()
