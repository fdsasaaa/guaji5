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


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        err(f"缺少文件: {path}")
        return ""
    return target.read_text(encoding="utf-8")


def load_json(path: str) -> dict:
    text = read(path)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception as exc:
        err(f"{path} JSON错误: {exc}")
        return {}


required = [
    "14_导演执行审计学习总控与模块化变更协议.md",
    "controller/pipeline.json",
    "controller/extensions.json",
    "tools/lottery_controller.py",
    "tools/validate_controller_architecture.py",
    "docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.md",
]
for item in required:
    if not (ROOT / item).exists():
        err(f"缺少总控升级文件: {item}")

pipeline = load_json("controller/pipeline.json")
extensions = load_json("controller/extensions.json")
protocol = read("14_导演执行审计学习总控与模块化变更协议.md")
agents = read("AGENTS.md")
readme = read("README.md")
workflow = read(".github/workflows/validate.yml")
controller = read("tools/lottery_controller.py")

phases = pipeline.get("phases", [])
phase_ids = [item.get("id") for item in phases]
required_phases = [
    "INTAKE", "PREFLIGHT", "DIRECTOR", "CONTRACT_FROZEN",
    "EXECUTION", "VALIDATION", "AUDIT", "REWORK",
    "DELIVERY", "LEARNING", "COMPLETED",
]
if phase_ids != required_phases:
    err(f"阶段顺序错误: {phase_ids}")
if len(phase_ids) != len(set(phase_ids)):
    err("阶段ID重复")
if pipeline.get("branch_required") is not True:
    err("pipeline未强制任务分支")
if pipeline.get("direct_main_write_forbidden") is not True:
    err("pipeline未禁止直接写main")
if pipeline.get("max_rework_rounds") != 3:
    err("pipeline返工上限不是3")
if pipeline.get("cleanup", {}).get("default_action") != "PLAN_ONLY":
    err("清理默认动作不是PLAN_ONLY")
for key in [
    "base_ref_required", "base_commit_required_before_write",
    "changed_files_hash_required", "validation_evidence_required",
    "failed_version_evidence_must_remain", "force_push_forbidden",
]:
    if pipeline.get("rollback", {}).get(key) is not True:
        err(f"rollback.{key}未启用")

transitions = pipeline.get("transitions", {})
known = set(phase_ids) | {"BLOCKED"}
for source, targets in transitions.items():
    if source not in known:
        err(f"未知转移源: {source}")
    for target in targets:
        if target not in known:
            err(f"未知转移目标: {source}->{target}")
if "DELIVERY" in transitions.get("DIRECTOR", []):
    err("DIRECTOR不得直接进入DELIVERY")
if "EXECUTION" not in transitions.get("CONTRACT_FROZEN", []):
    err("冻结合同后无法进入执行")

domains = extensions.get("domains", [])
domain_ids = [item.get("id") for item in domains]
if set(domain_ids) != {"PPT", "SCHEME", "PROGRAM", "SYSTEM", "CLEANUP"}:
    err(f"扩展域不完整: {domain_ids}")
for item in domains:
    domain_id = item.get("id", "<unknown>")
    for key in ["purpose", "owned_paths", "protected_dependencies",
                "required_validators", "compatibility_contract", "rollback_unit"]:
        if not item.get(key):
            err(f"{domain_id}.{key}为空")
cleanup = next((item for item in domains if item.get("id") == "CLEANUP"), {})
if "先隔离后删除" not in cleanup.get("compatibility_contract", ""):
    err("清理域未规定先隔离后删除")

for phrase in [
    "一句话入口", "强制状态机", "本次设计合同", "自动返工纪律",
    "回滚与升级记录", "五类扩展域", "文件清理安全规则",
    "学习的三级权限", "默认创建Draft PR",
]:
    if phrase not in protocol:
        err(f"14号协议缺少关键内容: {phrase}")

for phrase in [
    "14_导演执行审计学习总控与模块化变更协议.md",
    "director—contract—execute—validate—audit—delivery—learning",
    "清理任务默认只生成计划",
]:
    if phrase not in agents:
        err(f"AGENTS缺少总控接管规则: {phrase}")

for phrase in [
    "启动彩票总控",
    "tools/lottery_controller.py",
    "controller/pipeline.json",
]:
    if phrase not in readme:
        err(f"README缺少总控入口: {phrase}")

for phrase in [
    "python tools/validate_controller_architecture.py",
    "python tools/lottery_controller.py validate",
]:
    if phrase not in workflow:
        err(f"CI未执行: {phrase}")

try:
    ast.parse(controller, filename="tools/lottery_controller.py")
except SyntaxError as exc:
    err(f"lottery_controller.py语法错误: {exc}")

for phrase in [
    "CONTROLLER_CONFIG_VALID",
    "rollback_manifest.json",
    "design_contract.json",
    "cleanup_plan.json",
    "force_push_forbidden",
]:
    if phrase not in controller:
        err(f"lottery_controller.py缺少能力: {phrase}")

if errors:
    print("CONTROLLER_ARCHITECTURE_INVALID")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("CONTROLLER_ARCHITECTURE_VALID")
