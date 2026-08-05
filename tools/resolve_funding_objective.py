#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(request: str, config: dict[str, Any]) -> dict[str, Any]:
    text = request.strip()
    if not text:
        raise ValueError("request不能为空")
    hits: dict[str, list[str]] = {}
    for objective in ("DURABLE", "RECOVERY_PROFIT"):
        terms = config["objective_types"][objective].get("explicit_terms", [])
        matched = [term for term in terms if term in text]
        if matched:
            hits[objective] = matched
    if len(hits) == 1:
        objective = next(iter(hits))
        reason = f"命中明确资金目标词: {', '.join(hits[objective])}"
    elif len(hits) == 0:
        objective = config.get("default_when_unspecified", "AUTO_COMPARE")
        reason = "未发现明确资金目标词，进入耐久型与回利型双候选比较"
    else:
        objective = "AUTO_COMPARE"
        reason = "同时出现两类目标，必须双候选比较，禁止擅自选择"
    return {
        "schema_version": 1,
        "request": text,
        "objective_type": objective,
        "reason": reason,
        "matched_terms": hits,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--config", type=Path, default=Path("controller/funding_objectives.json"))
    args = parser.parse_args()
    print(json.dumps(resolve(args.request, load_config(args.config)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
