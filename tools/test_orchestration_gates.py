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
    evidence = load_valid_fixture()
    failures: list[str] = []

    core_errors = core.validate_evidence(evidence, cfg)
    if core_errors:
        failures.append("有效综合夹具未通过核心校验: " + " | ".join(core_errors))
    score_errors = scoring.validate_evidence(evidence)
    if score_errors:
        failures.append("有效综合夹具未通过评分校验: " + " | ".join(score_errors))

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

    bad_total = copy.deepcopy(evidence)
    bad_total["candidate_profiles"][0]["scorecard"]["total"] += 1
    must_fail(scoring.validate_evidence(bad_total), "评分total错误", failures)

    if failures:
        print("ORCHESTRATION_GATE_TESTS_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("ORCHESTRATION_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
