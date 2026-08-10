#!/usr/bin/env python3
from pathlib import Path
import argparse, copy, json, re, sys

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'PPT叙事视角与扩展规则.json'
TESTS_PATH = ROOT / 'PPT叙事视角验收测试集.jsonl'
TEMPLATE_PATH = ROOT / 'controller/templates/ppt_narrative_contract.template.json'

CORE_RULE_IDS = {f'PNR-{i:03d}' for i in range(1, 8)}
CORE_TEST_IDS = {f'PNR-T{i:03d}' for i in range(1, 8)}
CORE_FAILURE_STATES = {
    'PPT_HUMAN_BETTOR_NARRATIVE_MISSING',
    'PPT_SYSTEM_DESIGN_PERSPECTIVE_FORBIDDEN',
    'PPT_ANALYSIS_BEFORE_SELECTION_MISSING',
    'PPT_PLAY_SELECTION_REASON_MISSING',
    'PPT_EXECUTION_STRUCTURE_REASON_MISSING',
    'PPT_FUNDING_REASON_MISSING',
    'PPT_SOFTWARE_OPERATION_TOO_EARLY',
}
REQUIRED_EVIDENCE_FIELDS = [
    'research_question',
    'historical_observation_summary',
    'number_derivation_summary',
    'number_selection_reason',
    'play_selection_reason',
    'execution_structure_reason',
    'funding_strategy_reason',
    'observation_and_stop_rule',
]


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path):
    rows = []
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise RuntimeError(f'{path.name} 第{lineno}行JSON无效: {exc}') from exc
    return rows


def validate_registry():
    errors = []
    try:
        policy = load_json(POLICY_PATH)
        tests = load_jsonl(TESTS_PATH)
        template = load_json(TEMPLATE_PATH)
    except Exception as exc:
        return [str(exc)], {}, [], {}

    if policy.get('status') != 'MANDATORY':
        errors.append('叙事策略必须为MANDATORY')
    if int(policy.get('schema_version', 0)) < 1:
        errors.append('叙事策略schema_version无效')
    if policy.get('default_narrative_role') != 'HUMAN_BETTOR_RESEARCHER':
        errors.append('默认叙事角色必须为HUMAN_BETTOR_RESEARCHER')

    story_arc = policy.get('required_story_arc') or []
    expected_arc = [
        'RESEARCH_QUESTION',
        'HISTORICAL_OBSERVATION',
        'ANALYSIS_AND_NUMBER_DERIVATION',
        'NUMBER_SELECTION_REASON',
        'PLAY_SELECTION_REASON',
        'EXECUTION_STRUCTURE_REASON',
        'FUNDING_STRATEGY_REASON',
        'SOFTWARE_OPERATION',
        'OBSERVATION_AND_STOP_RULE',
    ]
    if story_arc != expected_arc:
        errors.append('required_story_arc核心顺序被破坏；扩展应通过schema升级或兼容追加')

    rules = policy.get('hard_rules') or []
    rule_ids = [r.get('rule_id') for r in rules]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append('hard_rules存在重复rule_id')
    if not CORE_RULE_IDS.issubset(set(rule_ids)):
        errors.append(f'缺少核心叙事规则: {sorted(CORE_RULE_IDS - set(rule_ids))}')

    test_ids = [t.get('测试ID') for t in tests]
    if len(test_ids) != len(set(test_ids)):
        errors.append('叙事验收测试存在重复测试ID')
    if not CORE_TEST_IDS.issubset(set(test_ids)):
        errors.append(f'缺少核心叙事测试: {sorted(CORE_TEST_IDS - set(test_ids))}')

    test_by_id = {t.get('测试ID'): t for t in tests}
    failure_states = set()
    rule_pattern = re.compile(r'^PNR-\d{3}$')
    test_pattern = re.compile(r'^PNR-T\d{3}$')
    for rule in rules:
        rid = rule.get('rule_id')
        if not isinstance(rid, str) or not rule_pattern.match(rid):
            errors.append(f'非法rule_id: {rid!r}')
        for field in ['name', 'severity', 'requirement', 'failure_state', 'test_id']:
            if not rule.get(field):
                errors.append(f'{rid}缺少字段: {field}')
        if rule.get('severity') != 'BLOCK':
            errors.append(f'{rid}当前硬门禁severity必须为BLOCK')
        tid = rule.get('test_id')
        if tid not in test_by_id:
            errors.append(f'{rid}引用不存在的测试: {tid}')
        elif test_by_id[tid].get('失败状态') != rule.get('failure_state'):
            errors.append(f'{rid}的failure_state与{tid}不一致')
        if rule.get('failure_state'):
            failure_states.add(rule['failure_state'])

    for tid in test_ids:
        if not isinstance(tid, str) or not test_pattern.match(tid):
            errors.append(f'非法测试ID: {tid!r}')

    if not CORE_FAILURE_STATES.issubset(failure_states):
        errors.append(f'缺少核心失败状态: {sorted(CORE_FAILURE_STATES - failure_states)}')

    ext = policy.get('extension_contract') or {}
    for key, expected in {
        'append_only_rule_ids': True,
        'new_rule_must_add_test': True,
        'existing_rule_semantics_may_not_silently_change': True,
        'breaking_change_requires_schema_version_bump': True,
        'policy_change_requires_branch_pr_and_validation': True,
        'validator_must_not_hardcode_total_rule_count': True,
    }.items():
        if ext.get(key) is not expected:
            errors.append(f'extension_contract.{key}必须为{expected}')

    if template.get('policy_id') != policy.get('policy_id'):
        errors.append('叙事合同模板policy_id与策略不一致')
    if template.get('narrative_role') != policy.get('default_narrative_role'):
        errors.append('叙事合同模板默认角色不一致')
    if template.get('story_arc') != story_arc:
        errors.append('叙事合同模板story_arc与策略不一致')
    if template.get('software_operation_position') != 'AFTER_REASONING':
        errors.append('叙事合同模板软件操作必须后置')
    template_test_ids = {x.get('test_id') for x in (template.get('test_results') or [])}
    missing_template_tests = set(test_ids) - template_test_ids
    if missing_template_tests:
        errors.append(f'叙事合同模板缺少测试: {sorted(missing_template_tests)}')

    return errors, policy, tests, template


def validate_evidence_obj(evidence, policy, tests, label='evidence'):
    errors = []
    if evidence.get('policy_id') != policy.get('policy_id'):
        errors.append(f'{label}: policy_id不一致')
    if evidence.get('narrative_role') != policy.get('default_narrative_role'):
        errors.append(f'{label}: PPT_HUMAN_BETTOR_NARRATIVE_MISSING')
    if evidence.get('primary_frame') not in policy.get('allowed_primary_frames', []):
        errors.append(f'{label}: PPT_SYSTEM_DESIGN_PERSPECTIVE_FORBIDDEN')
    if evidence.get('primary_frame') in policy.get('forbidden_primary_frames', []):
        errors.append(f'{label}: PPT_SYSTEM_DESIGN_PERSPECTIVE_FORBIDDEN')
    if evidence.get('forbidden_primary_frame_hits'):
        errors.append(f'{label}: PPT_SYSTEM_DESIGN_PERSPECTIVE_FORBIDDEN')
    if evidence.get('story_arc') != policy.get('required_story_arc'):
        errors.append(f'{label}: PPT_ANALYSIS_BEFORE_SELECTION_MISSING')
    for field in REQUIRED_EVIDENCE_FIELDS:
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{label}: 缺少叙事证据字段 {field}')
    angle_ids = evidence.get('analysis_angle_ids')
    if not isinstance(angle_ids, list) or not angle_ids:
        errors.append(f'{label}: PPT_ANALYSIS_BEFORE_SELECTION_MISSING')
    if evidence.get('software_operation_position') != 'AFTER_REASONING':
        errors.append(f'{label}: PPT_SOFTWARE_OPERATION_TOO_EARLY')
    refs = evidence.get('evidence_refs') or {}
    for ref_name in ['number_source', 'funding', 'software_execution']:
        if not str(refs.get(ref_name, '')).strip():
            errors.append(f'{label}: 缺少evidence_refs.{ref_name}')

    required_tests = {t['测试ID'] for t in tests}
    results = {x.get('test_id'): x for x in (evidence.get('test_results') or [])}
    missing = required_tests - set(results)
    if missing:
        errors.append(f'{label}: 缺少叙事测试结果 {sorted(missing)}')
    for tid in required_tests & set(results):
        if results[tid].get('passed') is not True:
            errors.append(f'{label}: {tid}未通过')
        if not str(results[tid].get('evidence', '')).strip():
            errors.append(f'{label}: {tid}缺少证据说明')
    return errors


def build_self_test_evidence(policy, tests, template):
    obj = copy.deepcopy(template)
    obj.update({
        'run_id': 'SELF-TEST',
        'research_question': '验证某个历史现象是否具有可重复的下一期投注价值',
        'historical_observation_summary': '从冻结历史窗口观察到明确的频次或状态差异',
        'analysis_angle_ids': ['SELF-TEST-ANGLE'],
        'number_derivation_summary': '按冻结窗口统计、排序并按既定规则选出投注号码',
        'number_selection_reason': '号码来自排名与阈值，不是预设测试码',
        'play_selection_reason': '当前玩法能直接承载所选号码且注数与研究问题匹配',
        'execution_structure_reason': '执行结构用于控制同一期投注覆盖与风险分布',
        'funding_strategy_reason': '资金路径由玩法经济结构、本金和停止边界共同决定',
        'observation_and_stop_rule': '达到冻结观察期或风险边界即停止并复盘',
        'evidence_refs': {
            'number_source': 'SELF-TEST-NUMBER',
            'funding': 'SELF-TEST-FUNDING',
            'software_execution': 'SELF-TEST-SOFTWARE',
        },
    })
    obj['test_results'] = [
        {'test_id': t['测试ID'], 'passed': True, 'evidence': 'self-test evidence'} for t in tests
    ]
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--scan-runs', action='store_true')
    args = ap.parse_args()

    errors, policy, tests, template = validate_registry()
    if not errors and args.self_test:
        valid = build_self_test_evidence(policy, tests, template)
        valid_errors = validate_evidence_obj(valid, policy, tests, 'SELF-TEST-VALID')
        if valid_errors:
            errors.append('有效自测合同被拒绝: ' + '; '.join(valid_errors))
        invalid = copy.deepcopy(valid)
        invalid['narrative_role'] = 'SYSTEM_DESIGNER'
        invalid['primary_frame'] = 'SYSTEM_DESIGN'
        invalid['software_operation_position'] = 'BEFORE_REASONING'
        invalid['analysis_angle_ids'] = []
        invalid_errors = validate_evidence_obj(invalid, policy, tests, 'SELF-TEST-INVALID')
        joined = '\n'.join(invalid_errors)
        for state in [
            'PPT_HUMAN_BETTOR_NARRATIVE_MISSING',
            'PPT_SYSTEM_DESIGN_PERSPECTIVE_FORBIDDEN',
            'PPT_ANALYSIS_BEFORE_SELECTION_MISSING',
            'PPT_SOFTWARE_OPERATION_TOO_EARLY',
        ]:
            if state not in joined:
                errors.append(f'无效自测未触发预期状态: {state}')

    if not errors and args.evidence:
        path = Path(args.evidence)
        if not path.is_absolute():
            path = ROOT / path
        try:
            evidence = load_json(path)
            errors.extend(validate_evidence_obj(evidence, policy, tests, str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)))
        except Exception as exc:
            errors.append(f'无法读取叙事合同 {path}: {exc}')

    if not errors and args.scan_runs:
        runs_root = ROOT / 'controller/runs'
        if runs_root.exists():
            for path in sorted(runs_root.rglob('ppt_narrative_contract.json')):
                try:
                    evidence = load_json(path)
                    errors.extend(validate_evidence_obj(evidence, policy, tests, str(path.relative_to(ROOT))))
                except Exception as exc:
                    errors.append(f'无法读取叙事合同 {path}: {exc}')

    if errors:
        print('PPT_NARRATIVE_POLICY_FAILED')
        for item in errors:
            print('- ' + item)
        raise SystemExit(1)
    print(f"PPT_NARRATIVE_POLICY_OK policy={policy.get('policy_id')} rules={len(policy.get('hard_rules', []))} tests={len(tests)} extensible=YES")


if __name__ == '__main__':
    main()
