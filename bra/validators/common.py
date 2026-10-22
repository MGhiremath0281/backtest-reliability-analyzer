"""Shared helpers for dataset validators."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable
from datetime import date

from ..csv_io import Row, Table
from ..models import DatasetResult
from ..parsing import clean, format_date


def check_schema(
    table: Table,
    result: DatasetResult,
    *,
    required: Iterable[str],
    known: Iterable[str],
) -> set[str]:
    """Report missing and unexpected columns. Returns the missing columns."""

    headers = set(table.headers)
    required_set = set(required)
    known_set = set(known)

    missing = sorted(required_set - headers)
    unexpected = sorted(headers - known_set)

    if missing:
        result.add_error(
            "columns.missing",
            f"Missing required column(s): {', '.join(missing)}.",
        )
    if unexpected:
        result.add_warning(
            "columns.unexpected",
            f"Unexpected column(s): {', '.join(unexpected)}.",
        )
    return set(missing)


def date_coverage(dates: Iterable[date | None], column: str) -> dict[str, str] | None:
    """Build a stable coverage object from parsed dates."""

    valid = [value for value in dates if value is not None]
    if not valid:
        return None
    return {
        "date_column": column,
        "start": format_date(min(valid)),
        "end": format_date(max(valid)),
    }


def add_duplicate_issues(
    result: DatasetResult,
    groups: dict[Hashable, list[Row]],
    *,
    code: str,
    label: str,
    preview: Callable[[Hashable], str],
) -> int:
    """Add one error per duplicate group and return the number of extra rows."""

    extra_rows = 0
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        if len(group) < 2:
            continue
        extra_rows += len(group) - 1
        lines = ", ".join(str(row.number) for row in group)
        result.add_error(
            code,
            (
                f"Duplicate {label}: {preview(key)} appears {len(group)} times "
                f"(lines {lines})."
            ),
            row=group[1].number,
        )
    return extra_rows


def count_values(rows: Iterable[Row], column: str) -> dict[str, int]:
    """Count cleaned non-empty values in a column, sorted by value."""

    counter = Counter(clean(row.get(column)) for row in rows)
    counter.pop("", None)
    return dict(sorted(counter.items()))


def count_pairs(
    rows: Iterable[Row],
    first: str,
    second: str,
) -> dict[str, dict[str, int]]:
    """Count non-empty values for two columns as a nested mapping."""

    counter: Counter[tuple[str, str]] = Counter()
    for row in rows:
        left = clean(row.get(first))
        right = clean(row.get(second))
        if left and right:
            counter[(left, right)] += 1

    nested: dict[str, dict[str, int]] = defaultdict(dict)
    for (left, right), count in sorted(counter.items()):
        nested[left][right] = count
    return dict(nested)
