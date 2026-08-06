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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def standard_evidence_paths() -> list[Path]:
    paths: list[Path] = []
    for task_path in sorted((ROOT / "controller" / "runs").glob("*/task.json")):
        try:
            if load(task_path).get("task_type") == "STANDARD_SCHEME_TASK":
                evidence_path = task_path.parent / "function_orchestration.json"
                if evidence_path.exists():
                    paths.append(evidence_path)
        except Exception:
            paths.append(task_path.parent / "function_orchestration.json")
    return paths


def main() -> int:
    config = load(ROOT / "controller" / "function_orchestration.json")
    registry = load(ROOT / "controller" / "feature_evidence_registry.json")
    errors: list[str] = []
    paths = standard_evidence_paths()
    if not paths:
        errors.append("没有可验证的标准方案编排证据")

    first: dict | None = None
    for path in paths:
        try:
            evidence = load(path)
            first = first or evidence
            errors += [f"{path.relative_to(ROOT)}: {item}" for item in core.validate_evidence(evidence, config)]
            errors += [f"{path.relative_to(ROOT)}: {item}" for item in scoring.validate_evidence(evidence)]
            errors += [f"{path.relative_to(ROOT)}: {item}" for item in gate.validate_registry(evidence, registry)]
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}读取或校验失败: {exc}")

    if first is not None:
        bad_schema = copy.deepcopy(first)
        bad_schema["schema_version"] = 0
        if not core.validate_evidence(bad_schema, config):
            errors.append("schema_version错误未被核心校验拒绝")

        bad_score = copy.deepcopy(first)
        if bad_score.get("candidate_profiles"):
            bad_score["candidate_profiles"][0].pop("scorecard", None)
            if not scoring.validate_evidence(bad_score):
                errors.append("缺少scorecard未被评分校验拒绝")

        bad_registry = copy.deepcopy(first)
        if bad_registry.get("funding_paths"):
            bad_registry["funding_paths"][0]["software_evidence_level"] = "E7"
            if not gate.validate_registry(bad_registry, registry):
                errors.append("资金路径证据等级越权未被注册表校验拒绝")

    if errors:
        print("ORCHESTRATION_GATE_TESTS_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ORCHESTRATION_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
