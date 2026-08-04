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
LEVEL = {f"E{i}": i for i in range(8)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_rank(value: Any) -> int:
    return LEVEL.get(str(value), -1)


def profile_min_evidence(item: dict[str, Any]) -> int:
    ranks: list[int] = []
    claims = item.get("feature_evidence", [])
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, dict):
                ranks.append(evidence_rank(claim.get("claimed_level")))
    layers = item.get("layers", {})
    if isinstance(layers, dict):
        for layer in layers.values():
            if isinstance(layer, dict) and layer.get("final_enabled") is True:
                ranks.append(evidence_rank(layer.get("evidence_level")))
    return min(ranks) if ranks else -1


def funding_evidence(item: dict[str, Any]) -> int:
    return evidence_rank(item.get("software_evidence_level"))


def validate_blockers(item: dict[str, Any], label: str, errors: list[str]) -> bool:
    blockers = item.get("hard_blockers", [])
    if not isinstance(blockers, list) or not blockers:
        errors.append(f"{label}: 证据已达正式门槛但被标记不合格，缺少hard_blockers")
        return False
    valid = True
    for index, blocker in enumerate(blockers, 1):
        if not isinstance(blocker, dict):
            errors.append(f"{label}: hard_blockers[{index}]必须为对象")
            valid = False
            continue
        if not str(blocker.get("reason", "")).strip() or not str(blocker.get("evidence_ref", "")).strip():
            errors.append(f"{label}: hard_blockers[{index}]缺少reason或evidence_ref")
            valid = False
    return valid


def validate_item(
    item: dict[str, Any],
    label: str,
    minimum_evidence: int,
    errors: list[str],
) -> float | None:
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
        notes = {}
    for key, value in values.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
            errors.append(f"{label}: {key}必须为0—10")
        if not str(notes.get(key, "")).strip():
            errors.append(f"{label}: {key}缺少评分理由")

    if minimum_evidence < 0:
        errors.append(f"{label}: 无法确定软件证据等级")
    else:
        evidence_cap = min(10, minimum_evidence * 2)
        if values.get("software_evidence", 0) > evidence_cap:
            errors.append(f"{label}: software_evidence评分超过证据等级上限{evidence_cap}")
        minimum_unverified_penalty = max(0, (3 - minimum_evidence) * 2)
        if values.get("unverified_penalty", 0) < minimum_unverified_penalty:
            errors.append(f"{label}: unverified_penalty至少应为{minimum_unverified_penalty}")

    calculated = sum(values.get(key, 0) for key in POSITIVE) - sum(values.get(key, 0) for key in PENALTY)
    declared = score.get("total")
    if not isinstance(declared, (int, float)) or isinstance(declared, bool) or not math.isclose(float(declared), float(calculated), abs_tol=1e-9):
        errors.append(f"{label}: total错误，应为{calculated}")

    eligible = item.get("eligible")
    if eligible not in {True, False}:
        errors.append(f"{label}: eligible必须为布尔值")
    if not str(item.get("eligibility_reason", "")).strip():
        errors.append(f"{label}: 缺少eligibility_reason")
    evidence_ready = minimum_evidence >= 3
    if eligible is True and not evidence_ready:
        errors.append(f"{label}: E3以下不得标记为正式eligible")
    if eligible is False and evidence_ready:
        validate_blockers(item, label, errors)
    if item.get("decision") == "SELECTED" and eligible is not True:
        errors.append(f"{label}: SELECTED必须同时eligible=true")
    if item.get("decision") == "PROBE_ONLY" and eligible is True:
        errors.append(f"{label}: PROBE_ONLY不得标记正式eligible")
    return float(calculated)


def validate_exposure_penalties(paths: list[dict[str, Any]], errors: list[str]) -> None:
    comparable: list[tuple[float, float, str]] = []
    for path in paths:
        exposure = path.get("worst_case_exposure")
        score = path.get("scorecard", {}).get("components", {}) if isinstance(path.get("scorecard"), dict) else {}
        penalty = score.get("exposure_penalty") if isinstance(score, dict) else None
        if isinstance(exposure, (int, float)) and not isinstance(exposure, bool) and isinstance(penalty, (int, float)) and not isinstance(penalty, bool):
            comparable.append((float(exposure), float(penalty), str(path.get("path_id", "<unknown>"))))
    for exposure_a, penalty_a, id_a in comparable:
        for exposure_b, penalty_b, id_b in comparable:
            if exposure_a > exposure_b and penalty_a < penalty_b:
                errors.append(f"资金路径{id_a}: 暴露高于{id_b}但exposure_penalty更低")


def validate_evidence(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profiles = data.get("candidate_profiles", [])
    paths = data.get("funding_paths", [])
    if not isinstance(profiles, list):
        profiles = []
        errors.append("candidate_profiles必须为数组")
    if not isinstance(paths, list):
        paths = []
        errors.append("funding_paths必须为数组")

    profile_scores: dict[str, float] = {}
    path_scores: dict[str, float] = {}
    for item in profiles:
        if not isinstance(item, dict):
            errors.append("画像项必须为对象")
            continue
        item_id = str(item.get("profile_id", "<unknown>"))
        total = validate_item(item, f"画像{item_id}", profile_min_evidence(item), errors)
        if total is not None and item.get("eligible") is True:
            profile_scores[item_id] = total
    for item in paths:
        if not isinstance(item, dict):
            errors.append("资金路径项必须为对象")
            continue
        item_id = str(item.get("path_id", "<unknown>"))
        total = validate_item(item, f"资金路径{item_id}", funding_evidence(item), errors)
        if total is not None and item.get("eligible") is True:
            path_scores[item_id] = total
    validate_exposure_penalties([item for item in paths if isinstance(item, dict)], errors)

    selection = data.get("selection", {})
    if not isinstance(selection, dict):
        selection = {}
        errors.append("selection必须为对象")
    selected_profile = selection.get("selected_profile_id")
    selected_path = selection.get("selected_funding_path_id")
    override_reason = str(selection.get("score_override_reason", "")).strip()
    override_refs = selection.get("score_override_evidence_refs", [])
    valid_override = bool(override_reason) and isinstance(override_refs, list) and bool(override_refs) and all(str(ref).strip() for ref in override_refs)

    if selected_profile not in profile_scores:
        errors.append("最终画像未标记eligible或缺少有效评分")
    elif profile_scores and profile_scores[selected_profile] < max(profile_scores.values()) and not valid_override:
        errors.append("最终画像不是最高分且缺少证据化覆盖理由")
    if selected_path not in path_scores:
        errors.append("最终资金路径未标记eligible或缺少有效评分")
    elif path_scores and path_scores[selected_path] < max(path_scores.values()) and not valid_override:
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
