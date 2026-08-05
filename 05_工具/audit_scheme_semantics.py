#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELIMITER_POLICY = ROOT / "scheme_field_delimiter_policy.json"
DEFAULT_MONITOR_POLICY = ROOT / "betting_monitor_policy.json"


def decode(data):
    for enc in ("gbk", "utf-8-sig", "utf-8"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("unknown", data, 0, 1, "cannot decode")


def parse_fields(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    fields = {}
    for line in lines[2:]:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return lines, fields


def valid_group(group):
    nums = [x.strip() for x in group.split(",") if x.strip()]
    return bool(nums) and len(nums) == len(set(nums)) and all(
        x.isdigit() and 0 <= int(x) <= 9 for x in nums
    )


def load_json_policy(path, required, label):
    with Path(path).open("r", encoding="utf-8") as fh:
        policy = json.load(fh)
    missing = sorted(required - set(policy))
    if missing:
        raise ValueError(f"{label}缺少字段: {', '.join(missing)}")
    return policy


def load_delimiter_policy(path=DEFAULT_DELIMITER_POLICY):
    return load_json_policy(
        path,
        {
            "direct_single_group_fields",
            "forbidden_group_delimiters",
            "structural_semicolon_whitelist",
            "multi_group_resolution",
        },
        "分隔符策略",
    )


def load_monitor_policy(path=DEFAULT_MONITOR_POLICY):
    return load_json_policy(
        path,
        {
            "monitor_field",
            "mode_field",
            "enabled_prefix",
            "disabled_values",
            "allowed_symbols",
            "allowed_modes",
            "disabled_mode",
            "symbol_meaning",
        },
        "投注监控策略",
    )


def is_scheme(lines):
    return len(lines) >= 2 and lines[0] in {"True", "False"} and bool(lines[1])


def check_direct_number_delimiters(fields, policy, errors):
    forbidden = tuple(policy["forbidden_group_delimiters"])
    for field in policy["direct_single_group_fields"]:
        value = fields.get(field)
        if not value:
            continue
        bad = [delimiter for delimiter in forbidden if delimiter in value]
        if not bad:
            continue
        shown = "、".join(repr(x) for x in bad)
        errors.append(
            f"{field}是单方案单号码组字段，禁止使用{shown}切分多个投注组；"
            f"{policy['multi_group_resolution']}。错误值: {value}"
        )


def check_betting_monitor(fields, policy, errors):
    monitor_field = policy["monitor_field"]
    mode_field = policy["mode_field"]
    value = fields.get(monitor_field)
    if value is None:
        return

    mode = fields.get(mode_field)
    disabled_values = set(policy["disabled_values"])
    allowed_modes = {str(x) for x in policy["allowed_modes"]}
    disabled_mode = str(policy["disabled_mode"])

    if value in disabled_values:
        if mode is not None and mode != disabled_mode:
            errors.append(
                f"{monitor_field}关闭时{mode_field}必须为{disabled_mode}，当前为{mode}"
            )
        return

    prefix = policy["enabled_prefix"]
    if not value.startswith(prefix):
        errors.append(
            f"{monitor_field}格式非法；关闭仅允许{sorted(disabled_values)}，"
            f"启用必须使用{prefix}<01序列>。错误值: {value}"
        )
        return

    sequence = value[len(prefix):]
    if not sequence:
        errors.append(f"{monitor_field}启用后必须提供非空01序列")
    else:
        allowed_symbols = {str(x) for x in policy["allowed_symbols"]}
        invalid_symbols = sorted(set(sequence) - allowed_symbols)
        if invalid_symbols:
            errors.append(
                f"{monitor_field}序列只能包含0和1；"
                f"0代表{policy['symbol_meaning']['0']}，"
                f"1代表{policy['symbol_meaning']['1']}。"
                f"非法字符: {''.join(invalid_symbols)}，错误值: {value}"
            )

    if mode is None:
        errors.append(f"{monitor_field}启用时缺少{mode_field}")
    elif mode not in allowed_modes:
        errors.append(f"{mode_field}只能是{sorted(allowed_modes)}，当前为{mode}")


def audit_bytes(data, label, delimiter_policy=None, monitor_policy=None):
    delimiter_policy = delimiter_policy or load_delimiter_policy()
    monitor_policy = monitor_policy or load_monitor_policy()
    text, enc = decode(data)
    lines, fields = parse_fields(text)
    errors = []
    warnings = []
    strategy = lines[1] if len(lines) > 1 else None
    result = {
        "label": label,
        "encoding": enc,
        "strategy": strategy,
        "scheme_detected": is_scheme(lines),
        "errors": errors,
        "warnings": warnings,
    }
    if not result["scheme_detected"]:
        result["skipped"] = "not_a_scheme_txt"
        return result

    check_direct_number_delimiters(fields, delimiter_policy, errors)
    check_betting_monitor(fields, monitor_policy, errors)

    if strategy == "高级开某投某":
        pos = (
            fields.get("高级开某投某正投号码", "").split("|")
            if fields.get("高级开某投某正投号码")
            else []
        )
        neg = (
            fields.get("高级开某投某反投号码", "").split("|")
            if fields.get("高级开某投某反投号码")
            else []
        )
        result.update(
            {
                "positive_group_count": len(pos),
                "negative_group_count": len(neg),
                "positive_unique_count": len(set(pos)),
                "negative_unique_count": len(set(neg)),
            }
        )
        if len(pos) != 10:
            errors.append("高级开某投某正投映射必须有10组")
        if len(neg) != 10:
            errors.append("高级开某投某反投映射必须有10组")
        if pos and len(set(pos)) < 2:
            errors.append("正投为常量映射：10个触发号码没有改变投注集合")
        if neg and len(set(neg)) < 2:
            errors.append("反投为常量映射：10个触发号码没有改变投注集合")
        for kind, groups in (("正投", pos), ("反投", neg)):
            for i, group in enumerate(groups):
                if not valid_group(group):
                    errors.append(f"{kind}第{i}组号码非法或重复: {group}")

    plan = fields.get("倍投计划")
    result["bet_plan"] = plan
    if plan:
        plan_items = [x.strip() for x in plan.split(",") if x.strip()]
        if plan_items and len(set(plan_items)) == 1:
            warnings.append("倍投计划为平倍；正式任务需确认已完成四路资金评审")

    result["active_extra_settings"] = [
        key
        for key, value in fields.items()
        if key
        in {
            "投注监控",
            "真实投注1",
            "真实投注2",
            "模拟投注1",
            "模拟投注2",
            "盈利跳转",
            "亏损跳转",
            "盈利停止",
            "亏损停止",
            "投注时间",
        }
        and value.startswith("True")
    ]
    return result


def iter_targets(path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if (
                    not info.is_dir()
                    and info.filename.lower().endswith(".txt")
                    and Path(info.filename).name.startswith(("A", "B", "C", "D", "G", "L"))
                ):
                    yield f"{path.name}::{info.filename}", archive.read(info)
    elif path.suffix.lower() == ".txt" and path.is_file():
        yield str(path), path.read_bytes()


def changed_targets(base_ref):
    proc = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{base_ref}...HEAD",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    for raw in proc.stdout.splitlines():
        path = ROOT / raw.strip()
        if path.exists() and path.suffix.lower() in {".txt", ".zip"}:
            yield path


def run_self_test(delimiter_policy, monitor_policy):
    fixtures = [
        (
            "valid_single_group",
            "True\n定码轮换\n定码轮换内容=8 6 3\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "invalid_ascii_semicolon",
            "True\n定码轮换\n定码轮换内容=8 6 3;7 2 9;4 0 1\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_chinese_semicolon",
            "True\n定码轮换\n定码轮换内容=8 6 3；7 2 9\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "valid_combo_reference_semicolon",
            "True\n组合方案出号\n组合方案出号内容=方案863;方案729;方案401\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "valid_advanced_rotation_structure",
            "True\n高级定码轮换\n高级定码轮换内容=1|0 2|1|1;2|3 4|1|1;\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "valid_monitor_disabled",
            "True\n定码轮换\n投注监控=False-\n投注监控模式=0\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "valid_monitor_0011",
            "True\n定码轮换\n投注监控=True-0011\n投注监控模式=0\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "valid_monitor_start_only",
            "True\n定码轮换\n投注监控=True-101010\n投注监控模式=1\n倍投计划=1,2,3\n",
            False,
        ),
        (
            "invalid_monitor_digit_2",
            "True\n定码轮换\n投注监控=True-0012\n投注监控模式=0\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_text",
            "True\n定码轮换\n投注监控=True-挂挂中中\n投注监控模式=0\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_spaces",
            "True\n定码轮换\n投注监控=True-0 0 1 1\n投注监控模式=0\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_empty",
            "True\n定码轮换\n投注监控=True-\n投注监控模式=0\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_disabled_with_sequence",
            "True\n定码轮换\n投注监控=False-0011\n投注监控模式=0\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_mode",
            "True\n定码轮换\n投注监控=True-0011\n投注监控模式=2\n倍投计划=1,2,3\n",
            True,
        ),
        (
            "invalid_monitor_missing_mode",
            "True\n定码轮换\n投注监控=True-0011\n倍投计划=1,2,3\n",
            True,
        ),
    ]
    failures = []
    for name, text, should_fail in fixtures:
        result = audit_bytes(
            text.encode("gbk"),
            f"self-test::{name}",
            delimiter_policy,
            monitor_policy,
        )
        failed = bool(result["errors"])
        if failed != should_fail:
            failures.append(
                f"{name}: expected_fail={should_fail}, actual_errors={result['errors']}"
            )
    if failures:
        raise AssertionError("；".join(failures))
    return len(fixtures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--changed-since")
    parser.add_argument("--delimiter-policy", default=str(DEFAULT_DELIMITER_POLICY))
    parser.add_argument("--monitor-policy", default=str(DEFAULT_MONITOR_POLICY))
    args = parser.parse_args()

    delimiter_policy = load_delimiter_policy(args.delimiter_policy)
    monitor_policy = load_monitor_policy(args.monitor_policy)
    self_test_count = (
        run_self_test(delimiter_policy, monitor_policy) if args.self_test else 0
    )
    targets = [Path(raw) for raw in args.paths]
    if args.changed_since:
        targets.extend(changed_targets(args.changed_since))

    results = []
    seen = set()
    for path in targets:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for label, data in iter_targets(path):
            results.append(audit_bytes(data, label, delimiter_policy, monitor_policy))

    if args.json:
        print(
            json.dumps(
                {"self_tests": self_test_count, "results": results},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if self_test_count:
            print(f"SELF_TEST_OK cases={self_test_count}")
        for result in results:
            print(
                f"{result['label']}: strategy={result['strategy']} "
                f"errors={len(result['errors'])} warnings={len(result['warnings'])}"
            )
            for error in result["errors"]:
                print("  ERROR " + error)
            for warning in result["warnings"]:
                print("  WARN " + warning)

    if any(result["errors"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
