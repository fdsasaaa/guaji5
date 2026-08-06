#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

SUPPORTED_CATEGORIES = {
    "遗漏出号", "高级开某投某", "随机出号", "高级定码轮换", "定码轮换",
    "冷热温出号", "固定取码", "足迹出号", "重号侦测", "组合方案出号", "组合方案轮投",
}
ADVANCED_CONFIG = Path("GJBTScheme/高级倍投主配置.txt")
ADVANCED_KEYS = ["软件名称", "ID", "倍数", "中后ID", "挂后ID", "中后监控", "中后跳转", "挂后监控", "挂后跳转"]


def _crlf_only(data: bytes) -> bool:
    return b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")


def _decode_main(path: Path) -> str:
    data = path.read_bytes()
    if not _crlf_only(data):
        raise ValueError(f"{path.name}: 主方案必须使用CRLF")
    try:
        return data.decode("gbk")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name}: 主方案必须使用GBK") from exc


def _fields(lines: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"{label}: 非字段文本混入方案：{line!r}")
        key, value = line.split("=", 1)
        if not key or key in result:
            raise ValueError(f"{label}: 空字段名或重复字段：{key!r}")
        result[key] = value
    return result


def _positive_plan(value: str, label: str) -> list[int]:
    try:
        plan = [int(x) for x in value.split(",")]
    except Exception as exc:
        raise ValueError(f"{label}: 倍投计划不是整数序列") from exc
    if not plan or any(x <= 0 for x in plan):
        raise ValueError(f"{label}: 倍投计划必须全部为正整数")
    return plan


def _validate_advanced(folder: Path, display_name: str) -> None:
    path = folder / ADVANCED_CONFIG
    if not path.is_file():
        raise ValueError(f"{display_name}: 缺少 {ADVANCED_CONFIG.as_posix()}")
    data = path.read_bytes()
    if not data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name}: 必须使用UTF-8 BOM")
    if not _crlf_only(data):
        raise ValueError(f"{path.name}: 必须使用CRLF")
    rows = [x for x in data.decode("utf-8-sig").split("\r\n") if x]
    if len(rows) != 8:
        raise ValueError(f"{path.name}: 当前主配置必须正好8局，实际{len(rows)}局")
    for expected_id, row in enumerate(rows, 1):
        parts = row.split(";")
        if len(parts) != 9:
            raise ValueError(f"{path.name}: 第{expected_id}局不是固定9字段")
        keys = [part.split("=", 1)[0] if "=" in part else "" for part in parts]
        if keys != ADVANCED_KEYS:
            raise ValueError(f"{path.name}: 第{expected_id}局字段顺序错误")
        values = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in parts}
        if values["ID"] != str(expected_id):
            raise ValueError(f"{path.name}: 局ID必须连续1-8")
        if int(values["倍数"]) <= 0:
            raise ValueError(f"{path.name}: 倍数必须大于0")
        for key in ("中后ID", "挂后ID"):
            if not 1 <= int(values[key]) <= 8:
                raise ValueError(f"{path.name}: {key}超出1-8")
        for key in ("中后监控", "挂后监控"):
            if values[key] != "False":
                raise ValueError(f"{path.name}: 当前导入保护禁止开启{key}")
        for key in ("中后跳转", "挂后跳转"):
            if values[key] != f"False-{display_name}":
                raise ValueError(f"{path.name}: {key}引用名与主方案显示名不一致")


def validate_main_scheme(path: Path, folder: Path) -> None:
    lines = _decode_main(path).split("\r\n")
    while lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 3:
        raise ValueError(f"{path.name}: 不是完整方案TXT")
    enabled, category = lines[0], lines[1]
    if enabled not in {"True", "False"}:
        raise ValueError(f"{path.name}: 第1行只能是True或False")
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"{path.name}: 第2行不是已识别一级分类：{category!r}")
    if not path.name.endswith(f"-{category}.txt"):
        raise ValueError(f"{path.name}: 文件名后缀与第2行一级分类不一致")
    fields = _fields(lines[2:], path.name)
    if fields.get("SchemeCreator") is None or fields["SchemeCreator"] != "":
        raise ValueError(f"{path.name}: SchemeCreator必须存在且默认留空")

    if category == "定码轮换":
        if not fields.get("定码轮换内容"):
            raise ValueError(f"{path.name}: 定码轮换必须使用定码轮换内容=")
        if "投注内容" in fields:
            raise ValueError(f"{path.name}: 禁止使用不存在的通用投注内容=字段")
        if fields.get("定码轮换单组") not in {"True", "False"}:
            raise ValueError(f"{path.name}: 定码轮换单组必须明确True/False")
        if fields.get("玩法类型") == "定位胆" and fields.get("任选位置", "") != "":
            raise ValueError(f"{path.name}: 固定位置定位胆的任选位置必须为空")

    plan_type = fields.get("倍投类型")
    plan = _positive_plan(fields.get("倍投计划", ""), path.name)
    if plan_type == "1":
        if plan != [1] * 8:
            raise ValueError(f"{path.name}: 高级倍投主方案必须写8个占位1")
        if fields.get("倍投方案") != "高级倍投主配置":
            raise ValueError(f"{path.name}: 高级倍投方案名必须为高级倍投主配置")
        display_name = path.name[: -(len(category) + 5)]
        _validate_advanced(folder, display_name)
    elif plan_type == "0":
        if not fields.get("倍投方案"):
            raise ValueError(f"{path.name}: 普通倍投方案不能为空")
    else:
        raise ValueError(f"{path.name}: 倍投类型必须为0或1")


def validate_folder(folder: Path) -> None:
    if not folder.is_dir():
        raise ValueError(f"不是文件夹：{folder}")
    txts = sorted(folder.rglob("*.txt"))
    mains = [p for p in txts if not (p.name == "高级倍投主配置.txt" and p.parent.name == "GJBTScheme")]
    if not mains:
        raise ValueError("导入文件夹内没有主方案TXT")
    for path in mains:
        validate_main_scheme(path, folder)


def validate_path(path: Path) -> None:
    if path.is_dir():
        validate_folder(path)
        return
    if path.suffix.lower() != ".zip":
        raise ValueError("仅支持文件夹或ZIP")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(tmp)
        validate_folder(Path(tmp))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an exact software import folder or ZIP")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        validate_path(args.path)
    except Exception as exc:
        print(f"IMPORT_PACKAGE_INVALID: {exc}")
        raise SystemExit(1)
    print("IMPORT_PACKAGE_VALID")


if __name__ == "__main__":
    main()
