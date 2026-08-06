#!/usr/bin/env python3
from pathlib import Path
import tempfile

from validate_scheme_import_folder import validate_folder


def write_main(path: Path, *, content_field: str = "定码轮换内容=4 8 6 9 3 5 7", position: str = "", plan: str = "1,1,1,1,1,1,1,1") -> None:
    lines = [
        "False", "定码轮换", "软件名称=CXGGJ", "玩法类型=定位胆", "玩法名称=个位",
        "金额模式=2", "任选中奖=1-10", f"任选位置={position}", content_field,
        "定码轮换单组=True", "换号规则=9", "换号期数=0", "翻倍方式=0", "正集=True",
        "倍投类型=1", f"倍投计划={plan}", "倍投方案=高级倍投主配置",
        "显示更多=False", "投注时间=False", "SchemeCreator=",
    ]
    path.write_bytes(("\r\n".join(lines) + "\r\n\r\n\r\n").encode("gbk"))


def write_config(folder: Path, display_name: str) -> None:
    target = folder / "GJBTScheme"
    target.mkdir()
    states = [(1, 1, 1, 2), (2, 2, 1, 3), (3, 6, 1, 4), (4, 18, 5, 5),
              (5, 1, 6, 6), (6, 1, 7, 7), (7, 1, 8, 8), (8, 1, 1, 1)]
    rows = []
    for sid, mult, win_id, loss_id in states:
        rows.append(
            f"软件名称=CXGGJ;ID={sid};倍数={mult};中后ID={win_id};挂后ID={loss_id};"
            f"中后监控=False;中后跳转=False-{display_name};挂后监控=False;挂后跳转=False-{display_name}"
        )
    (target / "高级倍投主配置.txt").write_bytes(
        b"\xef\xbb\xbf" + ("\r\n".join(rows) + "\r\n").encode("utf-8")
    )


def expect_failure(folder: Path) -> None:
    try:
        validate_folder(folder)
    except ValueError:
        return
    raise AssertionError(f"Expected validation failure: {folder}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        good = root / "good"
        good.mkdir()
        display = "个位热七码四级回利四期降压"
        write_main(good / f"{display}-定码轮换.txt")
        write_config(good, display)
        validate_folder(good)

        extra_txt = root / "extra_txt"
        extra_txt.mkdir()
        write_main(extra_txt / f"{display}-定码轮换.txt")
        write_config(extra_txt, display)
        (extra_txt / "投注数字_直接查看.txt").write_text("投注数字：4 8 6 9 3 5 7", encoding="utf-8")
        expect_failure(extra_txt)

        generic_field = root / "generic_field"
        generic_field.mkdir()
        write_main(generic_field / f"{display}-定码轮换.txt", content_field="投注内容=4 8 6 9 3 5 7")
        write_config(generic_field, display)
        expect_failure(generic_field)

        bad_position = root / "bad_position"
        bad_position.mkdir()
        write_main(bad_position / f"{display}-定码轮换.txt", position="4")
        write_config(bad_position, display)
        expect_failure(bad_position)

        six_slots = root / "six_slots"
        six_slots.mkdir()
        write_main(six_slots / f"{display}-定码轮换.txt", plan="1,1,1,1,1,1")
        write_config(six_slots, display)
        expect_failure(six_slots)

    print("SCHEME_IMPORT_FOLDER_TESTS_OK")


if __name__ == "__main__":
    main()
