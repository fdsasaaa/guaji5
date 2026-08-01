#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []


def fail(message: str) -> None:
    errors.append(message)


def load_json(name: str):
    try:
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{name}读取失败: {exc}")
        return {}


def load_jsonl(name: str):
    items = []
    try:
        for number, line in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception as exc:
                fail(f"{name}:{number} JSON错误: {exc}")
    except Exception as exc:
        fail(f"{name}读取失败: {exc}")
    return items


manifest = load_json("SYSTEM_MANIFEST.json")
state = load_json("SYSTEM_STATE.json")
state_cn = load_json("系统状态.json")
protocol = (ROOT / "05A_方案讲解PPT生产协议.md").read_text(encoding="utf-8")
override = (ROOT / "00A_当前强制覆盖与废止规则.md").read_text(encoding="utf-8")
page_types = load_jsonl("PPT页面类型卡片.jsonl")
tests = load_jsonl("PPT讲解验收测试集.jsonl")

if state != state_cn:
    fail("SYSTEM_STATE.json 与 系统状态.json 不一致")

expected_order = "技术定义→真实技术缘由或实验规则说明→核心规则与必要边界→完整案例"
if manifest.get("PPT默认理解顺序") != expected_order:
    fail("SYSTEM_MANIFEST未登记完整PPT理解顺序")
if state.get("PPT默认理解顺序") != expected_order:
    fail("SYSTEM_STATE未登记完整PPT理解顺序")
if expected_order not in override:
    fail("00A覆盖层缺少完整PPT理解顺序")

for phrase in [
    "技术定义",
    "真实技术缘由或实验规则说明",
    "核心规则和必要边界",
    "完整实际案例",
    "每一页都必须有演讲者备注",
    "http://www.laocaimi.org",
    "PPT_BRAND_LINK_NOT_CLICKABLE",
]:
    if phrase not in protocol:
        fail(f"05A缺少关键规则: {phrase}")

if "→ 技术和核心规则\n→ 真实缘由或实验规则说明" in protocol:
    fail("05A仍保留规则早于缘由的旧顺序")

if manifest.get("PPT所有页面必须有备注") is not True:
    fail("SYSTEM_MANIFEST未强制所有页面备注")
if state.get("PPT所有页面必须有备注") is not True:
    fail("SYSTEM_STATE未强制所有页面备注")
if manifest.get("PPT品牌链接必须可点击") is not True:
    fail("SYSTEM_MANIFEST未强制品牌链接可点击")
if state.get("PPT品牌链接必须可点击") is not True:
    fail("SYSTEM_STATE未强制品牌链接可点击")

brand = manifest.get("PPT固定品牌结束页", {})
if brand.get("网址") != "www.laocaimi.org":
    fail("品牌网址显示文字错误")
if brand.get("网址链接") != "http://www.laocaimi.org":
    fail("品牌网址超链接目标错误")
if brand.get("联系方式") != "https://t.me/laocaimi1314":
    fail("Telegram显示文字错误")
if brand.get("联系方式链接") != "https://t.me/laocaimi1314":
    fail("Telegram超链接目标错误")

if len(page_types) < 14:
    fail(f"页面类型数量不足14，实际{len(page_types)}")
for item in page_types:
    if not item.get("备注重点"):
        fail(f"页面类型{item.get('页面类型ID')}缺少备注重点")
brand_cards = [item for item in page_types if item.get("页面类型ID") == "BRAND_END"]
if not brand_cards:
    fail("缺少BRAND_END页面类型")
else:
    targets = brand_cards[0].get("超链接目标", {})
    if targets.get("www.laocaimi.org") != "http://www.laocaimi.org":
        fail("BRAND_END网址链接目标错误")
    if targets.get("https://t.me/laocaimi1314") != "https://t.me/laocaimi1314":
        fail("BRAND_END Telegram链接目标错误")

if len(tests) < 49:
    fail(f"PPT验收测试数量不足49，实际{len(tests)}")
test_ids = {item.get("测试ID") for item in tests}
for required_id in ["PPT-T047", "PPT-T048", "PPT-T049"]:
    if required_id not in test_ids:
        fail(f"缺少PPT验收测试: {required_id}")
failure_states = {item.get("失败状态") for item in tests}
if "PPT_BRAND_LINK_NOT_CLICKABLE" not in failure_states:
    fail("验收测试未覆盖品牌链接不可点击")

if manifest.get("PPT讲解验收测试数量") != len(tests):
    fail("SYSTEM_MANIFEST的PPT测试数量与JSONL不一致")
if state.get("PPT讲解验收测试数量") != len(tests):
    fail("SYSTEM_STATE的PPT测试数量与JSONL不一致")

if errors:
    print("PPT_DIRECTOR_RULES_FAILED")
    for item in errors:
        print("-", item)
    sys.exit(1)

print(
    "PPT_DIRECTOR_RULES_OK "
    f"page_types={len(page_types)} tests={len(tests)} "
    "order=TECH_DEFINE_REASON_RULE_CASE notes=ALL_SLIDES brand_links=CLICKABLE"
)
