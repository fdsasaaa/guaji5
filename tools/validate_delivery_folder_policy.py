#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import sys

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


policy_path = ROOT / "00B_统一交付文件夹规则.md"
agents_path = ROOT / "AGENTS.md"
workflow_path = ROOT / ".github" / "workflows" / "validate.yml"
packager_path = ROOT / "tools" / "package_delivery_folder.py"

for path in (policy_path, agents_path, workflow_path, packager_path):
    require(path.exists(), f"缺少文件: {path.relative_to(ROOT)}")

if policy_path.exists():
    policy = policy_path.read_text(encoding="utf-8")
    for phrase in (
        "一个统一交付文件夹ZIP",
        "内含且仅含",
        "方案套ZIP",
        "人工讲解型PPTX",
        "其他内容不受影响",
    ):
        require(phrase in policy, f"00B缺少关键语义: {phrase}")

if agents_path.exists():
    agents = agents_path.read_text(encoding="utf-8")
    require("00B_统一交付文件夹规则.md" in agents, "AGENTS未登记00B")
    require("一个统一交付文件夹ZIP" in agents, "AGENTS未启用统一交付文件夹")

if workflow_path.exists():
    workflow = workflow_path.read_text(encoding="utf-8")
    require("python tools/package_delivery_folder.py" in workflow, "工作流未执行交付文件夹打包")
    require("python tools/validate_delivery_folder_policy.py" in workflow, "工作流未执行交付文件夹校验")
    require("dist/**/*_交付文件夹.zip" in workflow, "工作流未只上传统一交付文件夹ZIP")
    require("dist/B394_SET_001_delivery/**" not in workflow, "工作流仍上传整个构建目录")

outer_zips = sorted((ROOT / "dist").glob("*_delivery/*_交付文件夹.zip"))
for outer_zip in outer_zips:
    with ZipFile(outer_zip) as zf:
        files = [name for name in zf.namelist() if not name.endswith("/")]
    require(len(files) == 2, f"{outer_zip.name}内部文件数不是2: {files}")
    if len(files) == 2:
        folders = {name.split("/", 1)[0] for name in files if "/" in name}
        require(len(folders) == 1, f"{outer_zip.name}不是单一顶层文件夹")
        require(sum(name.lower().endswith(".pptx") for name in files) == 1, f"{outer_zip.name}缺少唯一PPTX")
        require(sum(name.endswith("_方案套.zip") for name in files) == 1, f"{outer_zip.name}缺少唯一方案套ZIP")

if errors:
    print("DELIVERY_FOLDER_POLICY_FAILED")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("DELIVERY_FOLDER_POLICY_OK", f"artifacts={len(outer_zips)}")
