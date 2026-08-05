from __future__ import annotations

from resolve_funding_objective import resolve


def config():
    return {
        "default_when_unspecified": "AUTO_COMPARE",
        "objective_types": {
            "DURABLE": {"explicit_terms": ["耐久型", "抗造", "低回撤"]},
            "RECOVERY_PROFIT": {"explicit_terms": ["回利型", "连本带利", "中一期盈利"]},
        },
    }


def run_tests():
    assert resolve("生成一套耐久型方案", config())["objective_type"] == "DURABLE"
    assert resolve("做一套回利型，中一期盈利", config())["objective_type"] == "RECOVERY_PROFIT"
    assert resolve("自主生成一套方案", config())["objective_type"] == "AUTO_COMPARE"
    assert resolve("比较耐久型和回利型", config())["objective_type"] == "AUTO_COMPARE"


if __name__ == "__main__":
    run_tests()
    print("funding objective resolver tests: PASS")
