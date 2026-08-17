#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate that STANDARD_SCHEME_TASK no longer auto-generates PPT artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "controller" / "scheme_ppt_decoupling_contract.json"
PIPELINE = ROOT / "controller" / "pipeline.json"
AGENTS = ROOT / "AGENTS.md"
OVERRIDE = ROOT / "00D_方案与PPT彻底解耦强制覆盖规则.md"
PPT_PROTOCOL = ROOT / "05F_玩家教学PPT独立二次任务协议.md"
MASTER_PROMPT = ROOT / "玩家教学PPT独立创建总控口述_V1.0.md"
CARD_TEMPLATE = ROOT / "controller" / "templates" / "player_teaching_material_card.template.md"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def main() -> int:
    for p in (CONTRACT, PIPELINE, AGENTS, OVERRIDE, PPT_PROTOCOL, MASTER_PROMPT, CARD_TEMPLATE):
        if not p.exists():
            fail(f"missing required decoupling source: {p.relative_to(ROOT)}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("status") != "ACTIVE":
        fail("scheme/PPT decoupling contract must be ACTIVE")

    scheme = contract.get("standard_scheme_task", {})
    if scheme.get("auto_generate_ppt") is not False:
        fail("STANDARD_SCHEME_TASK must have auto_generate_ppt=false")
    if scheme.get("required_bridge_artifact") != "玩家教学素材卡.md":
        fail("scheme task must require 玩家教学素材卡.md as bridge artifact")
    if scheme.get("bridge_template") != "controller/templates/player_teaching_material_card.template.md":
        fail("scheme task must bind the player teaching material-card template")
    forbidden = set(scheme.get("forbidden_artifacts", []))
    if not {"*.ppt", "*.pptx", "PPT蓝图"}.issubset(forbidden):
        fail("standard scheme task must forbid PPT/PPTX/PPT blueprint")
    if scheme.get("may_read_ppt_protocols") is not False:
        fail("standard scheme task must not load PPT protocols")

    teaching = contract.get("teaching_card_contract", {})
    card_text = CARD_TEMPLATE.read_text(encoding="utf-8")
    if teaching.get("template") != "controller/templates/player_teaching_material_card.template.md":
        fail("teaching-card contract must point to the template")
    for section in teaching.get("required_sections", []):
        if section not in card_text:
            fail(f"material-card template missing section: {section}")

    ppt = contract.get("player_teaching_ppt_task", {})
    if ppt.get("trigger") != "EXPLICIT_USER_REQUEST_ONLY":
        fail("player PPT task must require explicit user request")
    if ppt.get("may_modify_scheme_logic") is not False:
        fail("player PPT task must not modify frozen scheme logic")

    pipeline = json.loads(PIPELINE.read_text(encoding="utf-8"))
    dec = pipeline.get("scheme_ppt_decoupling", {})
    if dec.get("standard_scheme_auto_ppt") is not False:
        fail("pipeline must explicitly disable standard scheme auto PPT")
    if dec.get("standard_scheme_reads_ppt_protocols") is not False:
        fail("pipeline must explicitly block PPT protocols in standard scheme task")
    if dec.get("bridge_artifact") != "玩家教学素材卡.md":
        fail("pipeline bridge artifact must be 玩家教学素材卡.md")

    phases = {x.get("id"): x for x in pipeline.get("phases", [])}
    execution = str(phases.get("EXECUTION", {}).get("role", ""))
    audit = str(phases.get("AUDIT", {}).get("role", ""))
    delivery = str(phases.get("DELIVERY", {}).get("role", ""))
    if "禁止自动生成PPT" not in execution:
        fail("EXECUTION phase must explicitly forbid auto PPT")
    if "不做PPT审计" not in audit:
        fail("AUDIT phase must explicitly exclude PPT audit for standard scheme task")
    if "不含PPT" not in delivery:
        fail("DELIVERY phase must explicitly exclude PPT from standard scheme ZIP")

    agents_text = AGENTS.read_text(encoding="utf-8")
    required_agents = [
        "标准方案任务禁止自动生成PPT",
        "玩家教学素材卡.md",
        "PLAYER_TEACHING_PPT_TASK",
        "明确二次请求",
    ]
    for phrase in required_agents:
        if phrase not in agents_text:
            fail(f"AGENTS missing decoupling rule: {phrase}")

    override_text = OVERRIDE.read_text(encoding="utf-8")
    for phrase in ["标准方案创建与PPT创建彻底分离", "SCHEME_PPT_COUPLING_REGRESSION", "玩家教学素材卡.md"]:
        if phrase not in override_text:
            fail(f"00D missing decoupling phrase: {phrase}")

    print("[PASS] STANDARD_SCHEME_TASK is decoupled from PPT generation")
    print("[PASS] player teaching material card is bound to a reproducible template")
    print("[PASS] player PPT is explicit secondary task with teaching-card bridge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
