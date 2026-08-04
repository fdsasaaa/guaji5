#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json
import math
import re
import shutil
import sys

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_b394_delivery as base

PROJECT = "三区冠军三码"
ID = "B397-SET-001"
BATCH = "BATCH-B397-ZONE-CHAMPION-001"
PERIODS = 24
P0 = 0.30
FUNDING_SEQUENCE = [1, 1, 2, 3, 2, 1, 1, 1]
UNIT_EXPOSURE = 3
INPUT = ROOT / "01_本次输入" / "哈希分分彩_20260731_0181至0380.txt"
OUT = ROOT / "dist" / f"{PROJECT}_交付"
SCHEME_DIR = OUT / f"{PROJECT}_方案文件夹"
PPT = OUT / f"{PROJECT}_挂机前讲解.pptx"
SEO = OUT / f"{PROJECT}_YouTube_SEO.txt"
EVIDENCE = OUT / f"{PROJECT}_验证记录.json"
MANIFEST = OUT / "DELIVERY_MANIFEST.json"
OUTER = OUT / f"{PROJECT}_完整交付.zip"
POS = [(2, "百位"), (3, "十位"), (4, "个位")]
ZONES = [("低区", (0, 1, 2)), ("中区", (3, 4, 5, 6)), ("高区", (7, 8, 9))]


def choose(values: list[int]) -> tuple[list[int], list[dict]]:
    counts = Counter(values)
    last = {d: max((i for i, value in enumerate(values) if value == d), default=-1) for d in range(10)}
    selected: list[int] = []
    detail: list[dict] = []
    for name, digits in ZONES:
        ranked = sorted(digits, key=lambda d: (-counts[d], -last[d], d))
        selected.append(ranked[0])
        detail.append({
            "分区": name,
            "范围": list(digits),
            "排序": [{"数字": d, "出现次数": counts[d], "最近位置": last[d]} for d in ranked],
            "冠军": ranked[0],
        })
    return selected, detail


def tail_p(n: int, hits: int, p: float = P0) -> float:
    return min(1.0, sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(hits, n + 1)))


def max_miss_streak(values: list[bool]) -> int:
    best = run = 0
    for value in values:
        run = 0 if value else run + 1
        best = max(best, run)
    return best


def summary(values: list[bool]) -> dict:
    n = len(values)
    hits = sum(values)
    return {
        "预测次数": n,
        "命中次数": hits,
        "命中比例": round(hits / n, 6),
        "随机三码理论基准": P0,
        "相对基准差": round(hits / n - P0, 6),
        "独立近似单侧二项P值": round(tail_p(n, hits), 6),
        "最大连续未中": max_miss_streak(values),
    }


def freeze(rows: list[tuple[str, list[int]]]) -> dict:
    result: dict = {}
    for index, name in POS:
        selected, detail = choose([digits[index] for _, digits in rows])
        result[name] = {
            "位置索引": index,
            "样本期数": len(rows),
            "固定分区": {"低区": [0, 1, 2], "中区": [3, 4, 5, 6], "高区": [7, 8, 9]},
            "分区排序": detail,
            "冻结号码": selected,
            "运行中是否更新": False,
        }
    return result


def audit(rows: list[tuple[str, list[int]]]) -> dict:
    segments = {"校准段": [], "验证段": [], "审计段": []}
    per_position = {name: [] for _, name in POS}
    combined: list[bool] = []
    for t in range(60, len(rows)):
        for index, name in POS:
            selected, _ = choose([digits[index] for _, digits in rows[:t]])
            hit = rows[t][1][index] in selected
            combined.append(hit)
            per_position[name].append(hit)
            segment = "校准段" if t < 120 else "验证段" if t < 160 else "审计段"
            segments[segment].append(hit)
    return {
        "方法": "从第61期开始逐期扩展窗口；每次仅使用此前同位置数据，在固定低中高三区各取频次冠军。",
        "总计": summary(combined),
        "分段": {key: summary(value) for key, value in segments.items()},
        "分位置": {key: summary(value) for key, value in per_position.items()},
        "统计边界": "二项P值仅作独立近似参考；位置间和时间上可能相关。",
        "样本边界": "200期数据已被项目复用，不属于新的独立样本外。",
    }


def set_value(lines: list[str], prefix: str, value: str) -> None:
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = prefix + value
            return
    raise ValueError(f"缺少字段: {prefix}")


def formal_txt(play: str, digits: list[int]) -> str:
    lines = base.common("定码轮换", play, True)
    lines += ["换号规则=9", f"换号期数={PERIODS}"]
    lines += base.tail()
    set_value(lines, "倍投类型=", "0")
    sequence_text = ",".join(map(str, FUNDING_SEQUENCE))
    set_value(lines, "倍投计划=", sequence_text)
    set_value(lines, "倍投方案=", sequence_text)
    lines += [f"定码轮换内容={' '.join(map(str, digits))}", "定码轮换单组=True", "SchemeCreator="]
    return "\r\n".join(lines) + "\r\n"


def build_scheme_folder(groups: dict) -> None:
    if SCHEME_DIR.exists():
        shutil.rmtree(SCHEME_DIR)
    SCHEME_DIR.mkdir(parents=True)
    for position in ["百位", "十位", "个位"]:
        digits = groups[position]["冻结号码"]
        visible_digits = "".join(map(str, digits))
        filename = f"{position}{visible_digits}-定码轮换.txt"
        (SCHEME_DIR / filename).write_bytes(formal_txt(position, digits).encode("gbk"))


def count_line(groups: dict, position: str) -> str:
    return "  ·  ".join(
        f"{item['分区']} {item['冠军']}（{item['排序'][0]['出现次数']}次）"
        for item in groups[position]["分区排序"]
    )


def build_ppt(groups: dict, issue: str, historical: dict) -> None:
    cover = ROOT / "assets" / "ppt" / "fixed_pages" / "首页背景图谱.png"
    end = ROOT / "assets" / "ppt" / "fixed_pages" / "固定最后一页_画面.png"
    prs = base.fixed.new_prs()
    accents = {"百位": "gold", "十位": "blue", "个位": "green"}

    slide = base.fixed.add_cover(prs, cover)
    base.fixed.add_text(slide, Inches(.82), Inches(1.02), Inches(9.2), Inches(.72), PROJECT, 34, base.COLORS["white"], True)
    base.fixed.add_text(slide, Inches(.84), Inches(1.86), Inches(9.7), Inches(.38), "低中高三区，各选一名频次冠军", 17, base.COLORS["gold"], True)
    base.fixed.add_text(slide, Inches(.84), Inches(5.88), Inches(9.8), Inches(.34), "挂机前规则与资金节奏说明", 14, base.COLORS["white"])
    base.fixed.set_notes(slide, "本期只冻结规则、投注数字和资金节奏，不提前宣布有效。")

    slide = base.body_slide(prs, "这次验证什么", "研究问题")
    base.card(slide, Inches(.78), Inches(1.8), Inches(5.55), Inches(3.82), "分区后再竞争", "把0—9固定分成低、中、高三区，每区只选一名历史频次冠军。", "gold", 18, 19)
    base.card(slide, Inches(6.58), Inches(1.8), Inches(5.55), Inches(3.82), "规则一次冻结", "百位、十位、个位分别计算，连续24期不改号码、不改资金序列。", "blue", 18, 19)
    base.fixed.set_notes(slide, "说明实验问题和固定参数边界。")

    slide = base.body_slide(prs, "三区怎样划分", "核心规则")
    for i, (title, body, accent) in enumerate([("低区", "0 1 2", "gold"), ("中区", "3 4 5 6", "blue"), ("高区", "7 8 9", "green")]):
        base.card(slide, Inches(.82 + i * 4.08), Inches(1.95), Inches(3.52), Inches(2.25), title, body, accent, 20, 25)
    base.card(slide, Inches(.82), Inches(4.52), Inches(11.68), Inches(1.34), "冠军规则", "区内按出现次数降序；同频优先最近出现；仍相同取较小数字。", "gold", 17, 18)
    base.fixed.set_notes(slide, "分区和并列规则均在运行前冻结。")

    slide = base.body_slide(prs, "本轮实际投注数字", "投注号码")
    for i, position in enumerate(["百位", "十位", "个位"]):
        digits = " ".join(map(str, groups[position]["冻结号码"]))
        base.card(slide, Inches(.72 + i * 4.05), Inches(1.82), Inches(3.82), Inches(3.95), position, f"{count_line(groups, position)}\n\n实际投注：\n{digits}", accents[position], 19, 18)
    base.fixed.add_text(slide, Inches(.88), Inches(6.08), Inches(11.4), Inches(.3), f"数据截止：{issue}｜数字同时写入文件名和TXT投注字段", 15, base.COLORS["gray"], True, PP_ALIGN.CENTER)
    base.fixed.set_notes(slide, "必须直接读出百位269、十位037、个位168。")

    slide = base.body_slide(prs, "以百位完整复算一次", "完整案例")
    for i, item in enumerate(groups["百位"]["分区排序"]):
        ranking = " > ".join(f"{row['数字']}（{row['出现次数']}次）" for row in item["排序"])
        body = f"范围：{' '.join(map(str, item['范围']))}\n\n排序：\n{ranking}\n\n冠军：{item['冠军']}"
        base.card(slide, Inches(.72 + i * 4.05), Inches(1.82), Inches(3.82), Inches(3.92), item["分区"], body, ["gold", "blue", "green"][i], 18, 16)
    base.fixed.add_text(slide, Inches(.9), Inches(6.02), Inches(11.5), Inches(.38), f"百位实际投注：{' '.join(map(str, groups['百位']['冻结号码']))}", 20, base.COLORS["white"], True, PP_ALIGN.CENTER)
    base.fixed.set_notes(slide, "其他位置使用相同算法。")

    slide = base.body_slide(prs, "方案文件怎样运行", "执行规则")
    for i, position in enumerate(["百位", "十位", "个位"]):
        digits = "".join(map(str, groups[position]["冻结号码"]))
        base.card(slide, Inches(.82 + i * 4.08), Inches(1.95), Inches(3.52), Inches(2.08), f"{i + 1}  {position}", f"文件名：{position}{digits}\n投注：{' '.join(digits)}", accents[position], 18, 18)
    base.card(slide, Inches(.82), Inches(4.38), Inches(11.68), Inches(1.42), "软件设置", "导入方案文件夹中的3份TXT → 手工开启顶部方案轮投 → 每期运行一个位置 → 24期后停止。", "gold", 17, 18)
    base.fixed.set_notes(slide, "外部交付的方案文件夹不再放说明、记录模板、随机对照和探针。")

    sequence_text = " → ".join(map(str, FUNDING_SEQUENCE))
    slide = base.body_slide(prs, "资金路径不再机械平倍", "倍投设计")
    base.card(slide, Inches(.78), Inches(1.8), Inches(7.15), Inches(3.92), "温和升压—主动释放", f"资金序列：\n\n{sequence_text}\n\n先缓慢升到3倍，再主动降回1倍。", "gold", 19, 22)
    base.card(slide, Inches(8.18), Inches(1.8), Inches(3.95), Inches(3.92), "硬边界", "最高：3倍\n8步合计：12倍\n不无限递增\n24期强制停止", "green", 18, 19)
    base.fixed.set_notes(slide, "资金路径只改变暴露节奏，不提高号码中奖概率。普通倍投运行语义当前按E2控制实验处理，首次导入必须核对。")

    historical_total = historical["总计"]
    full_stage_exposure = UNIT_EXPOSURE * sum(FUNDING_SEQUENCE) * (PERIODS // len(FUNDING_SEQUENCE))
    slide = base.body_slide(prs, "本金与停止边界", "风险控制")
    base.card(slide, Inches(.78), Inches(1.8), Inches(3.55), Inches(3.92), "每期基础", "3个定位胆号码\n每个按1元\n基础暴露3元", "gold", 18, 21)
    base.card(slide, Inches(4.58), Inches(1.8), Inches(3.55), Inches(3.92), "建议本金", f"8步一轮36元\n24期三轮\n毛暴露上限{full_stage_exposure}元", "blue", 18, 20)
    base.card(slide, Inches(8.38), Inches(1.8), Inches(3.55), Inches(3.92), "停止规则", "止盈：不设置\n止损：不设置\n满24期停止\n不得临时加倍", "green", 18, 18)
    base.fixed.set_notes(slide, "108元是按完整24期资金序列计算的毛暴露预算，不是盈利目标。")

    slide = base.body_slide(prs, "怎样判断这套设计", "验证方法")
    base.card(slide, Inches(.78), Inches(1.82), Inches(5.55), Inches(3.82), "每期记录", "期号、实际位置、投注数字、当前倍数、开奖号、命中与否。", "gold", 18, 19)
    base.card(slide, Inches(6.58), Inches(1.82), Inches(5.55), Inches(3.82), "运行后再下结论", f"旧数据滚动命中 {historical_total['命中次数']}/{historical_total['预测次数']}，约{historical_total['命中比例'] * 100:.2f}%。接近随机基准，不能提前宣传优势。", "blue", 18, 17)
    base.fixed.set_notes(slide, "真正结论只来自新的24期真实运行记录。")

    base.fixed.add_end(prs, end)
    base.fixed.save(prs, PPT)


def build_seo(groups: dict) -> None:
    numbers = f"百位{''.join(map(str, groups['百位']['冻结号码']))}、十位{''.join(map(str, groups['十位']['冻结号码']))}、个位{''.join(map(str, groups['个位']['冻结号码']))}"
    text = f"""标题：三区冠军三码验证：低中高各取1码，24期实测\n\n标签：彩票实验室,三区冠军,定位胆,时时彩研究,彩票数据分析,挂机方案,倍投策略,号码验证,彩票方案测试,五位数彩票\n\n描述：本期验证“三区冠军三码”方案。把0—9固定分为低区、中区和高区，每个位置各选出一名历史频次冠军，本轮投注数字为{numbers}。资金路径采用1,1,2,3,2,1,1,1的温和升压与主动释放结构，最高3倍，连续运行24期后停止。内容仅用于数据实验与软件方案验证，不承诺盈利，也不把历史频次解释为未来必然规律。\n"""
    SEO.write_text(text, encoding="utf-8")


def validate(groups: dict) -> dict:
    errors: list[str] = []
    expected_files = []
    sequence_text = ",".join(map(str, FUNDING_SEQUENCE))
    for position in ["百位", "十位", "个位"]:
        digits = groups[position]["冻结号码"]
        visible = "".join(map(str, digits))
        path = SCHEME_DIR / f"{position}{visible}-定码轮换.txt"
        expected_files.append(path)
        if not path.exists():
            errors.append(f"缺少方案文件: {path.name}")
            continue
        raw = path.read_bytes()
        text = raw.decode("gbk")
        if b"\r\n" not in raw or not text.startswith("True\r\n"):
            errors.append(f"TXT编码、换行或启用状态错误: {path.name}")
        if f"定码轮换内容={' '.join(map(str, digits))}\r\n" not in text:
            errors.append(f"投注数字缺失: {path.name}")
        if f"倍投计划={sequence_text}\r\n" not in text or f"倍投方案={sequence_text}\r\n" not in text:
            errors.append(f"资金序列不一致: {path.name}")
        if re.search(r"倍投计划=1(?:,1)+\r\n", text):
            errors.append(f"仍为机械平倍: {path.name}")
    actual_files = sorted(path for path in SCHEME_DIR.rglob("*") if path.is_file())
    if actual_files != sorted(expected_files):
        errors.append("方案文件夹必须只包含3份可导入TXT")

    presentation = Presentation(PPT)
    visible_text = "\n".join(shape.text for slide in presentation.slides for shape in slide.shapes if hasattr(shape, "text") and shape.text)
    if len(presentation.slides) != 10:
        errors.append(f"PPT页数错误: {len(presentation.slides)}")
    for index, slide in enumerate(presentation.slides, 1):
        if not slide.notes_slide.notes_text_frame.text.strip():
            errors.append(f"第{index}页无备注")
    for position in ["百位", "十位", "个位"]:
        digits = " ".join(map(str, groups[position]["冻结号码"]))
        if digits not in visible_text:
            errors.append(f"PPT缺少投注数字: {position}")
    if "1 → 1 → 2 → 3 → 2 → 1 → 1 → 1" not in visible_text:
        errors.append("PPT缺少资金序列")
    for forbidden in [ID, "SET_001", "保证盈利", "稳定盈利", "回本"]:
        if forbidden in visible_text:
            errors.append(f"PPT禁词: {forbidden}")

    seo_text = SEO.read_text(encoding="utf-8")
    if seo_text.count("标题：") != 1 or seo_text.count("标签：") != 1 or seo_text.count("描述：") != 1:
        errors.append("SEO文件必须恰好包含一个标题、一行标签和一个描述")
    tag_line = next((line for line in seo_text.splitlines() if line.startswith("标签：")), "")
    tags = [tag.strip() for tag in tag_line.removeprefix("标签：").split(",") if tag.strip()]
    if not 8 <= len(tags) <= 10:
        errors.append(f"SEO标签数量错误: {len(tags)}")

    if OUTER.exists():
        OUTER.unlink()
    with ZipFile(OUTER, "w", ZIP_DEFLATED) as archive:
        for path in sorted(SCHEME_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=f"{SCHEME_DIR.name}/{path.relative_to(SCHEME_DIR).as_posix()}")
        archive.write(PPT, arcname=PPT.name)
        archive.write(SEO, arcname=SEO.name)

    with ZipFile(OUTER) as archive:
        names = archive.namelist()
        root_entries = {name.split("/", 1)[0] for name in names}
        expected_roots = {SCHEME_DIR.name, PPT.name, SEO.name}
        if root_entries != expected_roots:
            errors.append(f"完整包根目录不是严格3项: {sorted(root_entries)}")
        if any(name.lower().endswith((".md", ".csv", ".json", ".zip")) for name in names):
            errors.append("完整包含说明、记录、JSON或嵌套ZIP")

    if errors:
        raise ValueError(";".join(errors))
    return {
        "外层ZIP根目录": "EXACTLY_3_ITEMS",
        "方案文件夹": "3_IMPORTABLE_TXT_ONLY",
        "投注数字": "FILENAME_TXT_PPT_VISIBLE",
        "资金路径": FUNDING_SEQUENCE,
        "最高倍数": max(FUNDING_SEQUENCE),
        "PPT页数": 10,
        "SEO": "ONE_TITLE_ONE_TAG_LINE_ONE_DESCRIPTION",
    }


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = base.parse_draws(INPUT)
    if len(rows) != 200:
        raise ValueError("本批要求200期")
    groups = freeze(rows)
    historical = audit(rows)
    build_scheme_folder(groups)
    build_ppt(groups, rows[-1][0], historical)
    build_seo(groups)
    checks = validate(groups)

    stage_gross_exposure = UNIT_EXPOSURE * sum(FUNDING_SEQUENCE) * (PERIODS // len(FUNDING_SEQUENCE))
    evidence = {
        "批次ID": BATCH,
        "方案内部ID": ID,
        "自然名称": PROJECT,
        "阶段": "PRE_RUN_SETUP",
        "数据来源": {
            "文件": str(INPUT.relative_to(ROOT)).replace("\\", "/"),
            "期号范围": f"{rows[0][0]}—{rows[-1][0]}",
            "总期数": len(rows),
            "数据复用状态": "REUSED_DATA_NOT_INDEPENDENT_HOLDOUT",
        },
        "观察对象": "百位、十位、个位分别建模",
        "分析角度": "固定分区频次冠军",
        "计算过程": "0—2、3—6、7—9三区固定；区内频次降序，同频按最近出现与数字升序；每区取1码。",
        "冻结结果": groups,
        "历史滚动审计": historical,
        "正式执行": {
            "顶部方案轮投": "人工勾选",
            "运行期数": PERIODS,
            "每期基础成本": UNIT_EXPOSURE,
            "资金路径类型": "CONTROLLED_PRESSURE_RELEASE",
            "资金序列": FUNDING_SEQUENCE,
            "最高倍数": max(FUNDING_SEQUENCE),
            "8步总倍数": sum(FUNDING_SEQUENCE),
            "24期毛暴露预算": stage_gross_exposure,
            "建议本金": stage_gross_exposure,
            "止盈": "不设置",
            "止损": "不设置",
            "替代停止条件": f"满{PERIODS}期硬停止",
            "软件证据等级": "E2",
            "首次导入核对": True,
        },
        "结论边界": "资金路径改变暴露节奏，不提高号码中奖概率；最终结论只使用新的实际挂机记录。",
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = [PPT, SEO, EVIDENCE, OUTER, *sorted(SCHEME_DIR.glob("*.txt"))]
    MANIFEST.write_text(
        json.dumps({
            "project": PROJECT,
            "stage": "PRE_RUN_SETUP",
            "validation": checks,
            "external_delivery": OUTER.name,
            "files": {str(path.relative_to(OUT)): base.sha256(path) for path in files},
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "B397_DELIVERY_V2_OK",
        ",".join(f"{name}:{groups[name]['冻结号码']}" for name in ["百位", "十位", "个位"]),
        f"funding={FUNDING_SEQUENCE}",
        OUTER.name,
    )


if __name__ == "__main__":
    main()
