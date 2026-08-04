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
sys.path.insert(0, str(ROOT / "tools"))
import validate_function_orchestration as core

LEVEL = {f"E{i}": i for i in range(8)}
SCHEME_PATTERNS = [
    re.compile(r"^tools/build_.*delivery\.py$"),
    re.compile(r"^03_批次归档/.*\.json$"),
    re.compile(r"^youtube_seo/.*\.json$"),
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
OUTCOMES = {"CANDIDATE", "PROBE_ONLY", "SELECTED", "BLOCKED"}
DELIVERY_MODES = {"BASELINE_ONLY", "BASELINE_PLUS_EXPERIMENT", "EXPERIMENT_ONLY"}


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


def registry_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["feature_id"]: item for item in registry.get("features", [])}


def check_claim(
    errors: list[str],
    feature_id: Any,
    claimed: Any,
    refs: Any,
    registry: dict[str, dict[str, Any]],
    label: str,
) -> None:
    if not isinstance(feature_id, str) or not feature_id:
        errors.append(f"{label}: feature_id缺失")
        return
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


def validate_registry(
    evidence: dict[str, Any],
    registry_object: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    registry = registry_map(registry_object)

    for profile in evidence.get("candidate_profiles", []):
        if not isinstance(profile, dict):
            errors.append("候选画像必须为对象")
            continue
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
            if isinstance(feature_id, str):
                claimed_ids.add(feature_id)
            check_claim(
                errors,
                feature_id,
                claim.get("claimed_level"),
                claim.get("evidence_refs"),
                registry,
                f"{profile_id}.{feature_id}",
            )
        features = set(profile.get("features", [])) if isinstance(profile.get("features"), list) else set()
        if not features.issubset(claimed_ids):
            errors.append(f"{profile_id}: features缺少证据声明{sorted(features - claimed_ids)}")

    for path in evidence.get("funding_paths", []):
        if not isinstance(path, dict):
            errors.append("资金路径必须为对象")
            continue
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
        if not isinstance(setting, dict):
            errors.append("更多设置记录必须为对象")
            continue
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
    return errors


def baseline_streak(modes: list[Any]) -> int:
    count = 0
    for mode in reversed(modes):
        if mode == "BASELINE_ONLY":
            count += 1
        else:
            break
    return count


def expected_window(history: list[Any], current: Any, limit: int) -> list[Any]:
    return (history + [current])[-limit:]


def validate_ledger_transition(
    evidence: dict[str, Any],
    base_ledger: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    due = base_ledger.get("next_due_features", [])
    evidence_due = evidence.get("coverage_debt", {}).get("due_features", [])
    if evidence_due != due:
        errors.append(f"coverage_debt.due_features必须等于基线中央账本: expected={due}, actual={evidence_due}")

    base_modes = base_ledger.get("recent_delivery_modes", [])
    evidence_modes = evidence.get("recent_delivery_modes", [])
    if evidence_modes != base_modes:
        errors.append("recent_delivery_modes必须原样读取基线中央账本")
    if base_ledger.get("baseline_only_streak") != baseline_streak(base_modes):
        errors.append("基线中央账本baseline_only_streak与recent_delivery_modes不一致")

    base_fingerprints = base_ledger.get("recent_selected_fingerprints", [])
    repeat = evidence.get("repeat_guard", {})
    if not isinstance(repeat, dict) or repeat.get("last_three_fingerprints") != base_fingerprints:
        errors.append("repeat_guard.last_three_fingerprints必须原样读取基线中央账本")

    update = evidence.get("ledger_update", {})
    if not isinstance(update, dict):
        return errors + ["ledger_update必须为对象"]
    base_sequence = base_ledger.get("sequence")
    if update.get("from_sequence") != base_sequence:
        errors.append("ledger_update.from_sequence与基线中央账本不一致")
    if not isinstance(base_sequence, int) or update.get("to_sequence") != base_sequence + 1:
        errors.append("ledger_update.to_sequence必须相对基线加1")
    outcomes = update.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
        errors.append("ledger_update.outcomes必须为对象")
    for feature_id in due:
        outcome = outcomes.get(feature_id)
        if not isinstance(outcome, dict):
            errors.append(f"到期功能缺少结果: {feature_id}")
            continue
        result = outcome.get("outcome")
        if result not in OUTCOMES:
            errors.append(f"{feature_id}: outcome无效")
        if not str(outcome.get("evidence_ref", "")).strip():
            errors.append(f"{feature_id}: 缺少结果证据引用")
        if result == "BLOCKED" and not str(outcome.get("blocked_reason", "")).strip():
            errors.append(f"{feature_id}: BLOCKED缺少blocked_reason")
    next_due = update.get("next_due_features")
    if not isinstance(next_due, list) or not next_due:
        errors.append("ledger_update.next_due_features不能为空")
    if len(next_due) != len(set(next_due)):
        errors.append("ledger_update.next_due_features存在重复")
    return errors


def validate_registry_and_ledger(
    evidence: dict[str, Any],
    registry_object: dict[str, Any],
    base_ledger: dict[str, Any],
) -> list[str]:
    return validate_registry(evidence, registry_object) + validate_ledger_transition(evidence, base_ledger)


def validate_run(
    run_dir: Path,
    config: dict[str, Any],
    registry: dict[str, Any],
    base_ledger: dict[str, Any] | None = None,
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
    directory_run_id = run_dir.name
    if evidence.get("run_id") != directory_run_id:
        errors.append("function_orchestration.run_id必须等于运行目录名")
    if task.get("run_id") != directory_run_id:
        errors.append("task.run_id必须等于运行目录名")
    errors += core.validate_evidence(evidence, config)
    errors += validate_registry(evidence, registry)
    if base_ledger is not None:
        errors += validate_ledger_transition(evidence, base_ledger)
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
        return ["标准方案PR必须更新中央功能覆盖账本"]
    if base_ledger is None:
        return ["无法读取基线功能覆盖账本"]
    if len(evidence_paths) != 1:
        return ["一个PR只能关闭一个标准方案批次的覆盖债务"]

    evidence = load(evidence_paths[0])
    update = evidence.get("ledger_update", {})
    selection = evidence.get("selection", {})
    repeat = evidence.get("repeat_guard", {})
    run_id = evidence.get("run_id")
    base_sequence = base_ledger.get("sequence")
    window = base_ledger.get("selection_window", 3)
    if not isinstance(window, int) or window < 1:
        errors.append("中央账本selection_window必须为正整数")
        window = 3

    if not isinstance(base_sequence, int) or branch_ledger.get("sequence") != base_sequence + 1:
        errors.append("中央功能覆盖账本sequence必须相对基线加1")
    if branch_ledger.get("sequence") != update.get("to_sequence"):
        errors.append("分支账本sequence与证据ledger_update.to_sequence不一致")
    if branch_ledger.get("next_due_features") != update.get("next_due_features"):
        errors.append("分支账本next_due_features与证据ledger_update不一致")
    if branch_ledger.get("last_run_id") != run_id:
        errors.append("分支账本last_run_id与本次run_id不一致")

    current_mode = selection.get("delivery_mode")
    if current_mode not in DELIVERY_MODES:
        errors.append("本次delivery_mode无效")
    expected_modes = expected_window(base_ledger.get("recent_delivery_modes", []), current_mode, window)
    if branch_ledger.get("recent_delivery_modes") != expected_modes:
        errors.append("分支账本recent_delivery_modes未按窗口追加本次模式")
    expected_streak = baseline_streak(expected_modes)
    if branch_ledger.get("baseline_only_streak") != expected_streak:
        errors.append("分支账本baseline_only_streak未正确更新")

    current_fingerprint = repeat.get("fingerprint")
    expected_fingerprints = expected_window(base_ledger.get("recent_selected_fingerprints", []), current_fingerprint, window)
    if branch_ledger.get("recent_selected_fingerprints") != expected_fingerprints:
        errors.append("分支账本recent_selected_fingerprints未按窗口追加本次指纹")

    branch_features = branch_ledger.get("features", {})
    if not isinstance(branch_features, dict):
        return errors + ["分支账本features必须为对象"]
    outcomes = update.get("outcomes", {})
    for feature_id in base_ledger.get("next_due_features", []):
        outcome = outcomes.get(feature_id, {}) if isinstance(outcomes, dict) else {}
        entry = branch_features.get(feature_id)
        if not isinstance(entry, dict):
            errors.append(f"分支账本缺少到期功能: {feature_id}")
            continue
        result = outcome.get("outcome")
        if result in {"CANDIDATE", "PROBE_ONLY", "SELECTED"}:
            if entry.get("last_material_candidate_run") != run_id:
                errors.append(f"{feature_id}: last_material_candidate_run未更新")
            if entry.get("consecutive_not_material") != 0:
                errors.append(f"{feature_id}: consecutive_not_material未清零")
        if result == "SELECTED" and entry.get("last_selected_run") != run_id:
            errors.append(f"{feature_id}: last_selected_run未更新")
        if result == "BLOCKED":
            if entry.get("blocked_reason") != outcome.get("blocked_reason"):
                errors.append(f"{feature_id}: blocked_reason未同步")
            if entry.get("blocked_evidence_ref") != outcome.get("evidence_ref"):
                errors.append(f"{feature_id}: blocked_evidence_ref未同步")
    return errors


def changed_standard_task(changed: list[str]) -> bool:
    for path in changed:
        if not re.fullmatch(r"controller/runs/[^/]+/task\.json", path):
            continue
        target = ROOT / path
        if not target.exists():
            continue
        try:
            if load(target).get("task_type") == "STANDARD_SCHEME_TASK":
                return True
        except Exception:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="")
    args = parser.parse_args()

    config = load(ROOT / "controller" / "function_orchestration.json")
    registry = load(ROOT / "controller" / "feature_evidence_registry.json")
    branch_ledger = load(ROOT / "controller" / "function_coverage_ledger.json")
    errors: list[str] = []

    # Historical runs are immutable evidence. Validate internal semantics and
    # registry claims only; never reinterpret an old run against a later ledger.
    for task_path in sorted((ROOT / "controller" / "runs").glob("*/task.json")):
        run_errors = validate_run(task_path.parent, config, registry, None)
        errors += [f"{task_path.parent.relative_to(ROOT)}: {error}" for error in run_errors]

    changed: list[str] = []
    base_ledger: dict[str, Any] | None = None
    if args.base:
        try:
            changed = git_changed(args.base)
            base_ledger = git_show_json(args.base, "controller/function_coverage_ledger.json")
        except RuntimeError as exc:
            errors.append(str(exc))

    scheme_signal = (
        any(any(pattern.match(path) for pattern in SCHEME_PATTERNS) for path in changed)
        or changed_standard_task(changed)
    )
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
        task_relative = f"{path.parent.relative_to(ROOT).as_posix()}/task.json"
        if task_relative not in changed:
            errors.append(f"新方案编排证据必须同时新增或更新本次task.json: {task_relative}")
        run_errors = validate_run(path.parent, config, registry, base_ledger)
        errors += [f"{path.parent.relative_to(ROOT)}: {error}" for error in run_errors]

    if changed_evidence:
        errors += validate_branch_ledger(changed, changed_evidence, base_ledger, branch_ledger)

    if errors:
        print("SCHEME_ORCHESTRATION_GATE_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SCHEME_ORCHESTRATION_GATE_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
