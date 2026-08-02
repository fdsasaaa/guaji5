#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "ppt" / "fixed_pages"
MANIFEST = ASSET_DIR / "PPT固定页资源清单.json"
errors: list[str] = []

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
R_EMBED = f"{{{NS['r']}}}embed"
COVER_MIN_LUMINANCE = 72


def fail(message: str) -> None:
    errors.append(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"固定页资源清单读取失败: {exc}")
        return {}


def slide_count(path: Path) -> int:
    with ZipFile(path) as zf:
        return sum(
            1
            for name in zf.namelist()
            if name.startswith("ppt/slides/slide")
            and name.endswith(".xml")
            and "/_rels/" not in name
        )


def slide_xml_bytes(path: Path, slide_no: int) -> bytes:
    with ZipFile(path) as zf:
        return zf.read(f"ppt/slides/slide{slide_no}.xml")


def _resolve_target(base: str, target: str) -> str:
    base_dir = PurePosixPath(base).parent
    parts: list[str] = []
    for part in (base_dir / target).parts:
        if part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def background_image(path: Path, slide_no: int) -> tuple[bytes | None, str | None]:
    slide_name = f"ppt/slides/slide{slide_no}.xml"
    rels_name = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
    with ZipFile(path) as zf:
        root = ET.fromstring(zf.read(slide_name))
        blip = root.find(".//p:bg//a:blip", NS)
        if blip is None:
            return None, None
        rel_id = blip.get(R_EMBED)
        if not rel_id or rels_name not in zf.namelist():
            return None, None
        rels = ET.fromstring(zf.read(rels_name))
        target = None
        for rel in rels.findall("pr:Relationship", NS):
            if rel.get("Id") == rel_id:
                target = rel.get("Target")
                break
        if not target:
            return None, None
        member = _resolve_target(slide_name, target)
        if member not in zf.namelist():
            return None, member
        return zf.read(member), member


def screen_shape_count(path: Path, slide_no: int) -> int:
    root = ET.fromstring(slide_xml_bytes(path, slide_no))
    tags = [
        f"{{{NS['p']}}}sp",
        f"{{{NS['p']}}}pic",
        f"{{{NS['p']}}}graphicFrame",
        f"{{{NS['p']}}}cxnSp",
        f"{{{NS['p']}}}contentPart",
    ]
    return sum(len(root.findall(f".//{tag}")) for tag in tags)


def has_normal_picture(path: Path, slide_no: int) -> bool:
    root = ET.fromstring(slide_xml_bytes(path, slide_no))
    return root.find(".//p:pic", NS) is not None


def has_picture_background(path: Path, slide_no: int) -> bool:
    root = ET.fromstring(slide_xml_bytes(path, slide_no))
    return root.find(".//p:bg//a:blipFill", NS) is not None


def _hex_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value or len(value) != 6:
        return None
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def validate_cover_text_contrast(path: Path) -> None:
    root = ET.fromstring(slide_xml_bytes(path, 1))
    for shape_index, shape in enumerate(root.findall(".//p:sp", NS), 1):
        texts = [node.text or "" for node in shape.findall(".//a:t", NS)]
        if not any(texts):
            continue
        for run in shape.findall(".//a:r", NS):
            text_node = run.find("a:t", NS)
            if text_node is None or not (text_node.text or "").strip():
                continue
            color_node = run.find("a:rPr/a:solidFill/a:srgbClr", NS)
            rgb = _hex_rgb(color_node.get("val") if color_node is not None else None)
            if rgb is None:
                fail(
                    f"PPT_COVER_TEXT_COLOR_NOT_EXPLICIT file={path.name} "
                    f"shape={shape_index} text={text_node.text!r}"
                )
            elif _luminance(rgb) < COVER_MIN_LUMINANCE:
                fail(
                    f"PPT_COVER_DARK_TEXT_FORBIDDEN file={path.name} "
                    f"text={text_node.text!r} color={rgb}"
                )
        for effect_color in shape.findall(".//a:effectLst//a:srgbClr", NS):
            rgb = _hex_rgb(effect_color.get("val"))
            if rgb is not None and _luminance(rgb) < COVER_MIN_LUMINANCE:
                fail(f"PPT_COVER_DARK_EFFECT_FORBIDDEN file={path.name} color={rgb}")
        for line_color in shape.findall(".//a:ln/a:solidFill/a:srgbClr", NS):
            rgb = _hex_rgb(line_color.get("val"))
            if rgb is not None and _luminance(rgb) < COVER_MIN_LUMINANCE:
                fail(f"PPT_COVER_DARK_TEXT_EFFECT_FORBIDDEN file={path.name} color={rgb}")


def validate_frozen_background_slide(path: Path, slide_no: int, expected_image: Path, label: str) -> None:
    if not has_picture_background(path, slide_no):
        fail(f"{label}未使用真正图片背景层: {path.name} slide={slide_no}")
        return
    if has_normal_picture(path, slide_no):
        fail(f"{label}仍包含普通可选中图片: {path.name} slide={slide_no}")
    count = screen_shape_count(path, slide_no)
    if count != 0:
        fail(f"{label}存在额外屏幕对象: {path.name} slide={slide_no} shapes={count}")
    data, member = background_image(path, slide_no)
    if data is None:
        fail(f"{label}背景图片关系无法解析: {path.name} slide={slide_no} target={member}")
        return
    if not expected_image.exists():
        fail(f"{label}标准画面缺失: {expected_image.relative_to(ROOT)}")
        return
    expected = sha256(expected_image)
    actual = sha256_bytes(data)
    if actual != expected:
        fail(f"{label}画面哈希不一致: {path.name} slide={slide_no} expected={expected} actual={actual}")


def validate_final_ppt(path: Path, second_png: Path, end_png: Path) -> None:
    if not path.exists():
        fail(f"最终PPT不存在: {path}")
        return
    try:
        count = slide_count(path)
    except Exception as exc:
        fail(f"最终PPT无法读取: {path}: {exc}")
        return
    if count < 3:
        fail(f"最终PPT页数不足3页: {path.name} slides={count}")
        return
    if not has_picture_background(path, 1) or has_normal_picture(path, 1):
        fail(f"PPT_COVER_BACKGROUND_NOT_EMBEDDED: {path.name}")
    validate_cover_text_contrast(path)
    validate_frozen_background_slide(path, 2, second_png, "PPT_FIXED_SECOND_PAGE")
    validate_frozen_background_slide(path, count, end_png, "PPT_FIXED_END_PAGE")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-ppt", action="append", default=[], help="validate a generated PPTX; may be repeated")
    args = parser.parse_args()

    manifest = load_manifest()
    required = manifest.get("files", {})
    if not isinstance(required, dict):
        fail("固定页资源清单files字段必须为对象")
        required = {}

    for rel, expected in required.items():
        path = ROOT / rel
        if not path.exists():
            fail(f"固定页资源缺失: {rel}")
            continue
        actual = sha256(path)
        if actual != expected:
            fail(f"固定页资源哈希不一致: {rel} expected={expected} actual={actual}")

    cover = ASSET_DIR / "首页背景图谱.png"
    second_png = ASSET_DIR / "固定第二页_原页画面.png"
    end_png = ASSET_DIR / "固定最后一页_画面.png"
    cover_tpl = ASSET_DIR / "固定首页模板.pptx"
    second = ASSET_DIR / "固定第二页_平台与联系.pptx"
    end = ASSET_DIR / "固定最后一页_标准版.pptx"
    full = ASSET_DIR / "PPT固定首页第二页末页模板_V3.9.3.pptx"
    protocol = ROOT / "05B_固定首页第二页末页协议.md"

    for path in [cover, second_png, end_png, cover_tpl, second, end, full, protocol]:
        if not path.exists():
            fail(f"必要文件缺失: {path.relative_to(ROOT)}")

    for pptx in [cover_tpl, second, end, full]:
        if not pptx.exists():
            continue
        try:
            with ZipFile(pptx) as zf:
                damaged = zf.testzip()
                if damaged is not None:
                    fail(f"PPTX压缩包损坏: {pptx.name} member={damaged}")
        except BadZipFile:
            fail(f"PPTX无法打开: {pptx.name}")

    if cover_tpl.exists():
        if slide_count(cover_tpl) != 1:
            fail("固定首页模板必须且只能有一页")
        if not has_picture_background(cover_tpl, 1) or has_normal_picture(cover_tpl, 1):
            fail("固定首页模板未使用不可选中的图片背景层")

    if second.exists():
        if slide_count(second) != 1:
            fail("固定第二页模板必须且只能有一页")
        validate_frozen_background_slide(second, 1, second_png, "PPT_FIXED_SECOND_PAGE")

    if end.exists():
        if slide_count(end) != 1:
            fail("固定最后一页标准版必须且只能有一页")
        validate_frozen_background_slide(end, 1, end_png, "PPT_FIXED_END_PAGE")

    if full.exists():
        if slide_count(full) != 3:
            fail("三页固定模板必须严格为3页")
        if not has_picture_background(full, 1) or has_normal_picture(full, 1):
            fail("三页模板第一页没有使用不可选中的背景层")
        validate_frozen_background_slide(full, 2, second_png, "PPT_FIXED_SECOND_PAGE")
        validate_frozen_background_slide(full, 3, end_png, "PPT_FIXED_END_PAGE")

    if protocol.exists():
        content = protocol.read_text(encoding="utf-8")
        for phrase in [
            "双击页面不得选中背景图",
            "首页禁止黑色或近黑色文字和效果",
            "第二页屏幕内容必须与用户模板第二页完全一致",
            "第二页不得叠加任何其他屏幕内容",
            "最后一页屏幕内容必须与用户模板第三页完全一致",
            "固定最后一页_标准版.pptx",
        ]:
            if phrase not in content:
                fail(f"05B协议缺少关键规则: {phrase}")

    for raw in args.final_ppt:
        paths = sorted(ROOT.glob(raw)) if any(c in raw for c in "*?[") else [ROOT / raw]
        if not paths:
            fail(f"最终PPT通配符未匹配文件: {raw}")
        for path in paths:
            validate_final_ppt(path, second_png, end_png)

    if errors:
        print("PPT_FIXED_PAGES_FAILED")
        for item in errors:
            print("-", item)
        return 1

    print(
        "PPT_FIXED_PAGES_OK",
        "cover=BACKGROUND_LIGHT_TEXT_ONLY",
        "second=EXACT_FROZEN_PAGE_2",
        "end=EXACT_FROZEN_LAST",
        f"final_ppts={len(args.final_ppt)}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
