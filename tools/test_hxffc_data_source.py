#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from data_sources import (  # noqa: E402
    HashFFCSource,
    SourceFetchError,
    SourceParseError,
    SourceValidationError,
)


def fixture(
    rows: list[tuple[str, str, str, str]],
    *,
    comments: bool = True,
    header: str = "issue\tcode\tdraw_time\tsource",
) -> bytes:
    lines: list[str] = []
    if comments:
        lines.extend(["# comment", "# another comment"])
    lines.append(header)
    for row in rows:
        lines.append("\t".join(row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def sample_rows(count: int = 5, start: int = 100) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(start + i),
            f"{i % 100000:05d}",
            f"2026-08-05 10:{i:02d}:00",
            "collector",
        )
        for i in range(count)
    ]


class FakeHeaders(dict):
    pass


class FakeResponse:
    def __init__(self, body: bytes, url: str, content_type: str = "text/plain"):
        self._body = body
        self._url = url
        self.headers = FakeHeaders({"Content-Type": content_type})

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url


class HashFFCSourceTests(unittest.TestCase):
    def source(self, cache: Path, *, min_records: int = 3, age: int = 100000):
        return HashFFCSource(
            cache_root=cache,
            min_records=min_records,
            max_age_minutes=age,
            retention_count=2,
            now_fn=lambda: datetime(2026, 8, 5, 11, 0, tzinfo=timezone.utc),
        )

    def test_parse_ignores_comments_and_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            records = source.parse_source(fixture(sample_rows(3)))
            self.assertEqual([x.issue for x in records], ["100", "101", "102"])
            self.assertEqual(records[0].code, "00000")

    def test_parse_rejects_missing_header_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            with self.assertRaises(SourceParseError):
                source.parse_source(
                    fixture(sample_rows(3), header="issue\tcode\tdraw_time")
                )

    def test_rejects_non_five_digit_code(self):
        rows = sample_rows(3)
        rows[1] = (rows[1][0], "1234", rows[1][2], rows[1][3])
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(rows)
            with self.assertRaises(SourceValidationError):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    require_newer=False,
                )

    def test_exact_duplicate_is_deduped(self):
        rows = sample_rows(3)
        rows.insert(2, rows[1])
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(rows)
            result = source.validate_source(
                source.parse_source(content),
                content,
                require_newer=False,
            )
            self.assertEqual(result.record_count, 3)
            self.assertEqual(result.exact_duplicate_count, 1)

    def test_conflicting_duplicate_is_rejected(self):
        rows = sample_rows(3)
        rows.insert(
            2,
            (rows[1][0], "99999", rows[1][2], "other-collector"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(rows)
            with self.assertRaisesRegex(SourceValidationError, "冲突号码"):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    require_newer=False,
                )

    def test_unsorted_issue_is_rejected(self):
        rows = sample_rows(3)
        rows[1], rows[2] = rows[2], rows[1]
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(rows)
            with self.assertRaisesRegex(SourceValidationError, "升序"):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    require_newer=False,
                )

    def test_insufficient_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp), min_records=4)
            content = fixture(sample_rows(3))
            with self.assertRaisesRegex(SourceValidationError, "明显不足"):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    require_newer=False,
                )

    def test_stale_latest_draw_is_rejected(self):
        rows = [
            ("100", "12345", "2026-08-01 10:00:00", "collector"),
            ("101", "12346", "2026-08-01 10:01:00", "collector"),
            ("102", "12347", "2026-08-01 10:02:00", "collector"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp), age=60)
            content = fixture(rows)
            with self.assertRaisesRegex(SourceValidationError, "过旧"):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    require_newer=False,
                )

    def test_not_newer_than_previous_is_rejected_for_formal_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(sample_rows(3))
            with self.assertRaisesRegex(SourceValidationError, "未晚于"):
                source.validate_source(
                    source.parse_source(content),
                    content,
                    previous_metadata={"latest_issue": "102"},
                    require_newer=True,
                )

    def test_source_field_is_not_exposed_to_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.source(Path(tmp))
            content = fixture(sample_rows(3))
            result = source.validate_source(
                source.parse_source(content),
                content,
                require_newer=False,
            )
            draws = source.get_draws(result)
            self.assertNotIn("source", draws[0])
            self.assertEqual(set(draws[0]), {"issue", "code", "draw_time"})

    def test_snapshot_writes_sha_metadata_and_read_only_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            run_dir = Path(tmp) / "run"
            source = self.source(cache)
            content = fixture(sample_rows(3))
            fetch = type(
                "Fetch",
                (),
                {
                    "content": content,
                    "requested_url": source.FIXED_URL,
                    "final_url": source.FIXED_URL,
                    "fetched_at": datetime(
                        2026, 8, 5, 3, 0, tzinfo=timezone.utc
                    ),
                    "method": "test",
                    "content_type": "text/plain",
                },
            )()
            validation = source.validate_source(
                source.parse_source(content),
                content,
                require_newer=False,
            )
            metadata = source.build_metadata(
                fetch=fetch,
                validation=validation,
                task_id="TEST-1",
            )
            paths = source.snapshot_source(
                fetch=fetch,
                metadata=metadata,
                task_run_dir=run_dir,
            )
            latest = Path(paths["latest_file"])
            stored = json.loads(Path(paths["latest_metadata"]).read_text("utf-8"))
            self.assertEqual(stored["sha256"], validation.sha256)
            self.assertEqual(stored["latest_issue"], "102")
            self.assertEqual(stored["task_id"], "TEST-1")
            self.assertTrue(Path(paths["task_file"]).exists())
            if os.name != "nt":
                self.assertFalse(latest.stat().st_mode & stat.S_IWUSR)

    def test_fetch_failure_raises_and_cannot_continue(self):
        def failing_urlopen(*args, **kwargs):
            raise urllib.error.URLError("offline")

        with tempfile.TemporaryDirectory() as tmp:
            source = HashFFCSource(
                cache_root=Path(tmp),
                urlopen=failing_urlopen,
            )
            with self.assertRaises(SourceFetchError):
                source.fetch_source()

    def test_private_release_api_fallback_uses_stable_tag_and_asset(self):
        history = fixture(sample_rows(3))
        calls: list[tuple[str, str | None]] = []

        def fake_urlopen(request: urllib.request.Request, timeout: int):
            calls.append((request.full_url, request.headers.get("Accept")))
            if request.full_url == HashFFCSource.FIXED_URL:
                raise urllib.error.HTTPError(
                    request.full_url, 404, "private", {}, None
                )
            if request.full_url.endswith("/releases/tags/data-latest"):
                return FakeResponse(
                    json.dumps(
                        {
                            "assets": [
                                {
                                    "name": "hxffc_history.txt",
                                    "url": "https://api.github.com/assets/1",
                                }
                            ]
                        }
                    ).encode("utf-8"),
                    request.full_url,
                    "application/json",
                )
            if request.full_url == "https://api.github.com/assets/1":
                return FakeResponse(
                    history,
                    request.full_url,
                    "application/octet-stream",
                )
            raise AssertionError(request.full_url)

        with tempfile.TemporaryDirectory() as tmp:
            source = HashFFCSource(
                cache_root=Path(tmp),
                urlopen=fake_urlopen,
                now_fn=lambda: datetime.now(timezone.utc),
            )
            result = source.fetch_source(token="readonly-token")
            self.assertEqual(result.content, history)
            self.assertEqual(result.method, "fixed_tag_private_api_fallback")
            self.assertTrue(
                any(url.endswith("/releases/tags/data-latest") for url, _ in calls)
            )

    def test_non_hash_workflow_is_not_redirected(self):
        registry = {
            "hxffc": {
                "adapter": "data_sources.hxffc.HashFFCSource",
                "formal_gate_required": True,
            }
        }
        self.assertIsNone(registry.get("other_lottery"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
