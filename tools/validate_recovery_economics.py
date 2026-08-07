#!/usr/bin/env python3
"""Validate a recovery-economics evidence JSON without claiming lottery advantage."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def fail(msg: str) -> None:
    raise ValueError(msg)


def validate(data: dict) -> dict:
    required = ["bankroll", "unit_total_cost", "gross_payout", "minimum_profit", "sequence", "platform_limits"]
    missing = [k for k in required if k not in data]
    if missing:
        fail(f"missing fields: {missing}")
    bankroll = float(data["bankroll"])
    c = float(data["unit_total_cost"])
    p = float(data["gross_payout"])
    g = float(data["minimum_profit"])
    r = float(data.get("rebate_rate", 0))
    seq = data["sequence"]
    if not isinstance(seq, list) or not seq:
        fail("sequence must be a non-empty list")
    if any((not isinstance(x, int)) or x <= 0 for x in seq):
        fail("all multipliers must be positive integers")
    if p <= c:
        fail("gross payout must exceed one-unit total cost")
    lim = data["platform_limits"]
    if any(lim.get(k) is None for k in ["max_multiplier", "max_period_total", "minimum_order"]):
        fail("platform limits must not be null")
    stages = []
    S = 0
    for i, m in enumerate(seq, 1):
        previous = c * S
        current = c * m
        rebate = c * (S + m) * r
        net = p * m + rebate - previous - current
        stages.append({"stage": i, "multiplier": m, "net": round(net, 8), "exposure": current})
        if net + 1e-9 < g:
            fail(f"stage {i} fails minimum profit: {net} < {g}")
        if m > float(lim["max_multiplier"]):
            fail(f"stage {i} exceeds max multiplier")
        if current > float(lim["max_period_total"]):
            fail(f"stage {i} exceeds max period total")
        S += m
    total = c * S
    if total > bankroll + 1e-9:
        fail(f"full-chain exposure {total} exceeds bankroll {bankroll}")
    return {
        "status": "PASS",
        "stages": len(seq),
        "total_multiplier": S,
        "full_chain_exposure": total,
        "max_multiplier": max(seq),
        "max_period_exposure": c * max(seq),
        "minimum_net": min(x["net"] for x in stages),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence", type=Path)
    args = ap.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    try:
        result = validate(data)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
