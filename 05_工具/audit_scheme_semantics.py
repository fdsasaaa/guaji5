#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "scheme_field_delimiter_policy.json"


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


def load_policy(path=DEFAULT_POLICY):
    with Path(path).open("r", encoding="utf-8") as fh:
        policy = json.load(fh)
    required = {
        "direct_single_group_fields",
        "forbidden_group_delimiters",
        "structural_semicolon_whitelist",
        "multi_group_resolution",
    }
    missing = sorted(required - set(policy))
    if missing:
        raise ValueError(f"分隔符策略缺少字段: {', '.join(missing)}")
    return policy


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


def audit_bytes(data, label, policy=None):
    policy = policy or load_policy()
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

    check_direct_number_delimiters(fields, policy, errors)

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
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"],
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


def run_self_test(policy):
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
    ]
    failures = []
    for name, text, should_fail in fixtures:
        result = audit_bytes(text.encode("gbk"), f"self-test::{name}", policy)
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
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    policy = load_policy(args.policy)
    self_test_count = run_self_test(policy) if args.self_test else 0
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
            results.append(audit_bytes(data, label, policy))

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
