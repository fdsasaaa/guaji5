#!/usr/bin/env python3
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "系统清单.json"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def validate_jsonl(path: Path, id_field: str):
    ids = set()
    count = 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if id_field not in obj:
            raise SystemExit(f"{path.name}第{lineno}行缺少{id_field}")
        if obj[id_field] in ids:
            raise SystemExit(f"{path.name}重复ID: {obj[id_field]}")
        ids.add(obj[id_field])
        count += 1
    return count

def build_text(manifest):
    pieces = [
        f"# AI挂机方案生成统一总典_{manifest['版本']}_{manifest['版本名称']}",
        "",
        f"版本：{manifest['版本']}  ",
        f"生成日期：{manifest['生成日期']}  ",
        "生成方式：由系统工作包正式源自动合并  ",
        "",
        "> **本文件是自动生成的便捷接管版，禁止单独编辑。**  ",
        "> 完整任务优先使用系统工作包ZIP；只拿到本文件时可以接管，但无法保证已回写模块和状态。  ",
        "> 软件主方案TXT仍使用GBK+CRLF；高级倍投配置使用UTF-8 BOM+CRLF。  ",
        "",
        "---",
        "",
        "## 自动合并索引",
        ""
    ]
    for i, name in enumerate(manifest["模块"], 1):
        pieces.append(f"{i}. `{name}`")
    base = len(manifest["模块"])
    for i, item in enumerate(manifest["总典附录"], 1):
        pieces.append(f"{base+i}. `{item['file']}`（{item['format']}附录）")
    pieces += ["", "---", ""]
    for name in manifest["模块"]:
        content = (ROOT / name).read_text(encoding="utf-8").strip()
        pieces += [
            f"<!-- MODULE_START:{name} -->",
            "",
            content,
            "",
            f"<!-- MODULE_END:{name} -->",
            "",
            "---",
            ""
        ]
    for item in manifest["总典附录"]:
        path = ROOT / item["file"]
        content = path.read_text(encoding="utf-8").strip()
        fence = "jsonl" if item["format"] == "jsonl" else "json"
        pieces += [
            f"# 附录：{item['file']}",
            "",
            f"> 以下内容与工作包内独立的`{item['file']}`一致。",
            "",
            f"```{fence}",
            content,
            "```",
            ""
        ]
    pieces += ["<!-- GENERATED_TOTAL_END -->", ""]
    return "\n".join(pieces)

def hash_sources(manifest, total_path):
    paths = [ROOT / x for x in manifest["模块"]]
    paths += [ROOT / x["file"] for x in manifest["总典附录"]]
    paths += [
        ROOT / "系统清单.json",
        ROOT / "05_工具/build_total.py",
        ROOT / "05_工具/validate_package.py",
        ROOT / "05_工具/validate_governance.py",
        ROOT / "05_工具/audit_scheme_semantics.py",
        total_path,
    ]
    delivery = ROOT / "02_本次输出"
    paths += sorted(p for p in delivery.rglob("*") if p.is_file())
    archive = ROOT / "03_批次归档"
    paths += sorted(archive.glob("*.json"))
    unique = []
    seen = set()
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            unique.append(path)
            seen.add(key)
    lines = [f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}" for p in unique]
    (ROOT / "系统哈希清单.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = load_json(MANIFEST)

    counts = {
        "history": validate_jsonl(ROOT/"历史方案索引.jsonl", "方案ID"),
        "angles": validate_jsonl(ROOT/"分析角度索引.jsonl", "角度ID"),
        "learning": validate_jsonl(ROOT/"学习事件索引.jsonl", "事件ID"),
        "rules": validate_jsonl(ROOT/"规则候选池.jsonl", "候选规则ID"),
        "atoms": validate_jsonl(ROOT/"技术原子表现档案.jsonl", "技术原子ID"),
        "software": validate_jsonl(ROOT/"软件行为证据索引.jsonl", "证据ID"),
        "batches": validate_jsonl(ROOT/"批次索引.jsonl", "批次ID"),
        "cases": validate_jsonl(ROOT/"方案组合案例索引.jsonl", "案例ID"),
        "negative_patterns": validate_jsonl(ROOT/"负面方案模式索引.jsonl", "负面模式ID"),
        "coverage": validate_jsonl(ROOT/"功能覆盖索引.jsonl", "功能ID"),
        "director_tests": validate_jsonl(ROOT/"总控验收测试集.jsonl", "测试ID"),
        "function_cards": validate_jsonl(ROOT/"功能能力卡片.jsonl", "功能ID"),
        "money_paths": validate_jsonl(ROOT/"资金路径模板库.jsonl", "资金路径ID"),
    }

    total_path = ROOT / manifest["自动合并总典"]
    expected = build_text(manifest)
    if args.check:
        if not total_path.exists():
            raise SystemExit("完整总典不存在")
        if total_path.read_text(encoding="utf-8") != expected:
            raise SystemExit("源文件与完整总典不同步")
        print(
            "CHECK_OK "
            + " ".join(f"{k}={v}" for k, v in counts.items())
            + f" total_sha256={sha256(total_path)}"
        )
        return

    total_path.write_text(expected, encoding="utf-8", newline="\n")
    hash_sources(manifest, total_path)
    print(
        "BUILD_OK "
        + " ".join(f"{k}={v}" for k, v in counts.items())
        + f" total={total_path.name} total_sha256={sha256(total_path)}"
    )

if __name__ == "__main__":
    main()
