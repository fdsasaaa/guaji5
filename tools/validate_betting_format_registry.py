#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "controller" / "betting_format_registry.json"


class BettingFormatError(ValueError):
    pass


class SemanticFormatMismatch(BettingFormatError):
    pass


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("unknown_format_policy") != "BLOCK_GENERATION":
        raise BettingFormatError("unknown_format_policy must be BLOCK_GENERATION")
    if data.get("semantic_mismatch_policy") != "BLOCK_GENERATION":
        raise BettingFormatError("semantic_mismatch_policy must be BLOCK_GENERATION")
    if not isinstance(data.get("formats"), dict) or not data["formats"]:
        raise BettingFormatError("registry must contain formats")
    if not isinstance(data.get("semantic_intents"), dict) or not data["semantic_intents"]:
        raise BettingFormatError("registry must contain semantic_intents")
    return data


def get_format(
    registry: dict[str, Any], *, strategy: str, play_type: str, play_name: str
) -> tuple[str, dict[str, Any]]:
    matches = [
        (format_id, spec)
        for format_id, spec in registry["formats"].items()
        if spec.get("strategy") == strategy
        and spec.get("play_type") == play_type
        and spec.get("play_name") == play_name
    ]
    if len(matches) != 1:
        raise BettingFormatError(
            f"format lookup must return exactly one match: strategy={strategy!r} "
            f"play_type={play_type!r} play_name={play_name!r}; matches={len(matches)}"
        )
    return matches[0]


def get_format_for_intent(
    registry: dict[str, Any], *, strategy: str, semantic_intent: str
) -> tuple[str, dict[str, Any]]:
    if semantic_intent not in registry["semantic_intents"]:
        raise BettingFormatError(f"unknown semantic intent: {semantic_intent}")
    matches = [
        (format_id, spec)
        for format_id, spec in registry["formats"].items()
        if spec.get("strategy") == strategy and spec.get("semantic_intent") == semantic_intent
    ]
    if len(matches) != 1:
        raise BettingFormatError(
            f"semantic lookup must return exactly one match: strategy={strategy!r} "
            f"semantic_intent={semantic_intent!r}; matches={len(matches)}"
        )
    return matches[0]


def require_generation_usage(spec: dict[str, Any], *, formal: bool) -> None:
    usage = spec.get("generation_usage")
    if formal and usage != "formal_allowed":
        raise BettingFormatError(
            f"formal generation blocked: generation_usage={usage!r}; "
            "this combination requires user import validation"
        )


def validate_bet_content(content: str, spec: dict[str, Any]) -> list[str]:
    cfg = spec["bet_content"]
    model = cfg.get("content_model")
    errors: list[str] = []

    if model == "position_sets":
        separator = cfg["segment_separator"]
        segments = content.split(separator)
        if len(segments) != int(cfg["segment_count"]):
            errors.append(f"segment_count={len(segments)} expected={cfg['segment_count']}")
        for idx, segment in enumerate(segments, 1):
            if cfg.get("segment_must_be_nonempty", True) and not segment:
                errors.append(f"segment{idx}: empty")
                continue
            if not re.fullmatch(r"[0-9]+", segment):
                errors.append(f"segment{idx}: must contain digits only")
            if cfg.get("segment_digits_must_be_unique") and len(set(segment)) != len(segment):
                errors.append(f"segment{idx}: duplicate digits are forbidden")
        return errors

    if model == "complete_numbers":
        width = int(cfg["number_width"])
        separator = cfg["number_separator"]
        if separator != " ":
            errors.append("complete_numbers currently requires one ASCII space separator")
            return errors
        pattern = rf"[0-9]{{{width}}}( [0-9]{{{width}}})*"
        if not re.fullmatch(pattern, content):
            errors.append(
                f"complete-number content must match {width}-digit numbers separated by single spaces"
            )
        return errors

    return [f"unknown content_model={model!r}"]


def exact_pair_to_bet_content(pair: str, spec: dict[str, Any]) -> str:
    """Render one complete two-digit number only for a complete-number format.

    This deliberately refuses to convert 60 -> 6-0. That conversion changes the
    software play semantics from 直选单式 to 直选复式 and is therefore blocked.
    """
    if not re.fullmatch(r"[0-9]{2}", pair):
        raise BettingFormatError(f"exact pair must be exactly two decimal digits: {pair!r}")
    cfg = spec["bet_content"]
    if cfg.get("content_model") != "complete_numbers":
        raise SemanticFormatMismatch(
            f"exact complete number {pair!r} cannot be rendered with "
            f"content_model={cfg.get('content_model')!r}; choose 直选单式 instead of 直选复式"
        )
    errors = validate_bet_content(pair, spec)
    if errors:
        raise BettingFormatError(f"complete number {pair!r} failed registry: {errors}")
    return pair


def position_pair_to_bet_content(pair: str, spec: dict[str, Any]) -> str:
    """Explicit helper for a position-set intent, not for a complete-number intent."""
    if not re.fullmatch(r"[0-9]{2}", pair):
        raise BettingFormatError(f"pair must be exactly two decimal digits: {pair!r}")
    cfg = spec["bet_content"]
    if cfg.get("content_model") != "position_sets" or int(cfg.get("segment_count", 0)) != 2:
        raise SemanticFormatMismatch("position-set renderer requires a registered 2-segment position_sets format")
    content = cfg["segment_separator"].join((pair[0], pair[1]))
    errors = validate_bet_content(content, spec)
    if errors:
        raise BettingFormatError(f"position-set content {content!r} failed registry: {errors}")
    return content


def render_round(
    content: str,
    spec: dict[str, Any],
    *,
    round_id: int = 1,
    param1: int = 1,
    param2: int = 1,
) -> str:
    errors = validate_bet_content(content, spec)
    if errors:
        raise BettingFormatError(f"invalid bet content {content!r}: {errors}")
    pattern = spec["bet_content"]["outer_pattern"]
    return pattern.format(round=round_id, bet_content=content, param1=param1, param2=param2)


def parse_main_txt(text: str) -> tuple[list[str], dict[str, str]]:
    lines = text.splitlines()
    fields: dict[str, str] = {}
    for line in lines[2:]:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return lines, fields


def validate_main_txt(text: str, spec: dict[str, Any]) -> list[str]:
    lines, fields = parse_main_txt(text)
    req = spec["required_template_values"]
    errors: list[str] = []
    if not lines or lines[0] != req["line1"]:
        errors.append(f"line1 must be {req['line1']!r}")
    if len(lines) < 2 or lines[1] != req["line2"]:
        errors.append(f"line2 must be {req['line2']!r}")
    for key, expected in req.items():
        if key in {"line1", "line2"}:
            continue
        actual = fields.get(key)
        if actual != expected:
            errors.append(f"{key}={actual!r}, expected {expected!r}")
    field_value = fields.get("高级定码轮换内容")
    if field_value is None:
        errors.append("missing 高级定码轮换内容")
    else:
        parts = field_value.split("|")
        if len(parts) != 4:
            errors.append("高级定码轮换内容 must contain exactly four pipe-separated fields for one round")
        else:
            errors.extend(validate_bet_content(parts[1], spec))
    return errors


def self_test() -> None:
    registry = load_registry()

    multi_id, multi = get_format(
        registry, strategy="高级定码轮换", play_type="前二", play_name="直选复式"
    )
    assert multi_id == "CAT05_FRONT2_DIRECT_MULTI"
    assert not validate_bet_content("6-0", multi)
    assert not validate_bet_content("012-123", multi)
    assert validate_bet_content("60", multi)
    assert position_pair_to_bet_content("60", multi) == "6-0"
    try:
        exact_pair_to_bet_content("60", multi)
    except SemanticFormatMismatch:
        pass
    else:
        raise AssertionError("60 must never be silently rewritten to 6-0 for an exact-number intent")

    single_id, single = get_format_for_intent(
        registry,
        strategy="高级定码轮换",
        semantic_intent="EXACT_COMPLETE_TWO_DIGIT_NUMBER",
    )
    assert single_id == "CAT05_FRONT2_DIRECT_SINGLE_TEST"
    assert exact_pair_to_bet_content("60", single) == "60"
    assert not validate_bet_content("08", single)
    assert not validate_bet_content("28 49 60 81 02", single)
    for bad in single["invalid_examples"]:
        assert validate_bet_content(bad, single), f"negative example unexpectedly passed: {bad}"
    try:
        require_generation_usage(single, formal=True)
    except BettingFormatError:
        pass
    else:
        raise AssertionError("test_only direct-single carrier must block formal generation")

    good_text = "\n".join(
        [
            "False",
            "高级定码轮换",
            "软件名称=CXGGJ",
            "玩法类型=前二",
            "玩法名称=直选单式",
            "任选位置=",
            "换号期数=1",
            "高级定码轮换内容=1|60|1|1",
        ]
    )
    assert not validate_main_txt(good_text, single)
    wrong_semantics = good_text.replace("玩法名称=直选单式", "玩法名称=直选复式").replace(
        "1|60|1|1", "1|6-0|1|1"
    )
    assert validate_main_txt(wrong_semantics, single)
    print("BETTING_FORMAT_REGISTRY_SELF_TEST_PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    load_registry()
    if args.self_test:
        self_test()
    else:
        print("BETTING_FORMAT_REGISTRY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
