#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []


def err(message: str) -> None:
    errors.append(message)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        err(f"{path.name} JSON错误: {exc}")
        return {}


required = [
    "AGENTS.md",
    "SYSTEM_MANIFEST.json",
    "SYSTEM_STATE.json",
    "系统状态.json",
    "当前任务.json",
    "CHANGELOG.md",
    "05A_方案讲解PPT生产协议.md",
    "10_静默方案总控与外部参考吸收协议.md",
    "11_智能功能调度与资金路径编排协议.md",
    "13_GitHub持续工作区与参考灵感自由重构协议.md",
    "功能能力卡片.jsonl",
    "资金路径模板库.jsonl",
    ".github/workflows/validate.yml",
]
for relative in required:
    if not (ROOT / relative).exists():
        err(f"缺少必需文件: {relative}")

manifest = load_json(ROOT / "SYSTEM_MANIFEST.json")
state = load_json(ROOT / "SYSTEM_STATE.json")
state_cn = load_json(ROOT / "系统状态.json")
task = load_json(ROOT / "当前任务.json")

expected_version = manifest.get("版本")
version_fields = {
    "SYSTEM_MANIFEST.版本": expected_version,
    "SYSTEM_STATE.版本": state.get("版本"),
    "SYSTEM_STATE.version": state.get("version"),
    "SYSTEM_STATE.当前版本": state.get("当前版本"),
    "当前任务.版本": task.get("版本"),
}
for field, value in version_fields.items():
    if value != expected_version:
        err(f"版本不同步: {field}={value!r}, expected={expected_version!r}")

if state_cn != state:
    err("SYSTEM_STATE.json 与 系统状态.json 内容不同步")
if manifest.get("仓库") != "fdsasaaa/guaji5":
    err("仓库标识错误")
if state.get("仓库") != "fdsasaaa/guaji5":
    err("状态文件仓库标识错误")
if task.get("基线仓库") != "fdsasaaa/guaji5":
    err("当前任务基线仓库错误")
if "13_GitHub持续工作区与参考灵感自由重构协议.md" not in manifest.get("模块", []):
    err("模块13未登记")
if "05A_方案讲解PPT生产协议.md" not in manifest.get("模块", []):
    err("PPT模块05A未登记")
if not state.get("无需重复上传工作包"):
    err("状态文件未启用无需重复上传工作包")
if not task.get("无需重复上传工作包"):
    err("当前任务未启用无需重复上传工作包")

# PPT模块必须是单一PPT、三层结构和讲解审查模式。
if manifest.get("PPT单文件原则") is not True:
    err("清单未启用PPT单文件原则")
if manifest.get("PPT人工讲解审查") is not True:
    err("清单未启用PPT人工讲解审查")
if state.get("PPT唯一文件") is not True:
    err("状态文件未启用PPT唯一文件")
if state.get("PPT人工讲解审查") is not True:
    err("状态文件未启用PPT人工讲解审查")

for temporary in ["GITHUB_MIGRATION_V3.9.2.zip", "TRIGGER_V3.9.2.txt"]:
    if (ROOT / temporary).exists():
        err(f"一次性迁移文件未清理: {temporary}")

workflow = ROOT / ".github/workflows/validate.yml"
if workflow.exists() and "tools/validate_repository.py" not in workflow.read_text(encoding="utf-8"):
    err("长期校验工作流未调用仓库校验脚本")

jsonl_specs = {
    "历史方案索引.jsonl": "方案ID",
    "分析角度索引.jsonl": "角度ID",
    "学习事件索引.jsonl": "事件ID",
    "规则候选池.jsonl": "候选规则ID",
    "技术原子表现档案.jsonl": "技术原子ID",
    "软件行为证据索引.jsonl": "证据ID",
    "批次索引.jsonl": "批次ID",
    "方案组合案例索引.jsonl": "案例ID",
    "负面方案模式索引.jsonl": "负面模式ID",
    "功能覆盖索引.jsonl": "功能ID",
    "总控验收测试集.jsonl": "测试ID",
    "功能能力卡片.jsonl": "功能ID",
    "资金路径模板库.jsonl": "资金路径ID",
}
for filename, key in jsonl_specs.items():
    path = ROOT / filename
    if not path.exists():
        err(f"缺少索引: {filename}")
        continue
    seen = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception as exc:
            err(f"{filename}:{line_number} JSON错误 {exc}")
            continue
        if key not in obj:
            err(f"{filename}:{line_number} 缺少{key}")
            continue
        if obj[key] in seen:
            err(f"{filename}:{line_number} 重复{key}={obj[key]}")
        seen.add(obj[key])

for path in ROOT.rglob("*.txt"):
    if "01_本次输入" in path.parts or "08_版本与优化记录" in path.name:
        continue
    try:
        text = path.read_text(encoding="gbk")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
    rows = re.findall(r"^\s*([0-9])\s*[|,;:\t ]+([^\r\n]+)$", text, re.M)
    if len(rows) >= 10:
        values = [value.strip() for _, value in rows[:10]]
        if len(set(values)) == 1:
            err(f"疑似0-9常量高级映射: {path.relative_to(ROOT)}")

protocol_path = ROOT / "13_GitHub持续工作区与参考灵感自由重构协议.md"
protocol = protocol_path.read_text(encoding="utf-8") if protocol_path.exists() else ""
for phrase in ["无法原样生成TXT时", "自由重构", "四路资金路径", "无需等待二次确认"]:
    if phrase not in protocol:
        err(f"模块13缺少关键语义: {phrase}")

ppt_path = ROOT / "05A_方案讲解PPT生产协议.md"
ppt_protocol = ppt_path.read_text(encoding="utf-8") if ppt_path.exists() else ""
for phrase in [
    "一套方案只生成一个PPT",
    "主讲页面",
    "演讲者备注",
    "技术附录",
    "先举例，再归纳规则",
    "观众必须记住的话",
    "人工讲解审查",
    "统计结果必须翻译成人话",
    "PPT_MULTIPLE_COMPANION_FILES",
    "PPT_STILL_REPORT_STYLE",
]:
    if phrase not in ppt_protocol:
        err(f"PPT模块缺少关键语义: {phrase}")

for deprecated in [
    "方案ID_PPT逐页脚本与旁白.md",
    "方案ID_PPT事实校验表.json",
]:
    if deprecated in ppt_protocol:
        err(f"PPT模块仍包含已废止的默认独立文件: {deprecated}")

if errors:
    print("VALIDATION_FAILED")
    for item in errors:
        print("-", item)
    sys.exit(1)

print(
    "VALIDATION_OK "
    f"version={state.get('当前版本', '?')} "
    f"repo={state.get('仓库', '?')} "
    f"task={task.get('任务ID', '?')} "
    "ppt=SINGLE_DECK_THREE_LAYER"
)
