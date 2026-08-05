#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validate_function_orchestration as core
import validate_orchestration_scoring as scoring
import validate_scheme_orchestration_gate as gate


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def rank(level: str) -> int:
    return int(level[1:])


def score(evidence_rank: int, total_bias: int = 0, exposure_penalty: int = 2) -> dict:
    components = {
        "problem_fit": 8 + total_bias,
        "software_evidence": min(10, max(0, evidence_rank * 2)),
        "risk_fit": 7,
        "novelty": 5,
        "explanation_value": 7,
        "coverage_value": 5,
        "exposure_penalty": exposure_penalty,
        "unverified_penalty": max(0, (3 - evidence_rank) * 2),
        "complexity_penalty": 2,
        "logic_confusion_penalty": 1,
    }
    notes = {key: "夹具评分理由" for key in components}
    total = sum(components[key] for key in scoring.POSITIVE) - sum(components[key] for key in scoring.PENALTY)
    return {"components": components, "notes": notes, "total": total}


def registry_map(registry: dict) -> dict[str, dict]:
    return {item["feature_id"]: item for item in registry["features"]}


def apply_registry_to_profile(profile: dict, registry: dict[str, dict]) -> int:
    claims: dict[str, dict] = {}
    for feature_id in profile["features"]:
        item = registry[feature_id]
        claims[feature_id] = {
            "feature_id": feature_id,
            "claimed_level": item["max_formal_level"],
            "evidence_refs": item["evidence_refs"],
        }
    profile["feature_evidence"] = list(claims.values())
    for layer in profile["layers"].values():
        features = layer.get("feature_ids", [])
        if features:
            layer["evidence_level"] = min(
                (registry[feature]["max_formal_level"] for feature in features),
                key=rank,
            )
    levels = [rank(claim["claimed_level"]) for claim in profile["feature_evidence"]]
    levels += [
        rank(layer["evidence_level"])
        for layer in profile["layers"].values()
        if layer.get("final_enabled") is True
    ]
    return min(levels)


def build_valid() -> tuple[dict, dict, dict]:
    registry = load("controller/feature_evidence_registry.json")
    ledger = load("controller/function_coverage_ledger.json")
    central = registry_map(registry)
    evidence = core.fixture()

    profile_ranks: dict[str, int] = {}
    for profile in evidence["candidate_profiles"]:
        profile_rank = apply_registry_to_profile(profile, central)
        profile_ranks[profile["profile_id"]] = profile_rank
        profile["eligible"] = profile["decision"] == "SELECTED"
        profile["eligibility_reason"] = "正式基准可入选" if profile["eligible"] else "证据未达E3，仅比较或探针"
        profile["hard_blockers"] = []
        profile["scorecard"] = score(profile_rank, 1 if profile["profile_id"] == "BASE" else 0)

    path_feature = {
        "FLAT": "FUNDING_FLAT",
        "LIMITED_LINEAR": "FUNDING_LIMITED_LINEAR",
        "PRESSURE_RELEASE": "FUNDING_PRESSURE_RELEASE",
        "ADVANCED_STATE": "FUNDING_ADVANCED_STATE",
    }
    exposure_penalties = {"FLAT": 1, "ADVANCED_STATE": 2, "PRESSURE_RELEASE": 3, "LIMITED_LINEAR": 4}
    for path in evidence["funding_paths"]:
        feature = central[path_feature[path["kind"]]]
        path_rank = rank(feature["max_formal_level"])
        path["software_evidence_level"] = feature["max_formal_level"]
        path["evidence_refs"] = feature["evidence_refs"]
        path["eligible"] = path["decision"] == "SELECTED"
        path["eligibility_reason"] = "正式基准可入选" if path["eligible"] else "证据未达E3或未选"
        path["hard_blockers"] = []
        path["scorecard"] = score(
            path_rank,
            1 if path["kind"] == "FLAT" else 0,
            exposure_penalties[path["kind"]],
        )

    setting_feature = {
        "MONITORING": "MONITORING",
        "SIMULATION_REAL_SWITCH": "SIMULATION_REAL_SWITCH",
    }
    for setting in evidence["more_settings_review"]:
        feature = central[setting_feature[setting["category"]]]
        setting["evidence_refs"] = feature["evidence_refs"]
        setting["evidence_level"] = feature["max_formal_level"]

    evidence["coverage_debt"]["due_features"] = ledger["next_due_features"]
    evidence["recent_delivery_modes"] = ledger["recent_delivery_modes"]
    evidence["repeat_guard"]["last_three_fingerprints"] = ledger["recent_selected_fingerprints"]
    fingerprint = evidence["repeat_guard"]["fingerprint"]
    trailing = 0
    for previous in reversed(ledger["recent_selected_fingerprints"]):
        if previous == fingerprint:
            trailing += 1
        else:
            break
    evidence["repeat_guard"]["repeat_count"] = trailing
    evidence["ledger_update"] = {
        "from_sequence": ledger["sequence"],
        "to_sequence": ledger["sequence"] + 1,
        "outcomes": {feature: {"outcome": "CANDIDATE", "evidence_ref": "SELF-TEST"} for feature in ledger["next_due_features"]},
        "next_due_features": ["PROFIT_LOSS_JUMP", "PROFIT_LOSS_STOP", "TIME_WINDOW"],
    }
    evidence["selection"]["score_override_reason"] = ""
    evidence["selection"]["score_override_evidence_refs"] = []
    return evidence, registry, ledger


def advanced_ledger(base: dict, evidence: dict) -> dict:
    branch = copy.deepcopy(base)
    update = evidence["ledger_update"]
    branch["sequence"] = update["to_sequence"]
    branch["last_run_id"] = evidence["run_id"]
    branch["next_due_features"] = update["next_due_features"]
    window = branch["selection_window"]
    mode = evidence["selection"]["delivery_mode"]
    branch["recent_delivery_modes"] = (base["recent_delivery_modes"] + [mode])[-window:]
    branch["baseline_only_streak"] = 0 if mode != "BASELINE_ONLY" else base["baseline_only_streak"] + 1
    fingerprint = evidence["repeat_guard"]["fingerprint"]
    branch["recent_selected_fingerprints"] = (base["recent_selected_fingerprints"] + [fingerprint])[-window:]
    for feature in base["next_due_features"]:
        entry = branch["features"][feature]
        entry["last_material_candidate_run"] = evidence["run_id"]
        entry["consecutive_not_material"] = 0
    return branch


def main() -> int:
    evidence, registry, ledger = build_valid()
    errors: list[str] = []
    core_errors = core.validate_evidence(evidence, load("controller/function_orchestration.json"))
    if core_errors:
        errors.append("有效综合夹具未通过核心校验: " + " | ".join(core_errors))
    gate_errors = gate.validate_registry_and_ledger(evidence, registry, ledger)
    if gate_errors:
        errors.append("有效综合夹具未通过证据/基线账本校验: " + " | ".join(gate_errors))
    score_errors = scoring.validate_evidence(evidence)
    if score_errors:
        errors.append("有效综合夹具未通过评分校验: " + " | ".join(score_errors))

    with tempfile.TemporaryDirectory() as temp_dir:
        evidence_path = Path(temp_dir) / "function_orchestration.json"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
        branch_ledger = advanced_ledger(ledger, evidence)
        branch_errors = gate.validate_branch_ledger(
            ["controller/function_coverage_ledger.json", "controller/runs/SELF-TEST/function_orchestration.json"],
            [evidence_path], ledger, branch_ledger,
        )
        if branch_errors:
            errors.append("有效账本迁移被错误拒绝: " + " | ".join(branch_errors))
        stale_errors = gate.validate_branch_ledger(
            ["controller/function_coverage_ledger.json", "controller/runs/SELF-TEST/function_orchestration.json"],
            [evidence_path], ledger, ledger,
        )
        if not stale_errors:
            errors.append("未更新中央账本未被拒绝")

    inflated = copy.deepcopy(evidence)
    state = next(item for item in inflated["candidate_profiles"] if item["profile_id"] == "STATE")
    monitor = next(item for item in state["feature_evidence"] if item["feature_id"] == "MONITORING")
    monitor["claimed_level"] = "E3"
    if not gate.validate_registry_and_ledger(inflated, registry, ledger):
        errors.append("监控证据从E1伪造为E3未被拒绝")

    hidden_debt = copy.deepcopy(evidence)
    hidden_debt["coverage_debt"]["due_features"] = []
    if not gate.validate_registry_and_ledger(hidden_debt, registry, ledger):
        errors.append("清空中央到期功能未被拒绝")

    hidden_history = copy.deepcopy(evidence)
    hidden_history["recent_delivery_modes"] = []
    hidden_history["repeat_guard"]["last_three_fingerprints"] = []
    if not gate.validate_registry_and_ledger(hidden_history, registry, ledger):
        errors.append("清空中央最近模式与指纹未被拒绝")

    future_ledger = advanced_ledger(ledger, evidence)
    if gate.validate_registry(evidence, registry):
        errors.append("历史证据在未来账本环境下不应失效")
    if not gate.validate_ledger_transition(evidence, future_ledger):
        errors.append("旧证据错误地通过了未来账本迁移校验")

    missing_score = copy.deepcopy(evidence)
    del missing_score["candidate_profiles"][0]["scorecard"]
    if not scoring.validate_evidence(missing_score):
        errors.append("缺少画像评分未被拒绝")

    lower_selected = copy.deepcopy(evidence)
    base = next(item for item in lower_selected["candidate_profiles"] if item["profile_id"] == "BASE")
    state = next(item for item in lower_selected["candidate_profiles"] if item["profile_id"] == "STATE")
    base["scorecard"] = score(3, -3)
    state["eligible"] = True
    state["scorecard"] = score(3, 2)
    for claim in state["feature_evidence"]:
        claim["claimed_level"] = "E3"
    for layer in state["layers"].values():
        if layer.get("final_enabled"):
            layer["evidence_level"] = "E3"
    if not scoring.validate_evidence(lower_selected):
        errors.append("低分画像无证据覆盖仍入选未被拒绝")

    hidden_eligible = copy.deepcopy(evidence)
    hidden_eligible["candidate_profiles"][0]["eligible"] = False
    hidden_eligible["candidate_profiles"][0]["hard_blockers"] = []
    if not scoring.validate_evidence(hidden_eligible):
        errors.append("达到E3的画像被无证据标记不合格未被拒绝")

    inflated_score = copy.deepcopy(evidence)
    state = next(item for item in inflated_score["candidate_profiles"] if item["profile_id"] == "STATE")
    state["scorecard"]["components"]["software_evidence"] = 8
    state["scorecard"]["total"] += 6
    if not scoring.validate_evidence(inflated_score):
        errors.append("低证据画像夸大software_evidence评分未被拒绝")

    if errors:
        print("ORCHESTRATION_GATE_TESTS_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ORCHESTRATION_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
