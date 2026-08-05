from __future__ import annotations

from validate_funding_path_integrity import validate


def fixture():
    def common(path_id, kind, decision="REJECTED"):
        return {
            "path_id": path_id,
            "kind": kind,
            "decision": decision,
            "reset_rule": "命中后回基础档",
            "cap_rule": "达到上限后停止",
            "selection_reason": "完成同口径资金对照",
        }

    flat = common("FLAT", "FLAT", "SELECTED")
    flat["sequence"] = [1] * 10
    linear = common("LIMITED_LINEAR", "LIMITED_LINEAR")
    linear["sequence"] = [1, 1, 2, 2, 3, 3]
    pressure = common("PRESSURE_RELEASE", "PRESSURE_RELEASE")
    pressure.update(sequence=[1, 1, 2, 2, 3, 2, 1, 1, 2, 1, 1], cycle_mode="STOP_AT_END")
    advanced = common("ADVANCED_STATE", "ADVANCED_STATE")
    advanced.update(
        states=["BASE", "BUILD", "RELEASE", "STOP"],
        transitions=[
            {"from": "BASE", "on": "WIN", "to": "BASE"},
            {"from": "BASE", "on": "LOSS", "to": "BUILD"},
            {"from": "BUILD", "on": "WIN", "to": "RELEASE"},
            {"from": "BUILD", "on": "LOSS", "to": "RELEASE"},
            {"from": "RELEASE", "on": "CAP", "to": "STOP"},
        ],
        partial_recovery_rule="命中但净值仍为负时只降压，不宣称回本",
    )
    stress = []
    for n in [10, 20, 30, 40, 50]:
        stress.append(
            {
                "loss_streak": n,
                "cumulative_investment": n * 0.5,
                "remaining_capital": 5000 - n * 0.5,
                "next_multiplier": 1,
                "next_investment": 0.5,
                "net_after_next_hit": -(n * 0.5) + 0.35,
                "full_recovery": False,
                "can_continue": True,
            }
        )
    return {
        "schema_version": 1,
        "run_id": "TEST",
        "capital_base": 5000,
        "minimum_unit": 0.1,
        "single_period_cost_at_1x": 0.5,
        "gross_return_at_1x": 0.85,
        "theoretical_hit_rate": 0.5,
        "historical_periods": 200,
        "data_maturity": "QUICK_EXPERIMENT_ONLY",
        "claims": ["仅流程验证"],
        "funding_paths": [flat, linear, pressure, advanced],
        "stress_checkpoints": stress,
        "random_simulation": {
            "paths": 10000,
            "model": "THEORETICAL_BERNOULLI",
            "periods_per_path": 200,
        },
    }


def run_tests():
    good = fixture()
    assert not validate(good), validate(good)

    repeated = fixture()
    repeated["funding_paths"][2]["sequence"] = [1, 1, 2, 2, 3, 3, 5, 5, 3, 2, 1, 1] * 5
    repeated["funding_paths"][2]["cycle_mode"] = "REPEAT"
    errors = validate(repeated)
    assert any("机械重复" in error for error in errors)
    assert any("不得无限循环" in error for error in errors)

    fake_state = fixture()
    fake_state["funding_paths"][3]["transitions"] = ["BASE->BUILD", "BUILD->BASE"]
    errors = validate(fake_state)
    assert any("结构化转移" in error or "from/on/to" in error for error in errors)

    missing_checkpoint = fixture()
    missing_checkpoint["stress_checkpoints"] = missing_checkpoint["stress_checkpoints"][:-1]
    assert any("10/20/30/40/50" in error for error in validate(missing_checkpoint))

    too_few_paths = fixture()
    too_few_paths["random_simulation"]["paths"] = 9999
    assert any("至少10000" in error for error in validate(too_few_paths))

    false_claim = fixture()
    false_claim["claims"] = ["稳定盈利"]
    assert any("禁止声称" in error for error in validate(false_claim))


if __name__ == "__main__":
    run_tests()
    print("funding path integrity tests: PASS")
