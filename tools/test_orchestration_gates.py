#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validate_function_orchestration as core
import validate_orchestration_scoring as scoring
import validate_scheme_orchestration_gate as gate

RUN_ID = "RL_ADV_20260806"
EVIDENCE_PATH = ROOT / "controller" / "runs" / RUN_ID / "function_orchestration.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_ledger(branch: dict) -> dict:
    """Reconstruct the immutable ledger read by RL_ADV_20260806.

    Adversarial tests must not reinterpret a valid historical run against the
    mutable current ledger. The previous test mixed current-ledger state with
    a partially rewritten fixture, which made the supposedly valid fixture
    internally inconsistent after every legitimate ledger advance.
    """
    base = copy.deepcopy(branch)
    base["sequence"] = 0
    base["last_run_id"] = None
    base["recent_delivery_modes"] = ["BASELINE_ONLY", "BASELINE_ONLY"]
    base["baseline_only_streak"] = 2
    base["recent_selected_fingerprints"] = [
        "cold_warm_omission|immediate|top_rotation|flat|18_period_hard_stop|none",
        "first_order_transition|immediate|top_rotation|flat|30_period_hard_stop|none",
    ]
    base["next_due_features"] = [
        "MONITORING",
        "FUNDING_ADVANCED_STATE",
        "SIMULATION_REAL_SWITCH",
    ]
    previous = {
        "MONITORING": 3,
        "FUNDING_ADVANCED_STATE": 3,
        "SIMULATION_REAL_SWITCH": 3,
    }
    for feature_id, count in previous.items():
        entry = base["features"][feature_id]
        entry["last_material_candidate_run"] = None
        entry["last_selected_run"] = None
        entry["consecutive_not_material"] = count
        entry.pop("blocked_reason", None)
        entry.pop("blocked_evidence_ref", None)
    return base


def expect_error(label: str, errors: list[str], failures: list[str]) -> None:
    if not errors:
        failures.append(label)


def main() -> int:
    config = load(ROOT / "controller" / "function_orchestration.json")
    registry = load(ROOT / "controller" / "feature_evidence_registry.json")
    branch_ledger = load(ROOT / "controller" / "function_coverage_ledger.json")
    base_ledger = baseline_ledger(branch_ledger)
    evidence = load(EVIDENCE_PATH)
    failures: list[str] = []

    core_errors = core.validate_evidence(evidence, config)
    if core_errors:
        failures.append("正式证据未通过核心校验: " + " | ".join(core_errors))
    registry_errors = gate.validate_registry_and_ledger(evidence, registry, base_ledger)
    if registry_errors:
        failures.append("正式证据未通过注册表/基线账本校验: " + " | ".join(registry_errors))
    score_errors = scoring.validate_evidence(evidence)
    if score_errors:
        failures.append("正式证据未通过评分校验: " + " | ".join(score_errors))

    branch_errors = gate.validate_branch_ledger(
        [
            "controller/function_coverage_ledger.json",
            f"controller/runs/{RUN_ID}/function_orchestration.json",
        ],
        [EVIDENCE_PATH],
        base_ledger,
        branch_ledger,
    )
    if branch_errors:
        failures.append("有效账本迁移被错误拒绝: " + " | ".join(branch_errors))

    inflated = copy.deepcopy(evidence)
    state_claim = inflated["candidate_profiles"][1]["feature_evidence"][0]
    state_claim["claimed_level"] = "E3"
    expect_error(
        "监控证据从E1伪造为E3未被拒绝",
        gate.validate_registry_and_ledger(inflated, registry, base_ledger),
        failures,
    )

    hidden_debt = copy.deepcopy(evidence)
    hidden_debt["coverage_debt"]["due_features"] = []
    expect_error(
        "清空中央到期功能未被拒绝",
        gate.validate_registry_and_ledger(hidden_debt, registry, base_ledger),
        failures,
    )

    stale_ledger = copy.deepcopy(base_ledger)
    expect_error(
        "未更新中央账本未被拒绝",
        gate.validate_branch_ledger(
            [
                "controller/function_coverage_ledger.json",
                f"controller/runs/{RUN_ID}/function_orchestration.json",
            ],
            [EVIDENCE_PATH],
            base_ledger,
            stale_ledger,
        ),
        failures,
    )

    missing_score = copy.deepcopy(evidence)
    del missing_score["candidate_profiles"][0]["scorecard"]
    expect_error("缺少画像评分未被拒绝", scoring.validate_evidence(missing_score), failures)

    hidden_eligible = copy.deepcopy(evidence)
    hidden_eligible["candidate_profiles"][0]["eligible"] = False
    hidden_eligible["candidate_profiles"][0]["hard_blockers"] = []
    expect_error("达到E3的画像被无证据标记不合格未被拒绝", scoring.validate_evidence(hidden_eligible), failures)

    advanced_selected = copy.deepcopy(evidence)
    for path in advanced_selected["funding_paths"]:
        path["decision"] = "SELECTED" if path["kind"] == "ADVANCED_STATE" else "REJECTED"
    advanced_selected["selection"]["selected_funding_path_id"] = "ADV"
    expect_error("E2高级倍投被正式入选未被拒绝", core.validate_evidence(advanced_selected, config), failures)

    fake_profiles = copy.deepcopy(evidence)
    first_signature = fake_profiles["candidate_profiles"][0]["material_signature"]
    for profile in fake_profiles["candidate_profiles"]:
        profile["material_signature"] = copy.deepcopy(first_signature)
    fake_profiles["repeat_guard"]["fingerprint"] = "|".join(
        first_signature[key] for key in core.SIGNATURE_KEYS
    )
    expect_error("伪多画像未被拒绝", core.validate_evidence(fake_profiles, config), failures)

    if failures:
        print("ORCHESTRATION_GATE_TESTS_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("ORCHESTRATION_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
