#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "ppt" / "fixed_pages"
MANIFEST = ASSET_DIR / "PPT固定页资源清单.json"
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"固定页资源清单读取失败: {exc}")
        return {}


def pptx_text(path: Path, slide_no: int = 1) -> str:
    with ZipFile(path) as zf:
        xml = zf.read(f"ppt/slides/slide{slide_no}.xml")
    root = ET.fromstring(xml)
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    return "".join(node.text or "" for node in root.findall(".//a:t", ns))


def slide_count(path: Path) -> int:
    with ZipFile(path) as zf:
        return sum(
            1
            for name in zf.namelist()
            if name.startswith("ppt/slides/slide")
            and name.endswith(".xml")
            and "/_rels/" not in name
        )


def slide_xml(path: Path, slide_no: int) -> str:
    with ZipFile(path) as zf:
        return zf.read(f"ppt/slides/slide{slide_no}.xml").decode("utf-8")


def slide_rels(path: Path, slide_no: int) -> str:
    with ZipFile(path) as zf:
        name = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
        return zf.read(name).decode("utf-8") if name in zf.namelist() else ""


manifest = load_manifest()
required = manifest.get("files", {})
if not isinstance(required, dict):
    fail("固定页资源清单files字段必须为对象")
    required = {}

for relative, expected in required.items():
    path = ROOT / relative
    if not path.exists():
        fail(f"固定页资源缺失: {relative}")
        continue
    actual = sha256(path)
    if actual != expected:
        fail(f"固定页资源哈希不一致: {relative} expected={expected} actual={actual}")

cover = ASSET_DIR / "首页背景图谱.png"
cover_tpl = ASSET_DIR / "固定首页模板.pptx"
second = ASSET_DIR / "固定第二页_平台与联系.pptx"
end = ASSET_DIR / "固定最后一页_标准版.pptx"
full = ASSET_DIR / "PPT固定首页第二页末页模板_V3.9.3.pptx"
protocol = ROOT / "05B_固定首页第二页末页协议.md"
materializer = ROOT / "tools" / "materialize_ppt_fixed_pages.py"

for path in [cover, cover_tpl, second, end, full, protocol, materializer]:
    if not path.exists():
        fail(f"必要文件缺失: {path.relative_to(ROOT)}")

for pptx in [cover_tpl, second, end, full]:
    if not pptx.exists():
        continue
    try:
        with ZipFile(pptx) as zf:
            if zf.testzip() is not None:
                fail(f"PPTX压缩包损坏: {pptx.name}")
    except BadZipFile:
        fail(f"PPTX无法打开: {pptx.name}")

if cover_tpl.exists():
    xml = slide_xml(cover_tpl, 1)
    if "<p:bg>" not in xml or "<a:blipFill" not in xml:
        fail("固定首页模板未使用图片背景层")
    if "<p:pic>" in xml:
        fail("固定首页模板仍包含普通全页图片")

if second.exists():
    if slide_count(second) != 1:
        fail("固定第二页模板必须且只能有一页")
    text = pptx_text(second)
    for phrase in [
        "先选平台，再谈方案",
        "www.laocaimi.org",
        "Telegram：@laocaimi1314",
        "没有100%盈利模式",
        "不承诺收益",
    ]:
        if phrase not in text:
            fail(f"固定第二页缺少文字: {phrase}")
    for forbidden in ["QQ", "157019375", "稳赚", "必胜", "100%稳定提现"]:
        if forbidden in text:
            fail(f"固定第二页存在禁用内容: {forbidden}")
    rels = slide_rels(second, 1)
    for link in ["http://www.laocaimi.org", "https://t.me/laocaimi1314"]:
        if link not in rels:
            fail(f"固定第二页缺少超链接: {link}")

if end.exists():
    if slide_count(end) != 1:
        fail("固定最后一页标准版必须且只能有一页")
    rels = slide_rels(end, 1)
    for link in ["http://www.laocaimi.org", "https://t.me/laocaimi1314"]:
        if link not in rels:
            fail(f"固定最后一页缺少超链接: {link}")

if full.exists():
    if slide_count(full) != 3:
        fail("三页固定模板必须严格为3页")
    xml1 = slide_xml(full, 1)
    if "<p:bg>" not in xml1 or "<p:pic>" in xml1:
        fail("三页模板第一页没有使用不可选中的背景层")
    text2 = pptx_text(full, 2)
    if "Telegram：@laocaimi1314" not in text2:
        fail("三页模板第二页联系方式错误")
    rels3 = slide_rels(full, 3)
    if "http://www.laocaimi.org" not in rels3 or "https://t.me/laocaimi1314" not in rels3:
        fail("三页模板最后一页超链接不完整")

if protocol.exists():
    content = protocol.read_text(encoding="utf-8")
    for phrase in [
        "双击页面不得选中背景图",
        "正文动态内容从第三页开始",
        "固定最后一页_标准版.pptx",
        "Telegram：@laocaimi1314",
        "materialize_ppt_fixed_pages.py",
    ]:
        if phrase not in content:
            fail(f"05B协议缺少关键规则: {phrase}")

if errors:
    print("PPT_FIXED_PAGES_FAILED")
    for item in errors:
        print("-", item)
    sys.exit(1)

print("PPT_FIXED_PAGES_OK cover=BACKGROUND second=FIXED_PAGE_2 end=FIXED_LAST links=VALID")
