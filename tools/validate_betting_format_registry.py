#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the self-contained betting format knowledge base.

Checks current authority, precedence, current formal coverage, and the legacy
knowledge supplement. It intentionally does not promote legacy knowledge to
current runtime evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "controller" / "betting_format_registry.json"
LEGACY = ROOT / "controller" / "legacy_play_grammar_catalog.json"
RULES = ROOT / "01_软件格式与已验证执行规则.md"
OVERLAY = ROOT / "00B_完整玩法格式字典与版本优先级.md"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def extract_formal_rows(text: str):
    rows = []
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## 1.4"):
            in_section = True
            continue
        if in_section and line.startswith("## 1.5"):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        combo = cells[1]
        parts = combo.split()
        if not parts or not parts[0].startswith("CAT"):
            continue
        code = parts[0]
        rest = parts[1:]
        if code in {"CAT03+龙虎", "CAT06+龙虎"}:
            if len(rest) < 1:
                fail(f"cannot parse formal combo: {combo}")
            rows.append((code, "龙虎", rest[-1]))
        elif len(rest) >= 2:
            rows.append((code, rest[-2], rest[-1]))
        else:
            fail(f"cannot parse formal combo: {combo}")
    return rows


def main() -> int:
    for p in (REGISTRY, LEGACY, RULES, OVERLAY):
        if not p.exists():
            fail(f"missing required file: {p.relative_to(ROOT)}")

    data = load_json(REGISTRY)
    legacy = load_json(LEGACY)

    if data.get("unknown_format_policy") != "REGISTRY_DEFECT_AND_BLOCK_GENERATION":
        fail("unknown format policy must be REGISTRY_DEFECT_AND_BLOCK_GENERATION")
    if data.get("external_v32_dependency") is not False:
        fail("external V3.2 dependency must be false")

    merge = data.get("merge_policy", {})
    priorities = merge.get("priority_high_to_low", [])
    expected_prefix = [
        "CURRENT_GITHUB_MAIN_VERIFIED",
        "NEWER_USER_CONFIRMED_OR_GITHUB_VERIFIED",
        "V3_4_RECOVERED",
        "LEGACY_REAL_TXT_SAMPLE",
    ]
    if priorities != expected_prefix:
        fail(f"unexpected source precedence: {priorities}")
    if merge.get("mode") != "FILL_GAPS_ONLY":
        fail("merge mode must be FILL_GAPS_ONLY")

    required_categories = data.get("required_known_primary_categories", [])
    categories = data.get("primary_categories", {})
    missing_categories = [c for c in required_categories if c not in categories]
    if missing_categories:
        fail(f"missing known primary categories: {missing_categories}")
    for name, rec in categories.items():
        state = str(rec.get("generation_state", "")).upper()
        if not state:
            fail(f"category {name} has no generation_state")
        if "UNKNOWN" in state:
            fail(f"known category {name} still ends in UNKNOWN state")

    coldhot = categories.get("冷热温出号", {})
    required_coldhot = {"冷热温统计期数", "冷热温出号类型", "冷热温容错个数"}
    if not required_coldhot.issubset(set(coldhot.get("dedicated_fields", []))):
        fail("cold/hot/warm dedicated fields are incomplete")

    advanced = data.get("betting_registry", {}).get("高级倍投", {})
    expected_advanced_fields = ["软件名称", "ID", "倍数", "中后ID", "挂后ID", "中后监控", "中后跳转", "挂后监控", "挂后跳转"]
    if advanced.get("fields_in_order") != expected_advanced_fields:
        fail("advanced betting 9-field order changed")

    settings = data.get("settings_registry", {})
    for key in ["投注监控", "换号规则", "正反集", "真实模拟切换", "盈亏停止", "盈亏跳转", "时间控制", "顶部方案轮投"]:
        if key not in settings:
            fail(f"missing settings registry: {key}")

    registered = data.get("formal_allowed_combinations", [])
    lookup = {(r.get("category_code"), r.get("play_type"), r.get("play_name")) for r in registered}
    formal_rows = extract_formal_rows(RULES.read_text(encoding="utf-8"))
    if len(formal_rows) < 20:
        fail(f"expected at least 20 formal rows from 01, got {len(formal_rows)}")
    missing_rows = [row for row in formal_rows if row not in lookup]
    if missing_rows:
        fail(f"01 formal combinations missing from registry: {missing_rows}")

    newer_single = ("CAT05", "前二", "直选单式")
    if newer_single not in lookup:
        fail("newer user-confirmed 前二直选单式 format is not migrated")

    grammars = data.get("play_content_grammars", {})
    if grammars.get("前二_直选单式", {}).get("forbidden_rewrite") is None:
        fail("semantic guard for exact two-digit numbers is missing")

    evidence = data.get("legacy_evidence", [])
    if not any("V3.4.0" in str(item.get("source", "")) for item in evidence):
        fail("V3.4 recovery source is not recorded")
    if not any("方案2-冷热温出号" in str(item.get("source", "")) for item in evidence):
        fail("legacy real cold/hot/warm TXT evidence is not recorded")

    # Historical knowledge completeness: these are design-known categories, not formal promotions.
    if legacy.get("status") != "KNOWLEDGE_SUPPLEMENT_ONLY":
        fail("legacy catalog must remain knowledge-only")
    hist = legacy.get("historical_level1_catalog", {})
    required_historical = [
        "遗漏出号", "开某投某", "固定取码", "定码轮换", "高级定码轮换",
        "冷热温出号", "随机出号", "自定义开某投某", "高级开某投某",
        "龙虎高级开某投某", "随机"
    ]
    missing_hist = [x for x in required_historical if x not in hist]
    if missing_hist:
        fail(f"historical level1 knowledge missing: {missing_hist}")
    for name in required_historical:
        if not hist[name].get("current_disposition"):
            fail(f"historical category has no current disposition: {name}")

    omission_fields = set(hist["遗漏出号"].get("known_fields", []))
    required_omission = {
        "遗漏出号期数", "遗漏出号类型", "遗漏检查数据传输期数",
        "遗漏期数缓存期数", "遗漏出号个数", "遗漏出号容错个数"
    }
    if not required_omission.issubset(omission_fields):
        fail("omission six-field legacy shape is incomplete")

    catalog = legacy.get("bet_content_grammar_catalog", {})
    for family in ["三位数", "二位数", "四位数", "五位数", "定位胆", "龙虎", "趣味", "不定位"]:
        if family not in catalog:
            fail(f"legacy betting grammar family missing: {family}")
    if catalog["二位数"].get("直选单式", {}).get("format") is None:
        fail("two-digit exact single grammar missing")
    if catalog["五位数"].get("直选复式", {}).get("format") is None:
        fail("five-position direct-multi grammar missing")

    conflict_rows = legacy.get("historical_conflicts_resolved_by_current_main", [])
    if len(conflict_rows) < 4 or any(x.get("winner") != "CURRENT_GITHUB_MAIN" for x in conflict_rows):
        fail("legacy/current conflict precedence is incomplete")

    overlay_text = OVERLAY.read_text(encoding="utf-8")
    if "低优先级来源只能填空" not in overlay_text or "REGISTRY_DEFECT" not in overlay_text:
        fail("00B precedence/defect rule missing")

    print("[PASS] betting format knowledge base is self-contained and precedence-safe")
    print(f"[INFO] current_primary_categories={len(categories)}")
    print(f"[INFO] historical_level1_known={len(hist)}")
    print(f"[INFO] legacy_play_grammar_families={len(catalog)}")
    print(f"[INFO] current_01_formal_rows={len(formal_rows)}")
    print(f"[INFO] registered_combinations={len(registered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
