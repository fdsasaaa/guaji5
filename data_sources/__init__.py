"""External lottery data-source adapters.

The package exposes validated, standardized draw records to the scheme layer.
Collection programs remain in their own repositories.
"""

from .base import (
    DrawRecord,
    FetchResult,
    SourceError,
    SourceFetchError,
    SourceParseError,
    SourceValidationError,
    ValidationResult,
)
from .hxffc import HashFFCSource

__all__ = [
    "DrawRecord",
    "FetchResult",
    "HashFFCSource",
    "SourceError",
    "SourceFetchError",
    "SourceParseError",
    "SourceValidationError",
    "ValidationResult",
]
