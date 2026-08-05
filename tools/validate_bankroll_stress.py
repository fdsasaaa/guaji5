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
CONFIG_PATH = ROOT / "controller" / "bankroll_stress.json"
TEMPLATE_PATH = ROOT / "controller" / "templates" / "bankroll_stress.template.json"
KINDS = {"FLAT", "LIMITED_LINEAR", "PRESSURE_RELEASE", "ADVANCED_STATE"}
DECISIONS = {"SELECTED", "REJECTED", "PROBE_ONLY"}
EVIDENCE = {f"E{i}": i for i in range(8)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def pos(value: Any) -> bool:
    return num(value) and float(value) > 0


def nonneg(value: Any) -> bool:
    return num(value) and float(value) >= 0


def present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def close(a: Any, b: Any) -> bool:
    return num(a) and num(b) and math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-6)


def tier_for(draws: int, cfg: dict[str, Any]) -> dict[str, Any] | None:
    for item in cfg.get("data_maturity_tiers", []):
        lo, hi = item.get("min_draws"), item.get("max_draws")
        if isinstance(lo, int) and draws >= lo and (hi is None or draws <= hi):
            return item
    return None


def validate_config(cfg: dict[str, Any]) -> list[str]:
    e: list[str] = []
    if cfg.get("schema_version") != 1: e.append("配置schema_version必须为1")
    if cfg.get("status") != "ACTIVE": e.append("资金压力配置必须为ACTIVE")
    if not pos(cfg.get("default_bankroll")): e.append("default_bankroll必须为正数")
    if not pos(cfg.get("default_minimum_stake")) or float(cfg.get("default_minimum_stake", 0)) < 0.1:
        e.append("default_minimum_stake不得低于0.1元")
    if set(cfg.get("required_path_kinds", [])) != KINDS: e.append("必须保留四类资金路径")
    if cfg.get("required_loss_streak_checkpoints") != [10, 20, 30, 40, 50]:
        e.append("必须固定检查10/20/30/40/50期连挂")
    if not isinstance(cfg.get("minimum_random_trials"), int) or cfg.get("minimum_random_trials", 0) < 10000:
        e.append("随机模拟下限必须至少10000条路径")
    if len(cfg.get("data_maturity_tiers", [])) < 4: e.append("数据成熟度分层不完整")
    required = (
        "theoretical_probability_required", "deterministic_streak_stress_required",
        "random_simulation_required", "historical_validation_required",
        "selected_path_must_survive_declared_stop", "recovery_claim_requires_explicit_payout_math",
        "negative_expectation_disclaimer_required", "software_executable_evidence_required",
    )
    for key in required:
        if cfg.get("requirements", {}).get(key) is not True: e.append(f"配置未启用: {key}")
    return e


def validate_path(path: dict[str, Any], bankroll: float, minimum: float, errors: list[str]) -> None:
    pid, kind = str(path.get("path_id", "<unknown>")), path.get("kind")
    if kind not in KINDS: errors.append(f"{pid}: kind无效")
    if path.get("decision") not in DECISIONS: errors.append(f"{pid}: decision无效")
    stakes = path.get("period_stakes")
    if not isinstance(stakes, list) or len(stakes) < 3 or any(not pos(x) for x in stakes):
        errors.append(f"{pid}: period_stakes至少3项且全部为正数"); return
    if any(float(x) + 1e-9 < minimum for x in stakes): errors.append(f"{pid}: 投注金额不得低于冻结最低投注{minimum}")
    if kind == "FLAT" and len({round(float(x), 9) for x in stakes}) != 1: errors.append(f"{pid}: FLAT必须恒定")
    if kind == "LIMITED_LINEAR" and (max(stakes) <= min(stakes) or any(float(b) < float(a) for a, b in zip(stakes, stakes[1:]))):
        errors.append(f"{pid}: LIMITED_LINEAR必须有限且不下降")
    if kind == "PRESSURE_RELEASE":
        rose = released = False
        for a, b in zip(stakes, stakes[1:]):
            if float(b) > float(a): rose = True
            if rose and float(b) < float(a): released = True
        if not released: errors.append(f"{pid}: PRESSURE_RELEASE必须先升压后降压")
    for key in ("algorithm", "reset_rule", "cap_rule", "reason"):
        if not present(path.get(key)): errors.append(f"{pid}: 缺少{key}")
    if not isinstance(path.get("declared_stop_period"), int) or path.get("declared_stop_period", 0) < 1:
        errors.append(f"{pid}: declared_stop_period无效")
    if not close(path.get("max_single_period_stake"), max(float(x) for x in stakes)):
        errors.append(f"{pid}: max_single_period_stake与序列不一致")
    if not pos(path.get("total_outlay_at_stop")): errors.append(f"{pid}: total_outlay_at_stop必须为正数")
    if path.get("decision") == "SELECTED" and float(path.get("total_outlay_at_stop", 0)) > bankroll + 1e-6:
        errors.append(f"{pid}: 正式路径累计投入超过本金")
    level = EVIDENCE.get(str(path.get("software_evidence_level")), -1)
    if level < 0: errors.append(f"{pid}: software_evidence_level无效")
    if path.get("decision") == "SELECTED":
        if level < 3: errors.append(f"{pid}: 正式路径软件证据不得低于E3")
        refs = path.get("software_evidence_refs")
        if not isinstance(refs, list) or not refs or any(not present(x) for x in refs):
            errors.append(f"{pid}: 正式路径必须绑定软件执行证据")


def validate_evidence(data: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    e: list[str] = []
    if data.get("schema_version") != 1: e.append("证据schema_version必须为1")
    if data.get("task_type") != "STANDARD_SCHEME_TASK": e.append("task_type必须为STANDARD_SCHEME_TASK")
    if data.get("status") not in {"DIRECTOR_COMPLETE", "CONTRACT_FROZEN", "VALIDATED", "COMPLETED"}: e.append("status无效")

    a = data.get("assumptions", {}) if isinstance(data.get("assumptions"), dict) else {}
    bankroll, minimum = a.get("bankroll"), a.get("minimum_stake")
    if not pos(bankroll): e.append("bankroll必须为正数"); bankroll = 0.0
    if not pos(minimum) or float(minimum or 0) < 0.1: e.append("minimum_stake不得低于0.1元"); minimum = 0.1
    if a.get("bankroll_source") not in {"DEFAULT_5000", "USER_SPECIFIED"}: e.append("bankroll_source必须为DEFAULT_5000或USER_SPECIFIED")
    if a.get("bankroll_source") == "DEFAULT_5000" and not close(bankroll, cfg.get("default_bankroll")): e.append("默认本金必须使用5000元")
    if a.get("currency") != cfg.get("currency"): e.append("currency与配置不一致")
    if not isinstance(a.get("bets_per_period"), int) or a.get("bets_per_period", 0) < 1: e.append("bets_per_period必须为正整数")
    if not pos(a.get("base_period_cost")) or float(a.get("base_period_cost", 0)) < float(minimum): e.append("base_period_cost不得低于最低投注")
    payout = a.get("payout_model", {}) if isinstance(a.get("payout_model"), dict) else {}
    for key in ("gross_return_per_base_period_hit", "net_profit_per_base_period_hit"):
        if not num(payout.get(key)): e.append(f"payout_model.{key}必须为数字")
    if not present(payout.get("calculation")): e.append("payout_model必须给出明确计算公式")
    if not isinstance(payout.get("evidence_refs"), list): e.append("payout_model.evidence_refs必须为数组")

    m = data.get("data_maturity", {}) if isinstance(data.get("data_maturity"), dict) else {}
    draws = m.get("draw_count")
    if not isinstance(draws, int) or isinstance(draws, bool) or draws < 1: e.append("draw_count必须为正整数"); draws = 1
    tier = tier_for(draws, cfg)
    if not tier: e.append("无法确定数据成熟度")
    else:
        if m.get("tier") != tier.get("tier"): e.append("data_maturity.tier与draw_count不一致")
        if m.get("claim_ceiling") != tier.get("claim_ceiling"): e.append("claim_ceiling与数据成熟度不一致")
    if not present(m.get("history_role")): e.append("history_role不能为空")
    if draws < cfg["requirements"]["long_term_safety_claim_forbidden_when_draws_lt"] and m.get("long_term_safe_claim") is not False:
        e.append("不足10000期不得声称长期安全")

    econ = data.get("scheme_economics", {}) if isinstance(data.get("scheme_economics"), dict) else {}
    if not num(econ.get("theoretical_hit_rate")) or not 0 < float(econ.get("theoretical_hit_rate", 0)) < 1: e.append("theoretical_hit_rate必须在0和1之间")
    if not present(econ.get("theoretical_hit_rate_source")): e.append("必须说明理论命中率来源")
    if not num(econ.get("historical_hit_rate")) or not 0 <= float(econ.get("historical_hit_rate", -1)) <= 1: e.append("historical_hit_rate必须在0和1之间")
    if not num(econ.get("expected_value_per_base_period")): e.append("expected_value_per_base_period必须为数字")
    if "不改变" not in str(econ.get("negative_expectation_disclaimer", "")): e.append("必须明确倍投不改变彩票底层期望")

    paths = data.get("candidate_paths", []) if isinstance(data.get("candidate_paths"), list) else []
    kinds = {p.get("kind") for p in paths if isinstance(p, dict)}
    if KINDS - kinds: e.append(f"资金候选四路不完整: {sorted(KINDS - kinds)}")
    by_id: dict[str, dict[str, Any]] = {}; selected: list[str] = []
    for path in paths:
        if not isinstance(path, dict): e.append("资金路径必须为对象"); continue
        pid = str(path.get("path_id", "")).strip()
        if not pid: e.append("资金路径缺少path_id"); continue
        if pid in by_id: e.append(f"资金路径ID重复: {pid}")
        by_id[pid] = path
        if path.get("decision") == "SELECTED": selected.append(pid)
        validate_path(path, float(bankroll), float(minimum), e)
    if len(selected) != 1: e.append("必须且只能选择一条正式资金路径")

    stress = data.get("loss_streak_stress", []) if isinstance(data.get("loss_streak_stress"), list) else []
    by_loss = {x.get("losses"): x for x in stress if isinstance(x, dict)}
    for checkpoint in cfg.get("required_loss_streak_checkpoints", []):
        item = by_loss.get(checkpoint)
        if item is None: e.append(f"缺少连续挂{checkpoint}期压力测试"); continue
        for key in ("cumulative_outlay", "remaining_bankroll", "next_period_stake", "hit_net_after_streak"):
            if not num(item.get(key)): e.append(f"连挂{checkpoint}期: {key}必须为数字")
        if nonneg(item.get("cumulative_outlay")) and not close(item.get("remaining_bankroll"), float(bankroll) - float(item["cumulative_outlay"])):
            e.append(f"连挂{checkpoint}期: 剩余本金计算不一致")
        survives = nonneg(item.get("remaining_bankroll")) and float(item.get("remaining_bankroll", -1)) >= float(item.get("next_period_stake", 0))
        if item.get("survives") is not survives: e.append(f"连挂{checkpoint}期: survives与资金计算不一致")
        if not isinstance(item.get("recovery_complete"), bool): e.append(f"连挂{checkpoint}期: recovery_complete必须为布尔值")
        if item.get("recovery_complete") is True and float(item.get("hit_net_after_streak", -1)) < 0: e.append(f"连挂{checkpoint}期: 声称完全回收但命中净结果为负")

    sim = data.get("probabilistic_stress", {}) if isinstance(data.get("probabilistic_stress"), dict) else {}
    if not present(sim.get("model")): e.append("随机压力测试缺少模型")
    if not isinstance(sim.get("simulation_trials"), int) or sim.get("simulation_trials", 0) < cfg.get("minimum_random_trials", 10000): e.append("simulation_trials不得低于10000")
    if not isinstance(sim.get("sequence_length"), int) or sim.get("sequence_length", 0) < 50: e.append("sequence_length不得低于50")
    if not isinstance(sim.get("seed"), int): e.append("随机模拟必须冻结seed")
    for key in ("ruin_probability", "probability_drawdown_10pct", "probability_drawdown_20pct"):
        if not num(sim.get(key)) or not 0 <= float(sim.get(key, -1)) <= 1: e.append(f"{key}必须在0和1之间")
    for key in ("median_max_drawdown", "p95_max_drawdown"):
        if not nonneg(sim.get(key)): e.append(f"{key}必须为非负数")
    if nonneg(sim.get("median_max_drawdown")) and nonneg(sim.get("p95_max_drawdown")) and float(sim["p95_max_drawdown"]) < float(sim["median_max_drawdown"]): e.append("p95_max_drawdown不得低于median_max_drawdown")
    for key in ("assumptions", "result_interpretation"):
        if not present(sim.get(key)): e.append(f"随机压力测试缺少{key}")

    hist = data.get("historical_validation", {}) if isinstance(data.get("historical_validation"), dict) else {}
    if hist.get("draw_count") != draws: e.append("historical_validation.draw_count与data_maturity不一致")
    if not present(hist.get("split_method")): e.append("historical_validation缺少split_method")
    if not present(hist.get("limitations")): e.append("historical_validation必须披露局限")
    req = cfg.get("requirements", {})
    if draws >= req.get("sample_split_required_when_draws_gte", 1000) and (not present(hist.get("training_range")) or not present(hist.get("validation_range"))): e.append("1000期以上必须给出训练区和验证区")
    if draws >= req.get("rolling_validation_required_when_draws_gte", 5000) and (not isinstance(hist.get("rolling_windows"), list) or not hist.get("rolling_windows")): e.append("5000期以上必须做滚动验证")
    if draws >= req.get("sealed_oos_required_when_draws_gte", 10000) and not present(hist.get("sealed_oos_range")): e.append("10000期以上必须保留封存样本外区")

    sel = data.get("selection", {}) if isinstance(data.get("selection"), dict) else {}
    sid, stop = sel.get("selected_path_id"), sel.get("declared_stop_period")
    if sid not in by_id or by_id.get(sid, {}).get("decision") != "SELECTED": e.append("selected_path_id不存在或未标记SELECTED")
    if not present(sel.get("selected_profile_id")): e.append("selection缺少selected_profile_id")
    if not isinstance(stop, int) or stop < 1: e.append("selection.declared_stop_period无效")
    for key in ("max_allowed_drawdown", "max_allowed_single_period_stake"):
        if not nonneg(sel.get(key)): e.append(f"selection.{key}必须为非负数")
    for key in ("decision_reason", "claim"):
        if not present(sel.get(key)): e.append(f"selection缺少{key}")
    if any(term in str(sel.get("claim", "")) for term in ("稳定盈利", "长期不亏", "稳赚", "必赚")): e.append("selection.claim包含禁止的长期盈利或不亏承诺")
    if isinstance(stop, int) and sid in by_id:
        item = by_loss.get(stop)
        if item is None: e.append("最终停止期必须在loss_streak_stress中有对应检查点")
        elif item.get("survives") is not True: e.append("正式路径在声明停止期前无法维持本金")
        if by_id[sid].get("declared_stop_period") != stop: e.append("资金路径与selection的停止期不一致")
    return e


def make_valid_fixture() -> dict[str, Any]:
    d = load(TEMPLATE_PATH)
    d["assumptions"]["payout_model"].update({"gross_return_per_base_period_hit": 1.95, "net_profit_per_base_period_hit": 1.85, "calculation": "命中毛返1.95元-本期成本0.1元=净1.85元", "evidence_refs": ["fixture:payout"]})
    d["scheme_economics"].update({"theoretical_hit_rate": .5, "theoretical_hit_rate_source": "定位胆选择5个数字，理论命中率5/10", "historical_hit_rate": .51, "expected_value_per_base_period": -.01})
    sequences = {
        "FLAT": [0.1] * 50,
        "LIMITED_LINEAR": [0.1] * 10 + [0.2] * 10 + [0.3] * 10 + [0.4] * 10 + [0.5] * 10,
        "PRESSURE_RELEASE": [0.1, 0.2, 0.3, 0.2, 0.1] * 10,
        "ADVANCED_STATE": [0.1] * 10 + [0.2] * 10 + [0.3] * 10 + [0.2] * 10 + [0.1] * 10,
    }
    for p in d["candidate_paths"]:
        p.update({"reason": "用于统一比较", "software_evidence_level": "E3", "software_evidence_refs": [f"fixture:{p['path_id']}"]})
        p["period_stakes"] = sequences[p["kind"]]; p["max_single_period_stake"] = max(p["period_stakes"]); p["total_outlay_at_stop"] = round(sum(p["period_stakes"]), 10)
        p["decision"] = "SELECTED" if p["path_id"] == "ADVANCED_STATE" else "REJECTED"
    stakes = sequences["ADVANCED_STATE"]
    for x in d["loss_streak_stress"]:
        n = x["losses"]; out = round(sum(stakes[:n]), 10); next_stake = stakes[min(n, len(stakes) - 1)]
        x.update({"cumulative_outlay": out, "remaining_bankroll": round(5000 - out, 10), "next_period_stake": next_stake, "hit_net_after_streak": -out + 1.85 * next_stake / .1, "recovery_complete": False, "survives": True})
    d["probabilistic_stress"].update({"ruin_probability": .001, "probability_drawdown_10pct": .02, "probability_drawdown_20pct": .005, "median_max_drawdown": 45.0, "p95_max_drawdown": 160.0, "assumptions": "独立伯努利近似，仅用于压力测试"})
    d["historical_validation"].update({"training_range": "draws-1-120", "validation_range": "draws-121-200", "historical_max_loss_streak": 8})
    d["selection"].update({"selected_profile_id": "EXECUTION_OR_FUNDING", "max_allowed_drawdown": 500.0, "max_allowed_single_period_stake": .3, "decision_reason": "兼顾生存期、暴露和软件可执行性"})
    return d


def self_test(cfg: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    valid = make_valid_fixture(); errors = validate_evidence(valid, cfg)
    if errors: failures.append("有效夹具被拒绝: " + "; ".join(errors))
    cases: list[tuple[str, dict[str, Any], str]] = []
    c = copy.deepcopy(valid); c["assumptions"]["minimum_stake"] = .01; cases.append(("最低投注", c, "minimum_stake不得低于0.1元"))
    c = copy.deepcopy(valid); c["candidate_paths"] = c["candidate_paths"][:-1]; cases.append(("四路缺失", c, "资金候选四路不完整"))
    c = copy.deepcopy(valid); c["loss_streak_stress"] = [x for x in c["loss_streak_stress"] if x["losses"] != 50]; cases.append(("50期缺失", c, "缺少连续挂50期压力测试"))
    c = copy.deepcopy(valid); c["probabilistic_stress"]["simulation_trials"] = 999; cases.append(("模拟不足", c, "simulation_trials不得低于10000"))
    c = copy.deepcopy(valid); c["data_maturity"]["long_term_safe_claim"] = True; cases.append(("短样本过度声称", c, "不足10000期不得声称长期安全"))
    c = copy.deepcopy(valid); c["selection"]["claim"] = "长期不亏并稳定盈利"; cases.append(("禁止承诺", c, "selection.claim包含禁止"))
    c = copy.deepcopy(valid); c["candidate_paths"][3]["software_evidence_level"] = "E2"; cases.append(("证据不足", c, "正式路径软件证据不得低于E3"))
    for name, fixture, expected in cases:
        got = validate_evidence(fixture, cfg)
        if not any(expected in msg for msg in got): failures.append(f"{name}: 未命中{expected!r}; 实际={got}")
    return failures


def scan_runs(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []; root = ROOT / "controller" / "runs"
    if not root.exists(): return errors
    for path in sorted(root.glob("*/bankroll_stress.json")):
        errors.extend(f"{path.relative_to(ROOT)}: {x}" for x in validate_evidence(load(path), cfg))
    return errors


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--evidence", type=Path); p.add_argument("--self-test", action="store_true"); p.add_argument("--scan-runs", action="store_true"); args = p.parse_args()
    cfg = load(CONFIG_PATH); errors = validate_config(cfg)
    if args.self_test: errors.extend(self_test(cfg))
    if args.evidence: errors.extend(validate_evidence(load(args.evidence), cfg))
    if args.scan_runs: errors.extend(scan_runs(cfg))
    if not args.evidence and not args.self_test and not args.scan_runs: errors.extend(validate_evidence(load(TEMPLATE_PATH), cfg))
    if errors:
        for error in errors: print(f"ERROR: {error}")
        return 1
    print("BANKROLL_STRESS_VALIDATION_OK"); return 0


if __name__ == "__main__": sys.exit(main())
