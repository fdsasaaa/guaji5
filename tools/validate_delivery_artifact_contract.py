#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate STANDARD_SCHEME_TASK delivery artifact safety rules.

Confirmed boundaries:
1. MAIN SCHEME TXT files default to empty SchemeCreator unless encryption/lock
   was explicitly requested.
2. Current user-exported ADVANCED BETTING TXT is a different file class: GBK +
   CRLF, 16 semicolon-separated fields, and may contain a software-generated
   non-empty SchemeCreator value.
3. All multiplier values are positive integers; decimal multipliers are invalid.
4. Fixed-pick packages must not mechanically use open-number segment 0-0 for
   every main scheme.
5. PPT is deliberately outside this validator and outside STANDARD_SCHEME_TASK.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "controller" / "delivery_artifact_contract.json"
ADV_OVERRIDE = ROOT / "controller" / "advanced_betting_gui_export_override.json"
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"

ADVANCED_FIELDS = [
    "软件名称", "ID", "倍数", "中后ID", "挂后ID", "中后监控", "中后跳转",
    "挂后监控", "挂后跳转", "是否盈利跳转", "是否亏损跳转", "盈利金额",
    "亏损金额", "盈利跳转局数", "亏损跳转局数", "SchemeCreator",
]


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


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


def split_advanced_line(line: str) -> list[tuple[str, str]] | None:
    parts = line.split(";")
    if len(parts) != len(ADVANCED_FIELDS):
        return None
    pairs: list[tuple[str, str]] = []
    for part in parts:
        if "=" not in part:
            return None
        k, v = part.split("=", 1)
        pairs.append((k.strip(), v.strip()))
    if [k for k, _ in pairs] != ADVANCED_FIELDS:
        return None
    return pairs


def looks_like_advanced_betting(raw: bytes) -> bool:
    for enc in ("gbk", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return False
    lines = [x for x in text.splitlines() if x.strip()]
    return bool(lines) and split_advanced_line(lines[0]) is not None


def validate_advanced_betting_txt(path: Path) -> None:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        fail(f"{path}: current user-confirmed advanced export must not have UTF-8 BOM")
    try:
        text = raw.decode("gbk")
    except UnicodeDecodeError as exc:
        fail(f"{path}: current user-confirmed advanced export must decode as GBK: {exc}")
    if len(text.splitlines()) > 1 and b"\r\n" not in raw:
        fail(f"{path}: advanced betting export must use CRLF")

    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        pairs = split_advanced_line(line)
        if pairs is None:
            fail(f"{path}:{lineno}: expected exact 16-field advanced betting export order")
        row = dict(pairs)
        if not row["倍数"].isdigit() or int(row["倍数"]) < 1:
            fail(f"{path}:{lineno}: 倍数 must be a positive integer")
        if row["中后监控"] not in {"False", "True"}:
            fail(f"{path}:{lineno}: 中后监控 must be False or True")
        if row["挂后监控"] not in {"False", "True"}:
            fail(f"{path}:{lineno}: 挂后监控 must be False or True")
        for key in ("中后跳转", "挂后跳转"):
            if not re.fullmatch(r"(?:False|True)-.+", row[key]):
                fail(f"{path}:{lineno}: {key} must be False-方案名 or True-方案名")


def validate_main_scheme_txt(path: Path, allow_encrypted: bool = False) -> tuple[bool, str | None]:
    raw = path.read_bytes()
    text = raw.decode(detect_encoding(path), errors="strict")
    matches = re.findall(r"(?m)^SchemeCreator=(.*)$", text)
    if not matches:
        fail(f"{path}: missing SchemeCreator= field")
    if len(matches) != 1:
        fail(f"{path}: expected exactly one SchemeCreator= field, got {len(matches)}")
    value = matches[0].strip()
    if value and not allow_encrypted:
        fail(f"{path}: MAIN SCHEME SchemeCreator must be empty by default, got {value!r}")
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
    if list(package_dir.rglob("*.ppt")) or list(package_dir.rglob("*.pptx")):
        fail(f"{package_dir}: STANDARD_SCHEME_TASK package must not contain PPT/PPTX")
    main_scheme_txts = []
    advanced_txts = []
    fixed_segments = []
    for p in package_dir.rglob("*.txt"):
        raw = p.read_bytes()
        if looks_like_advanced_betting(raw):
            advanced_txts.append(p)
            validate_advanced_betting_txt(p)
            continue
        if b"SchemeCreator=" in raw:
            main_scheme_txts.append(p)
            is_fixed, segment = validate_main_scheme_txt(p, allow_encrypted=allow_encrypted)
            if is_fixed:
                fixed_segments.append(segment)
    if not main_scheme_txts:
        fail(f"no MAIN SCHEME TXT containing SchemeCreator= found under {package_dir}")
    if len(fixed_segments) >= 5:
        if all(seg == "0-0" for seg in fixed_segments):
            fail("fixed-pick package uses open-number segment 0-0 for every file; this is forbidden")
        if len(set(fixed_segments)) < 3:
            fail(f"fixed-pick package must use at least 3 distinct open-number segments, got {sorted(set(fixed_segments))}")
    print(f"[PASS] main-scheme TXT gate: {len(main_scheme_txts)} files")
    if advanced_txts:
        print(f"[PASS] advanced-betting GUI-export gate: {len(advanced_txts)} files")
    if fixed_segments:
        print(f"[PASS] fixed-pick open-number segments: {sorted(set(fixed_segments))}")


def validate_repository_rules(contract: dict, adv_override: dict) -> None:
    if contract.get("status") != "ACTIVE":
        fail("delivery artifact contract must be ACTIVE")
    if contract.get("scope") != "STANDARD_SCHEME_TASK_DELIVERY_ONLY":
        fail("delivery contract scope must be STANDARD_SCHEME_TASK_DELIVERY_ONLY")
    if "public_ppt_contract" in contract:
        fail("PPT rules must not remain inside standard scheme delivery contract")

    txt_contract = contract.get("txt_scheme_creator_contract", {})
    if txt_contract.get("scope") != "main_scheme_txt_only":
        fail("SchemeCreator empty-value rule must be scoped to MAIN SCHEME TXT only")
    if txt_contract.get("default") != "SchemeCreator=":
        fail("default main-scheme SchemeCreator contract must be exactly SchemeCreator=")
    if txt_contract.get("allowed_non_empty_only_when_user_explicitly_requests") is not True:
        fail("non-empty main-scheme SchemeCreator must require explicit user request")

    if adv_override.get("status") != "ACTIVE":
        fail("advanced betting GUI-export override must be ACTIVE")
    adv = adv_override.get("advanced_betting_export_contract", {})
    if adv.get("encoding") != "GBK" or adv.get("bom") is not False or adv.get("line_ending") != "CRLF":
        fail("advanced betting current export must preserve GBK/no-BOM/CRLF evidence")
    if adv.get("field_order") != ADVANCED_FIELDS:
        fail("advanced betting current export must preserve exact 16-field order")
    creator = adv.get("scheme_creator", {})
    if creator.get("observed_non_empty") is not True:
        fail("advanced export must record observed non-empty SchemeCreator evidence")

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

    workflow_text = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
    if "validate_delivery_artifact_contract.py" not in workflow_text:
        fail("workflow does not run validate_delivery_artifact_contract.py")
    print("[PASS] STANDARD_SCHEME_TASK delivery contract is PPT-free and file-class aware")
    print("[PASS] main SchemeCreator, integer multiplier, fixed-pick and advanced GUI-export gates are enforced")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, help="optional generated STANDARD_SCHEME_TASK package directory to scan")
    parser.add_argument("--allow-encrypted", action="store_true", help="allow non-empty MAIN SCHEME SchemeCreator only for explicit encrypted builds")
    args = parser.parse_args()
    contract = load_json(CONTRACT)
    adv_override = load_json(ADV_OVERRIDE)
    validate_repository_rules(contract, adv_override)
    if args.package_dir:
        validate_package(args.package_dir, allow_encrypted=args.allow_encrypted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
