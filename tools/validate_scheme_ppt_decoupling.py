#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate scheme/PPT decoupling and player-teaching PPT V1.1 rules."""

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
MASTER_PROMPT = ROOT / "玩家教学PPT独立创建总控口述_V1.1.md"
PREVIOUS_PROMPT = ROOT / "玩家教学PPT独立创建总控口述_V1.0.md"
PAGE_MODELS = ROOT / "controller" / "player_teaching_page_models.json"
CARD_TEMPLATE = ROOT / "controller" / "templates" / "player_teaching_material_card.template.md"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def main() -> int:
    for p in (CONTRACT, PIPELINE, AGENTS, OVERRIDE, PPT_PROTOCOL, MASTER_PROMPT, PREVIOUS_PROMPT, PAGE_MODELS, CARD_TEMPLATE):
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
    if ppt.get("master_prompt") != "玩家教学PPT独立创建总控口述_V1.1.md":
        fail("V1.1 player-teaching master prompt must be canonical")
    if ppt.get("page_models") != "controller/player_teaching_page_models.json":
        fail("player PPT task must bind the V1.1 page-model registry")
    if ppt.get("director_text_visible_on_slide") is not False:
        fail("director text must never be visible on audience slides")
    if ppt.get("number_identity_required") is not True:
        fail("visible number identity gate must be enabled")
    if ppt.get("page_three_question_gate_required") is not True:
        fail("three-question page gate must be enabled")

    page_models = json.loads(PAGE_MODELS.read_text(encoding="utf-8"))
    if page_models.get("status") != "ACTIVE":
        fail("player teaching page-model registry must be ACTIVE")
    expected_storylines = {"WHY_THESE_NUMBERS", "HOW_THE_BETTING_AND_MONEY_WORK_TOGETHER"}
    if set(page_models.get("primary_storylines", [])) != expected_storylines:
        fail("player teaching page models must preserve exactly the two primary storylines")
    required_identities = {"历史数据", "观察条件", "候选号码", "最终投注号码", "倍数", "投注金额", "盈亏金额", "期数"}
    if not required_identities.issubset(set(page_models.get("number_identity_types", []))):
        fail("number identity types are incomplete")
    gate = page_models.get("page_gate", {})
    if gate.get("failure_if_any_answer_is_unclear") is not True:
        fail("page gate must fail ambiguous pages")
    if gate.get("forbid_director_text_on_slide") is not True:
        fail("director text must be forbidden on slide")
    for prefix in ["讲法：", "导演提示：", "本页目的：", "下一页：", "制作说明："]:
        if prefix not in gate.get("forbidden_visible_prefixes", []):
            fail(f"missing forbidden director-text prefix: {prefix}")
    required_model_ids = {
        "PICK_CANDIDATE_ELIMINATION",
        "PICK_MULTI_POSITION_BREAKDOWN",
        "PICK_CONDITION_TO_ACTION",
        "MONEY_ROLE_DIVISION",
        "MONEY_FOUR_STAGE_PATH",
        "MONEY_RECOVERY_EXAMPLE",
    }
    actual_model_ids = {m.get("id") for m in page_models.get("models", [])}
    if actual_model_ids != required_model_ids:
        fail(f"player teaching page model IDs mismatch: {sorted(actual_model_ids)}")

    prompt_text = MASTER_PROMPT.read_text(encoding="utf-8")
    protocol_text = PPT_PROTOCOL.read_text(encoding="utf-8")
    for phrase in [
        "正文只允许围绕两条主线展开",
        "人工理解层",
        "任何观众可见数字都必须有明确身份",
        "导演提示禁止进入观众页面",
        "候选淘汰页",
        "多位置独立拆解页",
        "条件 → 投注动作页",
        "多组任务分工页",
        "四阶段资金路径页",
        "真实回利过程页",
        "三问门禁",
        "为什么没有选最接近的另一个候选",
    ]:
        if phrase not in prompt_text:
            fail(f"V1.1 master prompt missing rule: {phrase}")
    for phrase in [
        "两条唯一主线",
        "数字身份硬门禁",
        "导演提示禁止进入观众页面",
        "选号页面三种成熟模型",
        "倍投页面三种成熟模型",
        "页面三问门禁",
    ]:
        if phrase not in protocol_text:
            fail(f"05F V1.1 protocol missing rule: {phrase}")

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
    for phrase in ["标准方案任务禁止自动生成PPT", "玩家教学素材卡.md", "PLAYER_TEACHING_PPT_TASK", "明确二次请求"]:
        if phrase not in agents_text:
            fail(f"AGENTS missing decoupling rule: {phrase}")

    override_text = OVERRIDE.read_text(encoding="utf-8")
    for phrase in ["标准方案创建与PPT创建彻底分离", "SCHEME_PPT_COUPLING_REGRESSION", "玩家教学素材卡.md"]:
        if phrase not in override_text:
            fail(f"00D missing decoupling phrase: {phrase}")

    print("[PASS] STANDARD_SCHEME_TASK is decoupled from PPT generation")
    print("[PASS] V1.1 player-teaching master prompt is canonical")
    print("[PASS] six mature page models, number-identity gate and three-question page gate are enforced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
