#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
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
DELIVERY_MODES = {"BASELINE_ONLY", "BASELINE_PLUS_EXPERIMENT", "EXPERIMENT_ONLY"}
EVIDENCE = {f"E{i}": i for i in range(8)}
SIGNATURE_KEYS = ("number_logic", "trigger", "execution", "funding", "stop", "time_simulation")
CATEGORY_REQUIRED_KEYS = {
    "MONITORING": ("mode", "trigger_condition", "max_monitor_periods"),
    "PROFIT_LOSS_JUMP": ("metric", "threshold", "target", "jump_count", "reset_rule"),
    "PROFIT_LOSS_STOP": ("metric", "threshold", "action", "reset_rule"),
    "SIMULATION_REAL_SWITCH": ("trigger_condition", "switch_to", "max_real_periods", "reset_rule"),
    "TIME_WINDOW": ("start", "end", "timezone", "outside_action"),
    "CHANGE_RULE": ("rule", "trigger_condition", "reset_rule"),
    "BET_DIRECTION": ("direction", "number_set", "basis"),
    "ROTATION_OR_COMBINATION": ("mode", "order", "restart_rule"),
}


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


def positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def close(a: Any, b: Any) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and math.isclose(float(a), float(b), abs_tol=1e-9)


def rank(level: Any) -> int:
    return EVIDENCE.get(str(level), -1)


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if cfg.get("schema_version") != 1:
        errors.append("配置schema_version必须为1")
    if cfg.get("status") != "ACTIVE":
        errors.append("功能编排配置必须为ACTIVE")
    if set(cfg.get("required_profile_types", [])) != PROFILE_TYPES:
        errors.append("候选画像类型不完整")
    if set(cfg.get("required_layers", [])) != LAYERS:
        errors.append("八层能力不完整")
    if set(cfg.get("required_funding_kinds", [])) != FUNDING_KINDS:
        errors.append("资金四路不完整")
    if cfg.get("minimum_candidate_profiles", 0) < 4:
        errors.append("候选画像下限必须至少4")
    if cfg.get("minimum_material_more_settings", 0) < 2:
        errors.append("更多设置实质候选下限必须至少2")
    if cfg.get("baseline_only_max_consecutive", 99) > 2:
        errors.append("连续纯平倍上限不得超过2批")
    if cfg.get("exploration_window_batches", 99) > 3:
        errors.append("低覆盖探索窗口不得超过3批")
    for key in (
        "ci_block_on_missing_orchestration",
        "ci_block_on_scheme_pr_without_changed_evidence",
        "central_evidence_level_cap_required",
        "central_coverage_ledger_update_required",
        "unverified_feature_formal_selection_forbidden",
        "advanced_with_new_state_first_use_forbidden",
    ):
        if cfg.get(key) is not True:
            errors.append(f"配置未启用: {key}")
    return errors


def validate_probe(item: dict[str, Any], label: str, errors: list[str]) -> None:
    probe = item.get("probe_constraints", {})
    if not isinstance(probe, dict):
        errors.append(f"{label}: probe_constraints必须为对象")
        return
    if probe.get("isolated") is not True or probe.get("single_variable") is not True:
        errors.append(f"{label}: 探针必须隔离且单变量")
    if not isinstance(probe.get("max_periods"), int) or isinstance(probe.get("max_periods"), bool) or not 1 <= probe["max_periods"] <= 30:
        errors.append(f"{label}: 探针期数必须1—30")
    if not positive_number(probe.get("max_cost")):
        errors.append(f"{label}: 探针成本必须为正数")


def validate_funding(item: dict[str, Any], errors: list[str]) -> None:
    pid = str(item.get("path_id", "<unknown>"))
    kind = item.get("kind")
    if kind not in FUNDING_KINDS:
        errors.append(f"{pid}: 未知资金路径{kind!r}")
        return
    if item.get("decision") not in DECISIONS:
        errors.append(f"{pid}: decision无效")
    if item.get("decision") == "SELECTED" and rank(item.get("software_evidence_level")) < 3:
        errors.append(f"{pid}: E3以下资金路径不得正式入选")
    if item.get("decision") == "PROBE_ONLY":
        validate_probe(item, pid, errors)

    unit = item.get("unit_exposure")
    if not positive_number(unit):
        errors.append(f"{pid}: unit_exposure必须为正数")
        unit = 0
    for key in ("max_multiplier", "total_multiplier", "worst_case_exposure"):
        if not positive_number(item.get(key)):
            errors.append(f"{pid}: {key}必须为正数")
    for key in ("reset_rule", "cap_rule", "reason"):
        if not present(item.get(key)):
            errors.append(f"{pid}: 缺少{key}")

    if kind != "ADVANCED_STATE":
        sequence = item.get("sequence")
        if not isinstance(sequence, list) or len(sequence) < 3 or any(not positive_number(x) for x in sequence):
            errors.append(f"{pid}: 必须给出至少3阶正数序列")
            return
        expected_max = max(sequence)
        expected_total = sum(sequence)
        expected_exposure = expected_total * unit
        if not close(item.get("max_multiplier"), expected_max):
            errors.append(f"{pid}: max_multiplier必须等于序列最大值{expected_max}")
        if not close(item.get("total_multiplier"), expected_total):
            errors.append(f"{pid}: total_multiplier必须等于序列总和{expected_total}")
        if unit and not close(item.get("worst_case_exposure"), expected_exposure):
            errors.append(f"{pid}: worst_case_exposure必须等于总倍数×单位暴露={expected_exposure}")
        if kind == "FLAT" and len(set(sequence)) != 1:
            errors.append(f"{pid}: 平倍序列必须恒定")
        if kind == "LIMITED_LINEAR":
            if max(sequence) <= min(sequence) or any(b < a for a, b in zip(sequence, sequence[1:])):
                errors.append(f"{pid}: 有限普通倍投必须实际递增且不下降")
        if kind == "PRESSURE_RELEASE":
            rose = False
            released = False
            for a, b in zip(sequence, sequence[1:]):
                if b > a:
                    rose = True
                if rose and b < a:
                    released = True
            if not released:
                errors.append(f"{pid}: 压力释放路径必须先升压后降压")
    else:
        states = item.get("states")
        transitions = item.get("transitions")
        exposure_path = item.get("exposure_path")
        if not isinstance(states, list) or len(states) < 2 or len(states) != len(set(map(str, states))):
            errors.append(f"{pid}: 高级路径至少2个不重复状态")
        if not isinstance(transitions, list) or len(transitions) < 2 or any(not present(x) for x in transitions):
            errors.append(f"{pid}: 高级路径至少2条明确转移")
        if not isinstance(exposure_path, list) or len(exposure_path) < 2 or any(not positive_number(x) for x in exposure_path):
            errors.append(f"{pid}: 高级路径必须给出至少2步最坏暴露路径")
            return
        expected_max = max(exposure_path)
        expected_total = sum(exposure_path)
        expected_exposure = expected_total * unit
        if not close(item.get("max_multiplier"), expected_max):
            errors.append(f"{pid}: max_multiplier必须等于暴露路径最大值{expected_max}")
        if not close(item.get("total_multiplier"), expected_total):
            errors.append(f"{pid}: total_multiplier必须等于暴露路径总和{expected_total}")
        if unit and not close(item.get("worst_case_exposure"), expected_exposure):
            errors.append(f"{pid}: worst_case_exposure必须等于暴露路径总倍数×单位暴露={expected_exposure}")


def signature(profile: dict[str, Any]) -> tuple[str, ...]:
    value = profile.get("material_signature", {})
    if not isinstance(value, dict):
        return tuple("" for _ in SIGNATURE_KEYS)
    return tuple(str(value.get(key, "")).strip() for key in SIGNATURE_KEYS)


def canonical_fingerprint(profile: dict[str, Any]) -> str:
    return "|".join(signature(profile))


def required_configuration(category: str, config: Any, errors: list[str]) -> None:
    if not isinstance(config, dict):
        errors.append(f"{category}: material_configuration必须为对象")
        return
    if not material(config):
        errors.append(f"{category}: 不能只写关闭，必须给出候选参数")
    for key in CATEGORY_REQUIRED_KEYS[category]:
        if not present(config.get(key)):
            errors.append(f"{category}: material_configuration缺少{key}")


def validate_evidence(data: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("证据schema_version必须为1")
    if data.get("task_type") != "STANDARD_SCHEME_TASK":
        errors.append("task_type必须为STANDARD_SCHEME_TASK")
    if data.get("status") not in {"DIRECTOR_COMPLETE", "CONTRACT_FROZEN", "VALIDATED", "COMPLETED"}:
        errors.append("证据状态无效")

    profiles = data.get("candidate_profiles", [])
    if not isinstance(profiles, list):
        profiles = []
        errors.append("candidate_profiles必须为数组")
    if len(profiles) < cfg.get("minimum_candidate_profiles", 4):
        errors.append("候选画像不足4个")
    types = {p.get("profile_type") for p in profiles if isinstance(p, dict)}
    if PROFILE_TYPES - types:
        errors.append(f"缺少画像类型: {sorted(PROFILE_TYPES - types)}")

    ids: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    signatures: set[tuple[str, ...]] = set()
    selected_profiles: list[str] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            errors.append("画像必须为对象")
            continue
        pid = str(profile.get("profile_id", "")).strip()
        if not pid:
            errors.append("画像缺少profile_id")
            continue
        if pid in ids:
            errors.append(f"画像ID重复: {pid}")
        ids.add(pid)
        by_id[pid] = profile
        if profile.get("profile_type") not in PROFILE_TYPES:
            errors.append(f"{pid}: profile_type无效")
        if profile.get("decision") not in DECISIONS:
            errors.append(f"{pid}: decision无效")
        if profile.get("decision") == "SELECTED":
            selected_profiles.append(pid)
        if not present(profile.get("reason")):
            errors.append(f"{pid}: 缺少理由")

        layers = profile.get("layers", {})
        if not isinstance(layers, dict) or set(layers) != LAYERS:
            errors.append(f"{pid}: 必须完整填写A—H八层")
        else:
            for layer_id, layer in layers.items():
                if not isinstance(layer, dict):
                    errors.append(f"{pid}.{layer_id}: 必须为对象")
                    continue
                for key in ("relevant", "candidates", "final_enabled", "decision_reason", "evidence_level"):
                    if key not in layer:
                        errors.append(f"{pid}.{layer_id}: 缺少{key}")
                if not isinstance(layer.get("relevant"), bool):
                    errors.append(f"{pid}.{layer_id}: relevant必须为布尔值")
                if not isinstance(layer.get("final_enabled"), bool):
                    errors.append(f"{pid}.{layer_id}: final_enabled必须为布尔值")
                candidates = layer.get("candidates")
                if not isinstance(candidates, list):
                    errors.append(f"{pid}.{layer_id}: candidates必须为数组")
                elif layer.get("relevant") is True and (not candidates or any(not present(x) for x in candidates)):
                    errors.append(f"{pid}.{layer_id}: relevant=true时必须有具体候选")
                if layer.get("relevant") is False and layer.get("final_enabled") is True:
                    errors.append(f"{pid}.{layer_id}: 不相关层不得启用")
                if not present(layer.get("decision_reason")):
                    errors.append(f"{pid}.{layer_id}: 理由不能为空")
                if rank(layer.get("evidence_level")) < 0:
                    errors.append(f"{pid}.{layer_id}: 证据等级无效")
                if profile.get("decision") == "SELECTED" and layer.get("final_enabled") is True and rank(layer.get("evidence_level")) < 3:
                    errors.append(f"{pid}.{layer_id}: E3以下功能不得正式启用")

        current_signature = signature(profile)
        if any(not value for value in current_signature):
            errors.append(f"{pid}: 六维实质签名必须全部填写")
        else:
            signatures.add(current_signature)
        if profile.get("profile_type") == "LOW_COVERAGE_PROBE":
            if profile.get("decision") not in {"PROBE_ONLY", "REJECTED"}:
                errors.append(f"{pid}: 低覆盖画像只能探针或淘汰")
            if profile.get("decision") == "PROBE_ONLY":
                validate_probe(profile, pid, errors)

    if len(signatures) < 3:
        errors.append("至少需要3个实质不同的候选签名，禁止只换号码或期数")
    if len(selected_profiles) != 1:
        errors.append(f"必须且只能有1个正式SELECTED画像，当前{len(selected_profiles)}个")

    paths = data.get("funding_paths", [])
    if not isinstance(paths, list):
        paths = []
        errors.append("funding_paths必须为数组")
    kinds = {p.get("kind") for p in paths if isinstance(p, dict)}
    if FUNDING_KINDS - kinds:
        errors.append(f"资金四路不完整: {sorted(FUNDING_KINDS - kinds)}")
    path_by_id: dict[str, dict[str, Any]] = {}
    selected_paths: list[str] = []
    for path in paths:
        if not isinstance(path, dict):
            errors.append("资金路径必须为对象")
            continue
        pid = str(path.get("path_id", "")).strip()
        if not pid:
            errors.append("资金路径缺少path_id")
            continue
        if pid in path_by_id:
            errors.append(f"资金路径ID重复: {pid}")
        path_by_id[pid] = path
        if path.get("decision") == "SELECTED":
            selected_paths.append(pid)
        validate_funding(path, errors)
    if len(selected_paths) != 1:
        errors.append(f"必须且只能有1条正式SELECTED资金路径，当前{len(selected_paths)}条")

    settings = data.get("more_settings_review", [])
    if not isinstance(settings, list):
        settings = []
        errors.append("more_settings_review必须为数组")
    material_categories: set[str] = set()
    seen_categories: set[str] = set()
    for item in settings:
        if not isinstance(item, dict):
            errors.append("更多设置记录必须为对象")
            continue
        category = item.get("category")
        if category not in SETTING_CATEGORIES:
            errors.append(f"未知更多设置类别: {category!r}")
            continue
        if category in seen_categories:
            errors.append(f"更多设置类别重复: {category}")
        seen_categories.add(category)
        required_configuration(category, item.get("material_configuration"), errors)
        if material(item.get("material_configuration")):
            material_categories.add(category)
        refs = item.get("candidate_profile_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{category}: 必须关联画像")
        else:
            unknown = set(refs) - set(by_id)
            if unknown:
                errors.append(f"{category}: 关联未知画像{sorted(unknown)}")
        if item.get("final_decision") not in DECISIONS:
            errors.append(f"{category}: final_decision无效")
        if not present(item.get("reason")):
            errors.append(f"{category}: 缺少理由")
        if rank(item.get("evidence_level")) < 0:
            errors.append(f"{category}: 证据等级无效")
        if item.get("final_decision") == "SELECTED" and rank(item.get("evidence_level")) < 3:
            errors.append(f"{category}: E3以下不得正式入选")
    if len(material_categories) < cfg.get("minimum_material_more_settings", 2):
        errors.append("实质更多设置候选不足2类")

    repeat = data.get("repeat_guard", {})
    if not isinstance(repeat, dict):
        repeat = {}
        errors.append("repeat_guard必须为对象")
    history_fingerprints = repeat.get("last_three_fingerprints", [])
    if not isinstance(history_fingerprints, list) or len(history_fingerprints) > 3:
        errors.append("last_three_fingerprints必须为最多3项数组")
        history_fingerprints = []
    selected_profile_id = data.get("selection", {}).get("selected_profile_id")
    selected_profile = by_id.get(selected_profile_id, {})
    fingerprint = canonical_fingerprint(selected_profile) if selected_profile else ""
    if repeat.get("fingerprint") != fingerprint:
        errors.append("repeat_guard.fingerprint必须等于最终画像六维签名")
    trailing = 0
    for previous in reversed(history_fingerprints):
        if previous == fingerprint:
            trailing += 1
        else:
            break
    if repeat.get("repeat_count") != trailing:
        errors.append(f"repeat_count必须等于历史连续重复数{trailing}")
    if trailing >= 2:
        if repeat.get("penalty_applied") is not True:
            errors.append("连续两批同画像后本批必须施加重复惩罚")
        if repeat.get("selected_same_fingerprint") is True and not present(repeat.get("override_reason")):
            errors.append("第三次仍入选相同画像必须有证据化例外理由")

    coverage = data.get("coverage_debt", {})
    due = coverage.get("due_features", []) if isinstance(coverage, dict) else []
    blocked = coverage.get("blocked_features", []) if isinstance(coverage, dict) else []
    represented: set[str] = set()
    for profile in profiles:
        if isinstance(profile, dict) and isinstance(profile.get("features"), list):
            represented.update(profile["features"])
    blocked_ids = {
        item.get("feature_id")
        for item in blocked
        if isinstance(item, dict) and present(item.get("reason")) and present(item.get("evidence_ref"))
    }
    for feature in due:
        if feature not in represented and feature not in blocked_ids:
            errors.append(f"覆盖债务未解决: {feature}")

    selection = data.get("selection", {})
    if not isinstance(selection, dict):
        selection = {}
        errors.append("selection必须为对象")
    selected_profile_id = selection.get("selected_profile_id")
    selected_path_id = selection.get("selected_funding_path_id")
    if selected_profile_id not in by_id or by_id.get(selected_profile_id, {}).get("decision") != "SELECTED":
        errors.append("最终画像不存在或未标记SELECTED")
    if selected_path_id not in path_by_id or path_by_id.get(selected_path_id, {}).get("decision") != "SELECTED":
        errors.append("最终资金路径不存在或未标记SELECTED")
    if not present(selection.get("reason")):
        errors.append("最终选择缺少理由")
    if selection.get("delivery_mode") not in DELIVERY_MODES:
        errors.append("delivery_mode无效")
    companion = selection.get("companion_probe_profile_id")
    if companion and (companion not in by_id or by_id[companion].get("decision") != "PROBE_ONLY"):
        errors.append("配套探针不存在或未标记PROBE_ONLY")

    recent = data.get("recent_delivery_modes", [])
    if not isinstance(recent, list) or any(mode not in DELIVERY_MODES for mode in recent):
        errors.append("recent_delivery_modes无效")
        recent = []
    if selection.get("delivery_mode") == "BASELINE_ONLY":
        baseline_streak = 0
        for mode in reversed(recent):
            if mode == "BASELINE_ONLY":
                baseline_streak += 1
            else:
                break
        if baseline_streak >= cfg.get("baseline_only_max_consecutive", 2):
            all_blocked = coverage.get("all_exploration_blocked") is True and bool(due) and len(blocked_ids) >= len(due)
            if not all_blocked and not companion:
                errors.append("连续纯平倍达到上限，必须交付非基准实验或隔离探针")

    selected = by_id.get(selected_profile_id, {})
    selected_path = path_by_id.get(selected_path_id, {})
    if selected.get("first_use") is True and selected.get("new_state_features") and selected_path.get("kind") == "ADVANCED_STATE":
        errors.append("新状态功能首次启用不得同时正式启用高级状态资金路径")
    return errors


def fixture() -> dict[str, Any]:
    def layer(enabled: bool = False, evidence: str = "E3") -> dict[str, Any]:
        return {
            "relevant": True,
            "candidates": ["具体候选"],
            "final_enabled": enabled,
            "decision_reason": "已完成实质审议",
            "evidence_level": evidence,
        }

    base_layers = {layer_id: layer(layer_id in "ADEFH") for layer_id in "ABCDEFGH"}

    def profile(
        pid: str,
        profile_type: str,
        values: list[str],
        decision: str,
        features: list[str],
        probe: bool = False,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "profile_id": pid,
            "profile_type": profile_type,
            "decision": decision,
            "reason": "六维结构有实质差异",
            "features": features,
            "layers": copy.deepcopy(base_layers),
            "material_signature": dict(zip(SIGNATURE_KEYS, values)),
            "first_use": False,
            "new_state_features": [],
        }
        if probe:
            item["probe_constraints"] = {"isolated": True, "single_variable": True, "max_periods": 12, "max_cost": 36}
        return item

    profiles = [
        profile("BASE", "BASELINE", ["条件频率", "立即", "轮投", "平倍", "30期硬停止", "不限时"], "SELECTED", ["STATIC_NUMBER_LOGIC"]),
        profile("STATE", "STATE", ["条件频率", "监控1期", "轮投", "平倍", "亏损停止", "不限时"], "REJECTED", ["MONITORING"]),
        profile("FUND", "EXECUTION_OR_FUNDING", ["条件频率", "立即", "轮投", "压力释放", "3倍封顶", "不限时"], "REJECTED", ["FUNDING_PRESSURE_RELEASE"]),
        profile("PROBE", "LOW_COVERAGE_PROBE", ["固定对照", "模拟输2次", "单方案", "平倍", "12期硬停止", "模拟转真实"], "PROBE_ONLY", ["SIMULATION_REAL_SWITCH"], True),
    ]
    profiles[1]["layers"]["B"] = layer(True, "E2")
    profiles[3]["layers"]["G"] = layer(True, "E2")
    selected_fingerprint = "|".join(signature(profiles[0]))

    return {
        "schema_version": 1,
        "run_id": "SELF-TEST",
        "task_type": "STANDARD_SCHEME_TASK",
        "status": "CONTRACT_FROZEN",
        "candidate_profiles": profiles,
        "funding_paths": [
            {"path_id": "FLAT", "kind": "FLAT", "sequence": [1, 1, 1, 1, 1, 1], "unit_exposure": 3, "max_multiplier": 1, "total_multiplier": 6, "worst_case_exposure": 18, "reset_rule": "阶段复位", "cap_rule": "1倍", "software_evidence_level": "E3", "decision": "SELECTED", "reason": "基准"},
            {"path_id": "LINEAR", "kind": "LIMITED_LINEAR", "sequence": [1, 1, 2, 2, 3, 3], "unit_exposure": 3, "max_multiplier": 3, "total_multiplier": 12, "worst_case_exposure": 36, "reset_rule": "命中复位", "cap_rule": "3倍", "software_evidence_level": "E2", "decision": "REJECTED", "reason": "回撤较高"},
            {"path_id": "PRESS", "kind": "PRESSURE_RELEASE", "sequence": [1, 2, 3, 2, 1, 1], "unit_exposure": 3, "max_multiplier": 3, "total_multiplier": 10, "worst_case_exposure": 30, "reset_rule": "6阶复位", "cap_rule": "3倍", "software_evidence_level": "E2", "decision": "REJECTED", "reason": "污染基准"},
            {"path_id": "ADV", "kind": "ADVANCED_STATE", "states": ["START", "LOSS", "RESET"], "transitions": ["START->LOSS", "LOSS->RESET"], "exposure_path": [1, 2, 2, 1, 1, 1], "unit_exposure": 3, "max_multiplier": 2, "total_multiplier": 8, "worst_case_exposure": 24, "reset_rule": "中后复位", "cap_rule": "2倍", "software_evidence_level": "E2", "decision": "PROBE_ONLY", "reason": "待E3", "probe_constraints": {"isolated": True, "single_variable": True, "max_periods": 10, "max_cost": 30}},
        ],
        "more_settings_review": [
            {"category": "MONITORING", "candidate_profile_ids": ["STATE"], "material_configuration": {"mode": "仅开始监控", "trigger_condition": "连续未中1期", "max_monitor_periods": 2}, "evidence_level": "E2", "final_decision": "PROBE_ONLY", "reason": "行为核对"},
            {"category": "SIMULATION_REAL_SWITCH", "candidate_profile_ids": ["PROBE"], "material_configuration": {"trigger_condition": "模拟连续输2次", "switch_to": "真实投注", "max_real_periods": 3, "reset_rule": "真实阶段结束回模拟"}, "evidence_level": "E2", "final_decision": "PROBE_ONLY", "reason": "行为核对"},
        ],
        "repeat_guard": {"fingerprint": selected_fingerprint, "last_three_fingerprints": ["旧画像A", "旧画像B"], "repeat_count": 0, "penalty_applied": False, "selected_same_fingerprint": False},
        "coverage_debt": {"due_features": ["SIMULATION_REAL_SWITCH"], "blocked_features": [], "all_exploration_blocked": False},
        "selection": {"selected_profile_id": "BASE", "selected_funding_path_id": "FLAT", "companion_probe_profile_id": "PROBE", "delivery_mode": "BASELINE_PLUS_EXPERIMENT", "reason": "基准加隔离探针"},
        "recent_delivery_modes": ["BASELINE_ONLY", "BASELINE_ONLY"],
    }


def self_test(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    good = fixture()
    good_errors = validate_evidence(good, cfg)
    if good_errors:
        errors.append("有效夹具被错误拒绝: " + " | ".join(good_errors))

    flat = copy.deepcopy(good)
    flat["candidate_profiles"] = [flat["candidate_profiles"][0]]
    flat["funding_paths"] = [flat["funding_paths"][0]]
    flat["more_settings_review"] = []
    flat["selection"]["delivery_mode"] = "BASELINE_ONLY"
    flat["selection"]["companion_probe_profile_id"] = None
    if not validate_evidence(flat, cfg):
        errors.append("纯平倍空审议未被拒绝")

    advanced = copy.deepcopy(good)
    for path in advanced["funding_paths"]:
        path["decision"] = "SELECTED" if path["kind"] == "ADVANCED_STATE" else "REJECTED"
    advanced["selection"]["selected_funding_path_id"] = "ADV"
    if not validate_evidence(advanced, cfg):
        errors.append("E2高级路径正式入选未被拒绝")

    fake = copy.deepcopy(good)
    first_signature = fake["candidate_profiles"][0]["material_signature"]
    for profile in fake["candidate_profiles"]:
        profile["material_signature"] = copy.deepcopy(first_signature)
    fake["repeat_guard"]["fingerprint"] = "|".join(signature(fake["candidate_profiles"][0]))
    if not validate_evidence(fake, cfg):
        errors.append("伪多画像未被拒绝")

    empty_layer = copy.deepcopy(good)
    empty_layer["candidate_profiles"][0]["layers"]["B"]["candidates"] = []
    if not validate_evidence(empty_layer, cfg):
        errors.append("相关层无具体候选未被拒绝")

    bad_exposure = copy.deepcopy(good)
    bad_exposure["funding_paths"][1]["worst_case_exposure"] = 1
    if not validate_evidence(bad_exposure, cfg):
        errors.append("错误资金暴露未被拒绝")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "controller" / "function_orchestration.json")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--scan-runs", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        config = load(args.config)
    except Exception as exc:
        print("FUNCTION_ORCHESTRATION_INVALID")
        print(f"- 配置读取失败: {exc}")
        return 1
    errors = validate_config(config)
    if args.evidence:
        try:
            errors += validate_evidence(load(args.evidence), config)
        except Exception as exc:
            errors.append(f"证据读取失败: {exc}")
    if args.scan_runs:
        for path in sorted((ROOT / "controller" / "runs").glob("*/function_orchestration.json")):
            try:
                errors += [f"{path.relative_to(ROOT)}: {error}" for error in validate_evidence(load(path), config)]
            except Exception as exc:
                errors.append(f"{path.relative_to(ROOT)}读取失败: {exc}")
    if args.self_test:
        errors += self_test(config)
    if errors:
        print("FUNCTION_ORCHESTRATION_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("FUNCTION_ORCHESTRATION_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
