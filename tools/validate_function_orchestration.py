#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE_TYPES = {"BASELINE", "STATE", "EXECUTION_OR_FUNDING", "LOW_COVERAGE_PROBE"}
LAYERS = set("ABCDEFGH")
FUNDING_KINDS = {"FLAT", "LIMITED_LINEAR", "PRESSURE_RELEASE", "ADVANCED_STATE"}
SETTING_CATEGORIES = {
    "MONITORING", "PROFIT_LOSS_JUMP", "PROFIT_LOSS_STOP",
    "SIMULATION_REAL_SWITCH", "TIME_WINDOW", "CHANGE_RULE",
    "BET_DIRECTION", "ROTATION_OR_COMBINATION",
}
DECISIONS = {"SELECTED", "REJECTED", "PROBE_ONLY"}
EVIDENCE = {f"E{i}": i for i in range(8)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def material(value: Any) -> bool:
    if isinstance(value, dict):
        return any(material(v) for k, v in value.items() if not (k in {"enabled", "active"} and v is False))
    if isinstance(value, list):
        return any(material(v) for v in value)
    return present(value)


def rank(level: Any) -> int:
    return EVIDENCE.get(str(level), -1)


def validate_config(cfg: dict[str, Any]) -> list[str]:
    e: list[str] = []
    if cfg.get("schema_version") != 1: e.append("配置schema_version必须为1")
    if cfg.get("status") != "ACTIVE": e.append("功能编排配置必须为ACTIVE")
    if set(cfg.get("required_profile_types", [])) != PROFILE_TYPES: e.append("候选画像类型不完整")
    if set(cfg.get("required_layers", [])) != LAYERS: e.append("八层能力不完整")
    if set(cfg.get("required_funding_kinds", [])) != FUNDING_KINDS: e.append("资金四路不完整")
    if cfg.get("minimum_candidate_profiles", 0) < 4: e.append("候选画像下限必须至少4")
    if cfg.get("minimum_material_more_settings", 0) < 2: e.append("更多设置实质候选下限必须至少2")
    if cfg.get("baseline_only_max_consecutive", 99) > 2: e.append("连续纯平倍上限不得超过2批")
    if cfg.get("exploration_window_batches", 99) > 3: e.append("低覆盖探索窗口不得超过3批")
    for key in ("ci_block_on_missing_orchestration", "unverified_feature_formal_selection_forbidden", "advanced_with_new_state_first_use_forbidden"):
        if cfg.get(key) is not True: e.append(f"配置未启用: {key}")
    return e


def validate_funding(item: dict[str, Any], e: list[str]) -> None:
    pid, kind = item.get("path_id", "<unknown>"), item.get("kind")
    if kind not in FUNDING_KINDS:
        e.append(f"{pid}: 未知资金路径{kind!r}")
        return
    if item.get("decision") not in DECISIONS: e.append(f"{pid}: decision无效")
    if item.get("decision") == "SELECTED" and rank(item.get("software_evidence_level")) < 3:
        e.append(f"{pid}: E3以下资金路径不得正式入选")
    for key in ("max_multiplier", "total_multiplier", "worst_case_exposure"):
        if not isinstance(item.get(key), (int, float)) or item[key] <= 0: e.append(f"{pid}: {key}必须为正数")
    for key in ("reset_rule", "cap_rule", "reason"):
        if not present(item.get(key)): e.append(f"{pid}: 缺少{key}")
    if kind != "ADVANCED_STATE":
        seq = item.get("sequence")
        if not isinstance(seq, list) or len(seq) < 3 or any(not isinstance(x, (int, float)) or x <= 0 for x in seq):
            e.append(f"{pid}: 必须给出至少3阶正数序列")
            return
        if kind == "FLAT" and len(set(seq)) != 1: e.append(f"{pid}: 平倍序列必须恒定")
        if kind == "LIMITED_LINEAR":
            if max(seq) <= min(seq) or any(b < a for a, b in zip(seq, seq[1:])): e.append(f"{pid}: 有限普通倍投必须实际递增且不下降")
        if kind == "PRESSURE_RELEASE":
            rose = False; released = False
            for a, b in zip(seq, seq[1:]):
                if b > a: rose = True
                if rose and b < a: released = True
            if not released: e.append(f"{pid}: 压力释放路径必须先升压后降压")
    else:
        if not isinstance(item.get("states"), list) or len(item["states"]) < 2: e.append(f"{pid}: 高级路径至少2个状态")
        if not isinstance(item.get("transitions"), list) or len(item["transitions"]) < 2: e.append(f"{pid}: 高级路径至少2条转移")
        if item.get("decision") == "PROBE_ONLY":
            probe = item.get("probe_constraints", {})
            if probe.get("isolated") is not True or probe.get("single_variable") is not True: e.append(f"{pid}: 高级探针必须隔离且单变量")
            if not isinstance(probe.get("max_periods"), int) or not 1 <= probe["max_periods"] <= 30: e.append(f"{pid}: 探针期数必须1—30")
            if not isinstance(probe.get("max_cost"), (int, float)) or probe["max_cost"] <= 0: e.append(f"{pid}: 探针成本必须为正数")


def signature(profile: dict[str, Any]) -> tuple[str, ...]:
    s = profile.get("material_signature", {})
    return tuple(str(s.get(k, "")).strip() for k in ("number_logic", "trigger", "execution", "funding", "stop", "time_simulation"))


def validate_evidence(data: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    e: list[str] = []
    if data.get("schema_version") != 1: e.append("证据schema_version必须为1")
    if data.get("task_type") != "STANDARD_SCHEME_TASK": e.append("task_type必须为STANDARD_SCHEME_TASK")
    if data.get("status") not in {"DIRECTOR_COMPLETE", "CONTRACT_FROZEN", "VALIDATED", "COMPLETED"}: e.append("证据状态无效")

    profiles = data.get("candidate_profiles", [])
    if not isinstance(profiles, list): profiles = []; e.append("candidate_profiles必须为数组")
    if len(profiles) < cfg.get("minimum_candidate_profiles", 4): e.append("候选画像不足4个")
    types = {p.get("profile_type") for p in profiles if isinstance(p, dict)}
    if PROFILE_TYPES - types: e.append(f"缺少画像类型: {sorted(PROFILE_TYPES-types)}")
    ids: set[str] = set(); by_id: dict[str, dict[str, Any]] = {}; sigs: set[tuple[str, ...]] = set()
    for p in profiles:
        if not isinstance(p, dict): e.append("画像必须为对象"); continue
        pid = str(p.get("profile_id", "")).strip()
        if not pid: e.append("画像缺少profile_id"); continue
        if pid in ids: e.append(f"画像ID重复: {pid}")
        ids.add(pid); by_id[pid] = p
        if p.get("decision") not in DECISIONS: e.append(f"{pid}: decision无效")
        if not present(p.get("reason")): e.append(f"{pid}: 缺少理由")
        layers = p.get("layers", {})
        if not isinstance(layers, dict) or set(layers) != LAYERS: e.append(f"{pid}: 必须完整填写A—H八层")
        else:
            for lid, layer in layers.items():
                if not isinstance(layer, dict): e.append(f"{pid}.{lid}: 必须为对象"); continue
                for key in ("relevant", "candidates", "final_enabled", "decision_reason", "evidence_level"):
                    if key not in layer: e.append(f"{pid}.{lid}: 缺少{key}")
                if not isinstance(layer.get("candidates"), list): e.append(f"{pid}.{lid}: candidates必须为数组")
                if not present(layer.get("decision_reason")): e.append(f"{pid}.{lid}: 理由不能为空")
                if rank(layer.get("evidence_level")) < 0: e.append(f"{pid}.{lid}: 证据等级无效")
                if p.get("decision") == "SELECTED" and layer.get("final_enabled") is True and rank(layer.get("evidence_level")) < 3:
                    e.append(f"{pid}.{lid}: E3以下功能不得正式启用")
        sig = signature(p)
        if not any(sig): e.append(f"{pid}: 缺少实质签名")
        else: sigs.add(sig)
        if p.get("profile_type") == "LOW_COVERAGE_PROBE":
            if p.get("decision") not in {"PROBE_ONLY", "REJECTED"}: e.append(f"{pid}: 低覆盖画像只能探针或淘汰")
            if p.get("decision") == "PROBE_ONLY":
                c = p.get("probe_constraints", {})
                if c.get("isolated") is not True or c.get("single_variable") is not True: e.append(f"{pid}: 探针必须隔离且单变量")
                if not isinstance(c.get("max_periods"), int) or not 1 <= c["max_periods"] <= 30: e.append(f"{pid}: 探针期数必须1—30")
                if not isinstance(c.get("max_cost"), (int, float)) or c["max_cost"] <= 0: e.append(f"{pid}: 探针成本必须为正数")
    if len(sigs) < 3: e.append("至少需要3个实质不同的候选签名，禁止只换号码或期数")

    paths = data.get("funding_paths", [])
    if not isinstance(paths, list): paths = []; e.append("funding_paths必须为数组")
    kinds = {p.get("kind") for p in paths if isinstance(p, dict)}
    if FUNDING_KINDS - kinds: e.append(f"资金四路不完整: {sorted(FUNDING_KINDS-kinds)}")
    path_by_id: dict[str, dict[str, Any]] = {}
    for p in paths:
        if not isinstance(p, dict): e.append("资金路径必须为对象"); continue
        pid = str(p.get("path_id", "")).strip()
        if not pid: e.append("资金路径缺少path_id"); continue
        if pid in path_by_id: e.append(f"资金路径ID重复: {pid}")
        path_by_id[pid] = p; validate_funding(p, e)

    settings = data.get("more_settings_review", [])
    if not isinstance(settings, list): settings = []; e.append("more_settings_review必须为数组")
    material_categories: set[str] = set()
    for item in settings:
        if not isinstance(item, dict): e.append("更多设置记录必须为对象"); continue
        cat = item.get("category")
        if cat not in SETTING_CATEGORIES: e.append(f"未知更多设置类别: {cat!r}"); continue
        if material(item.get("material_configuration")): material_categories.add(cat)
        else: e.append(f"{cat}: 不能只写关闭，必须给出候选参数")
        if not isinstance(item.get("candidate_profile_ids"), list) or not item["candidate_profile_ids"]: e.append(f"{cat}: 必须关联画像")
        if item.get("final_decision") not in DECISIONS: e.append(f"{cat}: final_decision无效")
        if not present(item.get("reason")): e.append(f"{cat}: 缺少理由")
        if rank(item.get("evidence_level")) < 0: e.append(f"{cat}: 证据等级无效")
        if item.get("final_decision") == "SELECTED" and rank(item.get("evidence_level")) < 3: e.append(f"{cat}: E3以下不得正式入选")
    if len(material_categories) < cfg.get("minimum_material_more_settings", 2): e.append("实质更多设置候选不足2类")

    repeat = data.get("repeat_guard", {})
    count = repeat.get("repeat_count", 0) if isinstance(repeat, dict) else -1
    if not isinstance(count, int) or count < 0: e.append("repeat_count必须为非负整数")
    elif count >= 3:
        if repeat.get("penalty_applied") is not True: e.append("连续3批同画像必须施加重复惩罚")
        if repeat.get("selected_same_fingerprint") is True and not present(repeat.get("override_reason")): e.append("重复画像仍入选必须有证据化例外理由")

    coverage = data.get("coverage_debt", {})
    due = coverage.get("due_features", []) if isinstance(coverage, dict) else []
    blocked = coverage.get("blocked_features", []) if isinstance(coverage, dict) else []
    represented: set[str] = set()
    for p in profiles:
        if isinstance(p, dict) and isinstance(p.get("features"), list): represented.update(p["features"])
    blocked_ids = {b.get("feature_id") for b in blocked if isinstance(b, dict) and present(b.get("reason")) and present(b.get("evidence_ref"))}
    for feature in due:
        if feature not in represented and feature not in blocked_ids: e.append(f"覆盖债务未解决: {feature}")

    sel = data.get("selection", {})
    sp, sf = sel.get("selected_profile_id"), sel.get("selected_funding_path_id")
    if sp not in by_id or by_id.get(sp, {}).get("decision") != "SELECTED": e.append("最终画像不存在或未标记SELECTED")
    if sf not in path_by_id or path_by_id.get(sf, {}).get("decision") != "SELECTED": e.append("最终资金路径不存在或未标记SELECTED")
    if not present(sel.get("reason")): e.append("最终选择缺少理由")
    companion = sel.get("companion_probe_profile_id")
    if companion and (companion not in by_id or by_id[companion].get("decision") != "PROBE_ONLY"): e.append("配套探针不存在或未标记PROBE_ONLY")
    recent = data.get("recent_delivery_modes", [])
    if sel.get("delivery_mode") == "BASELINE_ONLY" and isinstance(recent, list):
        trailing = 0
        for mode in reversed(recent):
            if mode == "BASELINE_ONLY": trailing += 1
            else: break
        if trailing >= cfg.get("baseline_only_max_consecutive", 2):
            all_blocked = coverage.get("all_exploration_blocked") is True and bool(due) and len(blocked_ids) >= len(due)
            if not all_blocked and not companion: e.append("连续纯平倍达到上限，必须交付非基准实验或隔离探针")

    selected = by_id.get(sp, {})
    selected_path = path_by_id.get(sf, {})
    if selected.get("first_use") is True and selected.get("new_state_features") and selected_path.get("kind") == "ADVANCED_STATE":
        e.append("新状态功能首次启用不得同时正式启用高级状态资金路径")
    return e


def fixture() -> dict[str, Any]:
    def layer(enabled: bool = False, ev: str = "E3") -> dict[str, Any]:
        return {"relevant": True, "candidates": ["候选"], "final_enabled": enabled, "decision_reason": "已审议", "evidence_level": ev}
    layers = {x: layer(x in "ADEFH") for x in "ABCDEFGH"}
    def prof(pid: str, typ: str, sig: list[str], decision: str, features: list[str], probe: bool = False) -> dict[str, Any]:
        p = {"profile_id": pid, "profile_type": typ, "decision": decision, "reason": "有实质差异", "features": features,
             "layers": copy.deepcopy(layers), "material_signature": dict(zip(("number_logic", "trigger", "execution", "funding", "stop", "time_simulation"), sig)),
             "first_use": False, "new_state_features": []}
        if probe: p["probe_constraints"] = {"isolated": True, "single_variable": True, "max_periods": 12, "max_cost": 36}
        return p
    profiles = [
        prof("BASE", "BASELINE", ["条件频率", "立即", "轮投", "平倍", "30期", "无"], "SELECTED", ["定码轮换"]),
        prof("STATE", "STATE", ["条件频率", "监控1期", "轮投", "平倍", "亏损停止", "无"], "REJECTED", ["投注监控", "亏损停止"]),
        prof("FUND", "EXECUTION_OR_FUNDING", ["条件频率", "立即", "轮投", "压力释放", "封顶", "无"], "REJECTED", ["压力释放倍投"]),
        prof("PROBE", "LOW_COVERAGE_PROBE", ["固定对照", "模拟输2次", "单方案", "平倍", "12期", "模拟转真实"], "PROBE_ONLY", ["模拟转真实"], True),
    ]
    profiles[1]["layers"]["B"] = layer(True, "E2")
    profiles[3]["layers"]["G"] = layer(True, "E2")
    return {
        "schema_version": 1, "run_id": "SELF-TEST", "task_type": "STANDARD_SCHEME_TASK", "status": "CONTRACT_FROZEN",
        "candidate_profiles": profiles,
        "funding_paths": [
            {"path_id": "FLAT", "kind": "FLAT", "sequence": [1,1,1,1,1,1], "max_multiplier": 1, "total_multiplier": 6, "worst_case_exposure": 18, "reset_rule": "阶段复位", "cap_rule": "1倍", "software_evidence_level": "E3", "decision": "SELECTED", "reason": "基准"},
            {"path_id": "LINEAR", "kind": "LIMITED_LINEAR", "sequence": [1,1,2,2,3,3], "max_multiplier": 3, "total_multiplier": 12, "worst_case_exposure": 36, "reset_rule": "命中复位", "cap_rule": "3倍", "software_evidence_level": "E3", "decision": "REJECTED", "reason": "回撤较高"},
            {"path_id": "PRESS", "kind": "PRESSURE_RELEASE", "sequence": [1,2,3,2,1,1], "max_multiplier": 3, "total_multiplier": 10, "worst_case_exposure": 30, "reset_rule": "6阶复位", "cap_rule": "3倍", "software_evidence_level": "E3", "decision": "REJECTED", "reason": "污染基准"},
            {"path_id": "ADV", "kind": "ADVANCED_STATE", "states": ["START", "LOSS", "RESET"], "transitions": ["START->LOSS", "LOSS->RESET"], "max_multiplier": 2, "total_multiplier": 8, "worst_case_exposure": 24, "reset_rule": "中后复位", "cap_rule": "2倍", "software_evidence_level": "E2", "decision": "PROBE_ONLY", "reason": "待E3", "probe_constraints": {"isolated": True, "single_variable": True, "max_periods": 10, "max_cost": 30}},
        ],
        "more_settings_review": [
            {"category": "MONITORING", "candidate_profile_ids": ["STATE"], "material_configuration": {"mode": "仅开始监控", "periods": 1}, "evidence_level": "E2", "final_decision": "PROBE_ONLY", "reason": "行为核对"},
            {"category": "SIMULATION_REAL_SWITCH", "candidate_profile_ids": ["PROBE"], "material_configuration": {"simulation_losses": 2, "switch_to": "真实投注", "real_cap": 3}, "evidence_level": "E2", "final_decision": "PROBE_ONLY", "reason": "行为核对"},
        ],
        "repeat_guard": {"repeat_count": 1, "penalty_applied": False, "selected_same_fingerprint": False},
        "coverage_debt": {"due_features": ["模拟转真实"], "blocked_features": [], "all_exploration_blocked": False},
        "selection": {"selected_profile_id": "BASE", "selected_funding_path_id": "FLAT", "companion_probe_profile_id": "PROBE", "delivery_mode": "BASELINE_PLUS_EXPERIMENT", "reason": "基准加隔离探针"},
        "recent_delivery_modes": ["BASELINE_ONLY", "BASELINE_ONLY"],
    }


def self_test(cfg: dict[str, Any]) -> list[str]:
    e: list[str] = []
    good = fixture()
    if validate_evidence(good, cfg): e.append("有效夹具被错误拒绝: " + " | ".join(validate_evidence(good, cfg)))
    flat = copy.deepcopy(good); flat["candidate_profiles"] = [flat["candidate_profiles"][0]]; flat["funding_paths"] = [flat["funding_paths"][0]]; flat["more_settings_review"] = []; flat["selection"]["delivery_mode"] = "BASELINE_ONLY"; flat["selection"]["companion_probe_profile_id"] = None
    if not validate_evidence(flat, cfg): e.append("纯平倍空审议未被拒绝")
    adv = copy.deepcopy(good)
    for p in adv["funding_paths"]:
        if p["kind"] == "ADVANCED_STATE": p["decision"] = "SELECTED"
    adv["selection"]["selected_funding_path_id"] = "ADV"
    if not validate_evidence(adv, cfg): e.append("E2高级路径正式入选未被拒绝")
    fake = copy.deepcopy(good); sig = fake["candidate_profiles"][0]["material_signature"]
    for p in fake["candidate_profiles"]: p["material_signature"] = copy.deepcopy(sig)
    if not validate_evidence(fake, cfg): e.append("伪多画像未被拒绝")
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "controller" / "function_orchestration.json")
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--scan-runs", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    try: cfg = load(args.config)
    except Exception as exc:
        print("FUNCTION_ORCHESTRATION_INVALID"); print(f"- 配置读取失败: {exc}"); return 1
    errors = validate_config(cfg)
    if args.evidence:
        try: errors += validate_evidence(load(args.evidence), cfg)
        except Exception as exc: errors.append(f"证据读取失败: {exc}")
    if args.scan_runs:
        for path in sorted((ROOT / "controller" / "runs").glob("*/function_orchestration.json")):
            try: errors += [f"{path.relative_to(ROOT)}: {x}" for x in validate_evidence(load(path), cfg)]
            except Exception as exc: errors.append(f"{path.relative_to(ROOT)}读取失败: {exc}")
    if args.self_test: errors += self_test(cfg)
    if errors:
        print("FUNCTION_ORCHESTRATION_INVALID")
        for x in errors: print(f"- {x}")
        return 1
    print("FUNCTION_ORCHESTRATION_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
