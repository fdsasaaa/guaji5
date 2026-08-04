#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def parse_sequence(value: str) -> list[int]:
    try:
        return [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError:
        return []


def validate(delivery_zip: Path, execution_contract: Path, contract_path: Path) -> list[str]:
    errors: list[str] = []
    contract = load_json(contract_path)
    execution = load_json(execution_contract)
    expected_sequence = execution.get("selected_delivery_path", {}).get("sequence", [])
    if not isinstance(expected_sequence, list) or len(expected_sequence) < 3 or any(not isinstance(x, int) or x <= 0 for x in expected_sequence):
        errors.append("delivery_execution_contract缺少有效资金序列")
        expected_sequence = []
    if expected_sequence and len(set(expected_sequence)) == 1:
        errors.append("用户要求差异化资金路径时不得仍为全平倍")
    if expected_sequence and max(expected_sequence) > contract.get("funding", {}).get("default_max_multiplier", 3):
        errors.append("资金序列超过默认最高倍数")

    if not delivery_zip.exists():
        return [f"完整交付ZIP不存在: {delivery_zip}"]
    with ZipFile(delivery_zip) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        roots = {name.split("/", 1)[0] for name in names}
        if len(roots) != contract.get("root_entry_count", 3):
            errors.append(f"完整包根目录必须严格3项，实际{len(roots)}项")
        ppt = [name for name in names if "/" not in name and name.lower().endswith(".pptx")]
        seo = [name for name in names if "/" not in name and name.lower().endswith(".txt")]
        folders = [root for root in roots if root not in set(ppt + seo)]
        if len(ppt) != 1:
            errors.append("完整包根目录必须恰好1个PPTX")
        if len(seo) != 1:
            errors.append("完整包根目录必须恰好1个SEO TXT")
        if len(folders) != 1:
            errors.append("完整包根目录必须恰好1个方案文件夹")
        if any(name.lower().endswith(".zip") for name in names):
            errors.append("完整包内禁止嵌套ZIP")
        if any(name.lower().endswith((".md", ".csv", ".json")) for name in names):
            errors.append("外部方案文件夹禁止说明、记录、JSON等内部文件")

        if folders:
            folder = folders[0]
            scheme_files = [name for name in names if name.startswith(folder + "/")]
            if not scheme_files:
                errors.append("方案文件夹为空")
            for name in scheme_files:
                if not name.lower().endswith(".txt"):
                    errors.append(f"方案文件夹出现非TXT文件: {name}")
                    continue
                raw = archive.read(name)
                try:
                    text = raw.decode("gbk")
                except UnicodeDecodeError:
                    errors.append(f"方案TXT不是GBK: {name}")
                    continue
                if b"\r\n" not in raw:
                    errors.append(f"方案TXT不是CRLF: {name}")
                number_value = find_value(text, "定码轮换内容=")
                if not re.fullmatch(r"\d(?: \d)+", number_value):
                    errors.append(f"方案TXT缺少明确投注数字: {name}")
                compact = number_value.replace(" ", "")
                if compact and compact not in Path(name).stem:
                    errors.append(f"投注数字未写入文件名: {name}")
                plan = parse_sequence(find_value(text, "倍投计划="))
                scheme = parse_sequence(find_value(text, "倍投方案="))
                if expected_sequence and (plan != expected_sequence or scheme != expected_sequence):
                    errors.append(f"TXT资金序列与delivery_execution_contract不一致: {name}")
                if plan and len(set(plan)) == 1 and execution.get("user_feedback_override", {}).get("flat_default_forbidden") is True:
                    errors.append(f"仍使用机械平倍: {name}")

        if seo:
            seo_text = archive.read(seo[0]).decode("utf-8")
            if seo_text.count("标题：") != contract.get("seo", {}).get("title_count", 1):
                errors.append("SEO标题数量不符合合同")
            if seo_text.count("标签：") != 1 or seo_text.count("描述：") != 1:
                errors.append("SEO必须恰好一行标签和一个描述")
            tag_line = next((line for line in seo_text.splitlines() if line.startswith("标签：")), "")
            tags = [tag.strip() for tag in tag_line.removeprefix("标签：").split(",") if tag.strip()]
            lower, upper = contract.get("seo", {}).get("tag_count_range", [8, 10])
            if not lower <= len(tags) <= upper:
                errors.append(f"SEO标签数量应为{lower}—{upper}，实际{len(tags)}")
            for forbidden in contract.get("seo", {}).get("forbidden_claims", []):
                if forbidden in seo_text:
                    errors.append(f"SEO出现禁词: {forbidden}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-zip", type=Path, required=True)
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=ROOT / "controller" / "external_delivery_contract.json")
    args = parser.parse_args()
    errors = validate(args.delivery_zip, args.execution_contract, args.contract)
    if errors:
        print("EXTERNAL_DELIVERY_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EXTERNAL_DELIVERY_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
