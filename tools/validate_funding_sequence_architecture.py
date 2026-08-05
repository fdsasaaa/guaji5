#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def error(message: str) -> None:
    errors.append(message)


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        error(f"缺少文件: {path}")
        return ""
    return target.read_text(encoding="utf-8")


def load(path: str) -> dict:
    text = read(path)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception as exc:
        error(f"{path} JSON错误: {exc}")
        return {}


required_files = [
    "11B_A_资金路径有效长度与循环披露补充协议.md",
    "controller/funding_sequence_structure.json",
    "controller/templates/funding_sequence_structure.template.json",
    "tools/validate_funding_sequence_structure.py",
    "tools/test_funding_sequence_structure_gates.py",
]
for path in required_files:
    if not (ROOT / path).exists():
        error(f"资金序列结构升级文件缺失: {path}")

config = load("controller/funding_sequence_structure.json")
pipeline = load("controller/pipeline.json")
orchestration = load("controller/function_orchestration.json")
protocol = read("11B_A_资金路径有效长度与循环披露补充协议.md")
agents = read("AGENTS.md")
readme = read("README.md")
workflow = read(".github/workflows/validate.yml")
validator = read("tools/validate_funding_sequence_structure.py")
gate_tests = read("tools/test_funding_sequence_structure_gates.py")

if config.get("schema_version") != 1 or config.get("status") != "ACTIVE":
    error("资金序列结构配置未激活或schema错误")
if set(config.get("sequence_modes", [])) != {"FINITE", "CYCLIC"}:
    error("资金序列结构配置缺少FINITE或CYCLIC")
for key, value in config.get("requirements", {}).items():
    if value is not True:
        error(f"资金序列结构配置未启用: {key}")

expected_states = {
    "FUNDING_SEQUENCE_STRUCTURE_MISSING",
    "EXPANDED_REPEAT_BLOCK",
    "EFFECTIVE_DESIGN_LENGTH_MISMATCH",
    "PATH_LENGTH_CLAIM_OVERSTATED",
    "CYCLE_DISCLOSURE_INVALID",
    "CROSS_CYCLE_STRESS_INCOMPLETE",
    "BANKROLL_SEQUENCE_MISMATCH",
    "POST_STOP_STAKE_DETECTED",
}
if not expected_states.issubset(set(config.get("failure_states", []))):
    error("资金序列结构配置失败状态不完整")

pipeline_block = pipeline.get("funding_sequence_structure", {})
for key, expected in {
    "config": "controller/funding_sequence_structure.json",
    "template": "controller/templates/funding_sequence_structure.template.json",
    "validator": "tools/validate_funding_sequence_structure.py",
    "gate_tests": "tools/test_funding_sequence_structure_gates.py",
    "required_evidence": "funding_sequence_structure.json",
    "missing_evidence_failure": "FUNDING_SEQUENCE_STRUCTURE_MISSING",
    "must_pass_before_contract_freeze": True,
    "canonical_single_cycle_storage_required": True,
    "cross_cycle_stress_required": True,
}.items():
    if pipeline_block.get(key) != expected:
        error(f"pipeline.funding_sequence_structure.{key}错误")

director = next((item for item in pipeline.get("phases", []) if item.get("id") == "DIRECTOR"), {})
if "funding_sequence_structure.json" not in director.get("required_outputs", []):
    error("DIRECTOR未强制输出funding_sequence_structure.json")
for state in expected_states:
    if pipeline.get("failure_routes", {}).get(state) not in {"DIRECTOR", "CONTRACT_FROZEN"}:
        error(f"资金序列失败状态未正确路由: {state}")

orchestration_block = orchestration.get("funding_sequence_structure", {})
for key, expected in {
    "config": "controller/funding_sequence_structure.json",
    "template": "controller/templates/funding_sequence_structure.template.json",
    "validator": "tools/validate_funding_sequence_structure.py",
    "gate_tests": "tools/test_funding_sequence_structure_gates.py",
    "required_evidence": "funding_sequence_structure.json",
    "must_pass_before_contract_freeze": True,
}.items():
    if orchestration_block.get(key) != expected:
        error(f"function_orchestration.funding_sequence_structure.{key}错误")
if not expected_states.issubset(set(orchestration.get("failure_states", []))):
    error("function_orchestration未登记全部资金序列失败状态")

for phrase in [
    "最小重复周期",
    "有效独立长度",
    "规范化存储",
    "跨轮压力与回收",
    "序列写得长，不等于设计得深",
]:
    if phrase not in protocol:
        error(f"11B-A协议缺少关键内容: {phrase}")
for phrase in [
    "funding_sequence_structure.json",
    "最小重复周期",
    "CYCLIC",
    "逐轮",
    "POST_STOP_STAKE_DETECTED",
]:
    if phrase not in agents:
        error(f"AGENTS缺少资金序列接管规则: {phrase}")
for phrase in [
    "有效长度与循环披露",
    "validate_funding_sequence_structure.py --self-test --scan-runs",
    "test_funding_sequence_structure_gates.py",
]:
    if phrase not in readme:
        error(f"README缺少资金序列入口: {phrase}")
for phrase in [
    "python tools/validate_funding_sequence_architecture.py",
    "python tools/validate_funding_sequence_structure.py --self-test --scan-runs",
    "python tools/test_funding_sequence_structure_gates.py",
]:
    if phrase not in workflow:
        error(f"CI未执行资金序列校验: {phrase}")

for path, source in [
    ("tools/validate_funding_sequence_structure.py", validator),
    ("tools/test_funding_sequence_structure_gates.py", gate_tests),
]:
    try:
        ast.parse(source, filename=path)
    except SyntaxError as exc:
        error(f"{path}语法错误: {exc}")
for phrase in [
    "minimum_repeat_period",
    "检测到展开式重复块",
    "cross_cycle_checkpoints",
    "next_period_stake",
    "FUNDING_SEQUENCE_STRUCTURE_VALIDATION_OK",
]:
    if phrase not in validator:
        error(f"资金序列校验器缺少能力: {phrase}")
for phrase in [
    "pattern * 5",
    "50期独立路径",
    "missing cycle stress",
    "post stop stake",
]:
    if phrase not in gate_tests:
        error(f"资金序列对抗测试缺少案例: {phrase}")

if errors:
    print("FUNDING_SEQUENCE_ARCHITECTURE_INVALID")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("FUNDING_SEQUENCE_ARCHITECTURE_VALID")
