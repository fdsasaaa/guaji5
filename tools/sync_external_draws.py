#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_sources import HashFFCSource, SourceError  # noqa: E402


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="同步并校验哈希分分彩固定历史数据源"
    )
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--cache-root",
        default=str(ROOT / "data_sources" / "hxffc"),
    )
    parser.add_argument("--run-dir")
    parser.add_argument("--min-records", type=int, default=100)
    parser.add_argument("--max-age-minutes", type=int, default=360)
    parser.add_argument("--retention-count", type=int, default=5)
    parser.add_argument(
        "--allow-same-latest",
        action="store_true",
        help="仅诊断/CI允许与上次期号相同；正式方案禁止使用",
    )
    parser.add_argument(
        "--report",
        help="额外写出本次调用报告JSON",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = HashFFCSource(
        cache_root=Path(args.cache_root),
        min_records=args.min_records,
        max_age_minutes=args.max_age_minutes,
        retention_count=args.retention_count,
    )
    try:
        draws, metadata, paths = source.sync(
            task_id=args.task_id,
            task_run_dir=Path(args.run_dir) if args.run_dir else None,
            require_newer=not args.allow_same_latest,
        )
    except SourceError as exc:
        payload = {
            "status": "BLOCKED",
            "failure_state": "EXTERNAL_DATA_SOURCE_FAILED",
            "source_id": HashFFCSource.SOURCE_ID,
            "source_url": HashFFCSource.FIXED_URL,
            "formal_generation_allowed": False,
            "reason": str(exc),
        }
        if args.report:
            write_json(Path(args.report), payload)
        print("DATA_SOURCE_BLOCKED")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    output = {
        "status": "PASS",
        "source_id": HashFFCSource.SOURCE_ID,
        "formal_generation_allowed": True,
        "metadata": metadata,
        "paths": paths,
        "draw_count": len(draws),
        "analysis_input_preview": draws[-3:],
    }
    if args.report:
        write_json(Path(args.report), output)
    print("DATA_SOURCE_VALID")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
