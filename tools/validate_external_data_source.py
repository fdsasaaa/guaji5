#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def err(message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        err(f"{path.relative_to(ROOT)} JSON错误: {exc}")
        return {}


required = [
    "controller/data_sources.json",
    "data_sources/__init__.py",
    "data_sources/base.py",
    "data_sources/hxffc.py",
    "data_sources/hxffc/.gitignore",
    "tools/sync_external_draws.py",
    "tools/test_hxffc_data_source.py",
    "docs/data_sources/哈希分分彩外部数据调用说明.md",
    "docs/upgrades/2026-08-05_HXFFC_EXTERNAL_DATA_SOURCE_V1.md",
    "docs/upgrades/2026-08-05_HXFFC_EXTERNAL_DATA_SOURCE_V1.rollback.json",
]
for rel in required:
    if not (ROOT / rel).is_file():
        err(f"缺少外部数据源文件: {rel}")

config = load_json(ROOT / "controller/data_sources.json")
pipeline = load_json(ROOT / "controller/pipeline.json")
source = config.get("sources", {}).get("hxffc", {})
expected_url = (
    "https://github.com/fdsasaaa/haxiffccaiji/"
    "releases/download/data-latest/hxffc_history.txt"
)
if config.get("status") != "ACTIVE":
    err("data_sources配置不是ACTIVE")
if config.get("formal_source_policy") != "EXTERNAL_FIRST_NO_STALE_FALLBACK":
    err("未禁止旧缓存冒充主数据源")
for key, expected in {
    "repository": "fdsasaaa/haxiffccaiji",
    "fixed_url": expected_url,
    "adapter": "data_sources.hxffc.HashFFCSource",
    "formal_gate_required": True,
    "write_access_to_source_repository": False,
    "source_field_available_to_analysis": False,
    "failure_state": "EXTERNAL_DATA_SOURCE_FAILED",
}.items():
    if source.get(key) != expected:
        err(f"controller/data_sources.json hxffc.{key}错误")
if source.get("format", {}).get("required_columns") != [
    "issue",
    "code",
    "draw_time",
    "source",
]:
    err("哈希分分彩字段契约错误")
if source.get("minimum_records", 0) < 20:
    err("最低有效记录数过低")
if source.get("cache_role") != "DISASTER_RECOVERY_AND_TRACE_ONLY":
    err("缓存角色未限制为容灾追溯")

pipeline_source = pipeline.get("data_sources", {})
for key, expected in {
    "registry": "controller/data_sources.json",
    "sync_tool": "tools/sync_external_draws.py",
    "validator": "tools/validate_external_data_source.py",
    "failure_state": "EXTERNAL_DATA_SOURCE_FAILED",
    "must_pass_before_director": True,
}.items():
    if pipeline_source.get(key) != expected:
        err(f"pipeline.data_sources.{key}错误")
preflight = next(
    (item for item in pipeline.get("phases", []) if item.get("id") == "PREFLIGHT"),
    {},
)
if "data_source_snapshot.json" not in preflight.get("required_outputs", []):
    err("PREFLIGHT未强制输出data_source_snapshot.json")
if pipeline.get("failure_routes", {}).get("EXTERNAL_DATA_SOURCE_FAILED") != "PREFLIGHT":
    err("外部数据源失败未路由回PREFLIGHT")

old_input = ROOT / "01_本次输入/哈希分分彩_20260731_0181至0380.txt"
if old_input.exists():
    err("旧固定200期开奖文件仍存在")

old_name = "哈希分分彩_20260731_0181至0380.txt"
for path in list((ROOT / "tools").rglob("*.py")) + list(
    (ROOT / "data_sources").rglob("*.py")
):
    text = path.read_text(encoding="utf-8")
    if old_name in text:
        err(f"程序仍引用旧固定开奖文件: {path.relative_to(ROOT)}")
    if "haxiffccaiji" in text and any(
        token in text
        for token in (
            "git push",
            "releases/assets",
            "DELETE ",
            "PATCH ",
            "POST ",
        )
    ):
        err(f"适配器疑似包含对采集仓库写操作: {path.relative_to(ROOT)}")
    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        err(f"Python语法错误: {path.relative_to(ROOT)}: {exc}")

for folder in (
    ROOT / "data_sources/hxffc/latest",
    ROOT / "data_sources/hxffc/snapshots",
):
    if folder.exists():
        committed = [item for item in folder.rglob("*") if item.is_file()]
        if committed:
            err(f"仓库中不应提交运行时累计数据: {committed}")

workflow_path = ROOT / ".github/workflows/validate.yml"
workflow = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
for phrase in (
    "python tools/test_hxffc_data_source.py",
    "python tools/validate_external_data_source.py",
    "controller/data_sources.json",
):
    if phrase not in workflow:
        err(f"CI未接入外部数据源校验: {phrase}")

adapter = (ROOT / "data_sources/hxffc.py").read_text(encoding="utf-8")
for phrase in (
    "fetch_source",
    "parse_source",
    "validate_source",
    "snapshot_source",
    "get_draws",
    "build_metadata",
    "FIXED_URL",
    "hashlib.sha256",
    "fixed_tag_private_api_fallback",
):
    if phrase not in adapter:
        err(f"哈希分分彩适配器缺少能力: {phrase}")

if errors:
    print("EXTERNAL_DATA_SOURCE_INVALID")
    for message in errors:
        print("- " + message)
    raise SystemExit(1)

print("EXTERNAL_DATA_SOURCE_VALID")
