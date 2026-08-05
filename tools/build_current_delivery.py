#!/usr/bin/env python3
"""Retired fixed-data Hash FFC batch builder.

The historical implementation depended on a repository-committed 200-draw file.
That input model is forbidden. New Hash FFC tasks must first run the governed
external data-source PREFLIGHT and consume its read-only task snapshot.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "BLOCKED_LEGACY_FIXED_DATA_BUILDER: build_current_delivery.py 已停用；"
    "先运行 tools/sync_external_draws.py 生成本次只读数据快照，"
    "再由当前方案导演按 design_contract.json 构建方案。"
)


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
