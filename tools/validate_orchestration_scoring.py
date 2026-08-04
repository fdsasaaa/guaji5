#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = (
    "problem_fit",
    "software_evidence",
    "risk_fit",
    "novelty",
    "explanation_value",
    "coverage_value",
)
PENALTY = (
    "exposure_penalty",
    "unverified_penalty",
    "complexity_penalty",
    "logic_confusion_penalty",
)
ALL = POSITIVE + PENALTY


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_item(item: dict[str, Any], label: str, errors: list[str]) -> float | None:
    score = item.get("scorecard")
    if not isinstance(score, dict):
        errors.append(f"{label}: 缺少scorecard")
        return None
    values = score.get("components")
    notes = score.get("notes")
    if not isinstance(values, dict) or set(values) != set(ALL):
        errors.append(f"{label}: scorecard.components字段不完整")
        return None
    if not isinstance(notes, dict) or set(notes) != set(ALL):
        errors.append(f"{label}: scorecard.notes字段不完整")
    for key, value in values.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
            errors.append(f"{label}: {key}必须为0—10")
        if not isinstance(notes, dict) or not str(notes.get(key, "")).strip():
            errors.append(f"{label}: {key}缺少评分理由")
    calculated = sum(values.get(key, 0) for key in POSITIVE) - sum(values.get(key, 0) for key in PENALTY)
    declared = score.get("total")
    if not isinstance(declared, (int, float)) or not math.isclose(float(declared), float(calculated), abs_tol=1e-9):
        errors.append(f"{label}: total错误，应为{calculated}")
    if item.get("eligible") not in {True, False}:
        errors.append(f"{label}: eligible必须为布尔值")
    if not str(item.get("eligibility_reason", "")).strip():
        errors.append(f"{label}: 缺少eligibility_reason")
    return float(calculated)


def validate_evidence(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profiles = data.get("candidate_profiles", [])
    paths = data.get("funding_paths", [])
    profile_scores: dict[str, float] = {}
    path_scores: dict[str, float] = {}
    for item in profiles:
        if not isinstance(item, dict):
            errors.append("画像项必须为对象")
            continue
        label = f"画像{item.get('profile_id', '<unknown>')}"
        total = validate_item(item, label, errors)
        if total is not None and item.get("eligible") is True:
            profile_scores[str(item.get("profile_id"))] = total
    for item in paths:
        if not isinstance(item, dict):
            errors.append("资金路径项必须为对象")
            continue
        label = f"资金路径{item.get('path_id', '<unknown>')}"
        total = validate_item(item, label, errors)
        if total is not None and item.get("eligible") is True:
            path_scores[str(item.get("path_id"))] = total

    selection = data.get("selection", {})
    selected_profile = selection.get("selected_profile_id")
    selected_path = selection.get("selected_funding_path_id")
    override_reason = str(selection.get("score_override_reason", "")).strip()
    override_refs = selection.get("score_override_evidence_refs", [])
    if selected_profile not in profile_scores:
        errors.append("最终画像未标记eligible或缺少有效评分")
    elif profile_scores:
        best = max(profile_scores.values())
        if profile_scores[selected_profile] < best:
            if not override_reason or not isinstance(override_refs, list) or not override_refs:
                errors.append("最终画像不是最高分且缺少证据化覆盖理由")
    if selected_path not in path_scores:
        errors.append("最终资金路径未标记eligible或缺少有效评分")
    elif path_scores:
        best = max(path_scores.values())
        if path_scores[selected_path] < best:
            if not override_reason or not isinstance(override_refs, list) or not override_refs:
                errors.append("最终资金路径不是最高分且缺少证据化覆盖理由")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--scan-runs", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    paths: list[Path] = []
    if args.evidence:
        paths.append(args.evidence)
    if args.scan_runs:
        for task in sorted((ROOT / "controller" / "runs").glob("*/task.json")):
            try:
                if load(task).get("task_type") == "STANDARD_SCHEME_TASK":
                    evidence = task.parent / "function_orchestration.json"
                    if evidence.exists():
                        paths.append(evidence)
            except Exception as exc:
                errors.append(f"{task.relative_to(ROOT)}读取失败: {exc}")
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            errors += [f"{path.relative_to(ROOT)}: {error}" for error in validate_evidence(load(path))]
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}读取失败: {exc}")
    if errors:
        print("ORCHESTRATION_SCORING_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ORCHESTRATION_SCORING_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
