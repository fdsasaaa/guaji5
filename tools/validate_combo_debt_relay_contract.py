#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate combo debt relay / advanced betting state design rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "controller" / "combo_debt_relay_contract.json"
ADV_OVERRIDE = ROOT / "controller" / "advanced_betting_gui_export_override.json"
PROTOCOL = ROOT / "11B_组合债务接力回利与高级倍投协议.md"

EXPECTED_FIELDS = [
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


def main() -> int:
    data = load_json(CONTRACT)
    override = load_json(ADV_OVERRIDE)
    if not PROTOCOL.exists():
        fail("missing 11B_组合债务接力回利与高级倍投协议.md")

    if data.get("status") != "ACTIVE":
        fail("combo debt relay contract must be ACTIVE")
    combo = data.get("combo_debt_relay_contract", {})
    required_roles = set(combo.get("required_roles", []))
    if not {"耐久组", "回补组", "救援组"}.issubset(required_roles):
        fail("combo relay must require endurance/recovery/rescue roles")
    if int(combo.get("minimum_distinct_advanced_state_graphs", 0)) < 3:
        fail("combo relay must require at least three distinct advanced state graphs")
    if combo.get("requires_soft_reset") is not True:
        fail("combo relay must require soft reset")
    if combo.get("requires_rescue_cooling") is not True:
        fail("combo relay must require rescue cooling")
    if combo.get("requires_combo_account_summary") is not True:
        fail("combo relay must require combo account summary")
    for forbidden in ["单次命中必回本", "保证回本", "稳赚", "倍投提高命中率"]:
        if forbidden not in combo.get("forbidden_claims", []):
            fail(f"missing forbidden claim: {forbidden}")

    adv = data.get("advanced_betting_state_graph_contract", {})
    if adv.get("field_order") != EXPECTED_FIELDS:
        fail("combo contract must use current user-confirmed 16-field advanced order")
    if adv.get("multiplier_rule") != "positive integers only":
        fail("advanced multiplier rule must be positive integers only")
    for bad in ["0", "0.01", "0.001", "decimal", "negative", "empty"]:
        if bad not in adv.get("forbidden_multipliers", []):
            fail(f"missing forbidden multiplier: {bad}")
    if "中后ID" not in str(adv.get("soft_reset_definition", "")):
        fail("soft reset definition must mention 中后ID")
    if "挂后ID" not in str(adv.get("cooling_definition", "")):
        fail("cooling definition must mention 挂后ID")

    event_controls = adv.get("event_controls", {})
    for key in ["中后监控", "挂后监控", "中后跳转", "挂后跳转"]:
        if key not in event_controls:
            fail(f"combo contract missing current GUI event control: {key}")

    current = override.get("advanced_betting_export_contract", {})
    if current.get("field_order") != EXPECTED_FIELDS:
        fail("advanced GUI export override 16-field order mismatch")
    if current.get("encoding") != "GBK" or current.get("bom") is not False or current.get("line_ending") != "CRLF":
        fail("current advanced export evidence must remain GBK/no-BOM/CRLF")
    monitors = current.get("monitor_contract", {})
    if not all(k in monitors for k in ("中后监控", "挂后监控")):
        fail("GUI export override must preserve both re-monitor controls")
    jumps = current.get("main_scheme_jump_contract", {})
    if not all(k in jumps for k in ("中后跳转", "挂后跳转")):
        fail("GUI export override must preserve both main-scheme jump controls")

    text = PROTOCOL.read_text(encoding="utf-8")
    for required in ["组合债务接力", "耐久组", "回补组", "救援组", "软复位", "冷却", "不能称为单次命中强回利", "重新监控", "主方案"]:
        if required not in text:
            fail(f"protocol missing required phrase: {required}")

    print("[PASS] combo debt relay contract is active and boundary-safe")
    print("[PASS] current 16-field advanced GUI/export controls are enforced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
