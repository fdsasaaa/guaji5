#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def package_delivery_dir(delivery_dir: Path) -> Path:
    pptx_files = sorted(p for p in delivery_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pptx")
    scheme_zips = sorted(
        p for p in delivery_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".zip"
        and not p.name.endswith("_交付文件夹.zip")
    )
    if len(pptx_files) != 1 or len(scheme_zips) != 1:
        raise RuntimeError(
            f"{delivery_dir}: 预期1个方案ZIP和1个PPTX，"
            f"实际ZIP={len(scheme_zips)} PPTX={len(pptx_files)}"
        )

    stem = delivery_dir.name.removesuffix("_delivery")
    folder_name = f"{stem}_交付文件夹"
    outer_zip = delivery_dir / f"{folder_name}.zip"
    if outer_zip.exists():
        outer_zip.unlink()

    with ZipFile(outer_zip, "w", ZIP_DEFLATED) as zf:
        for source in (scheme_zips[0], pptx_files[0]):
            zf.write(source, arcname=f"{folder_name}/{source.name}")

    with ZipFile(outer_zip) as zf:
        files = [name for name in zf.namelist() if not name.endswith("/")]
    if len(files) != 2:
        raise AssertionError(f"统一交付文件夹内容数量错误: {files}")
    return outer_zip


def main() -> None:
    delivery_dirs = sorted(path for path in DIST.glob("*_delivery") if path.is_dir())
    if not delivery_dirs:
        raise FileNotFoundError("dist下未找到*_delivery目录")
    outputs = [package_delivery_dir(path) for path in delivery_dirs]
    print("DELIVERY_FOLDER_PACKAGED", *(str(path.relative_to(ROOT)) for path in outputs))


if __name__ == "__main__":
    main()
