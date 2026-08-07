#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_betting_format_registry import (
    exact_pair_to_bet_content,
    get_format_for_intent,
    load_registry,
    render_round,
    validate_main_txt,
)

PAIRS = ("28", "49", "60", "81", "02")
STRATEGY = "高级定码轮换"
PLAY_TYPE = "前二"
PLAY_NAME = "直选单式"
SEMANTIC_INTENT = "EXACT_COMPLETE_TWO_DIGIT_NUMBER"

# 这是验证包，不是正式资金方案。当前组合仍缺用户导入验证。
COMMON = [
    "False",
    STRATEGY,
    "软件名称=CXGGJ",
    f"玩法类型={PLAY_TYPE}",
    f"玩法名称={PLAY_NAME}",
    "金额模式=2",
    "投注监控=False-50000",
    "投注监控模式=0",
    "任选中奖=1-10",
    "任选位置=",
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


def format_spec() -> tuple[str, dict[str, object]]:
    registry = load_registry()
    return get_format_for_intent(
        registry,
        strategy=STRATEGY,
        semantic_intent=SEMANTIC_INTENT,
    )


def render(pair: str) -> bytes:
    _, spec = format_spec()
    bet_content = exact_pair_to_bet_content(pair, spec)
    round_definition = render_round(bet_content, spec, round_id=1, param1=1, param2=1)
    lines = COMMON + [f"高级定码轮换内容={round_definition}", "SchemeCreator=", "", ""]
    text = "\r\n".join(lines)
    errors = validate_main_txt(text, spec)
    if errors:
        raise ValueError(f"{pair}: registered semantic/format gate failed before encoding: {errors}")
    return text.encode("gbk")


def validate(raw: bytes, pair: str) -> dict[str, object]:
    format_id, spec = format_spec()
    text = raw.decode("gbk")
    lines = text.splitlines()
    expected_content = exact_pair_to_bet_content(pair, spec)
    expected_round = render_round(expected_content, spec, round_id=1, param1=1, param2=1)
    format_errors = validate_main_txt(text, spec)
    checks = {
        "format_id": format_id,
        "semantic_intent": SEMANTIC_INTENT,
        "generation_usage": spec.get("generation_usage"),
        "gbk_no_bom": not raw.startswith(b"\xef\xbb\xbf"),
        "crlf": b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""),
        "line1_test_only_false": lines[0] == "False",
        "line2_strategy": lines[1] == STRATEGY,
        "front2_direct_single": f"玩法类型={PLAY_TYPE}" in text and f"玩法名称={PLAY_NAME}" in text,
        "optional_position_empty": "任选位置=\r\n" in text,
        "advanced_funding_reference": "倍投类型=1" in text and "倍投方案=高级倍投主配置" in text,
        "complete_pair_content": f"高级定码轮换内容={expected_round}" in text,
        "no_direct_multi_rewrite": f"高级定码轮换内容=1|{pair[0]}-{pair[1]}|1|1" not in text,
        "registry_gate": not format_errors,
        "scheme_creator_empty": "SchemeCreator=\r\n" in text,
        "generation_usage_test_only": spec.get("generation_usage") == "test_only",
        "formal_delivery_blocked": spec.get("allow_formal") is False,
        "needs_user_import_validation": spec.get("needs_user_import_validation") is True,
    }
    bool_checks = {key: value for key, value in checks.items() if isinstance(value, bool)}
    if not all(bool_checks.values()):
        raise ValueError(f"{pair}: validation failed: {checks}; format_errors={format_errors}")
    return {**checks, "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    format_id, spec = format_spec()
    report: dict[str, object] = {
        "status": "TEST_ONLY_PASS",
        "formal_delivery": False,
        "needs_user_import_validation": True,
        "format_id": format_id,
        "semantic_intent": SEMANTIC_INTENT,
        "strategy": STRATEGY,
        "play_type": PLAY_TYPE,
        "play_name": PLAY_NAME,
        "generation_usage": spec.get("generation_usage"),
        "files": {},
    }
    for i, pair in enumerate(PAIRS, 1):
        name = f"{i:02d}_前二{pair}-高级定码轮换_直选单式_验证.txt"
        raw = render(pair)
        (args.output / name).write_bytes(raw)
        report["files"][name] = validate(raw, pair)
    (args.output / "TXT直选单式验证摘要.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"FRONT2_60_DIRECT_SINGLE_TEST_BUNDLE_PASS files=5 format_id={format_id} formal=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
