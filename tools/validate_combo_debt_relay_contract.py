#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate combo debt relay / advanced betting state design rules.

This repository-level gate protects the B404 design lesson:
- Low-pressure integer schedules must not be sold as strict single-hit recovery.
- Combo relay packages must explicitly separate endurance, recovery and rescue.
- Advanced betting state graphs must include soft reset and cooling concepts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "controller" / "combo_debt_relay_contract.json"
PROTOCOL = ROOT / "11B_组合债务接力回利与高级倍投协议.md"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def main() -> int:
    if not CONTRACT.exists():
        fail("missing controller/combo_debt_relay_contract.json")
    if not PROTOCOL.exists():
        fail("missing 11B_组合债务接力回利与高级倍投协议.md")
    try:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse combo debt relay contract: {exc}")

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
    expected = ["软件名称", "ID", "倍数", "中后ID", "挂后ID", "中后监控", "中后跳转", "挂后监控", "挂后跳转"]
    if adv.get("field_order") != expected:
        fail("advanced betting 9-field order changed")
    if adv.get("multiplier_rule") != "positive integers only":
        fail("advanced multiplier rule must be positive integers only")
    for bad in ["0", "0.01", "0.001", "decimal", "negative", "empty"]:
        if bad not in adv.get("forbidden_multipliers", []):
            fail(f"missing forbidden multiplier: {bad}")
    if "中后ID" not in str(adv.get("soft_reset_definition", "")):
        fail("soft reset definition must mention 中后ID")
    if "挂后ID" not in str(adv.get("cooling_definition", "")):
        fail("cooling definition must mention 挂后ID")

    text = PROTOCOL.read_text(encoding="utf-8")
    for required in ["组合债务接力", "耐久组", "回补组", "救援组", "软复位", "冷却", "不能称为单次命中强回利"]:
        if required not in text:
            fail(f"protocol missing required phrase: {required}")

    print("[PASS] combo debt relay contract is active and boundary-safe")
    print("[PASS] advanced state graph requires integer multipliers, soft reset and rescue cooling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
