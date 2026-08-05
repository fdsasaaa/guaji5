#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import controller_data_source_gate as gate  # noqa: E402


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class ControllerDataSourceGateTests(unittest.TestCase):
    def test_non_hash_task_does_not_require_hash_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-NONHASH"
            run_dir.mkdir()
            errors = gate.validate_task_snapshot(
                run_dir=run_dir,
                task={"run_id": "RUN-NONHASH", "data_source": None},
            )
            self.assertEqual(errors, [])

    def test_hash_task_missing_snapshot_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-HASH"
            run_dir.mkdir()
            errors = gate.validate_task_snapshot(
                run_dir=run_dir,
                task={"run_id": "RUN-HASH", "data_source": "hxffc"},
            )
            self.assertTrue(errors)
            self.assertTrue(any("缺少" in item for item in errors))

    def build_valid_snapshot(self, run_dir: Path) -> dict:
        rows = [
            {
                "issue": str(202608050000 + index),
                "code": f"{index % 100000:05d}",
                "draw_time": "2026-08-05T03:00:00+00:00",
            }
            for index in range(100)
        ]
        history = (
            "# fixture\nissue\tcode\tdraw_time\tsource\n"
            + "\n".join(
                f"{item['issue']}\t{item['code']}\t2026-08-05 11:00:00\ttest"
                for item in rows
            )
            + "\n"
        ).encode("utf-8")
        inputs = run_dir / "inputs"
        inputs.mkdir(parents=True)
        history_path = inputs / "hxffc_history.txt"
        history_path.write_bytes(history)
        digest = hashlib.sha256(history).hexdigest()
        metadata = {
            "source_id": "hxffc",
            "source_url": (
                "https://github.com/fdsasaaa/haxiffccaiji/"
                "releases/download/data-latest/hxffc_history.txt"
            ),
            "validation_passed": True,
            "formal_generation_allowed": True,
            "sha256": digest,
            "record_count": 100,
            "earliest_issue": rows[0]["issue"],
            "latest_issue": rows[-1]["issue"],
        }
        write_json(inputs / "hxffc_metadata.json", metadata)
        write_json(
            inputs / "hxffc_draws.json",
            {
                "schema_version": 1,
                "source_id": "hxffc",
                "record_count": 100,
                "records": rows,
            },
        )
        write_json(
            run_dir / "data_source_snapshot.json",
            {
                "status": "PASS",
                "formal_generation_allowed": True,
                "metadata": metadata,
            },
        )
        return metadata

    def test_valid_hash_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-HASH"
            run_dir.mkdir()
            self.build_valid_snapshot(run_dir)
            errors = gate.validate_task_snapshot(
                run_dir=run_dir,
                task={"run_id": "RUN-HASH", "data_source": "hxffc"},
            )
            self.assertEqual(errors, [])

    def test_hash_mismatch_and_source_leak_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-HASH"
            run_dir.mkdir()
            self.build_valid_snapshot(run_dir)
            history = run_dir / "inputs" / "hxffc_history.txt"
            history.write_text("tampered", encoding="utf-8")
            draws_path = run_dir / "inputs" / "hxffc_draws.json"
            draws = json.loads(draws_path.read_text(encoding="utf-8"))
            draws["records"][0]["source"] = "must-not-reach-analysis"
            write_json(draws_path, draws)
            errors = gate.validate_task_snapshot(
                run_dir=run_dir,
                task={"run_id": "RUN-HASH", "data_source": "hxffc"},
            )
            self.assertTrue(any("SHA-256" in item for item in errors))
            self.assertTrue(any("泄漏" in item for item in errors))

    def test_controller_blocks_hash_director_without_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "runs"
            command = [
                sys.executable,
                str(ROOT / "tools" / "lottery_controller.py"),
                "start",
                "--request",
                "hash gate test",
                "--data-source",
                "hxffc",
                "--run-id",
                "RUN-HASH-GATE",
                "--run-root",
                str(run_root),
            ]
            start = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(start.returncode, 0, start.stderr)
            run_dir = run_root / "RUN-HASH-GATE"
            write_json(run_dir / "preflight.json", {"status": "PENDING"})
            first = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "lottery_controller.py"),
                    "advance",
                    "--run-id",
                    "RUN-HASH-GATE",
                    "--to",
                    "PREFLIGHT",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "lottery_controller.py"),
                    "advance",
                    "--run-id",
                    "RUN-HASH-GATE",
                    "--to",
                    "DIRECTOR",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("外部数据源闸门未通过", second.stderr)

    def test_controller_allows_non_hash_preflight_without_hash_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "runs"
            base = [
                sys.executable,
                str(ROOT / "tools" / "lottery_controller.py"),
            ]
            start = subprocess.run(
                base
                + [
                    "start",
                    "--request",
                    "non hash gate test",
                    "--mode",
                    "SYSTEM_UPGRADE_ONLY",
                    "--run-id",
                    "RUN-NONHASH-GATE",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            sync = subprocess.run(
                base
                + [
                    "sync-data",
                    "--run-id",
                    "RUN-NONHASH-GATE",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(sync.returncode, 0, sync.stderr)
            first = subprocess.run(
                base
                + [
                    "advance",
                    "--run-id",
                    "RUN-NONHASH-GATE",
                    "--to",
                    "PREFLIGHT",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(
                base
                + [
                    "advance",
                    "--run-id",
                    "RUN-NONHASH-GATE",
                    "--to",
                    "DIRECTOR",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(second.returncode, 0, second.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
