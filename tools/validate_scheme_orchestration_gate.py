#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools" / "validate_function_orchestration.py"
sys.path.insert(0, str(CORE_PATH.parent))
import validate_function_orchestration as core

LEVEL = {f"E{i}": i for i in range(8)}
SCHEME_PATTERNS = [
    re.compile(r"^tools/build_.*delivery\.py$"),
    re.compile(r"^03_批次归档/.*\.json$"),
    re.compile(r"^youtube_seo/.*\.json$"),
    re.compile(r"^controller/runs/[^/]+/task\.json$"),
]
FUNDING_REGISTRY = {
    "FLAT": "FUNDING_FLAT",
    "LIMITED_LINEAR": "FUNDING_LIMITED_LINEAR",
    "PRESSURE_RELEASE": "FUNDING_PRESSURE_RELEASE",
    "ADVANCED_STATE": "FUNDING_ADVANCED_STATE",
}
MORE_SETTING_REGISTRY = {
    "MONITORING": "MONITORING",
    "PROFIT_LOSS_JUMP": "PROFIT_LOSS_JUMP",
    "PROFIT_LOSS_STOP": "PROFIT_LOSS_STOP",
    "SIMULATION_REAL_SWITCH": "SIMULATION_REAL_SWITCH",
    "TIME_WINDOW": "TIME_WINDOW",
    "CHANGE_RULE": "CHANGE_RULE",
    "BET_DIRECTION": "BET_DIRECTION",
    "ROTATION_OR_COMBINATION": "ROTATION_OR_COMBINATION",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_changed(base: str) -> list[str]:
    if not base or not re.fullmatch(r"[0-9a-fA-F]{7,40}|[^ ]+/[^ ]+", base):
        return []
    try:
        process = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"无法读取PR差异: {exc.stderr.strip()}") from exc
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def registry_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["feature_id"]: item for item in registry.get("features", [])}


def check_claim(
    errors: list[str],
    feature_id: str,
    claimed: Any,
    refs: Any,
    registry: dict[str, dict[str, Any]],
    label: str,
) -> None:
    item = registry.get(feature_id)
    if not item:
        errors.append(f"{label}: 未登记功能{feature_id}")
        return
    if claimed not in LEVEL:
        errors.append(f"{label}: 证据等级无效")
        return
    maximum = item.get("max_formal_level")
    if maximum not in LEVEL:
        errors.append(f"{label}: 注册表最高等级无效")
        return
    if LEVEL[claimed] > LEVEL[maximum]:
        errors.append(f"{label}: 声称{claimed}超过注册表{maximum}")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{label}: 缺少evidence_refs")
        return
    allowed = set(item.get("evidence_refs", []))
    unknown = set(refs) - allowed
    if unknown:
        errors.append(f"{label}: 引用未登记证据{sorted(unknown)}")


def validate_registry_and_ledger(
    evidence: dict[str, Any],
    registry_object: dict[str, Any],
    ledger: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    registry = registry_map(registry_object)

    for profile in evidence.get("candidate_profiles", []):
        profile_id = profile.get("profile_id", "<unknown>")
        claims = profile.get("feature_evidence", [])
        if not isinstance(claims, list) or not claims:
            errors.append(f"{profile_id}: 缺少feature_evidence")
            continue
        claimed_ids: set[str] = set()
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append(f"{profile_id}: feature_evidence项必须为对象")
                continue
            feature_id = claim.get("feature_id")
            claimed_ids.add(feature_id)
            check_claim(
                errors,
                feature_id,
                claim.get("claimed_level"),
                claim.get("evidence_refs"),
                registry,
                f"{profile_id}.{feature_id}",
            )
        features = set(profile.get("features", []))
        if not features.issubset(claimed_ids):
            errors.append(f"{profile_id}: features缺少证据声明{sorted(features - claimed_ids)}")

    for path in evidence.get("funding_paths", []):
        feature_id = FUNDING_REGISTRY.get(path.get("kind"))
        if feature_id:
            check_claim(
                errors,
                feature_id,
                path.get("software_evidence_level"),
                path.get("evidence_refs"),
                registry,
                f"资金路径{path.get('path_id')}",
            )

    for setting in evidence.get("more_settings_review", []):
        category = setting.get("category")
        feature_id = MORE_SETTING_REGISTRY.get(category)
        if feature_id:
            check_claim(
                errors,
                feature_id,
                setting.get("evidence_level"),
                setting.get("evidence_refs"),
                registry,
                f"更多设置{category}",
            )

    due = ledger.get("next_due_features", [])
    evidence_due = evidence.get("coverage_debt", {}).get("due_features", [])
    if evidence_due != due:
        errors.append(f"coverage_debt.due_features必须等于中央账本: expected={due}, actual={evidence_due}")
    update = evidence.get("ledger_update", {})
    if update.get("from_sequence") != ledger.get("sequence"):
        errors.append("ledger_update.from_sequence与中央账本不一致")
    if update.get("to_sequence") != ledger.get("sequence", -1) + 1:
        errors.append("ledger_update.to_sequence必须加1")
    outcomes = update.get("outcomes", {})
    for feature_id in due:
        outcome = outcomes.get(feature_id)
        if not isinstance(outcome, dict):
            errors.append(f"到期功能缺少结果: {feature_id}")
            continue
        if outcome.get("outcome") not in {"CANDIDATE", "PROBE_ONLY", "SELECTED", "BLOCKED"}:
            errors.append(f"{feature_id}: outcome无效")
        if not outcome.get("evidence_ref"):
            errors.append(f"{feature_id}: 缺少结果证据引用")
    next_due = update.get("next_due_features")
    if not isinstance(next_due, list) or not next_due:
        errors.append("ledger_update.next_due_features不能为空")
    return errors


def validate_run(
    run_dir: Path,
    config: dict[str, Any],
    registry: dict[str, Any],
    ledger: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    task = load(run_dir / "task.json")
    if task.get("task_type") != "STANDARD_SCHEME_TASK":
        return errors
    evidence_path = run_dir / "function_orchestration.json"
    if not evidence_path.exists():
        return ["ORCHESTRATION_MISSING"]
    for required in ("director_decision.json", "design_contract.json"):
        if not (run_dir / required).exists():
            errors.append(f"{required}缺失")
    evidence = load(evidence_path)
    errors += core.validate_evidence(evidence, config)
    errors += validate_registry_and_ledger(evidence, registry, ledger)
    return errors


def validate_branch_ledger(
    changed: list[str],
    evidence_paths: list[Path],
    base_ledger: dict[str, Any] | None,
    branch_ledger: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not evidence_paths:
        return errors
    if "controller/function_coverage_ledger.json" not in changed:
        errors.append("标准方案PR必须更新中央功能覆盖账本")
        return errors
    if base_ledger is None:
        errors.append("无法读取基线功能覆盖账本")
        return errors
    if branch_ledger.get("sequence") != base_ledger.get("sequence", -1) + 1:
        errors.append("中央功能覆盖账本sequence必须加1")
    if len(evidence_paths) != 1:
        errors.append("一个PR只能关闭一个标准方案批次的覆盖债务")
        return errors
    evidence = load(evidence_paths[0])
    update = evidence.get("ledger_update", {})
    if branch_ledger.get("next_due_features") != update.get("next_due_features"):
        errors.append("分支账本next_due_features与证据ledger_update不一致")
    if branch_ledger.get("last_run_id") != evidence.get("run_id"):
        errors.append("分支账本last_run_id与本次run_id不一致")
    return errors


def git_show_json(base: str, path: str) -> dict[str, Any] | None:
    try:
        process = subprocess.run(
            ["git", "show", f"{base}:{path}"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(process.stdout)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="")
    args = parser.parse_args()

    config = load(ROOT / "controller" / "function_orchestration.json")
    registry = load(ROOT / "controller" / "feature_evidence_registry.json")
    ledger = load(ROOT / "controller" / "function_coverage_ledger.json")
    errors: list[str] = []

    for task_path in sorted((ROOT / "controller" / "runs").glob("*/task.json")):
        run_errors = validate_run(task_path.parent, config, registry, ledger)
        errors += [f"{task_path.parent.relative_to(ROOT)}: {error}" for error in run_errors]

    changed: list[str] = []
    if args.base:
        try:
            changed = git_changed(args.base)
        except RuntimeError as exc:
            errors.append(str(exc))
    scheme_signal = any(any(pattern.match(path) for pattern in SCHEME_PATTERNS) for path in changed)
    changed_evidence = [
        ROOT / path
        for path in changed
        if re.fullmatch(r"controller/runs/[^/]+/function_orchestration\.json", path)
    ]
    if scheme_signal and not changed_evidence:
        errors.append("标准方案PR出现方案交付信号但没有新增function_orchestration.json")
    for path in changed_evidence:
        if not path.exists():
            errors.append(f"变更证据不存在: {path.relative_to(ROOT)}")
            continue
        run_errors = validate_run(path.parent, config, registry, ledger)
        errors += [f"{path.parent.relative_to(ROOT)}: {error}" for error in run_errors]
    if changed_evidence:
        base_ledger = git_show_json(args.base, "controller/function_coverage_ledger.json") if args.base else None
        errors += validate_branch_ledger(changed, changed_evidence, base_ledger, ledger)

    if errors:
        print("SCHEME_ORCHESTRATION_GATE_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SCHEME_ORCHESTRATION_GATE_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
