#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "controller" / "funding_sequence_structure.json"
TEMPLATE_PATH = ROOT / "controller" / "templates" / "funding_sequence_structure.template.json"
MODES = {"FINITE", "CYCLIC"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def positive(value: Any) -> bool:
    return number(value) and float(value) > 0


def close(left: Any, right: Any) -> bool:
    return number(left) and number(right) and math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-6)


def minimum_repeat_period(values: list[Any]) -> int:
    size = len(values)
    if size <= 1:
        return size
    normalized = [round(float(value), 9) for value in values]
    for period in range(1, size):
        if size % period:
            continue
        if all(normalized[index] == normalized[index % period] for index in range(size)):
            return period
    return size


def stake_at(sequence: list[float], mode: str, stop: int, zero_based_period: int) -> float:
    if zero_based_period < 0 or zero_based_period >= stop:
        return 0.0
    if mode == "CYCLIC":
        return float(sequence[zero_based_period % len(sequence)])
    if zero_based_period >= len(sequence):
        return 0.0
    return float(sequence[zero_based_period])


def cumulative_outlay(sequence: list[float], mode: str, stop: int, losses: int) -> float:
    active = min(max(losses, 0), stop)
    return round(sum(stake_at(sequence, mode, stop, index) for index in range(active)), 10)


def hit_net(sequence: list[float], mode: str, stop: int, losses: int, base_cost: float, net_profit: float) -> float:
    next_stake = stake_at(sequence, mode, stop, losses)
    if next_stake <= 0 or base_cost <= 0:
        return 0.0
    return round(-cumulative_outlay(sequence, mode, stop, losses) + net_profit * next_stake / base_cost, 10)


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("配置schema_version必须为1")
    if config.get("status") != "ACTIVE":
        errors.append("资金序列结构闸门必须为ACTIVE")
    if set(config.get("sequence_modes", [])) != MODES:
        errors.append("sequence_modes必须包含FINITE和CYCLIC")
    for key, value in config.get("requirements", {}).items():
        if value is not True:
            errors.append(f"配置未启用: {key}")
    return errors


def bankroll_context(bankroll: dict[str, Any]) -> tuple[float, float, float, dict[str, dict[str, Any]]]:
    assumptions = bankroll.get("assumptions", {})
    payout = assumptions.get("payout_model", {})
    amount = float(assumptions.get("bankroll", 0) or 0)
    base_cost = float(assumptions.get("base_period_cost", 0) or 0)
    net_profit = float(payout.get("net_profit_per_base_period_hit", 0) or 0)
    paths = {
        str(item.get("path_id")): item
        for item in bankroll.get("candidate_paths", [])
        if isinstance(item, dict) and item.get("path_id")
    }
    return amount, base_cost, net_profit, paths


def validate_cycle_checkpoints(
    item: dict[str, Any],
    sequence: list[float],
    stop: int,
    bankroll_amount: float,
    base_cost: float,
    net_profit: float,
    errors: list[str],
) -> None:
    path_id = str(item.get("path_id", "<unknown>"))
    cycle_length = len(sequence)
    cycle_limit = math.ceil(stop / cycle_length)
    checkpoints = item.get("cross_cycle_checkpoints")
    if not isinstance(checkpoints, list):
        errors.append(f"{path_id}: 缺少cross_cycle_checkpoints")
        return
    by_cycle = {
        checkpoint.get("cycle_number"): checkpoint
        for checkpoint in checkpoints
        if isinstance(checkpoint, dict)
    }
    if set(by_cycle) != set(range(1, cycle_limit + 1)):
        errors.append(f"{path_id}: 必须逐轮记录1—{cycle_limit}轮跨轮压力")
    for cycle_number in range(1, cycle_limit + 1):
        checkpoint = by_cycle.get(cycle_number)
        if not isinstance(checkpoint, dict):
            continue
        losses = min(cycle_number * cycle_length, stop)
        outlay = cumulative_outlay(sequence, "CYCLIC", stop, losses)
        remaining = round(bankroll_amount - outlay, 10)
        next_stake = stake_at(sequence, "CYCLIC", stop, losses)
        net = hit_net(sequence, "CYCLIC", stop, losses, base_cost, net_profit)
        recovery = bool(next_stake > 0 and net >= 0)
        expected = {
            "losses_at_end": losses,
            "cumulative_outlay": outlay,
            "remaining_bankroll": remaining,
            "next_period_stake": next_stake,
            "hit_net_after_cycle": net,
        }
        for key, value in expected.items():
            if not close(checkpoint.get(key), value):
                errors.append(f"{path_id}: 第{cycle_number}轮{key}计算不一致，应为{value}")
        if checkpoint.get("recovery_complete") is not recovery:
            errors.append(f"{path_id}: 第{cycle_number}轮recovery_complete与跨轮回收不一致")


def validate_path(
    item: dict[str, Any],
    bankroll_path: dict[str, Any] | None,
    bankroll_amount: float,
    base_cost: float,
    net_profit: float,
    errors: list[str],
) -> None:
    path_id = str(item.get("path_id", "<unknown>"))
    sequence = item.get("canonical_sequence")
    if not isinstance(sequence, list) or not sequence or any(not positive(value) for value in sequence):
        errors.append(f"{path_id}: canonical_sequence必须为非空正数数组")
        return
    computed_period = minimum_repeat_period(sequence)
    if computed_period < len(sequence):
        errors.append(
            f"{path_id}: 检测到展开式重复块；输入长度{len(sequence)}的最小重复周期仅{computed_period}，"
            "必须只保存一轮最短规范序列"
        )
    if item.get("minimum_repeat_period") != computed_period:
        errors.append(f"{path_id}: minimum_repeat_period必须等于机器计算值{computed_period}")
    if item.get("effective_design_length") != len(sequence):
        errors.append(f"{path_id}: effective_design_length必须等于规范序列长度{len(sequence)}")
    if item.get("claimed_design_length") != len(sequence):
        errors.append(f"{path_id}: claimed_design_length不得超过有效独立长度{len(sequence)}")

    mode = item.get("sequence_mode")
    if mode not in MODES:
        errors.append(f"{path_id}: sequence_mode必须为FINITE或CYCLIC")
        return
    stop = item.get("execution_horizon")
    if not isinstance(stop, int) or isinstance(stop, bool) or stop < 1:
        errors.append(f"{path_id}: execution_horizon必须为正整数")
        return
    if item.get("declared_stop_period") != stop:
        errors.append(f"{path_id}: declared_stop_period必须等于execution_horizon")

    if mode == "FINITE":
        expected_claim = f"{len(sequence)}期独立路径"
        if stop > len(sequence):
            errors.append(f"{path_id}: FINITE路径停止期不得超过有效独立长度{len(sequence)}")
        if item.get("cycle_limit") not in {None, 1}:
            errors.append(f"{path_id}: FINITE路径cycle_limit只能为null或1")
        if item.get("cross_cycle_checkpoints") not in (None, []):
            errors.append(f"{path_id}: FINITE路径不得伪造跨轮压力表")
    else:
        cycle_limit = math.ceil(stop / len(sequence))
        expected_claim = f"{len(sequence)}期循环路径×{cycle_limit}轮"
        if stop <= len(sequence):
            errors.append(f"{path_id}: CYCLIC路径总运行期数必须大于单轮有效长度")
        if item.get("cycle_limit") != cycle_limit:
            errors.append(f"{path_id}: cycle_limit必须等于{cycle_limit}")
        validate_cycle_checkpoints(item, sequence, stop, bankroll_amount, base_cost, net_profit, errors)
    if item.get("design_claim") != expected_claim:
        errors.append(f"{path_id}: design_claim必须准确披露为“{expected_claim}”")

    if not isinstance(bankroll_path, dict):
        errors.append(f"{path_id}: bankroll_stress中缺少同名路径")
        return
    bankroll_sequence = bankroll_path.get("period_stakes")
    if not isinstance(bankroll_sequence, list) or len(bankroll_sequence) != len(sequence) or any(
        not close(left, right) for left, right in zip(bankroll_sequence, sequence)
    ):
        errors.append(f"{path_id}: bankroll_stress.period_stakes必须只保存同一规范序列")
    if bankroll_path.get("declared_stop_period") != stop:
        errors.append(f"{path_id}: bankroll_stress停止期与结构证据不一致")
    expected_outlay = cumulative_outlay(sequence, mode, stop, stop)
    if not close(bankroll_path.get("total_outlay_at_stop"), expected_outlay):
        errors.append(f"{path_id}: bankroll_stress.total_outlay_at_stop应为{expected_outlay}")


def validate_loss_stress(
    structure: dict[str, Any],
    bankroll: dict[str, Any],
    bankroll_amount: float,
    base_cost: float,
    net_profit: float,
    errors: list[str],
) -> None:
    selected_id = structure.get("selection", {}).get("selected_path_id")
    selected = next((item for item in structure.get("paths", []) if item.get("path_id") == selected_id), None)
    if not isinstance(selected, dict):
        errors.append("selection.selected_path_id不存在")
        return
    sequence = selected.get("canonical_sequence", [])
    mode = selected.get("sequence_mode")
    stop = selected.get("execution_horizon")
    if not isinstance(sequence, list) or mode not in MODES or not isinstance(stop, int):
        return
    stress = {
        item.get("losses"): item
        for item in bankroll.get("loss_streak_stress", [])
        if isinstance(item, dict)
    }
    required = {10, 20, 30, 40, 50, stop}
    for losses in sorted(required):
        checkpoint = stress.get(losses)
        if not isinstance(checkpoint, dict):
            errors.append(f"缺少连续挂{losses}期压力测试")
            continue
        outlay = cumulative_outlay(sequence, mode, stop, losses)
        remaining = round(bankroll_amount - outlay, 10)
        next_stake = stake_at(sequence, mode, stop, losses)
        net = hit_net(sequence, mode, stop, losses, base_cost, net_profit)
        stopped = losses >= stop
        expected = {
            "cumulative_outlay": outlay,
            "remaining_bankroll": remaining,
            "next_period_stake": next_stake,
            "hit_net_after_streak": net,
        }
        for key, value in expected.items():
            if not close(checkpoint.get(key), value):
                errors.append(f"连挂{losses}期: {key}与规范执行结构不一致，应为{value}")
        if stopped and next_stake != 0:
            errors.append(f"连挂{losses}期: 达到停止期后仍存在下一期投入")
        if "stopped" in checkpoint and checkpoint.get("stopped") is not stopped:
            errors.append(f"连挂{losses}期: stopped与声明停止期不一致")


def validate_evidence(structure: dict[str, Any], bankroll: dict[str, Any], config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if structure.get("schema_version") != 1:
        errors.append("结构证据schema_version必须为1")
    if structure.get("task_type") != "STANDARD_SCHEME_TASK":
        errors.append("task_type必须为STANDARD_SCHEME_TASK")
    if structure.get("status") not in {"DIRECTOR_COMPLETE", "CONTRACT_FROZEN", "VALIDATED", "COMPLETED"}:
        errors.append("status无效")
    if structure.get("bankroll_stress_ref") != config.get("bankroll_evidence_file_name"):
        errors.append("bankroll_stress_ref必须指向bankroll_stress.json")

    bankroll_amount, base_cost, net_profit, bankroll_paths = bankroll_context(bankroll)
    if bankroll_amount <= 0 or base_cost <= 0:
        errors.append("bankroll_stress缺少可用本金或基础成本")
    paths = structure.get("paths")
    if not isinstance(paths, list) or not paths:
        errors.append("paths必须为非空数组")
        return errors
    ids: set[str] = set()
    for item in paths:
        if not isinstance(item, dict):
            errors.append("路径结构项必须为对象")
            continue
        path_id = str(item.get("path_id", "")).strip()
        if not path_id:
            errors.append("路径结构缺少path_id")
            continue
        if path_id in ids:
            errors.append(f"路径结构ID重复: {path_id}")
        ids.add(path_id)
        validate_path(item, bankroll_paths.get(path_id), bankroll_amount, base_cost, net_profit, errors)
    bankroll_ids = set(bankroll_paths)
    if ids != bankroll_ids:
        errors.append(f"结构路径与bankroll_stress路径集合不一致: structure={sorted(ids)}, bankroll={sorted(bankroll_ids)}")
    validate_loss_stress(structure, bankroll, bankroll_amount, base_cost, net_profit, errors)
    return errors


def cycle_checkpoints(sequence: list[float], stop: int, bankroll: float, base_cost: float, net_profit: float) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for cycle_number in range(1, math.ceil(stop / len(sequence)) + 1):
        losses = min(cycle_number * len(sequence), stop)
        outlay = cumulative_outlay(sequence, "CYCLIC", stop, losses)
        next_stake = stake_at(sequence, "CYCLIC", stop, losses)
        net = hit_net(sequence, "CYCLIC", stop, losses, base_cost, net_profit)
        result.append({
            "cycle_number": cycle_number,
            "losses_at_end": losses,
            "cumulative_outlay": outlay,
            "remaining_bankroll": round(bankroll - outlay, 10),
            "next_period_stake": next_stake,
            "hit_net_after_cycle": net,
            "recovery_complete": bool(next_stake > 0 and net >= 0),
        })
    return result


def make_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    structure = load(TEMPLATE_PATH)
    bankroll = {
        "assumptions": {
            "bankroll": 5000.0,
            "base_period_cost": 0.1,
            "payout_model": {"net_profit_per_base_period_hit": 1.85},
        },
        "candidate_paths": [],
        "loss_streak_stress": [],
    }
    definitions = [
        ("FLAT", [0.1], "CYCLIC", 50),
        ("LIMITED_LINEAR", [0.1, 0.1, 0.2, 0.2, 0.3], "FINITE", 5),
        ("PRESSURE_RELEASE", [0.1, 0.2, 0.3, 0.2, 0.1], "CYCLIC", 50),
        ("ADVANCED_STATE", [0.1] * 10 + [0.2] * 10 + [0.3] * 10 + [0.2] * 10 + [0.1] * 10, "FINITE", 50),
    ]
    structure["paths"] = []
    for path_id, sequence, mode, stop in definitions:
        cycle_limit = math.ceil(stop / len(sequence)) if mode == "CYCLIC" else None
        structure["paths"].append({
            "path_id": path_id,
            "sequence_mode": mode,
            "canonical_sequence": sequence,
            "minimum_repeat_period": len(sequence),
            "effective_design_length": len(sequence),
            "claimed_design_length": len(sequence),
            "execution_horizon": stop,
            "declared_stop_period": stop,
            "cycle_limit": cycle_limit,
            "design_claim": f"{len(sequence)}期循环路径×{cycle_limit}轮" if mode == "CYCLIC" else f"{len(sequence)}期独立路径",
            "cross_cycle_checkpoints": cycle_checkpoints(sequence, stop, 5000.0, 0.1, 1.85) if mode == "CYCLIC" else None,
        })
        bankroll["candidate_paths"].append({
            "path_id": path_id,
            "period_stakes": sequence,
            "declared_stop_period": stop,
            "total_outlay_at_stop": cumulative_outlay(sequence, mode, stop, stop),
        })
    structure["selection"] = {"selected_path_id": "ADVANCED_STATE"}
    selected = next(item for item in structure["paths"] if item["path_id"] == "ADVANCED_STATE")
    for losses in [10, 20, 30, 40, 50]:
        sequence = selected["canonical_sequence"]
        stop = selected["execution_horizon"]
        bankroll["loss_streak_stress"].append({
            "losses": losses,
            "cumulative_outlay": cumulative_outlay(sequence, "FINITE", stop, losses),
            "remaining_bankroll": round(5000.0 - cumulative_outlay(sequence, "FINITE", stop, losses), 10),
            "next_period_stake": stake_at(sequence, "FINITE", stop, losses),
            "hit_net_after_streak": hit_net(sequence, "FINITE", stop, losses, 0.1, 1.85),
            "stopped": losses >= stop,
        })
    return structure, bankroll


def self_test(config: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    structure, bankroll = make_fixture()
    valid_errors = validate_evidence(structure, bankroll, config)
    if valid_errors:
        failures.append("有效夹具被拒绝: " + "; ".join(valid_errors))

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
    bankroll_target.update({
        "period_stakes": pattern * 5,
        "declared_stop_period": 60,
        "total_outlay_at_stop": sum(pattern) * 5,
    })
    if not any("检测到展开式重复块" in error for error in validate_evidence(case_structure, case_bankroll, config)):
        failures.append("12步复制5轮未被识别为展开式重复块")

    case_structure = copy.deepcopy(structure)
    target = next(item for item in case_structure["paths"] if item["path_id"] == "PRESSURE_RELEASE")
    target["claimed_design_length"] = 50
    if not any("claimed_design_length不得超过" in error for error in validate_evidence(case_structure, bankroll, config)):
        failures.append("循环路径夸大独立长度未被拒绝")

    case_structure = copy.deepcopy(structure)
    target = next(item for item in case_structure["paths"] if item["path_id"] == "PRESSURE_RELEASE")
    target["cross_cycle_checkpoints"][1]["cumulative_outlay"] += 1
    if not any("第2轮cumulative_outlay计算不一致" in error for error in validate_evidence(case_structure, bankroll, config)):
        failures.append("跨轮累计亏损错误未被拒绝")

    case_bankroll = copy.deepcopy(bankroll)
    case_bankroll["loss_streak_stress"][-1]["next_period_stake"] = 0.1
    if not any("next_period_stake与规范执行结构不一致" in error for error in validate_evidence(structure, case_bankroll, config)):
        failures.append("停止后继续投注未被拒绝")
    return failures


def scan_runs(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = ROOT / "controller" / "runs"
    if not root.exists():
        return errors
    for structure_path in sorted(root.glob("*/funding_sequence_structure.json")):
        bankroll_path = structure_path.with_name("bankroll_stress.json")
        if not bankroll_path.exists():
            errors.append(f"{structure_path.parent.relative_to(ROOT)}: 缺少bankroll_stress.json")
            continue
        errors.extend(
            f"{structure_path.relative_to(ROOT)}: {error}"
            for error in validate_evidence(load(structure_path), load(bankroll_path), config)
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--bankroll-evidence", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--scan-runs", action="store_true")
    args = parser.parse_args()
    config = load(CONFIG_PATH)
    errors = validate_config(config)
    if args.self_test:
        errors.extend(self_test(config))
    if args.evidence:
        bankroll_path = args.bankroll_evidence or args.evidence.with_name(config["bankroll_evidence_file_name"])
        if not bankroll_path.exists():
            errors.append(f"缺少关联资金证据: {bankroll_path}")
        else:
            errors.extend(validate_evidence(load(args.evidence), load(bankroll_path), config))
    if args.scan_runs:
        errors.extend(scan_runs(config))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("FUNDING_SEQUENCE_STRUCTURE_VALIDATION_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
