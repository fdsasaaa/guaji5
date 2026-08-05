#!/usr/bin/env python3
"""Retired fixed-data Hash FFC B394 builder.

The historical implementation read a repository-committed draw file. The
external data-source gate now owns all Hash FFC task inputs, so this builder
must not silently reuse or recreate the removed snapshot.
"""

from __future__ import annotations

MESSAGE = (
    "BLOCKED_LEGACY_FIXED_DATA_BUILDER: build_b394_delivery.py 已停用；"
    "哈希分分彩任务必须先通过外部固定Release数据源PREFLIGHT，"
    "并只读取本次运行目录中的 inputs/hxffc_draws.json。"
)


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
