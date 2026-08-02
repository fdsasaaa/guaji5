#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import json

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "ppt" / "fixed_pages"
SOURCE_DIR = ASSET_DIR / "source"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

W = Inches(13.333333)
H = Inches(7.5)
FONT = "Microsoft YaHei"
COVER_MIN_LUMINANCE = 72


def read_b64_parts(stem: str) -> bytes:
    parts = sorted(SOURCE_DIR.glob(f"{stem}.*.b64"))
    if not parts:
        raise FileNotFoundError(f"missing source chunks: {stem}.*.b64")
    payload = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    return base64.b64decode(payload)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def set_picture_background(slide, image_path: Path) -> None:
    pic = slide.shapes.add_picture(str(image_path), 0, 0, width=W, height=H)
    r_id = pic._element.blipFill.blip.rEmbed
    pic._element.getparent().remove(pic._element)
    bg = parse_xml(
        f'<p:bg {nsdecls("p", "a", "r")}>'
        '<p:bgPr>'
        '<a:blipFill dpi="0" rotWithShape="1">'
        f'<a:blip r:embed="{r_id}"/>'
        '<a:stretch><a:fillRect/></a:stretch>'
        '</a:blipFill>'
        '<a:effectLst/>'
        '</p:bgPr>'
        '</p:bg>'
    )
    slide._element.insert(0, bg)


def set_notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def _luminance(color: tuple[int, int, int]) -> float:
    r, g, b = color
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def add_text(
    slide,
    x,
    y,
    w,
    h,
    text,
    size,
    color,
    bold=False,
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.MIDDLE,
):
    rgb = tuple(int(v) for v in color)
    if getattr(slide, "_fixed_dark_cover", False) and _luminance(rgb) < COVER_MIN_LUMINANCE:
        raise ValueError(
            f"PPT_COVER_DARK_TEXT_FORBIDDEN color={rgb}; "
            "the fixed black cover requires light, high-contrast text/effects"
        )
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*rgb)
    return box


def add_round_rect(slide, x, y, w, h, fill, line, radius_type=MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(radius_type, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = RGBColor(*fill)
    s.line.color.rgb = RGBColor(*line)
    s.line.width = Pt(1)
    return s


def add_link_overlay(slide, x, y, w, h, url: str) -> None:
    """Legacy helper for non-fixed body slides only.

    Fixed slide 2 and the fixed last slide must never call this helper because
    their visible and invisible shape trees are frozen to the supplied pages.
    """
    s = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, x, y, w, h)
    s.fill.background()
    s.line.fill.background()
    s.click_action.hyperlink.address = url


def save_presentation(prs: Presentation, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)


def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    while len(prs.slides):
        r_id = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(r_id)
        del prs.slides._sldIdLst[0]
    return prs


def add_cover(prs: Presentation, cover_png: Path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_picture_background(slide, cover_png)
    slide._fixed_dark_cover = True
    set_notes(slide, "用一句话介绍本期验证主题和研究边界。黑色固定背景上只使用高对比浅色文字和效果。")
    return slide


def build_second_slide(prs: Presentation):
    """Append the exact user-supplied second page as a frozen background.

    No text box, decoration, link overlay, logo, page number, or dynamic content
    may be added to this slide. Speaker notes are the only allowed addition.
    """
    second_png = ASSET_DIR / "固定第二页_原页画面.png"
    if not second_png.exists():
        raise FileNotFoundError(f"fixed second-page render missing: {second_png}")
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_picture_background(slide, second_png)
    set_notes(slide, "这一页为用户提供的固定第二页，屏幕内容原样保留，不叠加任何其他内容。")
    return slide


def add_end(prs: Presentation, end_png: Path):
    """Append the exact fixed final page with no visible or invisible overlays."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_picture_background(slide, end_png)
    set_notes(slide, "这一页为固定结尾页，屏幕内容原样保留，不在其后追加普通播放页面。")
    return slide


def main() -> None:
    cover_source = ASSET_DIR / "首页背景图谱_嵌入源.webp"
    second_source = ASSET_DIR / "固定第二页_嵌入源.webp"
    end_source = ASSET_DIR / "固定最后一页_嵌入源.webp"
    cover_source.write_bytes(read_b64_parts("cover"))
    second_source.write_bytes(read_b64_parts("second"))
    end_source.write_bytes(read_b64_parts("end"))

    cover_png = ASSET_DIR / "首页背景图谱.png"
    second_png = ASSET_DIR / "固定第二页_原页画面.png"
    end_png = ASSET_DIR / "固定最后一页_画面.png"
    Image.open(cover_source).convert("RGB").save(cover_png, optimize=True)
    Image.open(second_source).convert("RGB").save(second_png, optimize=True)
    Image.open(end_source).convert("RGB").save(end_png, optimize=True)

    cover_prs = new_prs()
    add_cover(cover_prs, cover_png)
    save_presentation(cover_prs, ASSET_DIR / "固定首页模板.pptx")

    second_prs = new_prs()
    build_second_slide(second_prs)
    save_presentation(second_prs, ASSET_DIR / "固定第二页_平台与联系.pptx")

    end_prs = new_prs()
    add_end(end_prs, end_png)
    save_presentation(end_prs, ASSET_DIR / "固定最后一页_标准版.pptx")

    full = new_prs()
    add_cover(full, cover_png)
    build_second_slide(full)
    add_end(full, end_png)
    save_presentation(full, ASSET_DIR / "PPT固定首页第二页末页模板_V3.9.3.pptx")

    files = [
        cover_source,
        second_source,
        end_source,
        cover_png,
        second_png,
        end_png,
        ASSET_DIR / "固定首页模板.pptx",
        ASSET_DIR / "固定第二页_平台与联系.pptx",
        ASSET_DIR / "固定最后一页_标准版.pptx",
        ASSET_DIR / "PPT固定首页第二页末页模板_V3.9.3.pptx",
    ]
    manifest = {
        "version": "V3.9.3-FIXED-PAGES-2",
        "materializer": "tools/materialize_ppt_fixed_pages.py",
        "source_note": "cover/end use prior approved fixed visuals; second is a canonical full-slide render of page 2 from cp讲解模板(2).pptx",
        "rules": {
            "cover": "true OOXML image background; dynamic text must be light/high-contrast; black or near-black text/effects forbidden",
            "second": "exact frozen user page; background only; no added screen shapes/content",
            "end": "exact fixed user ending; background only; no overlays or later normal slide",
        },
        "files": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in files},
    }
    (ASSET_DIR / "PPT固定页资源清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("PPT_FIXED_PAGES_MATERIALIZED", len(files), "version=V3.9.3-FIXED-PAGES-2")


if __name__ == "__main__":
    main()
