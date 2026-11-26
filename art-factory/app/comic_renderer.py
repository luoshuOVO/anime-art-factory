from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

FONT_REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

STYLE_BADGES = {
    "explainer": ("科普图解条漫", (236, 72, 153)),
    "four_panel": ("四格日常漫", (14, 165, 233)),
    "story": ("番剧分镜长图", (139, 92, 246)),
}


def _find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            continue
        cur = ""
        for ch in para:
            candidate = cur + ch
            if font.getlength(candidate) <= max_width or not cur:
                cur = candidate
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def _draw_rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render_comic_strip(
    *,
    title: str,
    subtitle: str,
    takeaway: str,
    style: str,
    source_hint: str,
    panels: list[dict[str, Any]],
    panel_images: list[bytes],
) -> bytes:
    """Assemble clean anime panels into a crisp, readable Chinese vertical webtoon strip."""
    canvas_w = 1080
    margin_x = 36
    inner_w = canvas_w - margin_x * 2  # 1008
    img_pad = 16
    img_w = inner_w - img_pad * 2  # 976
    img_h = int(img_w * 9 / 16)  # 549 (matches 1024x576 16:9)

    bg_color = (248, 246, 241)
    ink = (24, 32, 48)
    muted = (96, 108, 128)
    shadow = (218, 214, 206)
    card_bg = (255, 255, 255)

    f_badge = _find_font(FONT_BOLD_CANDIDATES, 22)
    f_title = _find_font(FONT_BOLD_CANDIDATES, 42)
    f_sub = _find_font(FONT_REG_CANDIDATES, 25)
    f_num = _find_font(FONT_BOLD_CANDIDATES, 24)
    f_ptitle = _find_font(FONT_BOLD_CANDIDATES, 28)
    f_speaker = _find_font(FONT_BOLD_CANDIDATES, 22)
    f_dialog = _find_font(FONT_REG_CANDIDATES, 25)
    f_caption = _find_font(FONT_BOLD_CANDIDATES, 24)
    f_footer = _find_font(FONT_REG_CANDIDATES, 21)

    badge_text, accent = STYLE_BADGES.get(style, STYLE_BADGES["explainer"])

    # Pre-calculate header height
    title_lines = _wrap_text(title or "科普图解漫画", f_title, inner_w - 64)
    sub_lines = _wrap_text(subtitle or "", f_sub, inner_w - 64)
    header_h = 46 + 44 + len(title_lines) * 56 + (len(sub_lines) * 36 + 14 if sub_lines else 0) + 34

    # Pre-calculate each panel card layout
    panel_layouts: list[dict[str, Any]] = []
    for idx, p in enumerate(panels):
        p_title = str(p.get("panel_title") or f"第 {idx + 1} 格").strip()
        dialogues = p.get("dialogues") or []
        norm_dialogs: list[dict[str, Any]] = []
        for d in dialogues[:2]:
            if isinstance(d, dict):
                sp = str(d.get("speaker") or "学姐").strip()[:10]
                txt = str(d.get("text") or "").strip()
            else:
                sp = "旁白"
                txt = str(d).strip()
            if txt:
                d_lines = _wrap_text(txt, f_dialog, img_w - 170)
                norm_dialogs.append({"speaker": sp, "lines": d_lines})
        caption = str(p.get("caption") or "").strip()
        cap_lines = _wrap_text(f"划重点：{caption}", f_caption, img_w - 44) if caption else []

        top_bar_h = 62
        dialogs_h = 0
        for nd in norm_dialogs:
            bubble_h = max(52, len(nd["lines"]) * 34 + 22)
            nd["height"] = bubble_h
            dialogs_h += bubble_h + 12
        cap_h = (len(cap_lines) * 34 + 26) if cap_lines else 0
        extra_gap = 14 if (norm_dialogs or cap_lines) else 0
        card_h = top_bar_h + img_h + extra_gap + dialogs_h + cap_h + 22

        panel_layouts.append(
            {
                "idx": idx,
                "panel_title": p_title,
                "dialogs": norm_dialogs,
                "cap_lines": cap_lines,
                "cap_h": cap_h,
                "card_h": card_h,
            }
        )

    takeaway_lines = _wrap_text(takeaway or "一图看懂核心原理", f_sub, inner_w - 72)
    takeaway_h = 48 + len(takeaway_lines) * 38 + 30
    footer_h = 72

    total_h = (
        32
        + header_h
        + 28
        + sum(pl["card_h"] + 28 for pl in panel_layouts)
        + takeaway_h
        + 20
        + footer_h
    )

    canvas = Image.new("RGB", (canvas_w, total_h), bg_color)
    draw = ImageDraw.Draw(canvas)

    # 1. Header card
    y = 32
    _draw_rounded_box(draw, (margin_x + 6, y + 6, canvas_w - margin_x + 6, y + header_h + 6), 20, fill=shadow)
    _draw_rounded_box(draw, (margin_x, y, canvas_w - margin_x, y + header_h), 20, fill=(28, 37, 56), outline=ink, width=3)

    # Badge
    bw = int(f_badge.getlength(badge_text)) + 32
    _draw_rounded_box(draw, (margin_x + 32, y + 26, margin_x + 32 + bw, y + 64), 18, fill=accent)
    draw.text((margin_x + 48, y + 32), badge_text, font=f_badge, fill=(255, 255, 255))

    ty = y + 82
    for line in title_lines:
        draw.text((margin_x + 32, ty), line, font=f_title, fill=(255, 255, 255))
        ty += 56
    if sub_lines:
        ty += 8
        for line in sub_lines:
            draw.text((margin_x + 32, ty), line, font=f_sub, fill=(203, 213, 225))
            ty += 36

    y += header_h + 28

    # 2. Panel cards
    for pl in panel_layouts:
        idx = pl["idx"]
        ch = pl["card_h"]

        # Drop shadow & outer card
        _draw_rounded_box(draw, (margin_x + 6, y + 6, canvas_w - margin_x + 6, y + ch + 6), 18, fill=shadow)
        _draw_rounded_box(draw, (margin_x, y, canvas_w - margin_x, y + ch), 18, fill=card_bg, outline=ink, width=3)

        # Panel number pill & title
        num_txt = f"{idx + 1:02d}"
        _draw_rounded_box(draw, (margin_x + 18, y + 14, margin_x + 74, y + 50), 12, fill=ink)
        draw.text((margin_x + 30, y + 18), num_txt, font=f_num, fill=(255, 255, 255))
        draw.text((margin_x + 88, y + 16), pl["panel_title"][:28], font=f_ptitle, fill=ink)

        # Image frame
        ix = margin_x + img_pad
        iy = y + 62
        raw = panel_images[idx] if idx < len(panel_images) else None
        if raw:
            pimg = Image.open(io.BytesIO(raw)).convert("RGB")
            fitted = ImageOps.fit(pimg, (img_w, img_h), method=Image.Resampling.LANCZOS)
        else:
            fitted = Image.new("RGB", (img_w, img_h), (235, 240, 248))
        canvas.paste(fitted, (ix, iy))
        draw.rectangle((ix, iy, ix + img_w, iy + img_h), outline=ink, width=3)

        cy = iy + img_h + 14

        # Dialogue bubbles
        for d_idx, nd in enumerate(pl["dialogs"]):
            bh = nd["height"]
            sp = nd["speaker"]
            is_first = ("学姐" in sp or "讲师" in sp or d_idx == 0) and ("助手" not in sp and "小白" not in sp)
            sp_bg = (252, 231, 243) if is_first else (224, 242, 254)
            sp_fg = (157, 23, 77) if is_first else (7, 89, 133)
            bub_bg = (255, 250, 252) if is_first else (246, 251, 255)

            _draw_rounded_box(draw, (ix, cy, ix + img_w, cy + bh), 14, fill=bub_bg, outline=ink, width=2)
            # Speaker tag
            _draw_rounded_box(draw, (ix + 12, cy + 10, ix + 132, cy + 44), 10, fill=sp_bg)
            sw = f_speaker.getlength(sp)
            draw.text((ix + 12 + max(8, (120 - sw) / 2), cy + 14), sp, font=f_speaker, fill=sp_fg)

            dy = cy + 11
            for line in nd["lines"]:
                draw.text((ix + 148, dy), line, font=f_dialog, fill=ink)
                dy += 34
            cy += bh + 12

        # Caption highlight bar
        if pl["cap_lines"]:
            ch_box = pl["cap_h"]
            _draw_rounded_box(draw, (ix, cy, ix + img_w, cy + ch_box), 12, fill=(254, 243, 199), outline=(217, 119, 6), width=2)
            draw.rectangle((ix + 2, cy + 6, ix + 10, cy + ch_box - 6), fill=(217, 119, 6))
            ky = cy + 12
            for line in pl["cap_lines"]:
                draw.text((ix + 22, ky), line, font=f_caption, fill=(120, 53, 15))
                ky += 34

        y += ch + 28

    # 3. Takeaway summary card
    _draw_rounded_box(draw, (margin_x + 5, y + 5, canvas_w - margin_x + 5, y + takeaway_h + 5), 18, fill=shadow)
    _draw_rounded_box(draw, (margin_x, y, canvas_w - margin_x, y + takeaway_h), 18, fill=(236, 253, 245), outline=(5, 150, 105), width=3)
    draw.text((margin_x + 28, y + 18), "一句话带走", font=f_ptitle, fill=(6, 95, 70))
    ty = y + 58
    for line in takeaway_lines:
        draw.text((margin_x + 28, ty), line, font=f_sub, fill=(20, 83, 45))
        ty += 38

    y += takeaway_h + 20

    # 4. Footer
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    footer_text = f"二次元科普漫画工坊 · {date_str}"
    if source_hint:
        footer_text += f" · 来源：{source_hint[:42]}"
    fw = f_footer.getlength(footer_text)
    draw.text(((canvas_w - fw) / 2, y + 14), footer_text, font=f_footer, fill=muted)

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
