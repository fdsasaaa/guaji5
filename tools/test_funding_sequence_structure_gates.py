#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "validate_funding_sequence_structure.py"
spec = importlib.util.spec_from_file_location("validate_funding_sequence_structure", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def require_error(name: str, structure: dict, bankroll: dict, needle: str, config: dict) -> None:
    errors = module.validate_evidence(structure, bankroll, config)
    if not any(needle in error for error in errors):
        raise AssertionError(f"{name}: expected {needle!r}, got {errors}")


def main() -> int:
    config = module.load(ROOT / "controller" / "funding_sequence_structure.json")
    structure, bankroll = module.make_fixture()
    errors = module.validate_evidence(structure, bankroll, config)
    if errors:
        raise AssertionError(f"valid fixture failed: {errors}")

    pattern = [0.1, 0.1, 0.2, 0.2, 0.3, 0.3, 0.5, 0.5, 0.3, 0.2, 0.1, 0.1]
    case_structure = copy.deepcopy(structure)
    case_bankroll = copy.deepcopy(bankroll)
    target = next(item for item in case_structure["paths"] if item["path_id"] == "ADVANCED_STATE")
    target.update({
        "canonical_sequence": pattern * 5,
        "minimum_repeat_period": 12,
        "effective_design_length": 60,
        "claimed_design_length": 60,
        "execution_horizon": 60,
        "declared_stop_period": 60,
        "design_claim": "60期独立路径",
    })
    bankroll_target = next(item for item in case_bankroll["candidate_paths"] if item["path_id"] == "ADVANCED_STATE")
    bankroll_target.update({"period_stakes": pattern * 5, "declared_stop_period": 60, "total_outlay_at_stop": sum(pattern) * 5})
    require_error("expanded repeat", case_structure, case_bankroll, "检测到展开式重复块", config)

    case_structure = copy.deepcopy(structure)
    target = next(item for item in case_structure["paths"] if item["path_id"] == "PRESSURE_RELEASE")
    target["design_claim"] = "50期独立路径"
    require_error("false claim", case_structure, bankroll, "design_claim必须准确披露", config)

    case_structure = copy.deepcopy(structure)
    target = next(item for item in case_structure["paths"] if item["path_id"] == "PRESSURE_RELEASE")
    target["cross_cycle_checkpoints"] = None
    require_error("missing cycle stress", case_structure, bankroll, "缺少cross_cycle_checkpoints", config)

    case_bankroll = copy.deepcopy(bankroll)
    target = next(item for item in case_bankroll["candidate_paths"] if item["path_id"] == "PRESSURE_RELEASE")
    target["period_stakes"] = target["period_stakes"] * 10
    require_error("bankroll expanded", structure, case_bankroll, "必须只保存同一规范序列", config)

    case_bankroll = copy.deepcopy(bankroll)
    case_bankroll["loss_streak_stress"][-1]["next_period_stake"] = 0.1
    require_error("post stop stake", structure, case_bankroll, "next_period_stake与规范执行结构不一致", config)

    print("FUNDING_SEQUENCE_STRUCTURE_GATE_TESTS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
