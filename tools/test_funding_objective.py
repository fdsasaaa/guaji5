from __future__ import annotations

from validate_funding_objective import validate, validate_config


def economic():
    return {
        "capital_base": 5000.0,
        "capital_usage_limit": 0.2,
        "minimum_unit": 0.1,
        "cost_at_1x": 1.0,
        "gross_payout_on_hit_at_1x": 10.0,
        "rebate_at_1x": 0.0,
        "theoretical_hit_rate": 0.1,
        "target_profit": 0.1,
        "maximum_single_bet": 500.0,
        "maximum_multiplier": 500.0,
    }


def execution():
    return {
        "engine": "STRAIGHT",
        "path_style": "FRONT_SLOW_BACK_FAST",
        "selection_reason": "高奖玩法允许前段低倍，按逐档回利公式反推",
    }


def recovery_fixture():
    eco = economic()
    multipliers = [1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 5, 6, 7]
    stages = []
    prior = 0.0
    for index, mult in enumerate(multipliers, start=1):
        investment = eco["cost_at_1x"] * mult
        payout = eco["gross_payout_on_hit_at_1x"] * mult
        rebate = eco["rebate_at_1x"] * mult
        net = payout + rebate - investment - prior
        loss_after = prior + investment - rebate
        stages.append({
            "stage": index,
            "multiplier": mult,
            "cumulative_loss_before": prior,
            "investment": investment,
            "gross_payout_if_hit": payout,
            "rebate": rebate,
            "net_if_hit": net,
            "cumulative_loss_after_miss": loss_after,
            "remaining_capital_after_miss": eco["capital_base"] - loss_after,
            "executable": True,
        })
        prior = loss_after
    return {
        "schema_version": 1,
        "run_id": "RECOVERY-TEST",
        "objective_type": "RECOVERY_PROFIT",
        "economic_model": eco,
        "execution": execution(),
        "recovery_policy": {
            "requested_depth": len(stages),
            "computed_valid_depth": len(stages),
            "depth_status": "FULFILLED",
            "first_hit_rule": "EVERY_VALID_STAGE_NET_PROFIT",
            "all_miss_total_loss": prior,
            "probability_at_least_one_hit": 1 - (1 - eco["theoretical_hit_rate"]) ** len(stages),
        },
        "recovery_stages": stages,
        "claims": ["仅说明有效档位内逐档回利"],
    }


def durable_fixture():
    return {
        "schema_version": 1,
        "run_id": "DURABLE-TEST",
        "objective_type": "DURABLE",
        "economic_model": economic(),
        "execution": {
            "engine": "ADVANCED",
            "path_style": "STATE_CYCLE",
            "selection_reason": "以低倍、降压和尾仓自锁控制连续不中暴露",
        },
        "durable_policy": {
            "maximum_multiplier": 3,
            "tail_policy": "HOLD_LAST_1X",
            "loss_checkpoints": [10, 20, 30, 40, 50, 100],
            "positive_expectation_source": "NONE",
            "positive_expectation_evidence": "",
            "profit_evidence_level": "NOT_ESTABLISHED",
        },
        "claims": ["耐久仅代表资金暴露受控，不代表长期盈利"],
    }


def run_tests():
    config = {
        "schema_version": 1,
        "default_when_unspecified": "AUTO_COMPARE",
        "objective_types": {
            "DURABLE": {"explicit_terms": ["耐久型"]},
            "RECOVERY_PROFIT": {"explicit_terms": ["回利型"]},
            "AUTO_COMPARE": {},
        },
        "execution_engines": ["STRAIGHT", "ADVANCED"],
        "path_styles": ["FLAT", "FLAT_THEN_STEP", "STEP", "GEOMETRIC", "FRONT_SLOW_BACK_FAST", "RISE_FALL", "STATE_CYCLE", "MIXED"],
    }
    assert not validate_config(config), validate_config(config)
    assert not validate(durable_fixture()), validate(durable_fixture())
    recovery = recovery_fixture()
    assert not validate(recovery), validate(recovery)

    broken = recovery_fixture()
    broken["recovery_stages"][5]["net_if_hit"] += 1
    assert any("net_if_hit应为" in e for e in validate(broken))

    underpay = recovery_fixture()
    underpay["economic_model"]["gross_payout_on_hit_at_1x"] = 1.1
    assert any("低于目标微利" in e for e in validate(underpay))

    overcapital = recovery_fixture()
    overcapital["economic_model"]["capital_usage_limit"] = 0.001
    assert any("超过允许本金占用" in e for e in validate(overcapital))

    false_claim = durable_fixture()
    false_claim["claims"] = ["长期盈利"]
    assert any("禁止声称" in e for e in validate(false_claim))

    auto = {
        "schema_version": 1,
        "run_id": "AUTO",
        "objective_type": "AUTO_COMPARE",
        "economic_model": economic(),
        "execution": execution(),
        "candidate_objectives": ["DURABLE", "RECOVERY_PROFIT"],
        "selection_rule": "按用户目标、可执行深度和最大暴露评分后选择",
    }
    assert not validate(auto), validate(auto)


if __name__ == "__main__":
    run_tests()
    print("funding objective tests: PASS")
