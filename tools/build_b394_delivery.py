#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import materialize_ppt_fixed_pages as fixed  # noqa: E402

BATCH_ID = "BATCH-V394-TRIANGLE-SNAPSHOT-001"
SCHEME_ID = "B394-SET-001"
SLUG = "B394_SET_001_冷热三角快照接力"
INPUT_DATA = ROOT / "01_本次输入" / "哈希分分彩_20260731_0181至0380.txt"
OUT_ROOT = ROOT / "dist" / "B394_SET_001_delivery"
PACKAGE_STAGE = OUT_ROOT / "package"
ZIP_PATH = OUT_ROOT / f"{SLUG}_方案套.zip"
PPT_PATH = OUT_ROOT / f"{SLUG}_人工讲解型PPT.pptx"
MANIFEST_PATH = OUT_ROOT / "DELIVERY_MANIFEST.json"

COLORS = {
    "bg": (8, 12, 17), "panel": (18, 25, 32), "white": (244, 247, 250),
    "gray": (166, 178, 188), "gold": (232, 177, 64), "green": (65, 201, 151),
    "red": (226, 93, 93), "blue": (77, 153, 230), "line": (68, 82, 96),
}
POSITIONS = [("百位", 2), ("十位", 3), ("个位", 4)]
ROLE_NAMES = ["短热", "中温", "长遗漏"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_draws(path: Path) -> list[tuple[str, list[int]]]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"开奖数据第{line_no}行缺少等号")
        issue, number = line.split("=", 1)
        if not issue.isdigit() or len(number) != 5 or not number.isdigit():
            raise ValueError(f"开奖数据第{line_no}行格式错误: {line}")
        rows.append((issue, [int(c) for c in number]))
    if len(rows) != 200:
        raise ValueError(f"预期200期，实际{len(rows)}期")
    issues = [issue for issue, _ in rows]
    if issues != sorted(issues) or len(set(issues)) != len(issues):
        raise ValueError("期号不是严格升序或存在重复")
    return rows


def rank_by_frequency(window: list[int]) -> list[int]:
    counts = Counter(window)
    last_index = {d: max((i for i, x in enumerate(window) if x == d), default=-1) for d in range(10)}
    return sorted(range(10), key=lambda d: (-counts[d], -last_index[d], d))


def short_hot3(history: list[int]) -> tuple[int, int, int]:
    return tuple(sorted(rank_by_frequency(history[-6:])[:3]))


def middle_warm3(history: list[int]) -> tuple[int, int, int]:
    return tuple(sorted(rank_by_frequency(history[-12:])[3:6]))


def long_omission3(history: list[int]) -> tuple[int, int, int]:
    window = history[-18:]
    omissions = {}
    for digit in range(10):
        missing = 0
        for value in reversed(window):
            if value == digit:
                break
            missing += 1
        omissions[digit] = missing
    ranked = sorted(range(10), key=lambda d: (-omissions[d], d))
    return tuple(sorted(ranked[:3]))


def select_snapshot(rows: list[tuple[str, list[int]]], end: int) -> list[tuple[int, int, int]]:
    history = rows[:end]
    return [
        short_hot3([digits[2] for _, digits in history]),
        middle_warm3([digits[3] for _, digits in history]),
        long_omission3([digits[4] for _, digits in history]),
    ]


def max_miss_streak(hits: list[int]) -> int:
    current = maximum = 0
    for hit in hits:
        if hit:
            current = 0
        else:
            current += 1
            maximum = max(maximum, current)
    return maximum


def binomial_tail(n: int, k: int, p: float = 0.3) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def simulate_offset(rows: list[tuple[str, list[int]]], offset: int) -> dict:
    hits, trace, snapshots = [], [], []
    leg_hits = {0: [], 1: [], 2: []}
    for block_start in range(18, len(rows), 18):
        groups = select_snapshot(rows, block_start)
        block_end = min(block_start + 18, len(rows))
        snapshots.append({
            "冻结前最后期": rows[block_start - 1][0], "验证开始期": rows[block_start][0],
            "验证结束期": rows[block_end - 1][0], "短热百位": " ".join(map(str, groups[0])),
            "中温十位": " ".join(map(str, groups[1])), "长遗漏个位": " ".join(map(str, groups[2])),
        })
        for j, (issue, digits) in enumerate(rows[block_start:block_end]):
            leg = (j + offset) % 3
            position_name, position_index = POSITIONS[leg]
            selected = groups[leg]
            hit = int(digits[position_index] in selected)
            hits.append(hit)
            leg_hits[leg].append(hit)
            trace.append({
                "期号": issue, "接力位": leg + 1, "角色": ROLE_NAMES[leg], "位置": position_name,
                "选择": " ".join(map(str, selected)), "开奖号": digits[position_index], "命中": bool(hit),
            })
    splits = {"前段": (0, 110), "中段": (110, 146), "后段": (146, 182)}
    split_stats = {}
    for name, (start, end) in splits.items():
        count = sum(hits[start:end])
        split_stats[name] = {"命中": count, "总数": end - start, "命中率": count / (end - start)}
    return {
        "起点偏移": offset, "起点角色": ROLE_NAMES[offset], "命中": sum(hits), "总数": len(hits),
        "命中率": sum(hits) / len(hits), "随机理论": 0.3,
        "单侧二项检验p值": binomial_tail(len(hits), sum(hits)),
        "最大连续未中": max_miss_streak(hits), "分段": split_stats,
        "三角色": {
            ROLE_NAMES[i]: {"位置": POSITIONS[i][0], "命中": sum(leg_hits[i]), "总数": len(leg_hits[i]),
                            "命中率": sum(leg_hits[i]) / len(leg_hits[i])}
            for i in range(3)
        },
        "快照记录": snapshots, "追踪样例": trace[:18],
    }


def simulate(rows: list[tuple[str, list[int]]]) -> dict:
    offsets = [simulate_offset(rows, offset) for offset in range(3)]
    latest_groups = select_snapshot(rows, len(rows))
    rates = [item["命中率"] for item in offsets]
    result = {
        "方案ID": SCHEME_ID, "批次ID": BATCH_ID,
        "真实问题": "同一组6/12/18期快照，按百十个接力时，是否稳定优于同成本随机三码；接力起点会不会改变结论？",
        "数据": {"文件": str(INPUT_DATA.relative_to(ROOT)).replace("\\", "/"),
                 "范围": f"{rows[0][0]}—{rows[-1][0]}", "期数": len(rows), "滚动验证期数": len(rows) - 18,
                 "说明": "每18期重新冻结一次；该200期数据已被项目复用，不标独立样本外。"},
        "冻结规则": {
            "短热百位": "最近6期按出现次数排序，次数相同优先最近出现，取前3码。",
            "中温十位": "最近12期按同一排序，排除最热前三后取第4至第6名。",
            "长遗漏个位": "最近18期按当前遗漏从高到低排序，取前3码；并列取较小数字。",
            "接力": "顶部GUI方案轮投，每期只运行一个方案；18期后停止并重新生成快照。",
        },
        "本轮最新快照": {"短热百位": " ".join(map(str, latest_groups[0])),
                         "中温十位": " ".join(map(str, latest_groups[1])),
                         "长遗漏个位": " ".join(map(str, latest_groups[2])),
                         "来源截止期": rows[-1][0], "前向轮次": "后续18期"},
        "三种起点历史结果": offsets,
        "命中率范围": {"最低": min(rates), "最高": max(rates), "差值": max(rates) - min(rates)},
        "结论": "三个起点均未达到统计显著；起点变化造成约7个百分点以上差异，说明顺序偶然性足以改变观感，不能把某个起点的较好结果包装成稳定优势。",
        "资金冻结": {"单位": "1U=每个号码单注金额", "每期号码": 3, "每期暴露": "3U",
                     "主组18期毛暴露": "54U", "随机对照18期毛暴露": "54U", "建议本金": "108U",
                     "止盈止损模式": "NONE", "止盈": "不设置", "止损": "不设置",
                     "替代停止条件": "主组18期和随机对照18期分别跑完即停；不在同一轮内改码、换起点或追加倍投。"},
        "软件边界": ["顶部方案轮投的启用状态不能写入TXT，必须人工勾选。",
                     "GUI实际起始顺序和重启续位尚未E3冻结，运行时必须记录第一期实际方案。",
                     "本交付不使用组合方案轮投枪，避免把E2格式误写成E3运行正确。",
                     "快照号码在18期内固定；18期后必须重新计算，不宣称软件会自动更新冷热或遗漏。"],
    }
    if latest_groups != [(1, 4, 5), (1, 4, 9), (0, 2, 5)]:
        raise AssertionError(f"最新快照漂移: {latest_groups}")
    if [item["命中"] for item in offsets] != [63, 64, 51]:
        raise AssertionError(f"历史统计漂移: {[item['命中'] for item in offsets]}")
    return result


def common_lines(strategy: str, play_name: str, enabled: bool) -> list[str]:
    return ["True" if enabled else "False", strategy, "软件名称=CXGGJ", "玩法类型=定位胆",
            f"玩法名称={play_name}", "金额模式=2", "投注监控=False-", "投注监控模式=0",
            "任选中奖=1-10", "任选位置="]


def tail_lines() -> list[str]:
    return ["翻倍方式=0", "正集=True", "倍投类型=0", "倍投计划=1,1,1,1,1,1,1,1,1,1",
            "倍投方案=1,1,1,1,1,1,1,1,1,1", "显示更多=False", "真实投注1=False-50000",
            "真实投注2=False-50000", "模拟投注1=False-50000", "模拟投注2=False-50000",
            "盈利跳转=False-50000-1", "亏损跳转=False-50000-1", "盈利停止=False-50000",
            "亏损停止=False-50000", "投注时间=False", "投注时间类型=0",
            "范围开始时间=False-09:01:00", "范围停止时间=False-21:32:00", "范围停止类型=0",
            "倒计时停止时间=02:00:00", "倒计时停止类型=0"]


def fixed_scheme(play_name: str, digits: tuple[int, int, int], enabled: bool = True) -> str:
    lines = common_lines("定码轮换", play_name, enabled) + ["换号规则=9", "换号期数=18"] + tail_lines()
    lines += [f"定码轮换内容={' '.join(map(str, digits))}", "定码轮换单组=True", "SchemeCreator="]
    return "\r\n".join(lines) + "\r\n"


def random_scheme(play_name: str) -> str:
    lines = common_lines("随机出号", play_name, False) + ["换号规则=10", "换号期数=1"] + tail_lines()
    lines += ["随机出号模板=模板1", "随机出号个数=3", "SchemeCreator="]
    return "\r\n".join(lines) + "\r\n"


def write_gbk(path: Path, text: str) -> None:
    path.write_bytes(text.encode("gbk"))


def build_package(stats: dict) -> None:
    if PACKAGE_STAGE.exists():
        shutil.rmtree(PACKAGE_STAGE)
    PACKAGE_STAGE.mkdir(parents=True)
    latest = stats["本轮最新快照"]
    groups = [tuple(map(int, latest[key].split())) for key in ["短热百位", "中温十位", "长遗漏个位"]]
    for name, position, digits in [
        ("B001_短热145_百位-定码轮换.txt", "百位", groups[0]),
        ("B002_中温149_十位-定码轮换.txt", "十位", groups[1]),
        ("B003_长遗漏025_个位-定码轮换.txt", "个位", groups[2]),
    ]:
        write_gbk(PACKAGE_STAGE / name, fixed_scheme(position, digits, True))
    for name, position in [
        ("C001_随机三码_百位-随机出号.txt", "百位"),
        ("C002_随机三码_十位-随机出号.txt", "十位"),
        ("C003_随机三码_个位-随机出号.txt", "个位"),
    ]:
        write_gbk(PACKAGE_STAGE / name, random_scheme(position))
    offsets = stats["三种起点历史结果"]
    readme = f"""# {SCHEME_ID} 冷热三角·18期快照接力

## 这次没有照搬原稿

原稿要求短热、中温、长遗漏动态并集，再用组合枪自动接力。但仓库证据显示：组合方案轮投真实顺序尚未E3，冷热温和遗漏的内部动态语义也没有完整冻结。直接照写会得到一个看起来复杂、却无法证明软件按讲解运行的方案。

本版改成可核对的 **18期快照接力**：先按最近6/12/18期计算三组三码，冻结18期；三份定位胆方案通过顶部GUI“方案轮投”每期只运行一个；18期结束后必须重新生成快照。

## 本轮主组

- B001：短热百位 `1 4 5`，来自最近6期百位。
- B002：中温十位 `1 4 9`，来自最近12期十位频率第4至第6名。
- B003：长遗漏个位 `0 2 5`，来自最近18期个位当前遗漏。

导入后只勾选B001—B003，并手工勾选软件顶部“方案轮投”。顶部轮投不能由TXT控制。

## 随机对照

C001—C003是同位置、同三码数的随机对照。运行对照时，先取消B组，只勾选C组，并保持顶部方案轮投。主组和随机组禁止同时并投。

## 历史滚动复核

- 短热起点：{offsets[0]['命中']}/182 = {offsets[0]['命中率']:.2%}，p={offsets[0]['单侧二项检验p值']:.3f}
- 中温起点：{offsets[1]['命中']}/182 = {offsets[1]['命中率']:.2%}，p={offsets[1]['单侧二项检验p值']:.3f}
- 长遗漏起点：{offsets[2]['命中']}/182 = {offsets[2]['命中率']:.2%}，p={offsets[2]['单侧二项检验p值']:.3f}

三个起点都没有达到统计显著。仅改变起点，结果就从约28.0%变到35.2%，说明接力顺序本身足以制造“看起来有效”的差异。

## 资金与停止

- 1U=每个号码单注金额；每期只投一份方案，共3码，暴露3U。
- 主组18期毛暴露54U；随机组18期毛暴露54U。
- 建议本金108U；止盈不设置；止损不设置。
- 硬停止：每组18期跑完即停；不在轮内改码、改顺序或追加倍投。

## 必须记录

第一期实际运行方案、每期实际方案与命中、软件重启后是否续接原顺序。18期结束后停止，不继续使用过期快照。
"""
    (PACKAGE_STAGE / "00_使用说明.md").write_text(readme, encoding="utf-8")
    (PACKAGE_STAGE / "01_历史滚动验证.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PACKAGE_STAGE / "02_资金冻结.json").write_text(json.dumps(stats["资金冻结"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checklist = """# 导入与运行核对表

- [ ] 六个TXT均可导入且SchemeCreator为空
- [ ] B001显示定位胆百位，号码为1 4 5
- [ ] B002显示定位胆十位，号码为1 4 9
- [ ] B003显示定位胆个位，号码为0 2 5
- [ ] B组三份默认勾选，C组三份默认不勾选
- [ ] 顶部“方案轮投”已手工勾选
- [ ] 每期只运行一个方案，没有六份并投
- [ ] 已记录第一期实际起点和后续顺序
- [ ] 倍投始终为1
- [ ] 主组18期结束后停止，再单独运行随机对照18期
- [ ] 不在轮内修改号码、顺序或资金路径
"""
    (PACKAGE_STAGE / "03_导入运行核对表.md").write_text(checklist, encoding="utf-8")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with ZipFile(ZIP_PATH, "w", ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE_STAGE.iterdir()):
            zf.write(path, arcname=path.name)


def new_body_slide(prs: Presentation, title: str, kicker: str = ""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid(); fill.fore_color.rgb = RGBColor(*COLORS["bg"])
    if kicker:
        fixed.add_text(slide, Inches(0.78), Inches(0.38), Inches(4.0), Inches(0.30), kicker, 12, COLORS["gold"], True)
    fixed.add_text(slide, Inches(0.78), Inches(0.72), Inches(11.7), Inches(0.58), title, 28, COLORS["white"], True)
    line = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.78), Inches(1.42), Inches(11.74), Inches(0.025))
    line.fill.solid(); line.fill.fore_color.rgb = RGBColor(*COLORS["line"]); line.line.fill.background()
    return slide


def add_card(slide, x, y, w, h, title, body, accent="gold", title_size=16, body_size=13):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*COLORS["panel"])
    shape.line.color.rgb = RGBColor(*COLORS["line"]); shape.line.width = Pt(1)
    fixed.add_text(slide, x + Inches(0.24), y + Inches(0.16), w - Inches(0.48), Inches(0.34), title, title_size, COLORS[accent], True)
    fixed.add_text(slide, x + Inches(0.24), y + Inches(0.56), w - Inches(0.48), h - Inches(0.72), body, body_size, COLORS["white"], False, PP_ALIGN.LEFT, MSO_ANCHOR.TOP)
    return shape


def add_metric(slide, x, y, w, label, value, sub="", accent="gold"):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, Inches(1.12))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*COLORS["panel"])
    shape.line.color.rgb = RGBColor(*COLORS["line"])
    fixed.add_text(slide, x + Inches(0.18), y + Inches(0.12), w - Inches(0.36), Inches(0.22), label, 11, COLORS["gray"])
    fixed.add_text(slide, x + Inches(0.18), y + Inches(0.36), w - Inches(0.36), Inches(0.42), value, 25, COLORS[accent], True)
    if sub:
        fixed.add_text(slide, x + Inches(0.18), y + Inches(0.80), w - Inches(0.36), Inches(0.20), sub, 10, COLORS["gray"])


def hide_slide(slide) -> None:
    slide._element.set("show", "0")


def build_ppt(stats: dict) -> None:
    cover_png = ROOT / "assets" / "ppt" / "fixed_pages" / "首页背景图谱.png"
    end_png = ROOT / "assets" / "ppt" / "fixed_pages" / "固定最后一页_画面.png"
    for path in [cover_png, end_png]:
        if not path.exists():
            raise FileNotFoundError(f"固定页资源未物化: {path}")
    offsets, latest = stats["三种起点历史结果"], stats["本轮最新快照"]
    prs = fixed.new_prs()
    cover = fixed.add_cover(prs, cover_png)
    fixed.add_text(cover, Inches(0.82), Inches(1.05), Inches(8.8), Inches(0.62), "冷热三角快照接力", 32, COLORS["white"], True)
    fixed.add_text(cover, Inches(0.84), Inches(1.82), Inches(8.2), Inches(0.34), "6期短热 · 12期中温 · 18期长遗漏", 16, COLORS["gold"], True)
    fixed.add_text(cover, Inches(0.84), Inches(5.88), Inches(8.2), Inches(0.34), "每18期重算｜三种起点敏感性复核", 14, COLORS["white"])
    fixed.set_notes(cover, "这次不照搬动态三枪，而是把软件能够核对的部分保留下来，做成18期快照接力。")
    fixed.build_second_slide(prs)

    slide = new_body_slide(prs, "原方案最危险的地方", "先做减法")
    add_card(slide, Inches(0.78), Inches(1.78), Inches(5.55), Inches(3.62), "看起来很完整", "短热、中温、长遗漏两两并集，再用三把组合枪按百、十、个轮投。故事成立，但不等于软件会按故事运行。", "gold", 18, 17)
    add_card(slide, Inches(6.58), Inches(1.78), Inches(5.55), Inches(3.62), "证据没有跟上", "组合轮投真实顺序仍待E3；冷热温和遗漏的动态语义也未完全冻结。照抄只会制造伪复杂。", "red", 18, 17)
    fixed.add_text(slide, Inches(1.0), Inches(5.74), Inches(10.9), Inches(0.50), "所以本版只保留：三个时间窗口、三个号码角色、三个位置接力。", 19, COLORS["white"], True, PP_ALIGN.CENTER)
    fixed.set_notes(slide, "核心不是反对原创意，而是拒绝把未验证的软件行为包装成已经实现。")

    slide = new_body_slide(prs, "三条边，先冻结成一张快照", "核心技术")
    add_card(slide, Inches(0.72), Inches(1.78), Inches(3.82), Inches(3.82), "短热｜百位", f"看最近6期百位。\n按出现次数排序，次数相同看谁更近。\n本轮取：{latest['短热百位']}", "gold", 18, 17)
    add_card(slide, Inches(4.76), Inches(1.78), Inches(3.82), Inches(3.82), "中温｜十位", f"看最近12期十位。\n排除最热前三，再取第4至第6名。\n本轮取：{latest['中温十位']}", "blue", 18, 17)
    add_card(slide, Inches(8.80), Inches(1.78), Inches(3.82), Inches(3.82), "长遗漏｜个位", f"看最近18期个位。\n按当前遗漏从高到低取3码。\n本轮取：{latest['长遗漏个位']}", "green", 18, 17)
    fixed.add_text(slide, Inches(0.92), Inches(5.92), Inches(11.1), Inches(0.44), "号码冻结18期，不是每期偷偷改参数。", 19, COLORS["white"], True, PP_ALIGN.CENTER)
    fixed.set_notes(slide, "这三组号码都能从截止到202607310380的数据复算，18期内保持不变。")

    slide = new_body_slide(prs, "接力怎么跑", "执行规则")
    labels = [("B001", "百位 1 4 5", "短热"), ("B002", "十位 1 4 9", "中温"), ("B003", "个位 0 2 5", "长遗漏")]
    for i, (code, body, role) in enumerate(labels):
        x = Inches(0.88 + i * 4.05)
        add_card(slide, x, Inches(2.05), Inches(3.55), Inches(2.02), f"{code}｜{role}", body, ["gold", "blue", "green"][i], 17, 22)
        if i < 2:
            fixed.add_text(slide, x + Inches(3.58), Inches(2.77), Inches(0.44), Inches(0.42), "→", 24, COLORS["gray"], True, PP_ALIGN.CENTER)
    fixed.add_text(slide, Inches(0.95), Inches(4.62), Inches(11.0), Inches(0.56), "导入后手工勾选顶部“方案轮投”｜每期只运行一个方案｜18期后停止重算", 18, COLORS["white"], True, PP_ALIGN.CENTER)
    fixed.add_text(slide, Inches(1.30), Inches(5.54), Inches(10.3), Inches(0.54), "起点由软件实际显示决定，第一期必须记录。", 18, COLORS["red"], True, PP_ALIGN.CENTER)
    fixed.set_notes(slide, "TXT只能让三份主方案默认勾选，顶部轮投仍需手工开启。起点和重启续位必须记录。")

    slide = new_body_slide(prs, "一轮完整例子", "从输入到停止")
    add_card(slide, Inches(0.78), Inches(1.70), Inches(3.45), Inches(4.42), "轮前", "读取最近18期。\n算出百位短热145、十位中温149、个位长遗漏025。\n把三组号码写进TXT。", "gold", 17, 16)
    add_card(slide, Inches(4.45), Inches(1.70), Inches(3.45), Inches(4.42), "轮中", "第1期先看软件实际跑哪一份。\n此后每期记录方案、位置、号码、开奖号和命中。\n不改码，不改顺序。", "blue", 17, 16)
    add_card(slide, Inches(8.12), Inches(1.70), Inches(3.45), Inches(4.42), "轮后", "第18期结束立即停止。\n重新用最新数据计算下一张快照。\n旧号码不得无限续跑。", "green", 17, 16)
    fixed.set_notes(slide, "这是一个轮次化实验，不是永久挂机。十八期是冻结边界，也是停止边界。")

    slide = new_body_slide(prs, "同一套规则，只换起点", "历史滚动复核")
    add_metric(slide, Inches(0.82), Inches(1.88), Inches(3.55), "短热先跑", f"{offsets[0]['命中率']:.2%}", f"{offsets[0]['命中']}/182｜p={offsets[0]['单侧二项检验p值']:.3f}", "gold")
    add_metric(slide, Inches(4.89), Inches(1.88), Inches(3.55), "中温先跑", f"{offsets[1]['命中率']:.2%}", f"{offsets[1]['命中']}/182｜p={offsets[1]['单侧二项检验p值']:.3f}", "blue")
    add_metric(slide, Inches(8.96), Inches(1.88), Inches(3.55), "长遗漏先跑", f"{offsets[2]['命中率']:.2%}", f"{offsets[2]['命中']}/182｜p={offsets[2]['单侧二项检验p值']:.3f}", "green")
    add_card(slide, Inches(0.82), Inches(3.50), Inches(11.70), Inches(2.05), "最重要的结果", "只改变第一棒，命中率就从约28.0%变到35.2%。这不是稳定优势，反而证明顺序偶然性会明显改变观感。三个起点都没有达到统计显著。", "red", 18, 20)
    fixed.set_notes(slide, "这里不要挑35.2%单独宣传。三种起点都必须一起展示，结果才完整。")

    slide = new_body_slide(prs, "哪条边贡献更多", "拆分观察")
    for i, role in enumerate(ROLE_NAMES):
        item = offsets[0]["三角色"][role]
        add_metric(slide, Inches(0.82 + i * 4.07), Inches(1.90), Inches(3.55), f"{role}｜{item['位置']}", f"{item['命中率']:.2%}", f"{item['命中']}/{item['总数']}｜短热起点口径", ["gold", "blue", "green"][i])
    add_card(slide, Inches(0.82), Inches(3.54), Inches(11.70), Inches(2.10), "不能做的解释", "长遗漏在某个起点下较高，不代表遗漏理论成立；换一个起点，它可能大幅下降。角色贡献必须和接力顺序一起看，不能拆开选冠军。", "red", 18, 19)
    fixed.set_notes(slide, "角色数据只是诊断，不是选出一个冠军后删除另外两条边。")

    slide = new_body_slide(prs, "随机对照必须同成本", "对照设计")
    add_card(slide, Inches(0.78), Inches(1.78), Inches(5.55), Inches(3.60), "主组 B001—B003", "每期一个位置、3个号码。\n18期共54U毛暴露。\n号码在轮前冻结。", "gold", 18, 18)
    add_card(slide, Inches(6.58), Inches(1.78), Inches(5.55), Inches(3.60), "对照 C001—C003", "同样每期一个位置、3个号码。\n18期同样54U毛暴露。\n号码由软件随机生成。", "blue", 18, 18)
    fixed.add_text(slide, Inches(1.0), Inches(5.70), Inches(10.9), Inches(0.50), "两组必须分开运行；一起投会把成本翻倍，实验失效。", 20, COLORS["red"], True, PP_ALIGN.CENTER)
    fixed.set_notes(slide, "对照不是装饰。主组和随机组必须分别跑完，才有资格比较。")

    slide = new_body_slide(prs, "资金只负责让实验跑完", "资金与停止")
    add_metric(slide, Inches(0.82), Inches(1.90), Inches(3.55), "建议本金", "108U", "主组54U + 对照54U", "gold")
    add_metric(slide, Inches(4.89), Inches(1.90), Inches(3.55), "止盈", "不设置", "不因短期盈利提前挑结果", "blue")
    add_metric(slide, Inches(8.96), Inches(1.90), Inches(3.55), "止损", "不设置", "固定期数已限制毛暴露", "green")
    add_card(slide, Inches(0.82), Inches(3.54), Inches(11.70), Inches(2.05), "硬停止条件", "主组18期结束即停；随机对照18期结束即停。全程平倍，每码1U，不马丁、不追损、不在同一轮里重启。", "red", 18, 20)
    fixed.set_notes(slide, "这里的108U按毛暴露计算，不是收益目标。真正的停止条件是固定期数。")

    slide = new_body_slide(prs, "结论：结构有趣，优势未证实", "最终判断")
    add_card(slide, Inches(0.92), Inches(1.78), Inches(11.45), Inches(3.60), "保留它的理由", "三种时间窗口、三个号码角色和三个位置接力，适合做清晰的可证伪实验；每轮18期，规则能复算，成本能对齐。", "green", 19, 21)
    fixed.add_text(slide, Inches(1.0), Inches(5.60), Inches(10.9), Inches(0.58), "但历史结果对起点高度敏感，当前只能进入前向验证，不能宣称冷热三角存在稳定优势。", 20, COLORS["white"], True, PP_ALIGN.CENTER)
    fixed.set_notes(slide, "视频收尾要明确：结构值得测，但没有证据支持长期优势。")

    appendix = new_body_slide(prs, "隐藏附录｜规则与历史证据", "技术证据")
    hide_slide(appendix)
    evidence = (f"方案ID：{SCHEME_ID}\n批次ID：{BATCH_ID}\n数据：{stats['数据']['范围']}，200期，滚动验证182期\n"
                f"短热起点：{offsets[0]['命中']}/182={offsets[0]['命中率']:.6f}，p={offsets[0]['单侧二项检验p值']:.6f}\n"
                f"中温起点：{offsets[1]['命中']}/182={offsets[1]['命中率']:.6f}，p={offsets[1]['单侧二项检验p值']:.6f}\n"
                f"长遗漏起点：{offsets[2]['命中']}/182={offsets[2]['命中率']:.6f}，p={offsets[2]['单侧二项检验p值']:.6f}\n"
                "证据边界：复用历史E4；无独立E5。顶部GUI轮投行为E3，但起始顺序与重启续位未冻结。")
    add_card(appendix, Inches(0.82), Inches(1.72), Inches(11.70), Inches(4.98), "可复算记录", evidence, "blue", 18, 15)
    fixed.set_notes(appendix, "隐藏页保存完整统计和证据等级，正常播放不展示。")

    appendix2 = new_body_slide(prs, "隐藏附录｜资金与执行边界", "资金冻结")
    hide_slide(appendix2)
    money = ("1U=每个号码单注金额；每期3码=3U。\n主组18期毛暴露54U；随机对照18期毛暴露54U；建议本金108U。\n"
             "止盈止损模式：NONE；止盈不设置；止损不设置。\n替代停止条件：每组18期跑完即停，不改码、不加倍、不当天重启。\n"
             "TXT：GBK+CRLF；SchemeCreator为空；主组默认勾选、对照默认不勾选。\n软件边界：顶部方案轮投需人工勾选；实际首棒、排序和重启续位必须记录。")
    add_card(appendix2, Inches(0.82), Inches(1.72), Inches(11.70), Inches(4.98), "冻结口径", money, "gold", 18, 16)
    fixed.set_notes(appendix2, "隐藏页保存本金、止盈止损模式、金额和软件执行边界。")

    fixed.add_end(prs, end_png)
    PPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(PPT_PATH)


def validate_outputs(stats: dict) -> None:
    if not ZIP_PATH.exists() or not PPT_PATH.exists():
        raise AssertionError("交付物缺失")
    txt_files = sorted(PACKAGE_STAGE.glob("*.txt"))
    if len(txt_files) != 6:
        raise AssertionError(f"TXT数量错误: {len(txt_files)}")
    for path in txt_files:
        raw = path.read_bytes()
        if b"\r\n" not in raw or b"SchemeCreator=\r\n" not in raw:
            raise AssertionError(f"TXT编码或换行异常: {path.name}")
        text = raw.decode("gbk")
        if "倍投计划=1,1,1,1,1,1,1,1,1,1" not in text or text.count("SchemeCreator=") != 1:
            raise AssertionError(f"TXT资金或加密字段异常: {path.name}")
    expected = ["B001_短热145_百位-定码轮换.txt", "B002_中温149_十位-定码轮换.txt",
                "B003_长遗漏025_个位-定码轮换.txt", "C001_随机三码_百位-随机出号.txt",
                "C002_随机三码_十位-随机出号.txt", "C003_随机三码_个位-随机出号.txt"]
    if not all((PACKAGE_STAGE / name).exists() for name in expected):
        raise AssertionError("核心TXT文件名缺失")
    prs = Presentation(PPT_PATH)
    hidden = [slide for slide in prs.slides if slide._element.get("show") == "0"]
    if len(prs.slides) != 13 or len(hidden) != 2:
        raise AssertionError(f"PPT结构错误: slides={len(prs.slides)} hidden={len(hidden)}")
    for index, slide in enumerate(prs.slides, 1):
        if not slide.notes_slide.notes_text_frame.text.strip():
            raise AssertionError(f"第{index}页缺少备注")
    if stats["资金冻结"]["建议本金"] != "108U":
        raise AssertionError("本金冻结漂移")
    manifest = {
        "scheme_id": SCHEME_ID, "batch_id": BATCH_ID,
        "built_files": {ZIP_PATH.name: sha256(ZIP_PATH), PPT_PATH.name: sha256(PPT_PATH)},
        "package_txt_count": len(txt_files), "ppt_slide_count": len(prs.slides),
        "ppt_hidden_slide_count": len(hidden), "capital": "108U", "stop_mode": "NONE",
        "status": "BUILD_VALIDATED_AWAITING_E2_E3_FORWARD",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    rows = parse_draws(INPUT_DATA)
    stats = simulate(rows)
    build_package(stats)
    build_ppt(stats)
    validate_outputs(stats)
    print("DELIVERY_OK", f"scheme={SCHEME_ID}", f"zip={ZIP_PATH.name}", f"ppt={PPT_PATH.name}", "capital=108U", "stop_mode=NONE")


if __name__ == "__main__":
    main()
