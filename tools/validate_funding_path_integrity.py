#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CHECKPOINTS = [10, 20, 30, 40, 50]
KINDS = {"FLAT", "LIMITED_LINEAR", "PRESSURE_RELEASE", "ADVANCED_STATE"}
FORBIDDEN_CLAIMS = {"长期安全", "稳定盈利", "不容易亏损", "稳赚", "保证回本"}


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _period(seq: list[Any]) -> int | None:
    n = len(seq)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and n // p >= 2 and seq == seq[:p] * (n // p):
            return p
    return None


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version必须为1")
    if not str(data.get("run_id", "")).strip():
        errors.append("run_id不能为空")
    for key in ("capital_base", "minimum_unit", "single_period_cost_at_1x", "gross_return_at_1x"):
        if not _positive(data.get(key)):
            errors.append(f"{key}必须为正数")
    hit_rate = data.get("theoretical_hit_rate")
    if not isinstance(hit_rate, (int, float)) or isinstance(hit_rate, bool) or not 0 < hit_rate < 1:
        errors.append("theoretical_hit_rate必须在0和1之间")

    periods = data.get("historical_periods")
    if not isinstance(periods, int) or isinstance(periods, bool) or periods <= 0:
        errors.append("historical_periods必须为正整数")
    claims = " ".join(map(str, data.get("claims", [])))
    if isinstance(periods, int) and periods < 1000:
        if data.get("data_maturity") != "QUICK_EXPERIMENT_ONLY":
            errors.append("历史数据不足1000期时必须标记QUICK_EXPERIMENT_ONLY")
        for claim in FORBIDDEN_CLAIMS:
            if claim in claims:
                errors.append(f"历史数据不足1000期时禁止声称: {claim}")

    paths = data.get("funding_paths")
    if not isinstance(paths, list) or not paths:
        return errors + ["funding_paths必须为非空数组"]
    ids: set[str] = set()
    kinds: set[str] = set()
    selected: list[dict[str, Any]] = []
    for path in paths:
        if not isinstance(path, dict):
            errors.append("资金路径必须为对象")
            continue
        pid = str(path.get("path_id", "")).strip()
        if not pid or pid in ids:
            errors.append("资金路径ID不能为空或重复")
            continue
        ids.add(pid)
        kind = path.get("kind")
        if kind not in KINDS:
            errors.append(f"{pid}: kind无效")
            continue
        kinds.add(kind)
        if path.get("decision") == "SELECTED":
            selected.append(path)
        for key in ("reset_rule", "cap_rule", "selection_reason"):
            if not str(path.get(key, "")).strip():
                errors.append(f"{pid}: 缺少{key}")
        if kind != "ADVANCED_STATE":
            seq = path.get("sequence")
            if not isinstance(seq, list) or len(seq) < 3 or any(not _positive(v) for v in seq):
                errors.append(f"{pid}: 必须给出至少3档正数序列")
                continue
            if kind == "PRESSURE_RELEASE":
                rose = any(b > a for a, b in zip(seq, seq[1:]))
                released = any(b < a for a, b in zip(seq, seq[1:]))
                if not (rose and released):
                    errors.append(f"{pid}: 压力释放必须同时包含升压和降压")
                p = _period(seq)
                if p is not None and p < len(seq):
                    errors.append(f"{pid}: 检测到{p}档模板机械重复，不能冒充压力释放")
                if path.get("cycle_mode") == "REPEAT":
                    errors.append(f"{pid}: 压力释放不得无限循环，必须有限封顶或转入停止/冷却")
        else:
            if "sequence" in path and path.get("sequence"):
                errors.append(f"{pid}: 高级状态路径不得以固定sequence作为执行主体")
            states = path.get("states")
            transitions = path.get("transitions")
            if not isinstance(states, list) or len(states) < 3:
                errors.append(f"{pid}: 高级状态路径至少3个状态")
            if not isinstance(transitions, list) or len(transitions) < 4:
                errors.append(f"{pid}: 高级状态路径至少4条结构化转移")
            else:
                events: set[str] = set()
                for transition in transitions:
                    if not isinstance(transition, dict) or not all(
                        str(transition.get(key, "")).strip() for key in ("from", "on", "to")
                    ):
                        errors.append(f"{pid}: 每条状态转移必须包含from/on/to")
                        continue
                    events.add(str(transition["on"]).upper())
                for event in ("WIN", "LOSS", "CAP"):
                    if event not in events:
                        errors.append(f"{pid}: 状态转移缺少{event}事件")
            if not str(path.get("partial_recovery_rule", "")).strip():
                errors.append(f"{pid}: 必须说明部分回收后的处理，不能把命中等同于完全回本")

    if kinds != KINDS:
        errors.append(f"必须同时比较四类资金路径，缺少{sorted(KINDS - kinds)}")
    if len(selected) != 1:
        errors.append("必须且只能选择一条资金路径")

    stress = data.get("stress_checkpoints")
    if not isinstance(stress, list):
        errors.append("stress_checkpoints必须为数组")
    else:
        by_n = {row.get("loss_streak"): row for row in stress if isinstance(row, dict)}
        if sorted(by_n) != CHECKPOINTS:
            errors.append("必须完整计算10/20/30/40/50期连续挂期")
        required = {
            "cumulative_investment",
            "remaining_capital",
            "next_multiplier",
            "next_investment",
            "net_after_next_hit",
            "full_recovery",
            "can_continue",
        }
        for n in CHECKPOINTS:
            row = by_n.get(n)
            if row is None:
                continue
            missing = required - set(row)
            if missing:
                errors.append(f"{n}期压力表缺少{sorted(missing)}")
            if row.get("full_recovery") is True and row.get("net_after_next_hit", -1) < 0:
                errors.append(f"{n}期压力表回收判断与净结果矛盾")
            if row.get("can_continue") is True and row.get("remaining_capital", 0) < row.get("next_investment", 0):
                errors.append(f"{n}期压力表继续判断与本金矛盾")

    simulation = data.get("random_simulation")
    if not isinstance(simulation, dict):
        errors.append("random_simulation必须为对象")
    else:
        if not isinstance(simulation.get("paths"), int) or simulation.get("paths", 0) < 10000:
            errors.append("随机压力模拟至少10000条路径")
        if simulation.get("model") not in {"THEORETICAL_BERNOULLI", "EMPIRICAL_BOOTSTRAP"}:
            errors.append("随机模拟必须声明理论伯努利或历史重采样模型")
        if not isinstance(simulation.get("periods_per_path"), int) or simulation.get("periods_per_path", 0) <= 0:
            errors.append("随机模拟每条路径期数无效")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        from test_funding_path_integrity import run_tests

        run_tests()
        print("funding path integrity self-test: PASS")
        return 0
    if not args.evidence:
        parser.error("--evidence is required")
    errors = validate(json.loads(args.evidence.read_text(encoding="utf-8")))
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("funding path integrity: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
