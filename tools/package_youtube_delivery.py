#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

FORBIDDEN_CLAIMS = [
    "稳赚", "必胜", "包赢", "必中", "必出", "保证收益", "稳定盈利", "无风险",
    "内部必中号码", "AI预测下一期", "长期赚钱", "已经证明可以稳定盈利",
]
ENGINEERING_RE = re.compile(r"(?:^|[^A-Za-z0-9])(?:B|C)\d{3}(?:[^A-Za-z0-9]|$)|SET_\d+|方案ID|批次ID", re.I)
URL_RE = re.compile(r"https?://|www\.|t\.me/", re.I)
PREMATURE_TITLE_RE = re.compile(r"盈利|亏损|收益|回撤|命中率|实测结果|最终结果|最后赚|最后剩|优于随机|验证失败")
PREMATURE_DESC_RE = re.compile(r"本次盈利|本次亏损|已经优于随机|已证明有效|已证明无效|验证失败|最终命中率|最终收益")


def fail(code: str, detail: str) -> None:
    raise ValueError(f"{code}: {detail}")


def load_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("YOUTUBE_SEO_CONFIG_INVALID", str(exc))
    if not isinstance(data, dict):
        fail("YOUTUBE_SEO_CONFIG_INVALID", "根节点必须是对象")
    return data


def validate_config(data: dict) -> tuple[str, str, list[str], list[str], str]:
    project = str(data.get("project_name", "")).strip()
    stage = str(data.get("stage", "")).strip()
    titles = data.get("titles", [])
    tags = data.get("tags", [])
    description = str(data.get("description", "")).strip()

    if not project:
        fail("YOUTUBE_SEO_CONFIG_INVALID", "缺少project_name")
    if stage not in {"PRE_RUN_SETUP", "POST_RUN_REVIEW"}:
        fail("YOUTUBE_SEO_CONFIG_INVALID", f"stage错误: {stage}")
    if not isinstance(titles, list) or not 3 <= len(titles) <= 5:
        fail("YOUTUBE_SEO_TITLE_COUNT_INVALID", f"实际{len(titles) if isinstance(titles, list) else '非列表'}")
    if not isinstance(tags, list) or not 8 <= len(tags) <= 10:
        fail("YOUTUBE_SEO_TAG_COUNT_INVALID", f"实际{len(tags) if isinstance(tags, list) else '非列表'}")

    titles = [str(x).strip() for x in titles]
    tags = [str(x).strip() for x in tags]
    if any(not x for x in titles) or len(set(titles)) != len(titles):
        fail("YOUTUBE_SEO_TITLE_COUNT_INVALID", "标题存在空值或重复")
    if any(not x for x in tags) or len(set(tags)) != len(tags):
        fail("YOUTUBE_SEO_TAG_COUNT_INVALID", "标签存在空值或重复")
    if any("," in x or "，" in x or "\n" in x for x in tags):
        fail("YOUTUBE_SEO_TAG_SEPARATOR_INVALID", "单个标签不得包含逗号或换行")
    if len(description) < 80:
        fail("YOUTUBE_SEO_DESCRIPTION_MISSING", "描述过短")

    all_text = "\n".join([project, *titles, *tags, description])
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in all_text:
            fail("YOUTUBE_SEO_MISLEADING_METADATA", f"禁用词: {phrase}")
    if ENGINEERING_RE.search(all_text):
        fail("YOUTUBE_SEO_ENGINEERING_ID_VISIBLE", "出现工程编号或内部ID")
    if URL_RE.search(all_text):
        fail("YOUTUBE_SEO_GAMBLING_LINK_PRESENT", "SEO发布参考默认禁止URL或外部访问指令")
    if re.search(r"\d+(?:\.\d+)?U\b", all_text):
        fail("YOUTUBE_SEO_CURRENCY_UNIT_INVALID", "金额仍使用U")

    if stage == "PRE_RUN_SETUP":
        for title in titles:
            if PREMATURE_TITLE_RE.search(title):
                fail("YOUTUBE_SEO_PREMATURE_RESULT", f"挂机前标题出现结果词: {title}")
        if PREMATURE_DESC_RE.search(description):
            fail("YOUTUBE_SEO_PREMATURE_RESULT", "挂机前描述提前给出结果")
        if not any(phrase in description for phrase in ["不提前", "实际挂机", "结果复盘", "只冻结规则"]):
            fail("YOUTUBE_SEO_PREMATURE_RESULT", "挂机前描述未明确等待实际运行")

    return project, stage, titles, tags, description


def render_txt(project: str, stage: str, titles: list[str], tags: list[str], description: str) -> str:
    title_lines = "\n".join(f"{i}. {title}" for i, title in enumerate(titles, 1))
    tag_line = ",".join(tags)
    stage_label = "挂机前规则讲解" if stage == "PRE_RUN_SETUP" else "真实结果复盘"
    return (
        f"{project}｜YouTube发布参考\n\n"
        f"【内容阶段】\n{stage_label}\n\n"
        f"【YouTube标题参考】\n{title_lines}\n\n"
        f"【YouTube标签】\n{tag_line}\n\n"
        f"【YouTube视频描述】\n{description}\n\n"
        "【发布前核对】\n"
        "- 标题、缩略图和视频内容表达一致。\n"
        "- 标签填写在YouTube Studio标签栏，不复制成描述关键词墙。\n"
        "- 不添加稳赚、必中、保证收益或未发生的结果。\n"
        "- 不在本文件自动加入博彩平台链接、开户链接或外部联系方式。\n"
    )


def find_unique(delivery_dir: Path, suffix: str, keyword: str | None = None) -> Path:
    candidates = [p for p in delivery_dir.iterdir() if p.is_file() and p.name.endswith(suffix)]
    if keyword:
        candidates = [p for p in candidates if keyword in p.name]
    if len(candidates) != 1:
        fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", f"{suffix}/{keyword} 候选数量={len(candidates)}")
    return candidates[0]


def build(delivery_dir: Path, config_path: Path) -> tuple[Path, Path]:
    if not delivery_dir.exists():
        fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", f"目录不存在: {delivery_dir}")
    data = load_config(config_path)
    project, stage, titles, tags, description = validate_config(data)

    scheme_zip = find_unique(delivery_dir, ".zip", "方案套")
    pptx = find_unique(delivery_dir, ".pptx")
    seo_txt = delivery_dir / f"{project}_YouTube发布参考.txt"
    outer_zip = delivery_dir / f"{project}_完整交付.zip"

    seo_text = render_txt(project, stage, titles, tags, description)
    seo_txt.write_text(seo_text, encoding="utf-8-sig", newline="\n")

    if outer_zip.exists():
        outer_zip.unlink()
    with ZipFile(outer_zip, "w", ZIP_DEFLATED) as zf:
        for path in [scheme_zip, pptx, seo_txt]:
            zf.write(path, arcname=path.name)

    with ZipFile(outer_zip) as zf:
        names = zf.namelist()
        if len(names) != 3 or any("/" in name.rstrip("/") for name in names):
            fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", f"根目录结构错误: {names}")
        if sum(name.endswith("_方案套.zip") for name in names) != 1:
            fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", "方案套ZIP数量错误")
        if sum(name.endswith(".pptx") for name in names) != 1:
            fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", "PPTX数量错误")
        if sum(name.endswith("_YouTube发布参考.txt") for name in names) != 1:
            fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", "YouTube发布参考TXT数量错误")
        generated = zf.read(seo_txt.name).decode("utf-8-sig")
        if "【YouTube标题参考】" not in generated or "【YouTube标签】" not in generated or "【YouTube视频描述】" not in generated:
            fail("DELIVERY_OUTER_ZIP_STRUCTURE_INVALID", "SEO TXT内容缺失")
        tag_line = generated.split("【YouTube标签】\n", 1)[1].split("\n", 1)[0]
        if "，" in tag_line or not 7 <= tag_line.count(",") <= 9:
            fail("YOUTUBE_SEO_TAG_SEPARATOR_INVALID", tag_line)

    return seo_txt, outer_zip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-dir", required=True, type=Path)
    parser.add_argument("--seo-config", required=True, type=Path)
    args = parser.parse_args()
    try:
        seo_txt, outer_zip = build(args.delivery_dir, args.seo_config)
    except Exception as exc:
        print("YOUTUBE_DELIVERY_FAILED")
        print("-", exc)
        sys.exit(1)
    print(f"YOUTUBE_DELIVERY_OK seo={seo_txt.name} outer_zip={outer_zip.name} files=3")


if __name__ == "__main__":
    main()
