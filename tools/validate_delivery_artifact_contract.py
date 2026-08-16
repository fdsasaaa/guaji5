#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate delivery artifact safety rules.

This gate protects confirmed delivery boundaries:
1. Scheme TXT files must not show encrypted / creator-locked state unless the
   user explicitly asked for it. The default is an empty SchemeCreator value.
2. Public-facing PPT rules must stay player-teaching oriented.
3. Ordinary straight-line betting multiplier lists must use positive integers
   only; decimal multipliers such as 0.01 are invalid.
4. Fixed-pick packages must not mechanically write every open-number segment as
   0-0; fixed-pick content must show explainable segment diversity.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "controller" / "delivery_artifact_contract.json"
PUBLIC_PPT = ROOT / "05E_公开视频玩家教学PPT与交付物隔离协议.md"
AGENTS = ROOT / "AGENTS.md"
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def load_contract() -> dict:
    if not CONTRACT.exists():
        fail("missing controller/delivery_artifact_contract.json")
    try:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse delivery artifact contract: {exc}")


def detect_encoding(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("gbk")
        return "gbk"
    except UnicodeDecodeError:
        return "utf-8"


def parse_fields(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        fields.setdefault(k.strip(), []).append(v.strip())
    return fields


def is_positive_integer_sequence(value: str) -> bool:
    if not value or "." in value:
        return False
    parts = value.split(",")
    return all(part.isdigit() and int(part) >= 1 for part in parts)


def validate_scheme_txt(path: Path, allow_encrypted: bool = False) -> tuple[bool, str | None]:
    raw = path.read_bytes()
    text = raw.decode(detect_encoding(path), errors="strict")
    matches = re.findall(r"(?m)^SchemeCreator=(.*)$", text)
    if not matches:
        fail(f"{path}: missing SchemeCreator= field")
    if len(matches) != 1:
        fail(f"{path}: expected exactly one SchemeCreator= field, got {len(matches)}")
    value = matches[0].strip()
    if value and not allow_encrypted:
        fail(f"{path}: SchemeCreator must be empty by default, got {value!r}")
    if b"\r\n" not in raw:
        fail(f"{path}: delivered main TXT should use CRLF line endings")

    fields = parse_fields(text)
    bet_type = fields.get("倍投类型", [""])[0]
    if bet_type == "0":
        for key in ("倍投计划", "倍投方案"):
            values = fields.get(key, [])
            if len(values) != 1:
                fail(f"{path}: expected exactly one {key}= field")
            if not is_positive_integer_sequence(values[0]):
                fail(f"{path}: {key} must be positive integers only, got {values[0]!r}")

    fixed_values = fields.get("固定取码内容", [])
    if not fixed_values:
        return False, None
    if len(fixed_values) != 1:
        fail(f"{path}: expected exactly one 固定取码内容= field")
    fixed = fixed_values[0]
    parts = fixed.split("|")
    if len(parts) != 3:
        fail(f"{path}: 固定取码内容 must use 位置范围|开出号码段|投注内容, got {fixed!r}")
    open_segment = parts[1].strip()
    if not re.fullmatch(r"\d+-\d+", open_segment):
        fail(f"{path}: 固定取码 open-number segment must be a numeric range, got {open_segment!r}")
    return True, open_segment


def validate_package(package_dir: Path, allow_encrypted: bool = False) -> None:
    if not package_dir.exists():
        fail(f"package path does not exist: {package_dir}")
    scheme_txts = []
    fixed_segments = []
    for p in package_dir.rglob("*.txt"):
        raw = p.read_bytes()
        if b"SchemeCreator=" in raw:
            scheme_txts.append(p)
            is_fixed, segment = validate_scheme_txt(p, allow_encrypted=allow_encrypted)
            if is_fixed:
                fixed_segments.append(segment)
    if not scheme_txts:
        fail(f"no scheme TXT containing SchemeCreator= found under {package_dir}")
    if len(fixed_segments) >= 5:
        if all(seg == "0-0" for seg in fixed_segments):
            fail("fixed-pick package uses open-number segment 0-0 for every file; this is forbidden")
        if len(set(fixed_segments)) < 3:
            fail(f"fixed-pick package must use at least 3 distinct open-number segments, got {sorted(set(fixed_segments))}")
    print(f"[PASS] scheme TXT delivery gate: {len(scheme_txts)} files")
    if fixed_segments:
        print(f"[PASS] fixed-pick open-number segments: {sorted(set(fixed_segments))}")


def validate_repository_rules(contract: dict) -> None:
    if contract.get("status") != "ACTIVE":
        fail("delivery artifact contract must be ACTIVE")
    txt_contract = contract.get("txt_scheme_creator_contract", {})
    if txt_contract.get("default") != "SchemeCreator=":
        fail("default SchemeCreator contract must be exactly SchemeCreator=")
    if txt_contract.get("allowed_non_empty_only_when_user_explicitly_requests") is not True:
        fail("non-empty SchemeCreator must require explicit user request")

    integer_contract = contract.get("integer_multiplier_contract", {})
    if integer_contract.get("minimum_multiplier") != 1:
        fail("integer multiplier minimum must be 1")
    for forbidden in ["decimal multipliers", "0.01", "0.001", "empty plan"]:
        if forbidden not in integer_contract.get("forbidden", []):
            fail(f"integer multiplier forbidden item missing: {forbidden}")

    fixed_contract = contract.get("fixed_pick_content_contract", {})
    gate = fixed_contract.get("package_gate", {})
    if gate.get("all_zero_zero_open_segment_forbidden") is not True:
        fail("fixed-pick all-0-0 package gate must be enabled")
    if int(gate.get("minimum_distinct_open_number_segments", 0)) < 3:
        fail("fixed-pick segment diversity gate must require at least 3 distinct ranges")

    ppt_contract = contract.get("public_ppt_contract", {})
    required_story = {
        "玩法是什么", "数据窗口是什么", "每个数字为什么被选", "为什么不选其他数字",
        "多组如何搭配", "倍投只是资金管理不是提高命中", "连续不中如何停止或减压", "观众能学走什么",
    }
    if not required_story.issubset(set(ppt_contract.get("required_story_questions", []))):
        fail("public PPT required story questions are incomplete")
    for forbidden in ["GitHub", "PR", "JSON", "CSV", "GBK", "CRLF", "SchemeCreator", "生成器", "制作TXT", "设计挂机方案"]:
        if forbidden not in ppt_contract.get("forbidden_terms", []):
            fail(f"public PPT forbidden term missing: {forbidden}")

    public_text = PUBLIC_PPT.read_text(encoding="utf-8") if PUBLIC_PPT.exists() else ""
    for required in ["公开视频PPT不是工程报告", "每个最终投注数字为什么被留下", "倍投不改变中奖概率", "SchemeCreator"]:
        if required not in public_text:
            fail(f"05E public PPT protocol missing required rule: {required}")

    agents_text = AGENTS.read_text(encoding="utf-8") if AGENTS.exists() else ""
    for required in ["SchemeCreator=", "公开视频玩家教学", "后台执行包", "公开视频教学包"]:
        if required not in agents_text:
            fail(f"AGENTS missing delivery rule: {required}")

    workflow_text = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
    if "validate_delivery_artifact_contract.py" not in workflow_text:
        fail("workflow does not run validate_delivery_artifact_contract.py")
    print("[PASS] delivery artifact contract and public PPT protocol are enforced")
    print("[PASS] integer multiplier and fixed-pick segment gates are enforced")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, help="optional generated package directory to scan")
    parser.add_argument("--allow-encrypted", action="store_true", help="allow non-empty SchemeCreator only for explicit encrypted builds")
    args = parser.parse_args()
    contract = load_contract()
    validate_repository_rules(contract)
    if args.package_dir:
        validate_package(args.package_dir, allow_encrypted=args.allow_encrypted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
