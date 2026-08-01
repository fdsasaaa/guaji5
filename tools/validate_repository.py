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


def load_jsonl(path: Path, key: str):
    items = []
    seen = set()
    if not path.exists():
        err(f"缺少索引: {path.name}")
        return items
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception as exc:
            err(f"{path.name}:{line_number} JSON错误 {exc}")
            continue
        if key not in obj:
            err(f"{path.name}:{line_number} 缺少{key}")
            continue
        if obj[key] in seen:
            err(f"{path.name}:{line_number} 重复{key}={obj[key]}")
        seen.add(obj[key])
        items.append(obj)
    return items


required = [
    "AGENTS.md",
    "SYSTEM_MANIFEST.json",
    "SYSTEM_STATE.json",
    "系统状态.json",
    "当前任务.json",
    "CHANGELOG.md",
    "00A_当前强制覆盖与废止规则.md",
    "05A_方案讲解PPT生产协议.md",
    "PPT页面类型卡片.jsonl",
    "PPT讲解验收测试集.jsonl",
    "PPT压缩与精度规则.json",
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
ppt_precision = load_json(ROOT / "PPT压缩与精度规则.json")

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
for module in [
    "00A_当前强制覆盖与废止规则.md",
    "05A_方案讲解PPT生产协议.md",
    "13_GitHub持续工作区与参考灵感自由重构协议.md",
]:
    if module not in manifest.get("模块", []):
        err(f"模块未登记: {module}")
if "PPT压缩与精度规则.json" not in manifest.get("核心结构化文件", []):
    err("PPT压缩与精度规则未登记为核心结构化文件")
if not state.get("无需重复上传工作包"):
    err("状态文件未启用无需重复上传工作包")
if not task.get("无需重复上传工作包"):
    err("当前任务未启用无需重复上传工作包")

# PPT总控状态校验
ppt_boolean_checks = {
    "清单.PPT规则修改必须回写GitHub": manifest.get("PPT规则修改必须回写GitHub"),
    "清单.PPT单文件原则": manifest.get("PPT单文件原则"),
    "清单.PPT人工讲解审查": manifest.get("PPT人工讲解审查"),
    "清单.PPT压缩审查": manifest.get("PPT压缩审查"),
    "清单.PPT精度审查": manifest.get("PPT精度审查"),
    "清单.PPT页面价值门槛": manifest.get("PPT页面价值门槛"),
    "清单.PPT先技术后案例": manifest.get("PPT先技术后案例"),
    "清单.PPT规则独立执行检查": manifest.get("PPT规则独立执行检查"),
    "清单.PPT技术缘由真实性检查": manifest.get("PPT技术缘由真实性检查"),
    "清单.PPT标题核心准确检查": manifest.get("PPT标题核心准确检查"),
    "清单.PPT自然语言转换": manifest.get("PPT自然语言转换"),
    "清单.PPT视觉去重": manifest.get("PPT视觉去重"),
    "清单.PPT结论建议一致性检查": manifest.get("PPT结论建议一致性检查"),
    "清单.PPT停止对象精确检查": manifest.get("PPT停止对象精确检查"),
    "清单.PPT隐藏附录": manifest.get("PPT隐藏附录"),
    "清单.PPT附录证据完整性检查": manifest.get("PPT附录证据完整性检查"),
    "清单.PPT动态页数": manifest.get("PPT动态页数"),
    "状态.PPT规则修改必须回写GitHub": state.get("PPT规则修改必须回写GitHub"),
    "状态.PPT唯一文件": state.get("PPT唯一文件"),
    "状态.PPT页面价值门槛": state.get("PPT页面价值门槛"),
    "状态.PPT先技术后案例": state.get("PPT先技术后案例"),
    "状态.PPT技术缘由真实性检查": state.get("PPT技术缘由真实性检查"),
    "状态.PPT规则独立执行检查": state.get("PPT规则独立执行检查"),
    "状态.PPT标题核心准确检查": state.get("PPT标题核心准确检查"),
    "状态.PPT自然语言转换": state.get("PPT自然语言转换"),
    "状态.PPT视觉去重": state.get("PPT视觉去重"),
    "状态.PPT停止对象精确检查": state.get("PPT停止对象精确检查"),
    "状态.PPT结论建议一致性检查": state.get("PPT结论建议一致性检查"),
    "状态.PPT隐藏附录": state.get("PPT隐藏附录"),
    "状态.PPT附录证据完整性检查": state.get("PPT附录证据完整性检查"),
    "状态.PPT主讲附录一致性检查": state.get("PPT主讲附录一致性检查"),
    "状态.PPT页面类型识别": state.get("PPT页面类型识别"),
    "状态.PPT人工讲解审查": state.get("PPT人工讲解审查"),
    "状态.PPT压缩审查": state.get("PPT压缩审查"),
    "状态.PPT精度审查": state.get("PPT精度审查"),
    "状态.PPT渲染审查": state.get("PPT渲染审查"),
}
for field, value in ppt_boolean_checks.items():
    if value is not True:
        err(f"未启用PPT强制能力: {field}")

if manifest.get("PPT规则正式源") != "GitHub main":
    err("PPT规则正式源不是GitHub main")
if state.get("PPT规则正式源") != "GitHub main":
    err("状态文件PPT规则正式源不是GitHub main")
if manifest.get("PPT简单技术主讲页建议") != [7, 9]:
    err("清单简单技术主讲页建议不是7至9页")
if state.get("PPT简单技术主讲页建议") != [7, 9]:
    err("状态简单技术主讲页建议不是7至9页")
if manifest.get("PPT讲解验收测试数量", 0) < 40:
    err("清单PPT讲解验收测试数量不足40")
if state.get("PPT讲解验收测试数量", 0) < 40:
    err("状态PPT讲解验收测试数量不足40")

brand = manifest.get("PPT固定品牌结束页", {})
if brand.get("必须最后正常播放页") is not True:
    err("清单未要求品牌页为最后正常播放页")
if brand.get("网址") != "www.laocaimi.org":
    err("清单品牌网址错误")
if brand.get("联系方式") != "https://t.me/laocaimi1314":
    err("清单联系方式错误")
if state.get("PPT品牌页必须最后") is not True:
    err("状态未要求品牌页为最后正常播放页")
if state.get("PPT品牌网址") != "www.laocaimi.org":
    err("状态品牌网址错误")
if state.get("PPT联系方式") != "https://t.me/laocaimi1314":
    err("状态联系方式错误")

# 压缩与精度结构化规则
if ppt_precision.get("状态") != "MANDATORY":
    err("PPT压缩与精度规则未设为MANDATORY")
if ppt_precision.get("正式源") != "GitHub main":
    err("PPT压缩与精度规则正式源错误")
if ppt_precision.get("规则修改必须写入GitHub") is not True:
    err("PPT压缩与精度规则未强制GitHub写入")
if ppt_precision.get("主讲页目标", {}).get("简单技术通常页数") != [7, 9]:
    err("结构化规则简单技术页数范围错误")
if len(ppt_precision.get("页面价值门槛", [])) < 5:
    err("结构化规则页面价值门槛不足")
if ppt_precision.get("隐藏附录", {}).get("必须设置为隐藏幻灯片") is not True:
    err("结构化规则未要求隐藏附录")
if len(ppt_precision.get("隐藏附录", {}).get("数据项目最低证据", [])) < 10:
    err("结构化规则隐藏附录最低证据不足")
if ppt_precision.get("结论要求", {}).get("必须与建议一致") is not True:
    err("结构化规则未要求结论建议一致")
if len(ppt_precision.get("精度检查", [])) < 10:
    err("结构化规则精度检查不足")

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
    "PPT页面类型卡片.jsonl": "页面类型ID",
    "PPT讲解验收测试集.jsonl": "测试ID",
}
loaded_jsonl = {filename: load_jsonl(ROOT / filename, key) for filename, key in jsonl_specs.items()}

page_types = loaded_jsonl.get("PPT页面类型卡片.jsonl", [])
page_type_ids = {item.get("页面类型ID") for item in page_types}
required_page_types = {
    "COVER", "TECH_DEFINE", "TECH_REASON", "RULE", "STEP", "CASE",
    "DATA", "COMPARE", "RISK", "ADVICE", "CONCLUSION",
    "APPENDIX_DIVIDER", "APPENDIX", "BRAND_END",
}
missing_page_types = required_page_types - page_type_ids
if missing_page_types:
    err(f"PPT页面类型缺失: {sorted(missing_page_types)}")
if len(page_types) < 14:
    err(f"PPT页面类型数量不足: {len(page_types)}")
for item in page_types:
    for field in [
        "名称", "主要问题", "主页面重点", "备注重点", "首选结构",
        "可合并条件", "自然语言优先", "视觉去重", "隐藏页", "禁止",
    ]:
        if field not in item:
            err(f"页面类型{item.get('页面类型ID')}缺少{field}")
appendix_cards = [item for item in page_types if item.get("页面类型ID") in {"APPENDIX", "APPENDIX_DIVIDER"}]
if not appendix_cards or not all(item.get("隐藏页") is True for item in appendix_cards):
    err("附录页面类型未全部设置隐藏")
brand_cards = [item for item in page_types if item.get("页面类型ID") == "BRAND_END"]
if not brand_cards or brand_cards[0].get("隐藏页") is not False:
    err("品牌页错误设置为隐藏")
if len([item for item in page_types if item.get("页面类型ID") == "APPENDIX" and len(item.get("最低证据", [])) >= 10]) != 1:
    err("APPENDIX页面卡片最低证据不足")

ppt_tests = loaded_jsonl.get("PPT讲解验收测试集.jsonl", [])
if len(ppt_tests) < 40:
    err(f"PPT讲解验收测试数量不足: {len(ppt_tests)}")
required_failure_states = {
    "PPT_MULTIPLE_COMPANION_FILES",
    "PPT_RULE_NOT_IN_GITHUB",
    "PPT_COVER_NOT_COVER",
    "PPT_TITLE_CORE_MISMATCH",
    "PPT_CASE_BEFORE_TECH",
    "PPT_REASON_INVENTED",
    "PPT_RULE_NOT_EXECUTABLE",
    "PPT_OVER_SPLIT",
    "PPT_INTERNAL_DIRECTIVE_VISIBLE",
    "PPT_FORMULA_NOT_HUMANIZED",
    "PPT_CASE_ONLY_ANSWER",
    "PPT_SPOKEN_TEXT_VISIBLE",
    "PPT_VISUAL_DUPLICATION",
    "PPT_MAIN_PAGE_TOO_DENSE",
    "PPT_STATISTICS_NOT_HUMANIZED",
    "PPT_ADVICE_VAGUE",
    "PPT_STOP_TARGET_UNCLEAR",
    "PPT_CONCLUSION_AMBIGUOUS",
    "PPT_CONCLUSION_ADVICE_CONFLICT",
    "PPT_NOTES_MISSING",
    "PPT_NOTES_AI_STYLE",
    "PPT_APPENDIX_MIXED_IN_MAIN",
    "PPT_APPENDIX_NOT_HIDDEN",
    "PPT_APPENDIX_EVIDENCE_INCOMPLETE",
    "PPT_MAIN_APPENDIX_MISMATCH",
    "PPT_BRAND_PAGE_NOT_LAST",
    "PPT_BRAND_CONTACT_WRONG",
    "PPT_FIXED_TEMPLATE_OVERUSE",
    "PPT_NARRATION_REVIEW_FAILED",
    "PPT_PRECISION_REVIEW_FAILED",
    "PPT_RENDER_REVIEW_FAILED",
}
actual_failure_states = {item.get("失败状态") for item in ppt_tests}
missing_failures = required_failure_states - actual_failure_states
if missing_failures:
    err(f"PPT验收测试缺少失败状态: {sorted(missing_failures)}")

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

override_path = ROOT / "00A_当前强制覆盖与废止规则.md"
override = override_path.read_text(encoding="utf-8") if override_path.exists() else ""
for phrase in [
    "GitHub是唯一正式规则源",
    "废止旧三文件交付",
    "废止独立PPT配套文件",
    "废止机械拆页和固定结构",
    "废止程序化和重复表达",
    "PPT压缩与精度规则.json",
    "www.laocaimi.org",
    "https://t.me/laocaimi1314",
]:
    if phrase not in override:
        err(f"00A覆盖层缺少关键语义: {phrase}")

ppt_path = ROOT / "05A_方案讲解PPT生产协议.md"
ppt_protocol = ppt_path.read_text(encoding="utf-8") if ppt_path.exists() else ""
required_ppt_phrases = [
    "GitHub是规则唯一正式源",
    "单一PPT原则",
    "标题必须准确表达核心",
    "动态结构，不使用固定页数模板",
    "页面独立价值门槛",
    "公式和术语必须翻译成人话",
    "视觉内容去重与留白",
    "风险和停止建议必须精确",
    "结论必须短且与建议一致",
    "隐藏附录必须真正保存证据",
    "压缩和去程序化审查",
    "最终精度审查",
    "PPT页面类型卡片.jsonl",
    "PPT讲解验收测试集.jsonl",
    "www.laocaimi.org",
    "https://t.me/laocaimi1314",
    "PPT_RULE_NOT_IN_GITHUB",
    "PPT_OVER_SPLIT",
    "PPT_VISUAL_DUPLICATION",
    "PPT_APPENDIX_NOT_HIDDEN",
    "PPT_MAIN_APPENDIX_MISMATCH",
    "PPT_PRECISION_REVIEW_FAILED",
]
for phrase in required_ppt_phrases:
    if phrase not in ppt_protocol:
        err(f"PPT模块缺少关键语义: {phrase}")

for deprecated in [
    "方案ID_PPT逐页脚本与旁白.md",
    "方案ID_PPT事实校验表.json",
    "强制先举例，再归纳规则",
    "先跑一个例子",
]:
    if deprecated in ppt_protocol:
        err(f"PPT模块仍包含已废止规则: {deprecated}")

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
    f"ppt_page_types={len(page_types)} "
    f"ppt_tests={len(ppt_tests)} "
    "ppt=COMPRESSED_NATURAL_PRECISION_DIRECTOR"
)
