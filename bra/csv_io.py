"""Read-only CSV loading with integrity diagnostics.

The loader never rewrites source files. It reports structural problems as
``Issue`` objects so every validator sees the same CSV-integrity findings.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from .models import Issue, error, warning
from .parsing import is_blank, normalise_header

UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class Row:
    """One parsed CSV record with its physical line number."""

    number: int
    values: dict[str, str]

    def get(self, column: str) -> str:
        return self.values.get(column, "")


@dataclass
class Table:
    """A parsed CSV table plus structural issues found while reading it."""

    path: Path
    headers: list[str] = field(default_factory=list)
    raw_headers: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    readable: bool = True
    headers_ok: bool = True
    data_records_seen: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity.value == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity.value == "warning")

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)


def _empty_table(path: Path, issues: list[Issue], *, readable: bool = False) -> Table:
    return Table(
        path=path,
        readable=readable,
        headers_ok=False,
        issues=issues,
    )


def _decode_legacy_fallback(
    raw: bytes, exc: UnicodeDecodeError, issues: list[Issue]
) -> str | None:
    """Decode a non-UTF-8 file as Windows-1252, or report it as unreadable.

    NSE reference exports are sometimes published in a legacy single-byte
    encoding (for example ``delisted.csv`` uses byte ``0xA0``, a non-breaking
    space). The loader is read-only and never rewrites a source file, so a
    legacy-encoded file is decoded here and the deviation is recorded as a
    ``warning`` rather than silently discarded. ``Windows-1252`` is used
    because it is a strict superset of Latin-1 and decodes every byte value,
    so the fallback cannot itself fail. It is only applied after a genuine
    UTF-8 failure, so UTF-8 files are unaffected.
    """

    text = raw.decode("cp1252", errors="replace")
    issues.append(
        warning(
            "csv.encoding",
            (
                f"File is not valid UTF-8 (byte offset {exc.start}); it was "
                "decoded as Windows-1252 without modifying the source file."
            ),
        )
    )
    return text


def read_csv(path: Path) -> Table:
    """Read a CSV file and report integrity issues without modifying it."""

    issues: list[Issue] = []

    if not path.exists():
        return _empty_table(
            path,
            [
                error(
                    "csv.missing_file",
                    f"File does not exist: {path.name}",
                )
            ],
        )
    if not path.is_file():
        return _empty_table(
            path,
            [
                error(
                    "csv.unreadable",
                    f"Path is not a regular file: {path.name}",
                )
            ],
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _empty_table(
            path,
            [
                error(
                    "csv.unreadable",
                    f"Could not read file: {exc.strerror or exc}",
                )
            ],
        )

    if raw.startswith(UTF8_BOM):
        issues.append(
            warning(
                "csv.bom",
                "File starts with a UTF-8 BOM; it was decoded transparently.",
            )
        )

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        text = _decode_legacy_fallback(raw, exc, issues)
        if text is None:
            return _empty_table(path, issues)

    if not text.strip():
        issues.append(error("csv.empty", "File is empty."))
        return _empty_table(path, issues)

    reader = csv.reader(StringIO(text, newline=""), strict=True)
    raw_headers: list[str] | None = None
    header_line = 0
    parsed_rows: list[Row] = []
    data_records_seen = 0
    blank_lines = 0

    try:
        for record in reader:
            line_number = reader.line_num
            if raw_headers is None:
                if not record or all(is_blank(field) for field in record):
                    blank_lines += 1
                    continue
                raw_headers = record
                header_line = line_number
                continue

            if not record:
                blank_lines += 1
                continue

            data_records_seen += 1
            if len(record) != len(raw_headers):
                issues.append(
                    error(
                        "csv.field_count",
                        (
                            f"Row has {len(record)} fields but the header has "
                            f"{len(raw_headers)}; the row was skipped."
                        ),
                        row=line_number,
                    )
                )
                continue

            if all(is_blank(field) for field in record):
                blank_lines += 1
                continue

            parsed_rows.append(
                Row(
                    line_number,
                    dict(zip((normalise_header(h) for h in raw_headers), record)),
                )
            )
    except csv.Error as exc:
        issues.append(
            error(
                "csv.malformed",
                f"CSV parser error at line {reader.line_num}: {exc}.",
                row=reader.line_num,
            )
        )

    if blank_lines:
        issues.append(
            warning(
                "csv.blank_rows",
                f"Ignored {blank_lines} blank line(s) while reading the file.",
            )
        )

    if raw_headers is None:
        issues.append(error("csv.no_header", "File has no header row."))
        return Table(
            path=path,
            raw_headers=raw_headers or [],
            issues=issues,
            readable=True,
            headers_ok=False,
            data_records_seen=data_records_seen,
        )

    headers = [normalise_header(header) for header in raw_headers]
    header_errors = False

    blank_headers = [
        str(index + 1) for index, header in enumerate(headers) if not header
    ]
    if blank_headers:
        header_errors = True
        issues.append(
            error(
                "csv.header_blank",
                f"Blank header(s) at column position(s): {', '.join(blank_headers)}.",
                row=header_line,
            )
        )

    duplicate_headers = sorted(
        {header for header in headers if header and headers.count(header) > 1}
    )
    if duplicate_headers:
        header_errors = True
        issues.append(
            error(
                "csv.header_duplicate",
                f"Duplicate header(s) after normalisation: {', '.join(duplicate_headers)}.",
                row=header_line,
            )
        )

    changed_headers = [
        f"{raw!r} -> {normalised!r}"
        for raw, normalised in zip(raw_headers, headers)
        if raw != normalised
    ]
    if changed_headers:
        preview = ", ".join(changed_headers[:4])
        if len(changed_headers) > 4:
            preview += f", and {len(changed_headers) - 4} more"
        issues.append(
            warning(
                "csv.header_whitespace",
                (f"Header whitespace or newlines were normalised: {preview}."),
                row=header_line,
            )
        )

    if data_records_seen == 0:
        issues.append(error("csv.no_data_rows", "File has a header but no data rows."))
    elif not parsed_rows:
        issues.append(
            error(
                "csv.no_valid_rows",
                "No structurally valid data rows could be parsed.",
            )
        )

    return Table(
        path=path,
        headers=headers,
        raw_headers=raw_headers,
        rows=parsed_rows,
        issues=issues,
        readable=True,
        headers_ok=not header_errors,
        data_records_seen=data_records_seen,
    )
