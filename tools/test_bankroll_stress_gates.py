#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "validate_bankroll_stress.py"
spec = importlib.util.spec_from_file_location("validate_bankroll_stress", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def require_error(name: str, data: dict, needle: str, cfg: dict) -> None:
    errors = module.validate_evidence(data, cfg)
    if not any(needle in error for error in errors):
        raise AssertionError(f"{name}: expected {needle!r}, got {errors}")


def main() -> int:
    cfg = module.load(ROOT / "controller" / "bankroll_stress.json")
    valid = module.make_valid_fixture()
    errors = module.validate_evidence(valid, cfg)
    if errors:
        raise AssertionError(f"valid fixture failed: {errors}")

    case = copy.deepcopy(valid)
    case["assumptions"]["bankroll"] = 500
    selected = next(p for p in case["candidate_paths"] if p["decision"] == "SELECTED")
    selected["total_outlay_at_stop"] = 600
    require_error("bankroll break", case, "正式路径累计投入超过本金", cfg)

    case = copy.deepcopy(valid)
    case["loss_streak_stress"][4]["remaining_bankroll"] = -1
    case["loss_streak_stress"][4]["survives"] = True
    require_error("false survival", case, "survives与资金计算不一致", cfg)

    case = copy.deepcopy(valid)
    case["data_maturity"].update({
        "draw_count": 12000,
        "tier": "LARGE_SAMPLE",
        "claim_ceiling": "LARGE_SAMPLE_WITH_SEALED_OOS_REQUIRED",
        "long_term_safe_claim": False,
    })
    case["historical_validation"]["draw_count"] = 12000
    case["historical_validation"]["rolling_windows"] = [{"train": "1-5000", "test": "5001-7000"}]
    case["historical_validation"]["sealed_oos_range"] = None
    require_error("sealed oos", case, "10000期以上必须保留封存样本外区", cfg)

    print("BANKROLL_STRESS_GATE_TESTS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
