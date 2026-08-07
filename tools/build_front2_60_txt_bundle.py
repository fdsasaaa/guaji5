#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PAIRS = ("28", "49", "60", "81", "02")
COMMON = [
    "True",
    "高级定码轮换",
    "软件名称=CXGGJ",
    "玩法类型=前二",
    "玩法名称=直选复式",
    "金额模式=2",
    "投注监控=False-50000",
    "投注监控模式=0",
    "任选中奖=1-10",
    "任选位置=0,1",
    "换号规则=0",
    "换号期数=1",
    "翻倍方式=0",
    "正集=True",
    "倍投类型=1",
    "倍投计划=1,1,1,1,1,1,1,1",
    "倍投方案=高级倍投主配置",
    "显示更多=False",
    "真实投注1=False-50000",
    "真实投注2=False-50000",
    "模拟投注1=False-50000",
    "模拟投注2=False-50000",
    "盈利跳转=False-50000-1",
    "亏损跳转=False-50000-1",
    "盈利停止=False-50000",
    "亏损停止=False-50000",
    "投注时间=False",
    "投注时间类型=0",
    "范围开始时间=False-09:01:00",
    "范围停止时间=False-21:32:00",
    "范围停止类型=0",
    "倒计时停止时间=02:00:00",
    "倒计时停止类型=0",
]


def render(pair: str) -> bytes:
    a, b = pair
    lines = COMMON + [f"高级定码轮换内容=1|{a}-{b}|1|1", "SchemeCreator=", "", ""]
    return "\r\n".join(lines).encode("gbk")


def validate(raw: bytes, pair: str) -> dict[str, object]:
    text = raw.decode("gbk")
    lines = text.splitlines()
    checks = {
        "gbk_no_bom": not raw.startswith(b"\xef\xbb\xbf"),
        "crlf": b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""),
        "line1_true": lines[0] == "True",
        "line2_strategy": lines[1] == "高级定码轮换",
        "front2_direct_multi": "玩法类型=前二" in text and "玩法名称=直选复式" in text,
        "advanced_funding": "倍投类型=1" in text and "倍投方案=高级倍投主配置" in text,
        "pair_content": f"高级定码轮换内容=1|{pair[0]}-{pair[1]}|1|1" in text,
        "scheme_creator_empty": "SchemeCreator=\r\n" in text,
    }
    if not all(checks.values()):
        raise ValueError(f"{pair}: validation failed: {checks}")
    return {**checks, "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"status": "PASS", "strategy": "高级定码轮换", "play_type": "前二", "play_name": "直选复式", "files": {}}
    for i, pair in enumerate(PAIRS, 1):
        name = f"{i:02d}_前二{pair}-高级定码轮换.txt"
        raw = render(pair)
        (args.output / name).write_bytes(raw)
        report["files"][name] = validate(raw, pair)
    (args.output / "TXT补齐验证摘要.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FRONT2_60_TXT_BUNDLE_PASS files=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
