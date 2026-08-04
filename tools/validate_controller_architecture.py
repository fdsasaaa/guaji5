#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
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
    "11_智能功能调度与资金路径编排协议.md",
    "controller/pipeline.json",
    "controller/extensions.json",
    "controller/function_orchestration.json",
    "controller/templates/function_orchestration.template.json",
    "tools/lottery_controller.py",
    "tools/validate_controller_architecture.py",
    "tools/validate_function_orchestration.py",
    "docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.md",
    "docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.rollback.json",
    "docs/upgrades/2026-08-04_FUNCTION_ORCHESTRATION_V1.md",
    "docs/upgrades/2026-08-04_FUNCTION_ORCHESTRATION_V1.rollback.json",
]
for item in required:
    if not (ROOT / item).exists():
        err(f"缺少总控升级文件: {item}")

manifest = load_json("SYSTEM_MANIFEST.json")
pipeline = load_json("controller/pipeline.json")
extensions = load_json("controller/extensions.json")
orchestration = load_json("controller/function_orchestration.json")
rollback_record = load_json("docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.rollback.json")
orchestration_rollback = load_json("docs/upgrades/2026-08-04_FUNCTION_ORCHESTRATION_V1.rollback.json")
protocol = read("14_导演执行审计学习总控与模块化变更协议.md")
function_protocol = read("11_智能功能调度与资金路径编排协议.md")
agents = read("AGENTS.md")
readme = read("README.md")
workflow = read(".github/workflows/validate.yml")
controller = read("tools/lottery_controller.py")
orchestration_validator = read("tools/validate_function_orchestration.py")

if "14_导演执行审计学习总控与模块化变更协议.md" not in manifest.get("模块", []):
    err("SYSTEM_MANIFEST未登记14号协议")
for item in ["controller/pipeline.json", "controller/extensions.json", "controller/function_orchestration.json"]:
    if item not in manifest.get("核心结构化文件", []):
        err(f"SYSTEM_MANIFEST未登记核心结构化文件: {item}")
for item in ["tools/lottery_controller.py", "tools/validate_controller_architecture.py", "tools/validate_function_orchestration.py"]:
    if item not in manifest.get("工具", []):
        err(f"SYSTEM_MANIFEST未登记工具: {item}")
manifest_expect = {
    "总控协议": "14_导演执行审计学习总控与模块化变更协议.md",
    "总控流水线配置": "controller/pipeline.json",
    "总控扩展注册表": "controller/extensions.json",
    "总控程序": "tools/lottery_controller.py",
    "总控架构校验": "tools/validate_controller_architecture.py",
    "功能编排配置": "controller/function_orchestration.json",
    "功能编排模板": "controller/templates/function_orchestration.template.json",
    "功能编排校验": "tools/validate_function_orchestration.py",
    "总控自动返工上限": 3,
    "总控默认PR状态": "DRAFT",
    "总控自动合并": False,
    "总控强推": False,
    "清理默认模式": "PLAN_ONLY",
}
for key, expected in manifest_expect.items():
    if manifest.get(key) != expected:
        err(f"SYSTEM_MANIFEST.{key}错误: {manifest.get(key)!r}")
if manifest.get("总控扩展域") != ["PPT", "SCHEME", "PROGRAM", "SYSTEM", "CLEANUP"]:
    err("SYSTEM_MANIFEST.总控扩展域错误")
structure = manifest.get("总控结构要求", {})
if structure.get("功能画像最少") != 4:
    err("SYSTEM_MANIFEST.总控结构要求.功能画像最少不是4")
if structure.get("更多设置实质候选最少") != 2:
    err("SYSTEM_MANIFEST未强制至少2类更多设置实质候选")
if structure.get("资金路径种类最少") != 4:
    err("SYSTEM_MANIFEST未强制资金四路")

if pipeline.get("schema_version") != 2:
    err("pipeline.schema_version不是2")
if pipeline.get("status") != "ACTIVE":
    err(f"pipeline状态不是ACTIVE: {pipeline.get('status')!r}")
if pipeline.get("activated_by_pr") != 16:
    err("pipeline.activated_by_pr不是16")
if pipeline.get("activated_at_commit") != "2dc89ebe01f4d2f1804735140ce55c42ee447a5b":
    err("pipeline.activated_at_commit与PR #16合并提交不一致")
fo = pipeline.get("function_orchestration", {})
for key, expected in {
    "config": "controller/function_orchestration.json",
    "template": "controller/templates/function_orchestration.template.json",
    "validator": "tools/validate_function_orchestration.py",
    "required_evidence": "function_orchestration.json",
    "must_pass_before_contract_freeze": True,
}.items():
    if fo.get(key) != expected:
        err(f"pipeline.function_orchestration.{key}错误")

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
director = next((x for x in phases if x.get("id") == "DIRECTOR"), {})
if "function_orchestration.json" not in director.get("required_outputs", []):
    err("DIRECTOR未强制输出function_orchestration.json")
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
for state in orchestration.get("failure_states", []):
    if pipeline.get("failure_routes", {}).get(state) not in {"DIRECTOR", "CONTRACT_FROZEN"}:
        err(f"功能编排失败状态未正确路由: {state}")

if orchestration.get("status") != "ACTIVE":
    err("功能编排配置不是ACTIVE")
if orchestration.get("minimum_candidate_profiles", 0) < 4:
    err("功能编排候选画像不足4")
if orchestration.get("minimum_material_more_settings", 0) < 2:
    err("功能编排更多设置候选不足2")
if orchestration.get("baseline_only_max_consecutive", 99) > 2:
    err("连续纯平倍限制过宽")
if set(orchestration.get("required_profile_types", [])) != {"BASELINE", "STATE", "EXECUTION_OR_FUNDING", "LOW_COVERAGE_PROBE"}:
    err("功能编排四类画像不完整")
if set(orchestration.get("required_funding_kinds", [])) != {"FLAT", "LIMITED_LINEAR", "PRESSURE_RELEASE", "ADVANCED_STATE"}:
    err("功能编排资金四路不完整")


domains = extensions.get("domains", [])
domain_ids = [item.get("id") for item in domains]
if set(domain_ids) != {"PPT", "SCHEME", "PROGRAM", "SYSTEM", "CLEANUP"}:
    err(f"扩展域不完整: {domain_ids}")
for item in domains:
    domain_id = item.get("id", "<unknown>")
    for key in ["purpose", "owned_paths", "protected_dependencies", "required_validators", "compatibility_contract", "rollback_unit"]:
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
    "四种强制候选功能画像", "资金路径四路强制量化", "更多设置实质候选门槛",
    "连续平倍与重复画像限制", "功能覆盖债务", "机器验收",
]:
    if phrase not in function_protocol:
        err(f"11号协议缺少强制编排内容: {phrase}")

for phrase in [
    "14_导演执行审计学习总控与模块化变更协议.md",
    "director—contract—execute—validate—audit—delivery—learning",
    "清理任务默认只生成计划",
    "function_orchestration.json",
    "validate_function_orchestration.py --self-test --scan-runs",
]:
    if phrase not in agents:
        err(f"AGENTS缺少总控接管规则: {phrase}")

for phrase in ["启动彩票总控", "tools/lottery_controller.py", "controller/pipeline.json"]:
    if phrase not in readme:
        err(f"README缺少总控入口: {phrase}")
for phrase in [
    "python tools/validate_controller_architecture.py",
    "python tools/lottery_controller.py validate",
    "python tools/validate_function_orchestration.py --self-test --scan-runs",
]:
    if phrase not in workflow:
        err(f"CI未执行: {phrase}")

for path, source in [("tools/lottery_controller.py", controller), ("tools/validate_function_orchestration.py", orchestration_validator)]:
    try:
        ast.parse(source, filename=path)
    except SyntaxError as exc:
        err(f"{path}语法错误: {exc}")
for phrase in ["FUNCTION_ORCHESTRATION_VALID", "PRESSURE_RELEASE", "BASELINE_ONLY", "LOW_COVERAGE_PROBE"]:
    if phrase not in orchestration_validator:
        err(f"功能编排校验器缺少能力: {phrase}")
for phrase in ["CONTROLLER_CONFIG_VALID", "rollback_manifest.json", "design_contract.json", "cleanup_plan.json", "force_push_forbidden"]:
    if phrase not in controller:
        err(f"lottery_controller.py缺少能力: {phrase}")

for record, name, expected_base in [
    (rollback_record, "总控V1", None),
    (orchestration_rollback, "功能编排V1", "3c8757d89b8963be1f166d8cbbc0dd2f91907dc8"),
]:
    base_commit = record.get("base_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_commit):
        err(f"{name}机器回滚清单缺少有效base_commit")
    if expected_base and base_commit != expected_base:
        err(f"{name}基线提交错误")
    if record.get("force_push_allowed") is not False:
        err(f"{name}机器回滚清单未禁止强推")
    if record.get("auto_merge_allowed") is not False:
        err(f"{name}机器回滚清单未禁止自动合并")
    for item in record.get("files", []):
        if item.get("action") == "UPDATE" and not item.get("before_blob_sha"):
            err(f"{name}更新文件缺少before_blob_sha: {item.get('path')}")
        if not item.get("rollback"):
            err(f"{name}文件缺少回滚动作: {item.get('path')}")

recorded_paths = {item.get("path") for item in rollback_record.get("files", [])}
old_required = [
    "14_导演执行审计学习总控与模块化变更协议.md",
    "controller/pipeline.json", "controller/extensions.json",
    "tools/lottery_controller.py", "tools/validate_controller_architecture.py",
    "docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.md",
]
for item in old_required:
    if item not in recorded_paths:
        err(f"原机器回滚清单未登记: {item}")

if errors:
    print("CONTROLLER_ARCHITECTURE_INVALID")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("CONTROLLER_ARCHITECTURE_VALID")
