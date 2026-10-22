"""Field normalisation and parsing helpers.

The collected NSE exports use Indian digit grouping (for example
``1,70,07,168``), mixed-case month names, and sentinel values such as ``-``.
These helpers keep that parsing in one place so validators stay readable.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, timedelta

NOT_APPLICABLE = frozenset({"-", "--"})

DATE_FORMATS = (
    "%d-%b-%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
)

TIMESTAMP_FORMATS = (
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
)


def is_blank(value: str | None) -> bool:
    """Return True for None or whitespace-only values."""

    return value is None or not value.strip()


def is_not_applicable(value: str | None) -> bool:
    """Return True for explicit NSE sentinel values meaning 'not applicable'."""

    return value is not None and value.strip() in NOT_APPLICABLE


def clean(value: str | None) -> str:
    """Strip surrounding whitespace, turning None into an empty string."""

    return "" if value is None else value.strip()


def normalise_header(value: str) -> str:
    """Normalise a CSV header for matching without changing the source data.

    BOMs are removed by the reader, while surrounding whitespace, tabs, and
    embedded newlines are collapsed to a single space.
    """

    value = unicodedata.normalize("NFKC", value).replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> date | None:
    """Parse a supported date string, returning None when it cannot be parsed."""

    if is_blank(value):
        return None
    candidate = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a supported timestamp string, returning None when it cannot be parsed."""

    if is_blank(value):
        return None
    candidate = value.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def parse_number(value: str | None) -> float | None:
    """Parse an NSE numeric field, returning None for invalid or blank input."""

    if is_blank(value):
        return None
    candidate = value.strip().replace(",", "")
    candidate = candidate.replace("\u20b9", "").replace("%", "").strip()
    try:
        parsed = float(candidate)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def format_date(value: date | None) -> str | None:
    """Format a date as ISO 8601 for stable reports."""

    return value.isoformat() if value is not None else None


def format_timestamp(value: datetime | None) -> str | None:
    """Format a timestamp as ISO 8601 (without adding a timezone)."""

    return value.isoformat(sep=" ") if value is not None else None


def format_number(value: float | None) -> str:
    """Format a parsed number without exponent or redundant trailing zeros."""

    if value is None:
        return ""
    return format(value, ".15g")


def parse_excel_serial(value: str | None) -> date | None:
    """Convert an Excel 1900-system date serial to a date.

    XLSX workbooks store dates as numbers. The conversion is deliberately
    strict: only finite values in the range used by the collected workbook
    (roughly 1954-2119) are accepted, so ordinary numeric cells are not
    silently interpreted as dates.
    """

    if is_blank(value):
        return None
    try:
        serial = float(value.strip())
    except ValueError:
        return None
    if not math.isfinite(serial) or not 20000 <= serial <= 80000:
        return None
    return date(1899, 12, 30) + timedelta(days=int(serial))
