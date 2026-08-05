from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from .base import (
    DrawRecord,
    FetchResult,
    SourceFetchError,
    SourceParseError,
    SourceValidationError,
    ValidationResult,
)


class HashFFCSource:
    """Read-only adapter for the Hash FFC history release asset."""

    SOURCE_ID = "hxffc"
    FIXED_URL = (
        "https://github.com/fdsasaaa/haxiffccaiji/"
        "releases/download/data-latest/hxffc_history.txt"
    )
    REPOSITORY = "fdsasaaa/haxiffccaiji"
    RELEASE_TAG = "data-latest"
    ASSET_NAME = "hxffc_history.txt"
    REQUIRED_COLUMNS = ("issue", "code", "draw_time", "source")
    ISSUE_RE = re.compile(r"^[0-9]+$")
    CODE_RE = re.compile(r"^[0-9]{5}$")
    TOKEN_ENV_NAMES = ("HXFCCAIJI_READ_TOKEN", "HXFFC_DATA_TOKEN")
    USER_AGENT = "guaji5-hxffc-data-source/1.0"

    def __init__(
        self,
        *,
        cache_root: Path,
        min_records: int = 100,
        max_age_minutes: int = 360,
        retention_count: int = 5,
        source_timezone: str = "Asia/Shanghai",
        timeout_seconds: int = 30,
        now_fn: Callable[[], datetime] | None = None,
        urlopen: Callable[..., object] | None = None,
    ) -> None:
        if min_records < 1:
            raise ValueError("min_records must be positive")
        if max_age_minutes < 1:
            raise ValueError("max_age_minutes must be positive")
        if retention_count < 0:
            raise ValueError("retention_count cannot be negative")
        self.cache_root = Path(cache_root)
        self.min_records = min_records
        self.max_age_minutes = max_age_minutes
        self.retention_count = retention_count
        self.source_tz = ZoneInfo(source_timezone)
        self.timeout_seconds = timeout_seconds
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.urlopen = urlopen or urllib.request.urlopen

    @classmethod
    def token_from_environment(cls) -> str | None:
        for name in cls.TOKEN_ENV_NAMES:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _headers(token: str | None, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": HashFFCSource.USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _open(self, request: urllib.request.Request):
        return self.urlopen(request, timeout=self.timeout_seconds)

    @staticmethod
    def _read_response(response: object) -> tuple[bytes, str, str | None]:
        data = response.read()
        final_url = response.geturl() if hasattr(response, "geturl") else ""
        headers = getattr(response, "headers", None)
        content_type = headers.get("Content-Type") if headers is not None else None
        return data, final_url, content_type

    def _download_fixed_url(self, token: str | None) -> FetchResult:
        request = urllib.request.Request(
            self.FIXED_URL,
            headers=self._headers(token, "text/plain, application/octet-stream"),
        )
        response = self._open(request)
        content, final_url, content_type = self._read_response(response)
        return FetchResult(
            content=content,
            requested_url=self.FIXED_URL,
            final_url=final_url or self.FIXED_URL,
            fetched_at=self._aware_now(),
            method="fixed_release_url",
            content_type=content_type,
        )

    def _download_private_asset_via_api(self, token: str) -> FetchResult:
        release_api = (
            f"https://api.github.com/repos/{self.REPOSITORY}/"
            f"releases/tags/{self.RELEASE_TAG}"
        )
        release_request = urllib.request.Request(
            release_api,
            headers=self._headers(token, "application/vnd.github+json"),
        )
        release_response = self._open(release_request)
        release_bytes, _, _ = self._read_response(release_response)
        try:
            release = json.loads(release_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceFetchError("私有仓库Release元数据无法解析") from exc
        asset = next(
            (
                item
                for item in release.get("assets", [])
                if item.get("name") == self.ASSET_NAME
            ),
            None,
        )
        if not asset or not asset.get("url"):
            raise SourceFetchError(
                f"Release {self.RELEASE_TAG}缺少资产{self.ASSET_NAME}"
            )
        asset_request = urllib.request.Request(
            asset["url"],
            headers=self._headers(token, "application/octet-stream"),
        )
        asset_response = self._open(asset_request)
        content, final_url, content_type = self._read_response(asset_response)
        return FetchResult(
            content=content,
            requested_url=self.FIXED_URL,
            final_url=final_url or asset["url"],
            fetched_at=self._aware_now(),
            method="fixed_tag_private_api_fallback",
            content_type=content_type,
        )

    def fetch_source(self, token: str | None = None) -> FetchResult:
        """Download the stable release asset. Never use a commit SHA or dated file."""
        token = token or self.token_from_environment()
        try:
            result = self._download_fixed_url(token)
        except urllib.error.HTTPError as exc:
            if token and exc.code in {401, 403, 404}:
                try:
                    result = self._download_private_asset_via_api(token)
                except Exception as fallback_exc:
                    raise SourceFetchError(
                        f"固定地址下载失败，私有仓库只读回退也失败: {fallback_exc}"
                    ) from fallback_exc
            else:
                hint = (
                    "；采集仓库当前为私有时，请配置只读Secret "
                    "HXFCCAIJI_READ_TOKEN或HXFFC_DATA_TOKEN"
                    if exc.code in {401, 403, 404}
                    else ""
                )
                raise SourceFetchError(
                    f"固定地址下载失败: HTTP {exc.code}{hint}"
                ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceFetchError(f"固定地址下载失败: {exc}") from exc
        if not result.content:
            raise SourceFetchError("固定地址返回空内容")
        return result

    @staticmethod
    def _decode_utf8(content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceParseError("开奖文件不是有效UTF-8编码") from exc

    def parse_source(self, content: bytes) -> list[DrawRecord]:
        """Parse tab-delimited source and ignore comments and the header row."""
        text = self._decode_utf8(content)
        meaningful = [
            line.rstrip("\r\n")
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not meaningful:
            raise SourceParseError("下载文件没有有效内容")
        header = meaningful[0].split("\t")
        missing = [name for name in self.REQUIRED_COLUMNS if name not in header]
        if missing:
            raise SourceParseError(f"字段标题缺少: {missing}")
        indexes = {name: header.index(name) for name in self.REQUIRED_COLUMNS}
        max_index = max(indexes.values())
        records: list[DrawRecord] = []
        for line_no, line in enumerate(meaningful[1:], start=2):
            columns = line.split("\t")
            if len(columns) <= max_index:
                raise SourceParseError(
                    f"有效数据第{line_no}行字段数量不足: {line!r}"
                )
            issue = columns[indexes["issue"]].strip()
            code = columns[indexes["code"]].strip()
            draw_time_raw = columns[indexes["draw_time"]].strip()
            source = columns[indexes["source"]].strip()
            draw_time = self._parse_draw_time(draw_time_raw, line_no)
            records.append(
                DrawRecord(
                    issue=issue,
                    code=code,
                    draw_time=draw_time,
                    source=source,
                )
            )
        if not records:
            raise SourceParseError("标题行之后没有开奖记录")
        return records

    def _parse_draw_time(self, value: str, line_no: int) -> datetime:
        candidates = (value, value.replace("Z", "+00:00"))
        parsed: datetime | None = None
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
        if parsed is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            raise SourceParseError(
                f"有效数据第{line_no}行draw_time无法解析: {value!r}"
            )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self.source_tz)
        return parsed.astimezone(timezone.utc)

    def _aware_now(self) -> datetime:
        now = self.now_fn()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _load_previous_metadata(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def validate_source(
        self,
        records: Iterable[DrawRecord],
        raw_content: bytes,
        *,
        previous_metadata: dict | None = None,
        require_newer: bool = True,
    ) -> ValidationResult:
        """Validate and deduplicate. Conflicts, staleness and schema errors are fatal."""
        raw_records = list(records)
        if not raw_content:
            raise SourceValidationError("原始下载内容为空")
        if not raw_records:
            raise SourceValidationError("没有可校验开奖记录")

        deduped: list[DrawRecord] = []
        by_issue: dict[str, DrawRecord] = {}
        exact_duplicates = 0
        unique_order: list[str] = []
        for index, record in enumerate(raw_records, start=1):
            if not self.ISSUE_RE.fullmatch(record.issue):
                raise SourceValidationError(
                    f"第{index}条期号不是纯数字: {record.issue!r}"
                )
            if not self.CODE_RE.fullmatch(record.code):
                raise SourceValidationError(
                    f"第{index}条开奖号码不是严格5位数字: {record.code!r}"
                )
            if not record.source:
                raise SourceValidationError(f"第{index}条source为空")
            existing = by_issue.get(record.issue)
            if existing:
                if existing.code != record.code:
                    raise SourceValidationError(
                        f"同一期号出现冲突号码: {record.issue}="
                        f"{existing.code}/{record.code}"
                    )
                exact_duplicates += 1
                continue
            by_issue[record.issue] = record
            deduped.append(record)
            unique_order.append(record.issue)

        if len(deduped) < self.min_records:
            raise SourceValidationError(
                f"有效开奖数量明显不足: {len(deduped)} < {self.min_records}"
            )
        sorted_issues = sorted(unique_order, key=int)
        if unique_order != sorted_issues:
            raise SourceValidationError("历史数据未按期号升序排列")

        latest_draw = max(item.draw_time for item in deduped)
        earliest_draw = min(item.draw_time for item in deduped)
        now = self._aware_now()
        if latest_draw > now + timedelta(minutes=10):
            raise SourceValidationError(
                f"最新开奖时间明显位于未来: {latest_draw.isoformat()}"
            )
        age_minutes = (now - latest_draw).total_seconds() / 60
        if age_minutes > self.max_age_minutes:
            raise SourceValidationError(
                f"最新数据明显过旧: {age_minutes:.1f}分钟 > "
                f"{self.max_age_minutes}分钟"
            )

        previous_metadata = previous_metadata or {}
        previous_latest = previous_metadata.get("latest_issue")
        is_newer: bool | None = None
        if previous_latest:
            if not self.ISSUE_RE.fullmatch(str(previous_latest)):
                raise SourceValidationError("本地metadata中的latest_issue非法")
            is_newer = int(deduped[-1].issue) > int(str(previous_latest))
            if require_newer and not is_newer:
                raise SourceValidationError(
                    f"最新期号未晚于上次成功使用期号: "
                    f"{deduped[-1].issue} <= {previous_latest}"
                )

        warnings: list[str] = []
        if exact_duplicates:
            warnings.append(f"发现并按期号去除{exact_duplicates}条完全重复记录")

        return ValidationResult(
            records=tuple(deduped),
            sha256=hashlib.sha256(raw_content).hexdigest(),
            raw_record_count=len(raw_records),
            record_count=len(deduped),
            exact_duplicate_count=exact_duplicates,
            earliest_issue=deduped[0].issue,
            latest_issue=deduped[-1].issue,
            earliest_draw_time=earliest_draw,
            latest_draw_time=latest_draw,
            age_minutes=age_minutes,
            previous_latest_issue=str(previous_latest) if previous_latest else None,
            is_newer_than_previous=is_newer,
            warnings=tuple(warnings),
        )

    def build_metadata(
        self,
        *,
        fetch: FetchResult,
        validation: ValidationResult,
        task_id: str,
        validation_passed: bool = True,
    ) -> dict:
        metadata = {
            "schema_version": 1,
            "source_id": self.SOURCE_ID,
            "source_repository": self.REPOSITORY,
            "source_url": self.FIXED_URL,
            "download_time": fetch.fetched_at.isoformat(),
            "fetch_method": fetch.method,
            "final_url": fetch.final_url,
            "content_type": fetch.content_type,
            "task_id": task_id,
            "validation_passed": validation_passed,
            "formal_generation_allowed": validation_passed,
            "source_field_excluded_from_analysis": True,
        }
        metadata.update(validation.to_metadata())
        return metadata

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        temp_path.replace(path)
        try:
            path.chmod(0o444)
        except OSError:
            pass

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict) -> None:
        HashFFCSource._atomic_write(
            path,
            (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
        )

    def _prune_snapshots(self, snapshots_dir: Path) -> None:
        snapshots = sorted(
            snapshots_dir.glob("*_hxffc_history.txt"),
            key=lambda item: item.name,
        )
        excess = len(snapshots) - self.retention_count
        if excess <= 0:
            return
        for old in snapshots[:excess]:
            try:
                old.chmod(0o644)
            except OSError:
                pass
            old.unlink(missing_ok=True)
            sidecar = old.with_suffix(".metadata.json")
            try:
                sidecar.chmod(0o644)
            except OSError:
                pass
            sidecar.unlink(missing_ok=True)

    def snapshot_source(
        self,
        *,
        fetch: FetchResult,
        metadata: dict,
        task_run_dir: Path | None = None,
    ) -> dict[str, str]:
        """Persist read-only cache and task input snapshot after validation."""
        latest_dir = self.cache_root / "latest"
        snapshots_dir = self.cache_root / "snapshots"
        stamp = fetch.fetched_at.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
        latest_file = latest_dir / self.ASSET_NAME
        latest_metadata = latest_dir / "metadata.json"
        snapshot_file = snapshots_dir / f"{stamp}_hxffc_history.txt"
        snapshot_metadata = snapshots_dir / f"{stamp}_hxffc_history.metadata.json"

        self._atomic_write(latest_file, fetch.content)
        self._atomic_write_json(latest_metadata, metadata)
        if self.retention_count:
            self._atomic_write(snapshot_file, fetch.content)
            self._atomic_write_json(snapshot_metadata, metadata)
            self._prune_snapshots(snapshots_dir)

        paths = {
            "latest_file": str(latest_file),
            "latest_metadata": str(latest_metadata),
            "snapshot_file": str(snapshot_file) if self.retention_count else "",
            "snapshot_metadata": str(snapshot_metadata) if self.retention_count else "",
        }
        if task_run_dir is not None:
            task_input_dir = Path(task_run_dir) / "inputs"
            task_file = task_input_dir / self.ASSET_NAME
            task_metadata = task_input_dir / "hxffc_metadata.json"
            self._atomic_write(task_file, fetch.content)
            self._atomic_write_json(task_metadata, metadata)
            paths["task_file"] = str(task_file)
            paths["task_metadata"] = str(task_metadata)
        return paths

    @staticmethod
    def get_draws(validation: ValidationResult) -> list[dict[str, str]]:
        """Return standardized records without the upstream source field."""
        return [item.analysis_view() for item in validation.records]

    def sync(
        self,
        *,
        task_id: str,
        task_run_dir: Path | None = None,
        token: str | None = None,
        require_newer: bool = True,
    ) -> tuple[list[dict[str, str]], dict, dict[str, str]]:
        """Fetch, parse, validate and snapshot. Any error blocks formal generation."""
        previous = self._load_previous_metadata(
            self.cache_root / "latest" / "metadata.json"
        )
        fetch = self.fetch_source(token=token)
        records = self.parse_source(fetch.content)
        validation = self.validate_source(
            records,
            fetch.content,
            previous_metadata=previous,
            require_newer=require_newer,
        )
        metadata = self.build_metadata(
            fetch=fetch,
            validation=validation,
            task_id=task_id,
        )
        paths = self.snapshot_source(
            fetch=fetch,
            metadata=metadata,
            task_run_dir=task_run_dir,
        )
        draws = self.get_draws(validation)
        if task_run_dir is not None:
            run_dir = Path(task_run_dir)
            draws_path = run_dir / "inputs" / "hxffc_draws.json"
            snapshot_path = run_dir / "data_source_snapshot.json"
            self._atomic_write_json(
                draws_path,
                {
                    "schema_version": 1,
                    "source_id": self.SOURCE_ID,
                    "record_count": len(draws),
                    "records": draws,
                },
            )
            self._atomic_write_json(
                snapshot_path,
                {
                    "schema_version": 1,
                    "status": "PASS",
                    "formal_generation_allowed": True,
                    "metadata": metadata,
                    "paths": paths,
                },
            )
            paths["task_draws"] = str(draws_path)
            paths["data_source_snapshot"] = str(snapshot_path)
        return draws, metadata, paths
