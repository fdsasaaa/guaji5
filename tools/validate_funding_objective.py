#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

OBJECTIVES = {"DURABLE", "RECOVERY_PROFIT", "AUTO_COMPARE"}
ENGINES = {"STRAIGHT", "ADVANCED"}
STYLES = {"FLAT", "FLAT_THEN_STEP", "STEP", "GEOMETRIC", "FRONT_SLOW_BACK_FAST", "RISE_FALL", "STATE_CYCLE", "MIXED"}
TAILS = {"HOLD_LAST_1X", "STOP", "COOL_DOWN"}
EVIDENCE_LEVELS = {"NOT_ESTABLISHED", "EDGE_CANDIDATE", "OUT_OF_SAMPLE_VERIFIED"}
TOL = 1e-6


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: Any) -> bool:
    return _number(value) and value > 0


def _nonnegative(value: Any) -> bool:
    return _number(value) and value >= 0


def _close(a: Any, b: Any, tol: float = TOL) -> bool:
    return _number(a) and _number(b) and abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def _required_text(obj: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    if not str(obj.get(key, "")).strip():
        errors.append(f"{prefix}{key}不能为空")


def validate_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("资金目标配置schema_version必须为1")
    if data.get("default_when_unspecified") != "AUTO_COMPARE":
        errors.append("未指定资金目标时必须默认AUTO_COMPARE")
    objective_types = data.get("objective_types")
    if not isinstance(objective_types, dict):
        return errors + ["objective_types必须为对象"]
    for objective in OBJECTIVES:
        if objective not in objective_types:
            errors.append(f"缺少资金目标定义: {objective}")
    for objective in ("DURABLE", "RECOVERY_PROFIT"):
        terms = objective_types.get(objective, {}).get("explicit_terms")
        if not isinstance(terms, list) or not terms:
            errors.append(f"{objective}必须配置explicit_terms")
    if set(data.get("execution_engines", [])) != ENGINES:
        errors.append("execution_engines必须完整包含STRAIGHT和ADVANCED")
    if not STYLES.issubset(set(data.get("path_styles", []))):
        errors.append("path_styles不完整")
    return errors


def _validate_common(data: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if data.get("schema_version") != 1:
        errors.append("schema_version必须为1")
    _required_text(data, "run_id", errors)
    objective = data.get("objective_type")
    if objective not in OBJECTIVES:
        errors.append("objective_type必须为DURABLE、RECOVERY_PROFIT或AUTO_COMPARE")
    economic = data.get("economic_model")
    if not isinstance(economic, dict):
        errors.append("economic_model必须为对象")
        economic = {}
    for key in ("capital_base", "minimum_unit", "cost_at_1x", "gross_payout_on_hit_at_1x", "maximum_single_bet", "maximum_multiplier"):
        if not _positive(economic.get(key)):
            errors.append(f"economic_model.{key}必须为正数")
    for key in ("rebate_at_1x", "target_profit"):
        if not _nonnegative(economic.get(key)):
            errors.append(f"economic_model.{key}必须为非负数")
    usage = economic.get("capital_usage_limit")
    if not _number(usage) or not 0 < usage <= 1:
        errors.append("economic_model.capital_usage_limit必须在0和1之间")
    hit_rate = economic.get("theoretical_hit_rate")
    if not _number(hit_rate) or not 0 < hit_rate < 1:
        errors.append("economic_model.theoretical_hit_rate必须在0和1之间")
    execution = data.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution必须为对象")
        execution = {}
    if execution.get("engine") not in ENGINES:
        errors.append("execution.engine必须为STRAIGHT或ADVANCED")
    if execution.get("path_style") not in STYLES:
        errors.append("execution.path_style无效")
    _required_text(execution, "selection_reason", errors, "execution.")
    return economic, execution


def _validate_durable(data: dict[str, Any], economic: dict[str, Any], errors: list[str]) -> None:
    policy = data.get("durable_policy")
    if not isinstance(policy, dict):
        errors.append("耐久型必须提供durable_policy")
        return
    if policy.get("tail_policy") not in TAILS:
        errors.append("durable_policy.tail_policy无效")
    cap = policy.get("maximum_multiplier")
    if not _positive(cap):
        errors.append("durable_policy.maximum_multiplier必须为正数")
    elif _positive(economic.get("maximum_multiplier")) and cap > economic["maximum_multiplier"] + TOL:
        errors.append("耐久型封顶倍数超过经济模型允许上限")
    checkpoints = policy.get("loss_checkpoints")
    if not isinstance(checkpoints, list) or not {10, 20, 30, 40, 50}.issubset(set(checkpoints)):
        errors.append("耐久型必须至少覆盖10/20/30/40/50期连续不中压力节点")
    evidence = policy.get("profit_evidence_level")
    if evidence not in EVIDENCE_LEVELS:
        errors.append("durable_policy.profit_evidence_level无效")
    source = str(policy.get("positive_expectation_source", "")).strip()
    if not source:
        errors.append("durable_policy.positive_expectation_source不能为空")
    claims = [str(item) for item in data.get("claims", [])]
    if evidence != "OUT_OF_SAMPLE_VERIFIED":
        negations = ("不代表", "不得声称", "未证明", "不能证明", "不承诺", "禁止声称")
        for forbidden in ("长期盈利", "稳定盈利", "稳赚", "保证盈利"):
            for claim in claims:
                if forbidden in claim and not any(prefix in claim for prefix in negations):
                    errors.append(f"未达到样本外验证时禁止声称: {forbidden}")
                    break
    if source != "NONE" and not str(policy.get("positive_expectation_evidence", "")).strip():
        errors.append("声明正期望来源时必须提供positive_expectation_evidence")
    if source == "NONE" and evidence != "NOT_ESTABLISHED":
        errors.append("没有正期望来源时profit_evidence_level必须为NOT_ESTABLISHED")


def _validate_recovery(data: dict[str, Any], economic: dict[str, Any], errors: list[str]) -> None:
    policy = data.get("recovery_policy")
    if not isinstance(policy, dict):
        errors.append("回利型必须提供recovery_policy")
        return
    requested = policy.get("requested_depth")
    computed = policy.get("computed_valid_depth")
    if not isinstance(requested, int) or isinstance(requested, bool) or requested <= 0:
        errors.append("recovery_policy.requested_depth必须为正整数")
    if not isinstance(computed, int) or isinstance(computed, bool) or computed <= 0:
        errors.append("recovery_policy.computed_valid_depth必须为正整数")
    if policy.get("first_hit_rule") != "EVERY_VALID_STAGE_NET_PROFIT":
        errors.append("回利型first_hit_rule必须为EVERY_VALID_STAGE_NET_PROFIT")
    stages = data.get("recovery_stages")
    if not isinstance(stages, list) or not stages:
        errors.append("回利型必须提供非空recovery_stages")
        return
    if isinstance(computed, int) and computed != len(stages):
        errors.append("computed_valid_depth必须等于recovery_stages数量")
    if isinstance(requested, int) and isinstance(computed, int):
        status = policy.get("depth_status")
        expected = "FULFILLED" if computed >= requested else "CAPPED_BY_CONSTRAINTS"
        if status != expected:
            errors.append(f"recovery_policy.depth_status应为{expected}")
    prior_loss = 0.0
    capital_limit = float(economic.get("capital_base", 0)) * float(economic.get("capital_usage_limit", 0))
    target_profit = float(economic.get("target_profit", 0))
    cost_1x = float(economic.get("cost_at_1x", 0))
    payout_1x = float(economic.get("gross_payout_on_hit_at_1x", 0))
    rebate_1x = float(economic.get("rebate_at_1x", 0))
    max_bet = float(economic.get("maximum_single_bet", 0))
    max_mult = float(economic.get("maximum_multiplier", 0))
    for index, stage in enumerate(stages, start=1):
        prefix = f"第{index}档"
        if not isinstance(stage, dict):
            errors.append(f"{prefix}必须为对象")
            continue
        if stage.get("stage") != index:
            errors.append(f"{prefix}.stage必须连续从1开始")
        mult = stage.get("multiplier")
        if not _positive(mult):
            errors.append(f"{prefix}.multiplier必须为正数")
            continue
        expected_investment = cost_1x * float(mult)
        expected_payout = payout_1x * float(mult)
        expected_rebate = rebate_1x * float(mult)
        expected_hit_net = expected_payout + expected_rebate - expected_investment - prior_loss
        expected_loss_after_miss = prior_loss + expected_investment - expected_rebate
        checks = {
            "cumulative_loss_before": prior_loss,
            "investment": expected_investment,
            "gross_payout_if_hit": expected_payout,
            "rebate": expected_rebate,
            "net_if_hit": expected_hit_net,
            "cumulative_loss_after_miss": expected_loss_after_miss,
            "remaining_capital_after_miss": float(economic.get("capital_base", 0)) - expected_loss_after_miss,
        }
        for key, expected in checks.items():
            if not _close(stage.get(key), expected):
                errors.append(f"{prefix}.{key}应为{expected:.6f}")
        if expected_hit_net + TOL < target_profit:
            errors.append(f"{prefix}命中后净利{expected_hit_net:.6f}低于目标微利{target_profit:.6f}")
        if expected_investment > max_bet + TOL:
            errors.append(f"{prefix}投注{expected_investment:.6f}超过单期上限{max_bet:.6f}")
        if float(mult) > max_mult + TOL:
            errors.append(f"{prefix}倍数{mult}超过倍率上限{max_mult}")
        if expected_loss_after_miss > capital_limit + TOL:
            errors.append(f"{prefix}不中后累计净亏损超过允许本金占用")
        if stage.get("executable") is not True:
            errors.append(f"{prefix}.executable必须为true")
        prior_loss = expected_loss_after_miss
    if not _close(policy.get("all_miss_total_loss"), prior_loss):
        errors.append(f"recovery_policy.all_miss_total_loss应为{prior_loss:.6f}")
    p = economic.get("theoretical_hit_rate")
    if _number(p):
        expected_prob = 1 - (1 - float(p)) ** len(stages)
        if not _close(policy.get("probability_at_least_one_hit"), expected_prob):
            errors.append(f"recovery_policy.probability_at_least_one_hit应为{expected_prob:.12f}")


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    economic, _ = _validate_common(data, errors)
    objective = data.get("objective_type")
    if objective == "DURABLE":
        _validate_durable(data, economic, errors)
        if "recovery_stages" in data:
            errors.append("耐久型不得用recovery_stages冒充回利型")
    elif objective == "RECOVERY_PROFIT":
        _validate_recovery(data, economic, errors)
    elif objective == "AUTO_COMPARE":
        candidates = data.get("candidate_objectives")
        if not isinstance(candidates, list) or set(candidates) != {"DURABLE", "RECOVERY_PROFIT"}:
            errors.append("AUTO_COMPARE必须同时包含DURABLE和RECOVERY_PROFIT候选")
        _required_text(data, "selection_rule", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        from test_funding_objective import run_tests
        run_tests()
        print("funding objective self-test: PASS")
        return 0
    if args.config:
        errors = validate_config(json.loads(args.config.read_text(encoding="utf-8")))
    elif args.evidence:
        errors = validate(json.loads(args.evidence.read_text(encoding="utf-8")))
    else:
        parser.error("--evidence、--config或--self-test至少提供一个")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("funding objective: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
