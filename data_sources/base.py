from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class SourceError(RuntimeError):
    """Base error for external draw sources."""


class SourceFetchError(SourceError):
    """The external source could not be downloaded."""


class SourceParseError(SourceError):
    """The downloaded source does not match the declared schema."""


class SourceValidationError(SourceError):
    """The parsed source failed a formal quality gate."""


@dataclass(frozen=True, slots=True)
class DrawRecord:
    issue: str
    code: str
    draw_time: datetime
    source: str

    def analysis_view(self) -> dict[str, str]:
        """Return only fields the scheme layer may consume."""
        return {
            "issue": self.issue,
            "code": self.code,
            "draw_time": self.draw_time.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class FetchResult:
    content: bytes
    requested_url: str
    final_url: str
    fetched_at: datetime
    method: str
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    records: tuple[DrawRecord, ...]
    sha256: str
    raw_record_count: int
    record_count: int
    exact_duplicate_count: int
    earliest_issue: str
    latest_issue: str
    earliest_draw_time: datetime
    latest_draw_time: datetime
    age_minutes: float
    previous_latest_issue: str | None
    is_newer_than_previous: bool | None
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "raw_record_count": self.raw_record_count,
            "record_count": self.record_count,
            "exact_duplicate_count": self.exact_duplicate_count,
            "earliest_issue": self.earliest_issue,
            "latest_issue": self.latest_issue,
            "earliest_draw_time": self.earliest_draw_time.isoformat(),
            "latest_draw_time": self.latest_draw_time.isoformat(),
            "age_minutes": round(self.age_minutes, 2),
            "previous_latest_issue": self.previous_latest_issue,
            "is_newer_than_previous": self.is_newer_than_previous,
            "warnings": list(self.warnings),
        }
