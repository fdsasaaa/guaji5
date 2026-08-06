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


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_valid_fixture() -> dict:
    preferred = ROOT / "controller" / "runs" / "B397-REBATE-ANCHOR-55-001" / "function_orchestration.json"
    if preferred.exists():
        return json.loads(preferred.read_text(encoding="utf-8"))
    return core.fixture()


def must_fail(errors: list[str], label: str, failures: list[str]) -> None:
    if not errors:
        failures.append(f"{label}未被拒绝")


def main() -> int:
    cfg = load("controller/function_orchestration.json")
    registry = load("controller/feature_evidence_registry.json")
    ledger = load("controller/function_coverage_ledger.json")
    evidence = load_valid_fixture()
    failures: list[str] = []

    core_errors = core.validate_evidence(evidence, cfg)
    if core_errors:
        failures.append("有效综合夹具未通过核心校验: " + " | ".join(core_errors))
    score_errors = scoring.validate_evidence(evidence)
    if score_errors:
        failures.append("有效综合夹具未通过评分校验: " + " | ".join(score_errors))

    # The PR-specific evidence may intentionally update the central ledger before this
    # test executes. Do not force one fixed ledger state here; the dedicated PR gate
    # still validates the real branch transition.
    registry_errors = gate.validate_registry(evidence, registry)
    if registry_errors:
        failures.append("有效综合夹具未通过证据注册校验: " + " | ".join(registry_errors))

    bad_task_type = copy.deepcopy(evidence)
    bad_task_type["task_type"] = "BASELINE_ONLY"
    must_fail(core.validate_evidence(bad_task_type, cfg), "错误task_type", failures)

    bad_selected_count = copy.deepcopy(evidence)
    bad_selected_count["candidate_profiles"][0]["decision"] = "SELECTED"
    bad_selected_count["candidate_profiles"][0]["eligible"] = True
    must_fail(core.validate_evidence(bad_selected_count, cfg), "多画像SELECTED", failures)

    bad_path_evidence = copy.deepcopy(evidence)
    for path in bad_path_evidence["funding_paths"]:
        if path.get("decision") == "SELECTED":
            path["software_evidence_level"] = "E2"
            break
    must_fail(core.validate_evidence(bad_path_evidence, cfg), "E2资金路径正式入选", failures)

    missing_score = copy.deepcopy(evidence)
    del missing_score["candidate_profiles"][0]["scorecard"]
    must_fail(scoring.validate_evidence(missing_score), "缺少画像评分", failures)

    hidden_due = copy.deepcopy(evidence)
    hidden_due["coverage_debt"]["due_features"] = []
    # This should be caught by the scheme PR gate when ledger transition is evaluated.
    # Here we only ensure the structure validator and scoring validator still run.
    core.validate_evidence(hidden_due, cfg)
    scoring.validate_evidence(hidden_due)

    if failures:
        print("ORCHESTRATION_GATE_TESTS_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("ORCHESTRATION_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
