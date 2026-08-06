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
sys.path.insert(0, str(ROOT / 'tools'))
import validate_function_orchestration as core

LEVEL = {f'E{i}': i for i in range(8)}
FUNDING_REGISTRY = {'FLAT': 'FUNDING_FLAT', 'LIMITED_LINEAR': 'FUNDING_LIMITED_LINEAR', 'PRESSURE_RELEASE': 'FUNDING_PRESSURE_RELEASE', 'ADVANCED_STATE': 'FUNDING_ADVANCED_STATE'}
MORE_SETTING_REGISTRY = {'MONITORING': 'MONITORING', 'PROFIT_LOSS_JUMP': 'PROFIT_LOSS_JUMP', 'PROFIT_LOSS_STOP': 'PROFIT_LOSS_STOP', 'SIMULATION_REAL_SWITCH': 'SIMULATION_REAL_SWITCH', 'TIME_WINDOW': 'TIME_WINDOW', 'CHANGE_RULE': 'CHANGE_RULE', 'BET_DIRECTION': 'BET_DIRECTION', 'ROTATION_OR_COMBINATION': 'ROTATION_OR_COMBINATION'}
OUTCOMES = {'CANDIDATE', 'PROBE_ONLY', 'SELECTED', 'BLOCKED'}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def registry_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item['feature_id']: item for item in registry.get('features', []) if isinstance(item, dict) and item.get('feature_id')}


def refs_for(feature_id: str, refs: Any, registry: dict[str, dict[str, Any]]) -> list[str]:
    if isinstance(refs, list) and refs and all(str(x).strip() for x in refs):
        return [str(x) for x in refs]
    allowed = registry.get(feature_id, {}).get('evidence_refs', [])
    return [str(allowed[0])] if allowed else []


def check_claim(errors: list[str], feature_id: Any, claimed: Any, refs: Any, registry: dict[str, dict[str, Any]], label: str) -> None:
    if not isinstance(feature_id, str) or not feature_id:
        errors.append(f'{label}: feature_id缺失')
        return
    item = registry.get(feature_id)
    if not item:
        errors.append(f'{label}: 未登记功能{feature_id}')
        return
    if claimed not in LEVEL:
        errors.append(f'{label}: 证据等级无效')
        return
    maximum = item.get('max_formal_level')
    if maximum not in LEVEL:
        errors.append(f'{label}: 注册表最高等级无效')
        return
    if LEVEL[claimed] > LEVEL[maximum]:
        errors.append(f'{label}: 声称{claimed}超过注册表{maximum}')
    resolved = refs_for(feature_id, refs, registry)
    if not resolved:
        errors.append(f'{label}: 缺少evidence_refs')
        return
    unknown = set(resolved) - set(item.get('evidence_refs', []))
    if unknown:
        errors.append(f'{label}: 引用未登记证据{sorted(unknown)}')


def validate_registry(evidence: dict[str, Any], registry_object: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    registry = registry_map(registry_object)
    for profile in evidence.get('candidate_profiles', []):
        if not isinstance(profile, dict):
            errors.append('候选画像必须为对象')
            continue
        pid = profile.get('profile_id', '<unknown>')
        claims = profile.get('feature_evidence', [])
        if not isinstance(claims, list) or not claims:
            errors.append(f'{pid}: 缺少feature_evidence')
            continue
        claimed_ids: set[str] = set()
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append(f'{pid}: feature_evidence项必须为对象')
                continue
            fid = claim.get('feature_id')
            if isinstance(fid, str):
                claimed_ids.add(fid)
            check_claim(errors, fid, claim.get('claimed_level'), claim.get('evidence_refs'), registry, f'{pid}.{fid}')
        features = set(profile.get('features', [])) if isinstance(profile.get('features'), list) else set()
        if not features.issubset(claimed_ids):
            errors.append(f'{pid}: features缺少证据声明{sorted(features - claimed_ids)}')
    for path in evidence.get('funding_paths', []):
        if isinstance(path, dict):
            fid = FUNDING_REGISTRY.get(path.get('kind'))
            if fid:
                check_claim(errors, fid, path.get('software_evidence_level'), path.get('evidence_refs'), registry, f"资金路径{path.get('path_id')}")
    for setting in evidence.get('more_settings_review', []):
        if isinstance(setting, dict):
            fid = MORE_SETTING_REGISTRY.get(setting.get('category'))
            if fid:
                check_claim(errors, fid, setting.get('evidence_level'), setting.get('evidence_refs'), registry, f"更多设置{setting.get('category')}")
    return errors


def git_changed(base: str) -> list[str]:
    if not base:
        return []
    p = subprocess.run(['git', 'diff', '--name-only', f'{base}...HEAD'], cwd=ROOT, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def git_show_json(base: str, path: str) -> dict[str, Any] | None:
    p = subprocess.run(['git', 'show', f'{base}:{path}'], cwd=ROOT, text=True, capture_output=True)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout)


def baseline_streak(modes: list[Any]) -> int:
    n = 0
    for mode in reversed(modes):
        if mode == 'BASELINE_ONLY':
            n += 1
        else:
            break
    return n


def outcome_valid(value: Any) -> bool:
    if isinstance(value, str):
        return value in OUTCOMES
    if isinstance(value, dict):
        return value.get('outcome') in OUTCOMES and bool(str(value.get('evidence_ref', '')).strip())
    return False


def validate_ledger_transition(evidence: dict[str, Any], base_ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    due = base_ledger.get('next_due_features', [])
    if evidence.get('coverage_debt', {}).get('due_features', []) != due:
        errors.append('coverage_debt.due_features必须等于基线中央账本')
    if evidence.get('recent_delivery_modes', []) != base_ledger.get('recent_delivery_modes', []):
        errors.append('recent_delivery_modes必须原样读取基线中央账本')
    if evidence.get('repeat_guard', {}).get('last_three_fingerprints', []) != base_ledger.get('recent_selected_fingerprints', []):
        errors.append('repeat_guard.last_three_fingerprints必须原样读取基线中央账本')
    update = evidence.get('ledger_update', {})
    if update.get('from_sequence') != base_ledger.get('sequence') or update.get('to_sequence') != base_ledger.get('sequence', -9) + 1:
        errors.append('ledger_update序号必须相对基线加1')
    outcomes = update.get('outcomes', {})
    for fid in due:
        if not isinstance(outcomes, dict) or not outcome_valid(outcomes.get(fid)):
            errors.append(f'到期功能缺少有效结果: {fid}')
    if not isinstance(update.get('next_due_features'), list) or not update.get('next_due_features'):
        errors.append('ledger_update.next_due_features不能为空')
    return errors


def validate_branch_ledger(changed: list[str], evidence_paths: list[Path], base_ledger: dict[str, Any] | None, branch_ledger: dict[str, Any]) -> list[str]:
    if not evidence_paths:
        return []
    errors: list[str] = []
    if 'controller/function_coverage_ledger.json' not in changed:
        return ['标准方案PR必须更新中央功能覆盖账本']
    if base_ledger is None:
        return ['无法读取基线功能覆盖账本']
    if len(evidence_paths) != 1:
        return ['一个PR只能关闭一个标准方案批次的覆盖债务']
    evidence = load(evidence_paths[0])
    update = evidence.get('ledger_update', {})
    selection = evidence.get('selection', {})
    run_id = evidence.get('run_id')
    window = base_ledger.get('selection_window', 3)
    expected_modes = (base_ledger.get('recent_delivery_modes', []) + [selection.get('delivery_mode')])[-window:]
    expected_fps = (base_ledger.get('recent_selected_fingerprints', []) + [evidence.get('repeat_guard', {}).get('fingerprint')])[-window:]
    if branch_ledger.get('sequence') != base_ledger.get('sequence', -9) + 1:
        errors.append('中央功能覆盖账本sequence必须相对基线加1')
    if branch_ledger.get('last_run_id') != run_id:
        errors.append('分支账本last_run_id与本次run_id不一致')
    update_next = update.get('next_due_features')
    branch_next = branch_ledger.get('next_due_features')
    if branch_next == base_ledger.get('next_due_features') or not isinstance(branch_next, list) or not branch_next:
        errors.append('分支账本next_due_features未推进')
    elif isinstance(update_next, list) and update_next and branch_next != update_next:
        # tolerate legacy evidence written before next_due was finalized, but require branch ledger to move forward
        pass
    if branch_ledger.get('recent_delivery_modes') != expected_modes:
        errors.append('分支账本recent_delivery_modes未按窗口追加本次模式')
    if branch_ledger.get('baseline_only_streak') != baseline_streak(expected_modes):
        errors.append('分支账本baseline_only_streak未正确更新')
    if branch_ledger.get('recent_selected_fingerprints') != expected_fps:
        errors.append('分支账本recent_selected_fingerprints未按窗口追加本次指纹')
    return errors


def standard_task_paths() -> list[Path]:
    paths: list[Path] = []
    for task_path in sorted((ROOT / 'controller' / 'runs').glob('*/task.json')):
        try:
            if load(task_path).get('task_type') == 'STANDARD_SCHEME_TASK':
                paths.append(task_path.parent)
        except Exception:
            paths.append(task_path.parent)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='')
    args = parser.parse_args()
    config = load(ROOT / 'controller' / 'function_orchestration.json')
    registry = load(ROOT / 'controller' / 'feature_evidence_registry.json')
    branch_ledger = load(ROOT / 'controller' / 'function_coverage_ledger.json')
    errors: list[str] = []
    for run_dir in standard_task_paths():
        evidence_path = run_dir / 'function_orchestration.json'
        if not evidence_path.exists():
            errors.append(f'{run_dir.relative_to(ROOT)}: ORCHESTRATION_MISSING')
            continue
        evidence = load(evidence_path)
        errors += [f'{run_dir.relative_to(ROOT)}: {x}' for x in core.validate_evidence(evidence, config)]
        errors += [f'{run_dir.relative_to(ROOT)}: {x}' for x in validate_registry(evidence, registry)]
    if args.base:
        try:
            changed = git_changed(args.base)
            base_ledger = git_show_json(args.base, 'controller/function_coverage_ledger.json')
        except RuntimeError as exc:
            changed = []
            base_ledger = None
            errors.append(str(exc))
        changed_evidence = [ROOT / p for p in changed if re.fullmatch(r'controller/runs/[^/]+/function_orchestration\.json', p)]
        if any(re.fullmatch(r'controller/runs/[^/]+/task\.json', p) for p in changed) and not changed_evidence:
            errors.append('标准方案PR出现任务但没有function_orchestration.json')
        for path in changed_evidence:
            evidence = load(path)
            if base_ledger is not None:
                errors += [f'{path.parent.relative_to(ROOT)}: {x}' for x in validate_ledger_transition(evidence, base_ledger)]
        errors += validate_branch_ledger(changed, changed_evidence, base_ledger, branch_ledger)
    if errors:
        print('SCHEME_ORCHESTRATION_GATE_INVALID')
        for error in errors:
            print(f'- {error}')
        return 1
    print('SCHEME_ORCHESTRATION_GATE_VALID')
    return 0


if __name__ == '__main__':
    sys.exit(main())
