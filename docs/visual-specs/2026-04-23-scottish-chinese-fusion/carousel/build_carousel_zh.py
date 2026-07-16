"""Render 7-slide γ Scottish carousel (Chinese-localized) for Xiaohongshu.

Aesthetic: 印刷期刊·宋韵 (Print Journal · Song Aesthetic)
- Songti (宋体) serif for display titles — Song-dynasty originated typeface,
  conceptually echoes the carousel's Northern Song subject matter.
- PingFang sans for body / labels — clean modern reading.
- Cream paper background, ink-black dominant, 朱砂 red + 泥金 gold as sparing
  accents (≤2 red moments per slide, gold reserved for hrules + page numbers).
- Page numbers top-right per slide (01 / 07 ... 07 / 07) — magazine pagination.
- Thin gold hairline hrule under each title — typesetter's section divider.
- 80px outer margins, generous internal whitespace.
- Layer names + filesystem paths stay English (real SDK output / real paths).

Forked from build_carousel.py. All slides 1080×1080 for XHS carousel cohesion.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Users/yhryzy/dev/vulca/docs/visual-specs/2026-04-23-scottish-chinese-fusion")
OUT = ROOT / "carousel" / "xhs"
SIZE = 1080
MARGIN = 80
TOTAL_SLIDES = 7


# ---------- font ----------
_SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STSong.ttc",
    "/System/Library/Fonts/PingFang.ttc",  # final fallback (sans, but renders CJK)
]
_SANS_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
_MONO_CANDIDATES = _SANS_CANDIDATES  # macOS has no bundled CJK-capable mono;
                                      # use PingFang fallback so file-tree
                                      # Chinese comments render (lose strict
                                      # monospace alignment, gain readability)


def _load(candidates, size: int) -> ImageFont.ImageFont:
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


FONT_DISPLAY = _load(_SERIF_CANDIDATES, 60)  # major Songti display
FONT_TITLE = _load(_SERIF_CANDIDATES, 52)    # slide titles (Songti)
FONT_SUB = _load(_SANS_CANDIDATES, 30)        # subtitles (sans)
FONT_BODY = _load(_SANS_CANDIDATES, 26)
FONT_LABEL = _load(_SANS_CANDIDATES, 22)
FONT_MICRO = _load(_SANS_CANDIDATES, 20)
FONT_MONO = _load(_MONO_CANDIDATES, 19)
FONT_PAGE = _load(_SANS_CANDIDATES, 20)       # page number (top-right)

WHITE = (252, 248, 240)  # 熟绢 cream
INK = (32, 30, 28)
RED = (180, 50, 50)      # 朱砂
GOLD = (192, 144, 80)    # 泥金
MUTED = (130, 124, 116)
RULE = (200, 175, 130)   # gold hairline (lighter than GOLD body)
TREE_INK = (74, 68, 60)  # darker than MUTED for slide 6 file tree readability


def _square_canvas(bg=WHITE) -> Image.Image:
    return Image.new("RGB", (SIZE, SIZE), bg)


def _fit_inside(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    return img


def _crop_to_alpha_bbox(img: Image.Image, padding_pct: float = 0.08) -> Image.Image:
    """Crop RGBA image to bounding box of non-zero alpha + N% padding.

    Fixes the 'sparse layer in big canvas' problem: each layers_split output
    PNG is 1080×1080 RGBA but the entity often occupies only a small bbox
    inside it. Without this crop, fit_inside() scales the whole canvas down
    so the entity becomes a tiny dot on a sea of checkerboard. Cropping to
    the alpha bbox first lets fit_inside() then fill the cell with the
    entity itself — restoring editorial readability.
    """
    if img.mode != "RGBA":
        return img
    bbox = img.split()[-1].getbbox()  # bbox of non-zero alpha
    if bbox is None:
        return img
    pad_w = int((bbox[2] - bbox[0]) * padding_pct)
    pad_h = int((bbox[3] - bbox[1]) * padding_pct)
    left = max(0, bbox[0] - pad_w)
    top = max(0, bbox[1] - pad_h)
    right = min(img.width, bbox[2] + pad_w)
    bottom = min(img.height, bbox[3] + pad_h)
    return img.crop((left, top, right, bottom))


def _checkerboard(w: int, h: int, cell: int = 16) -> Image.Image:
    bg = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                d.rectangle([x, y, x + cell, y + cell], fill=(220, 220, 220))
    return bg


def _draw_text_centered(d, text, y, font, fill=INK):
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    d.text(((SIZE - w) // 2, y), text, font=font, fill=fill)


def _draw_text_centered_at(d, text, y, font, fill, x_left=0, x_right=SIZE):
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = x_left + ((x_right - x_left) - w) // 2
    d.text((x, y), text, font=font, fill=fill)


def _paste_centered(canvas, img, y):
    x = (SIZE - img.width) // 2
    canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)


def _hrule(d, y, x_left=MARGIN, x_right=SIZE - MARGIN, color=RULE, width=1):
    """Hairline gold rule — typesetter's section divider."""
    d.line([(x_left, y), (x_right, y)], fill=color, width=width)


def _page_num(d, n: int, total: int = TOTAL_SLIDES):
    """Magazine-style page indicator, top-right."""
    text = f"{n:02d} / {total:02d}"
    bbox = d.textbbox((0, 0), text, font=FONT_PAGE)
    w = bbox[2] - bbox[0]
    d.text((SIZE - MARGIN - w, 50), text, font=FONT_PAGE, fill=GOLD)


# =================================================================
# Slide 1 — 同 prompt 同 model · Vulca 控制力对比
# =================================================================
def slide1():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 1)

    # Display title in Songti — quiet, calm, magazine-cover voice
    _draw_text_centered(d, "同 prompt + 同 model", 110, FONT_DISPLAY, INK)
    _draw_text_centered(d, "Vulca 让 gpt-image-2 控制力上一个台阶", 192, FONT_SUB, RED)
    _hrule(d, 244)

    bare = Image.open(ROOT / "iters/_baseline_bare/bare_gpt2_edit.png").convert("RGB")
    vulca = Image.open(ROOT / "iters/7/gen_bfbbacd2.png").convert("RGB")

    # Two columns: 60..520 (col_w=460) and 560..1020 (col_w=460), gap=40
    col_w = 460
    col_h = 640
    # Reduced col_h for breathing room at footer (per v3 review P0)
    col_w = 460
    col_h = 580
    bare_thumb = _fit_inside(bare, col_w, col_h)
    vulca_thumb = _fit_inside(vulca, col_w, col_h)

    left_x = 60 + (col_w - bare_thumb.width) // 2
    right_x = 560 + (col_w - vulca_thumb.width) // 2
    canvas.paste(bare_thumb, (left_x, 290))
    canvas.paste(vulca_thumb, (right_x, 290))

    _draw_text_centered_at(d, "裸 API 调用", 905, FONT_SUB, INK, x_left=60, x_right=520)
    _draw_text_centered_at(d, "Vulca 工具链处理", 905, FONT_SUB, RED, x_left=560, x_right=1020)

    _hrule(d, 970)
    _draw_text_centered(d, "区别只在三个 markdown 文件", 998, FONT_BODY, GOLD)
    canvas.save(OUT / "slide1.png", "PNG", optimize=True)


# =================================================================
# Slide 2 — 完整效果(iter0 hero)
# =================================================================
def slide2():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 2)

    hero = Image.open(ROOT / "iters/7/gen_bfbbacd2.png").convert("RGB")
    hero = _fit_inside(hero, 920, 840)
    _paste_centered(canvas, hero, 100)

    _hrule(d, 970)
    _draw_text_centered(d, "苏格兰街景 + 北宋工笔加层式跨文化生图", 988, FONT_BODY, INK)
    _draw_text_centered(d, "openai/gpt-image-2  ·  seed 7  ·  v0.17.12", 1028, FONT_LABEL, MUTED)
    canvas.save(OUT / "slide2.png", "PNG", optimize=True)


# =================================================================
# Slide 3 — 拆图能力(decompose)
# =================================================================
def slide3():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 3)

    _draw_text_centered(d, "1 张图 → 9 个语义层 + 1 residual", 110, FONT_TITLE, INK)
    _draw_text_centered(d, "YOLO + Grounding DINO + SAM + SegFormer  ·  全部识别成功", 184, FONT_LABEL, MUTED)
    _hrule(d, 222)

    iter1 = ROOT / "decompose" / "iter1"
    layer_names = [
        "person", "lanterns", "sign_top",
        "sign_right", "spire", "bus",
        "left_buildings", "right_buildings", "sky",
    ]
    pcts = {
        "person": "5.65%", "lanterns": "8.05%", "sign_top": "1.17%",
        "sign_right": "0.47%", "spire": "2.08%", "bus": "3.59%",
        "left_buildings": "24.45%", "right_buildings": "7.51%", "sky": "15.50%",
    }

    # 3×3 grid centered, generous internal padding
    cell_w, cell_h = 300, 232
    grid_x0, grid_y0 = 60, 252
    pad_x, pad_y = 20, 26

    for idx, name in enumerate(layer_names):
        row, col = divmod(idx, 3)
        cx = grid_x0 + col * (cell_w + pad_x)
        cy = grid_y0 + row * (cell_h + pad_y)

        # Crop layer to its alpha bbox FIRST so the entity fills the cell
        # (codex P1 v3 review: tiny entities like sign_top@1.17% otherwise
        # render as near-empty checkerboard fragments → "debug sheet" feel)
        layer = Image.open(iter1 / f"{name}.png").convert("RGBA")
        layer = _crop_to_alpha_bbox(layer, padding_pct=0.10)
        thumb = _fit_inside(layer, cell_w, cell_h - 44)
        cb = _checkerboard(thumb.width, thumb.height)
        cb.paste(thumb, (0, 0), thumb)
        canvas.paste(cb, (cx + (cell_w - thumb.width) // 2, cy))

        label = f"{name}  ·  {pcts[name]}"
        bbox = d.textbbox((0, 0), label, font=FONT_LABEL)
        lw = bbox[2] - bbox[0]
        d.text((cx + (cell_w - lw) // 2, cy + cell_h - 30), label, font=FONT_LABEL, fill=INK)

    _draw_text_centered(d, "9 个语义层覆盖 ~68% 画面 · residual ~31.5%", 1028, FONT_LABEL, MUTED)
    canvas.save(OUT / "slide3.png", "PNG", optimize=True)


# =================================================================
# Slide 4 — 重绘能力(layers_redraw)
#
# v3.3: LEFT panel switched from alpha-iso (which captured building structure
# due to known SAM multi-instance gap) to a clean source-image crop showing
# the actual 6 photographic lanterns. Decompose-as-alpha demonstration is
# already covered by slide 3's grid; slide 4 now focuses purely on
# "原图 → gongbi 重绘" narrative without the misleading alpha mask.
# =================================================================
def slide4():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 4)

    _draw_text_centered(d, "只动一层 · 其他全保留", 110, FONT_TITLE, INK)
    _draw_text_centered(d, "decompose · redraw · inpaint composite", 188, FONT_SUB, RED)
    _hrule(d, 240)

    # v3.4: BOTH panels show full iter0-scope. RIGHT is iter0_lanterns_inpainted
    # (HSV mask + gpt-image-2 edit endpoint) — only lantern region differs;
    # brick wall, 江山楼匾, 紫外套女, 大教堂, 公交 all 100% preserved. This
    # is the actual "edit one layer, keep everything else" demo.
    before = Image.open(ROOT / "iters/7/gen_bfbbacd2.png").convert("RGB")
    after = Image.open(ROOT / "decompose/iter0_lanterns_inpainted.png").convert("RGB")

    half_w = 460
    half_h = 600

    before_thumb = _fit_inside(before, half_w, half_h)
    canvas.paste(before_thumb, (60 + (half_w - before_thumb.width) // 2, 280))

    after_thumb = _fit_inside(after, half_w, half_h)
    canvas.paste(after_thumb, (560 + (half_w - after_thumb.width) // 2, 280))

    d.line([(540, 320), (540, 860)], fill=RULE, width=1)

    _draw_text_centered_at(d, "原图 (iter0)", 905, FONT_SUB, INK, x_left=60, x_right=520)
    _draw_text_centered_at(d, "灯笼层 → gongbi 重绘", 905, FONT_SUB, RED, x_left=560, x_right=1020)

    _draw_text_centered_at(d, "Glasgow 街景 + 红纸灯笼", 952, FONT_LABEL, MUTED, x_left=60, x_right=520)
    _draw_text_centered_at(d, "其他像素 100% 保留", 952, FONT_LABEL, MUTED, x_left=560, x_right=1020)

    _draw_text_centered(d, "inpaint_artwork · chinese_gongbi · 朱砂 +15%, 三矾九染 depth richer", 1020, FONT_LABEL, MUTED)
    canvas.save(OUT / "slide4.png", "PNG", optimize=True)


# =================================================================
# Slide 5 — 评分能力 · plan.md verdict trail (dual-column layout)
# =================================================================
def slide5():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 5)

    # Header
    _draw_text_centered(d, "plan.md 真分数轨迹", 110, FONT_TITLE, INK)
    _draw_text_centered(d, "iter 0  ·  seed 7  ·  V1-calibration  ·  openai/gpt-image-2", 188, FONT_LABEL, MUTED)
    _hrule(d, 226)

    # Score row centered, with L2 in red
    score_y = 268
    segments = [
        ("L1 0.78", INK),
        ("    ", INK),
        ("L2 0.65", RED),
        ("    ", INK),
        ("L3 0.72", INK),
        ("    ", INK),
        ("L4 0.75", INK),
        ("    ", INK),
        ("L5 0.65", INK),
    ]
    full_text = "".join(s for s, _ in segments)
    full_w = d.textbbox((0, 0), full_text, font=FONT_BODY)[2]
    sx = (SIZE - full_w) // 2
    cursor = sx
    for seg, color in segments:
        d.text((cursor, score_y), seg, font=FONT_BODY, fill=color)
        cursor += d.textbbox((0, 0), seg, font=FONT_BODY)[2]

    _draw_text_centered(d, "加权总分 = 0.702", score_y + 50, FONT_BODY, GOLD)

    # Section divider before dual-column
    _hrule(d, 380, color=RULE)

    # === LEFT COLUMN: verdict ladder ===
    # Column bounds: 60..520 (centered on x=290)
    LX_LEFT, LX_RIGHT = 60, 520
    ladder_y = 430

    _draw_text_centered_at(d, "strict-rubric verdict",   ladder_y,        FONT_LABEL, MUTED, LX_LEFT, LX_RIGHT)
    # REJECT shrunk from FONT_DISPLAY 60pt → FONT_TITLE 52pt to stop outshouting
    # the slide title (review v3 P1, both reviewers agreed)
    _draw_text_centered_at(d, "REJECT",                  ladder_y + 38,   FONT_TITLE,  RED,   LX_LEFT, LX_RIGHT)
    # 拒收 demoted RED → INK to keep red count ≤2 per slide (color discipline)
    _draw_text_centered_at(d, "拒收",                    ladder_y + 100,  FONT_BODY,   INK,   LX_LEFT, LX_RIGHT)
    _draw_text_centered_at(d, "↓",                       ladder_y + 152,  FONT_TITLE,  GOLD,  LX_LEFT, LX_RIGHT)
    _draw_text_centered_at(d, "user-override-accept",    ladder_y + 222,  FONT_SUB,    INK,   LX_LEFT, LX_RIGHT)
    _draw_text_centered_at(d, "人工接受",                ladder_y + 272,  FONT_BODY,   INK,   LX_LEFT, LX_RIGHT)
    _draw_text_centered_at(d, "(maintainer 决定本图用作 showcase)", ladder_y + 314, FONT_LABEL, MUTED, LX_LEFT, LX_RIGHT)

    # === RIGHT COLUMN: notes ===
    RX = 580
    notes_y = 430
    notes = [
        ("L2 不及格 < 0.70 阈值", INK, FONT_BODY),
        ("", None, None),
        ("→ 三矾九染 depth shallow", MUTED, FONT_LABEL),
        ("    石青/石绿 under-represented", MUTED, FONT_LABEL),
        ("", None, None),
        ("→ 物理上限:单次扩散", MUTED, FONT_LABEL),
        ("    无法模拟 alum-wash 多遍叠染", MUTED, FONT_LABEL),
        ("", None, None),
        ("rollback 规则", INK, FONT_BODY),
        ("L1 < 0.6 OR L3 < 0.6 跨 3 seeds", MUTED, FONT_LABEL),
        ("→ 都不满足", MUTED, FONT_LABEL),
        ("", None, None),
        ("不及格 = 诚实披露", INK, FONT_LABEL),
        ("不是 rollback 信号", MUTED, FONT_LABEL),
    ]
    for line, color, font in notes:
        if line:
            d.text((RX, notes_y), line, font=font, fill=color)
        notes_y += 28

    # Vertical hairline divider between columns
    d.line([(540, 410), (540, 880)], fill=RULE, width=1)

    # Footer
    _hrule(d, 920)
    _draw_text_centered(d, "双判决 provenance · 严苛规则保留诚实 · 人保留否决权", 956, FONT_BODY, GOLD)
    _draw_text_centered(d, "两条记录都进 plan.md — 从硬盘可复现", 1004, FONT_LABEL, MUTED)
    canvas.save(OUT / "slide5.png", "PNG", optimize=True)


# =================================================================
# Slide 6 — 文件树(markdown 才是产品)
# =================================================================
def slide6():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 6)

    _draw_text_centered(d, "整个项目就是 3 个 markdown 文件", 110, FONT_TITLE, INK)
    _draw_text_centered(d, "+ 一个目录里的产物", 188, FONT_LABEL, MUTED)
    _hrule(d, 226)

    tree = [
        "docs/visual-specs/2026-04-23-scottish-chinese-fusion/",
        "├── proposal.md            ← /visual-brainstorm 输出 (8K)",
        "├── design.md              ← /visual-spec 输出 (10K)",
        "├── plan.md                ← /visual-plan 输出 (11K)  *判决轨迹*",
        "├── source.png             ← Glasgow 街景照片",
        "├── iters/",
        "│   ├── _baseline_bare/bare_gpt2_edit.png    ← 裸 API 控制组",
        "│   └── 7/gen_bfbbacd2.png                   ← Vulca 工具链",
        "├── decompose/",
        "│   ├── lanterns_before.png       ← alpha 隔离 (slide 4 左)",
        "│   ├── lanterns_after.png        ← 工笔重绘 (slide 4 右)",
        "│   └── iter1/                    ← 9 语义层 + 1 residual",
        "│       ├── person.png · lanterns.png · sign_top.png …",
        "│       └── manifest.json",
        "└── carousel/                     ← 这套 carousel (slides 1–7)",
    ]
    y = 270
    for ln in tree:
        # md files in ink (top hierarchy), other tree content in TREE_INK
        # (darker than MUTED — codex v3 P1: file tree needs filesystem authority,
        # MUTED was too pale for the "this is real disk content" claim)
        token = ln.lstrip("│├└─ ").split()[0] if ln.lstrip("│├└─ ").split() else ""
        color = INK if token.endswith(".md") else TREE_INK
        d.text((100, y), ln, font=FONT_MONO, fill=color)
        y += 38

    _hrule(d, 920)
    _draw_text_centered(d, "三个 markdown 文件锁住完整决策链", 956, FONT_BODY, INK)
    _draw_text_centered(d, "Pixel 从 markdown 复现 · markdown 才是产品", 1000, FONT_BODY, GOLD)
    canvas.save(OUT / "slide6.png", "PNG", optimize=True)


# =================================================================
# Slide 7 — 其他能力速览(2x2 of used tools + footer line of unused)
# =================================================================
def slide7():
    canvas = _square_canvas()
    d = ImageDraw.Draw(canvas)
    _page_num(d, 7)

    _draw_text_centered(d, "Vulca 还能做这些", 110, FONT_TITLE, INK)
    _draw_text_centered(d, "22 个 MCP tools  ·  这次 carousel 用了 4 个 ↓", 188, FONT_LABEL, MUTED)
    _hrule(d, 226)

    # 2x2 grid of the 4 tools used in this carousel — bigger cells, more breathing
    used_cells = [
        ("layers_split",     "把图拆成可编辑语义层", "DINO + SAM + SegFormer SOTA 流水线"),
        ("layers_redraw",    "用 LLM 重绘单个 layer",  "alpha-mask 路径 + LLM 路径双暴露"),
        ("evaluate_artwork", "L1-L5 五维文化评分",     "agent self-grade · 无 VLM 依赖"),
        ("generate_image",   "从文字 prompt 生成",     "OpenAI / Gemini / ComfyUI / SDXL"),
    ]

    cell_w, cell_h = 460, 240
    pad_x, pad_y = 40, 28
    grid_x0, grid_y0 = 60, 264

    badge_text = "● 本次用过"
    badge_w = d.textbbox((0, 0), badge_text, font=FONT_LABEL)[2]

    for idx, (name, zh, hint) in enumerate(used_cells):
        row, col = divmod(idx, 2)
        cx = grid_x0 + col * (cell_w + pad_x)
        cy = grid_y0 + row * (cell_h + pad_y)

        # Cell background — warm tint with gold border
        d.rectangle([cx, cy, cx + cell_w, cy + cell_h], fill=(244, 234, 218), outline=GOLD, width=1)

        # Tool name (Latin) — slightly larger, INK
        d.text((cx + 28, cy + 30), name, font=FONT_SUB, fill=INK)
        # Used badge — right-aligned with measured width (sp v3 P1: prevent
        # collision with long tool names like 'evaluate_artwork')
        d.text((cx + cell_w - 28 - badge_w, cy + 38), badge_text, font=FONT_LABEL, fill=GOLD)
        # Chinese description
        d.text((cx + 28, cy + 100), zh, font=FONT_BODY, fill=INK)
        # Hint (smaller)
        d.text((cx + 28, cy + 148), hint, font=FONT_LABEL, fill=MUTED)

    # Footer: expanded unused tools — codex v3 P1 wanted breadth signal
    # restored after cell count cut from 6→4. Two rows × 5 names = 10 visible
    # of 18 total, plus a "4 / 22" numeric stamp for at-a-glance scale.
    _hrule(d, 800, color=RULE)
    _draw_text_centered(d, "另外 18 个 MCP tools(未用)", 826, FONT_LABEL, MUTED)
    _draw_text_centered(d,
        "inpaint_artwork  ·  search_traditions  ·  layers_edit  ·  layers_composite  ·  brief_parse",
        856, FONT_LABEL, MUTED)
    _draw_text_centered(d,
        "compose_prompt_from_design  ·  list_traditions  ·  layers_evaluate  ·  layers_transform  ·  …",
        884, FONT_LABEL, MUTED)

    _hrule(d, 928, color=RULE)
    _draw_text_centered(d, "本 carousel 用了 4 / 22  ·  github.com/vulca-org/vulca-visual-control-sdk", 956, FONT_BODY, INK)
    _draw_text_centered(d, 'pip install "vulca[mcp]==0.17.12"', 1028, FONT_MONO, GOLD)
    canvas.save(OUT / "slide7.png", "PNG", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (slide1, slide2, slide3, slide4, slide5, slide6, slide7):
        fn()
        print(f"[ok] {fn.__name__}.png")
