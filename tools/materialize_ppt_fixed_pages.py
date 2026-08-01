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


def add_text(slide, x, y, w, h, text, size, color, bold=False, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE):
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
    run.font.color.rgb = RGBColor(*color)
    return box


def add_round_rect(slide, x, y, w, h, fill, line):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*fill)
    shape.line.color.rgb = RGBColor(*line)
    shape.line.width = Pt(1)
    return shape


def add_link_overlay(slide, x, y, w, h, url: str) -> None:
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
    shape.fill.transparency = 100
    shape.line.fill.background()
    shape.click_action.hyperlink.address = url


def add_money_badge(slide) -> None:
    cx, cy = Inches(11.65), Inches(0.86)
    bag = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, cx, cy, Inches(1.00), Inches(1.00))
    bag.fill.solid()
    bag.fill.fore_color.rgb = RGBColor(229, 173, 49)
    bag.line.color.rgb = RGBColor(255, 219, 115)
    bag.line.width = Pt(2)
    add_text(slide, cx, cy + Inches(0.03), Inches(1.00), Inches(0.94), "$", 34, (38, 40, 39), True, PP_ALIGN.CENTER)
    for dx, dy, size in [(0.82, 0.73, 0.20), (0.95, 0.62, 0.14), (-0.08, 0.78, 0.16)]:
        coin = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, cx + Inches(dx), cy + Inches(dy), Inches(size), Inches(size))
        coin.fill.solid()
        coin.fill.fore_color.rgb = RGBColor(240, 190, 62)
        coin.line.color.rgb = RGBColor(255, 223, 126)


def build_second_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(4, 7, 10)

    gold = (235, 179, 63)
    white = (245, 247, 249)
    gray = (177, 184, 192)
    card = (14, 19, 25)
    line = (72, 87, 101)
    green = (54, 205, 157)

    add_text(slide, Inches(0.82), Inches(0.55), Inches(3.2), Inches(0.36), "平台与联系", 18, gold, True)
    add_text(slide, Inches(0.82), Inches(1.04), Inches(8.7), Inches(0.62), "先选平台，再谈方案", 31, white, True)
    add_text(slide, Inches(0.82), Inches(1.80), Inches(8.8), Inches(0.38), "高赔率、出入金记录稳定、规则透明，是长期验证的前提。", 16, gray)
    add_money_badge(slide)

    add_round_rect(slide, Inches(0.72), Inches(2.53), Inches(5.78), Inches(1.18), card, line)
    add_text(slide, Inches(1.06), Inches(2.68), Inches(1.9), Inches(0.36), "信誉平台大全", 17, white, True)
    add_text(slide, Inches(3.00), Inches(2.62), Inches(3.05), Inches(0.48), "www.laocaimi.org", 28, gold, True)
    add_text(slide, Inches(3.02), Inches(3.17), Inches(2.6), Inches(0.24), "点击访问平台信息", 11, (135, 143, 151))
    add_link_overlay(slide, Inches(2.92), Inches(2.56), Inches(3.25), Inches(0.92), "http://www.laocaimi.org")

    add_round_rect(slide, Inches(6.70), Inches(2.53), Inches(5.40), Inches(1.18), card, line)
    add_text(slide, Inches(7.06), Inches(2.65), Inches(1.86), Inches(0.55), "内部方案 / 挂机\n战法", 15, white, True)
    add_text(slide, Inches(8.82), Inches(2.61), Inches(2.90), Inches(0.58), "Telegram：@laocaimi1314", 17, green, True)
    add_text(slide, Inches(8.82), Inches(3.22), Inches(2.2), Inches(0.20), "交流与方案咨询", 11, (135, 143, 151))
    add_link_overlay(slide, Inches(8.72), Inches(2.56), Inches(3.10), Inches(0.94), "https://t.me/laocaimi1314")

    add_round_rect(slide, Inches(0.72), Inches(4.10), Inches(11.38), Inches(1.08), (239, 241, 243), (239, 241, 243))
    add_text(slide, Inches(1.10), Inches(4.28), Inches(3.0), Inches(0.46), "没有100%盈利模式", 23, (31, 35, 39), True)
    add_text(slide, Inches(4.10), Inches(4.28), Inches(7.45), Inches(0.44), "做好资金管理，耐心等待；短期结果不能替代长期验证。", 16, (70, 77, 84))

    add_round_rect(slide, Inches(0.72), Inches(5.52), Inches(11.38), Inches(0.68), card, line)
    add_text(slide, Inches(1.10), Inches(5.62), Inches(10.6), Inches(0.40), "会员内容可讲“杠杆交易”方法；属于非博彩方向，不承诺收益。", 15, white)
    add_text(slide, Inches(0.84), Inches(6.63), Inches(4.2), Inches(0.22), "固定第二页 · 所有正式 PPT 必须保留", 10, (132, 139, 146))
    set_notes(slide, "这一页只做平台入口、联系方式和风险边界说明。强调没有百分之百盈利模式，后面的内容仍按数据实验来讲。")
    return slide


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
    set_notes(slide, "用一句话介绍本期验证主题和研究边界，标题由具体项目生成器覆盖。")
    return slide


def add_end(prs: Presentation, end_png: Path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_picture_background(slide, end_png)
    add_link_overlay(slide, Inches(0.72), Inches(3.38), Inches(4.55), Inches(0.76), "http://www.laocaimi.org")
    add_link_overlay(slide, Inches(0.72), Inches(4.26), Inches(4.55), Inches(0.62), "https://t.me/laocaimi1314")
    set_notes(slide, "简短收尾即可，提醒观众通过网址下载更多方案，或通过Telegram联系。")
    return slide


def main() -> None:
    cover_jpg = ASSET_DIR / "首页背景图谱_嵌入源.jpg"
    end_jpg = ASSET_DIR / "固定最后一页_嵌入源.jpg"
    cover_jpg.write_bytes(read_b64_parts("cover"))
    end_jpg.write_bytes(read_b64_parts("end"))

    cover_png = ASSET_DIR / "首页背景图谱.png"
    end_png = ASSET_DIR / "固定最后一页_画面.png"
    Image.open(cover_jpg).convert("RGB").save(cover_png, optimize=True)
    Image.open(end_jpg).convert("RGB").save(end_png, optimize=True)

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
        cover_jpg,
        end_jpg,
        cover_png,
        end_png,
        ASSET_DIR / "固定首页模板.pptx",
        ASSET_DIR / "固定第二页_平台与联系.pptx",
        ASSET_DIR / "固定最后一页_标准版.pptx",
        ASSET_DIR / "PPT固定首页第二页末页模板_V3.9.3.pptx",
    ]
    manifest = {
        "version": "V3.9.3-FIXED-PAGES-1",
        "materializer": "tools/materialize_ppt_fixed_pages.py",
        "source_note": "cover/end fixed visuals are embedded source renders derived from the user-provided files",
        "files": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in files},
    }
    (ASSET_DIR / "PPT固定页资源清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("PPT_FIXED_PAGES_MATERIALIZED", len(files))


if __name__ == "__main__":
    main()
