"""Shared constants, records, and read-only input parsing.

Everything in this module only reads source files. Nothing is ever inferred
from a period end, an ex date, a record date, or an effective date alone:
those are semantic dates of a period or event, not the timestamps at which a
result or an announcement became available. Malformed rows are reported
through the caller's ``DatasetResult`` and excluded from the affected
calculations; they are never repaired or rewritten in the source file.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ...csv_io import Row, Table, read_csv
from ...discovery import FINANCIAL_SYMBOL_RE, discover_datasets
from ...models import DatasetResult, Severity
from ...parsing import clean, parse_date, parse_timestamp

LOOKAHEAD_DATASET_ID = "lookahead:analysis"
LOOKAHEAD_CATEGORY = "lookahead_bias"
LOOKAHEAD_LABEL = "Look-ahead-bias assessment"

# Finding statuses used by the checks. ``not_applicable`` marks a check that
# had nothing to run (for example because no decision dates were supplied);
# it is different from ``unavailable``, where the requested check needed data
# that the collected evidence cannot provide.
STATUS_OK = "ok"
STATUS_CONFIRMED = "confirmed"
STATUS_SUSPICIOUS = "suspicious"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_INVALID = "invalid"

CHECK_STATUSES = (
    STATUS_OK,
    STATUS_CONFIRMED,
    STATUS_SUSPICIOUS,
    STATUS_UNAVAILABLE,
    STATUS_NOT_APPLICABLE,
    STATUS_INVALID,
)

# Finding kinds. They mirror the evidence classes the analyzer must keep
# apart: a confirmed temporal violation is reproducibly visible in the data
# itself, a suspicious pattern requires knowledge of what a decision consumed
# before it can be called a violation, and an insufficient conclusion marks
# evidence that the collected schemas simply do not contain.
KIND_CONFIRMED = "confirmed_lookahead_violation"
KIND_SUSPICIOUS = "potential_lookahead_risk"
KIND_INSUFFICIENT = "insufficient_lookahead_evidence"
KIND_CHECK = "lookahead_check_passed"
KIND_BACKTEST = "lookahead_backtest_specific_result"

# Structured issue codes. Severity is always ``warning`` on the analysis
# dataset; the kind/status fields of the structured findings carry the
# confirmed/suspicious/insufficient classification.
FINDING_CONFIRMED_CODE = "lookahead.confirmed_temporal_violation"
FINDING_SUSPICIOUS_CODE = "lookahead.potential_temporal_violation"
FINDING_INSUFFICIENT_CODE = "lookahead.insufficient_evidence"

# Per-check finding codes.
ISSUE_PUBLICATION_BEFORE_PERIOD = "lookahead.publication_before_period"
ISSUE_USED_BEFORE_PUBLICATION = "lookahead.information_used_before_publication"
ISSUE_REVISION_BEFORE_PUBLIC = "lookahead.revision_used_before_public"
ISSUE_FUTURE_UNIVERSE = "lookahead.future_universe_membership"
ISSUE_FUTURE_PRICE = "lookahead.future_price_used"
ISSUE_DERIVED_FORWARD = "lookahead.derived_forward_window"
ISSUE_INSUFFICIENT = "lookahead.insufficient_evidence"
ISSUE_DISSEMINATION_BEFORE_RECEIPT = "lookahead.dissemination_before_receipt"
ISSUE_PUBLICATION_MISSING = "lookahead.publication_timestamp_missing"
ISSUE_PERIOD_MISSING = "lookahead.period_end_missing"
ISSUE_TIMESTAMP_UNPARSEABLE = "lookahead.timestamp_unparseable"
ISSUE_CURRENT_LISTING_MISSING = "lookahead.current_listing_missing"
ISSUE_RESTATEMENT_WINDOW = "lookahead.restatement_window"
ISSUE_RECORD_BEFORE_EX_DATE = "lookahead.record_date_before_ex_date"
ISSUE_EX_DATE_MISSING = "lookahead.ex_date_missing"
ISSUE_ANNOUNCEMENT_UNAVAILABLE = "lookahead.announcement_timestamp_unavailable"
ISSUE_PRE_EVENT_PRICE_MISSING = "lookahead.pre_event_price_missing"
ISSUE_PRICE_AVAILABILITY_UNKNOWN = "lookahead.price_availability_unknown"
ISSUE_UNIVERSE_NOT_POINT_IN_TIME = "lookahead.point_in_time_universe_missing"

CHECK_PUBLICATION_TIMING = "publication_timing"
CHECK_REVISIONS = "financial_revisions"
CHECK_UNIVERSE = "point_in_time_universe"
CHECK_PRICE_ACTION = "price_action_timing"
CHECK_DERIVED = "derived_feature_timing"
CHECK_DECISIONS = "decision_timestamp_coverage"

CHECK_NAMES = (
    CHECK_PUBLICATION_TIMING,
    CHECK_REVISIONS,
    CHECK_UNIVERSE,
    CHECK_PRICE_ACTION,
    CHECK_DERIVED,
    CHECK_DECISIONS,
)

MAX_EXAMPLES = 8

FINANCIAL_KINDS = frozenset(
    {
        "financials",
        "integrated_financials",
        "derived_financials_legacy",
        "derived_financials_integrated",
    }
)
LEGACY_FINANCIAL_KINDS = frozenset({"financials", "derived_financials_legacy"})
INTEGRATED_FINANCIAL_KINDS = frozenset(
    {"integrated_financials", "derived_financials_integrated"}
)
PRICE_KINDS = frozenset({"prices", "derived_prices"})
CORPORATE_ACTION_KINDS = frozenset({"corporate_actions", "derived_corporate_actions"})
LISTING_KINDS = frozenset({"current_listing", "derived_current_listings"})
SNAPSHOT_KINDS = frozenset({"index_snapshot"})

LOOKAHEAD_RELEVANT_KINDS = (
    FINANCIAL_KINDS
    | PRICE_KINDS
    | CORPORATE_ACTION_KINDS
    | LISTING_KINDS
    | SNAPSHOT_KINDS
)


@dataclass(frozen=True)
class FinancialRecord:
    """One financial-results row with its reporting period and availability."""

    symbol: str
    company: str
    period_end: date | None
    dissemination: datetime | None
    broadcast: datetime | None
    receipt: datetime | None
    revised: datetime | None
    revision_present: bool
    source: str
    row: int
    # Full dataset kind the row was read from (``financials``,
    # ``derived_financials_integrated``, ...). It lets the derived-feature
    # check attribute violations to the pipeline that produced the file.
    kind: str = ""
    submission: str = ""


@dataclass(frozen=True)
class CorporateActionRecord:
    """One corporate-action event with its entitlement dates."""

    symbol: str
    company: str
    purpose: str
    ex_date: date | None
    record_date: date | None
    source: str
    row: int


@dataclass(frozen=True)
class PriceRecord:
    """One dated price row."""

    symbol: str
    trade_date: date
    source: str
    row: int


FINANCIAL_PERIOD_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": ("PERIOD ENDED", "period_end_date"),
    "integrated_financials": ("QUARTER END DATE", "quarter_end_date"),
    "derived_financials_legacy": ("period_end_date",),
    "derived_financials_integrated": ("quarter_end_date",),
}
FINANCIAL_DISSEMINATION_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": ("Exchange Dissemination Time", "exchange_dissemination_time"),
    "integrated_financials": (
        "EXCHANGE DISSEMINATION TIME",
        "exchange_dissemination_time",
    ),
    "derived_financials_legacy": ("exchange_dissemination_time",),
    "derived_financials_integrated": ("exchange_dissemination_time",),
}
FINANCIAL_RECEIVED_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": ("Exchange Received Time", "exchange_received_time"),
    "derived_financials_legacy": ("exchange_received_time",),
    "integrated_financials": ("BROADCAST DATE/TIME", "broadcast_datetime"),
    "derived_financials_integrated": ("broadcast_datetime",),
}
FINANCIAL_BROADCAST_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": (),
    "derived_financials_legacy": (),
    "integrated_financials": ("BROADCAST DATE/TIME", "broadcast_datetime"),
    "derived_financials_integrated": ("broadcast_datetime",),
}
FINANCIAL_REVISED_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": (),
    "derived_financials_legacy": (),
    "integrated_financials": ("REVISED DATE/TIME", "revised_datetime"),
    "derived_financials_integrated": ("revised_datetime",),
}
FINANCIAL_SUBMISSION_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": (),
    "derived_financials_legacy": (),
    "integrated_financials": ("TYPE OF SUBMISSION", "submission_type"),
    "derived_financials_integrated": ("submission_type",),
}
FINANCIAL_SYMBOL_COLUMNS: dict[str, tuple[str, ...]] = {
    "financials": ("SYMBOL", "symbol"),
    "derived_financials_legacy": ("symbol",),
    "integrated_financials": ("SYMBOL", "symbol"),
    "derived_financials_integrated": ("symbol",),
}
CORPORATE_ACTION_SYMBOL_COLUMNS = ("SYMBOL", "symbol")
CORPORATE_ACTION_COMPANY_COLUMNS = ("COMPANY NAME", "company_name")
CORPORATE_ACTION_PURPOSE_COLUMNS = ("PURPOSE", "purpose")
CORPORATE_ACTION_EX_DATE_COLUMNS = ("EX-DATE", "ex_date")
CORPORATE_ACTION_RECORD_DATE_COLUMNS = ("RECORD DATE", "record_date")
PRICE_SYMBOL_COLUMNS = ("Symbol", "symbol")
PRICE_TRADE_DATE_COLUMNS = ("Date", "trade_date")

SENTINEL_VALUES = frozenset({"-", "--"})


def text(row: Row, *columns: str) -> str:
    """Return the first non-blank value among ``columns``."""

    for column in columns:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def relative(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` for traceable report references."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _parse_value(raw: Any, parser: Any) -> Any:
    """Parse one raw cell, skipping blanks and NSE ``-``/``--`` sentinels."""

    value = clean(raw)
    if not value or value in SENTINEL_VALUES:
        return None
    return parser(value)


def _parse_day(row: Row, columns: tuple[str, ...]) -> date | None:
    for column in columns:
        parsed = _parse_value(row.get(column), parse_date)
        if parsed is not None:
            return parsed
    return None


def _parse_moment(row: Row, columns: tuple[str, ...]) -> datetime | None:
    for column in columns:
        parsed = _parse_value(row.get(column), parse_timestamp)
        if parsed is not None:
            return parsed
    return None


def financial_records(
    tables: Mapping[str, Sequence[Table]],
) -> list[FinancialRecord]:
    """Collect financial rows (legacy and integrated, raw and derived).

    Every discovered kind is read so the derived-feature check can attribute
    violations to the pipeline that produced a file. Legacy exports carry no
    symbol column, so the symbol encoded in the filename is the documented
    fallback (the same rule the preparation pipeline applies).
    """

    return _financial_records_with_counts(tables)[0]


def _financial_records_with_counts(
    tables: Mapping[str, Sequence[Table]],
) -> tuple[list[FinancialRecord], int, list[str]]:
    """Return financial records, the undated-row count, and parse problems.

    Each parse problem string is ``"{label} {value!r} (line N in {source})"``
    so the analysis can report it without re-reading the source file.

    Derived financial tables are preferred over raw tables so that re-computed
    values are used in place of original exports when both are available.
    """

    problems: list[tuple[str, int, str, str]] = []
    records: list[FinancialRecord] = []
    rows_without_period = 0

    def make(row: Row, table: Table, kind: str) -> FinancialRecord | None:
        nonlocal rows_without_period
        period = _parse_day(row, FINANCIAL_PERIOD_COLUMNS[kind])
        if period is None:
            rows_without_period += 1
        dissemination = _parse_moment(row, FINANCIAL_DISSEMINATION_COLUMNS[kind])
        broadcast = _parse_moment(row, FINANCIAL_BROADCAST_COLUMNS[kind])
        receipt = _parse_moment(row, FINANCIAL_RECEIVED_COLUMNS[kind])
        revised = _parse_moment(row, FINANCIAL_REVISED_COLUMNS[kind])
        submission = text(row, *FINANCIAL_SUBMISSION_COLUMNS[kind])
        symbol = text(row, *FINANCIAL_SYMBOL_COLUMNS[kind])
        if not symbol and kind in LEGACY_FINANCIAL_KINDS:
            match = FINANCIAL_SYMBOL_RE.search(table.path.name)
            if match:
                symbol = match.group("symbol").upper()
        for label, is_timestamp, columns in (
            ("period end", False, FINANCIAL_PERIOD_COLUMNS[kind]),
            ("dissemination", True, FINANCIAL_DISSEMINATION_COLUMNS[kind]),
            ("receipt", True, FINANCIAL_RECEIVED_COLUMNS[kind]),
            ("broadcast", True, FINANCIAL_BROADCAST_COLUMNS[kind]),
            ("revision", True, FINANCIAL_REVISED_COLUMNS[kind]),
        ):
            parser = parse_timestamp if is_timestamp else parse_date
            for column in columns:
                value = clean(row.get(column))
                if value and value not in SENTINEL_VALUES and parser(value) is None:
                    problems.append((str(table.path), row.number, label, value))
                    break
        return FinancialRecord(
            symbol=symbol,
            company=text(row, "COMPANY NAME", "company_name"),
            period_end=period,
            dissemination=dissemination,
            broadcast=broadcast,
            receipt=receipt,
            revised=revised,
            revision_present=(
                revised is not None or clean(submission).casefold() == "revised"
            ),
            source=str(table.path),
            row=row.number,
            kind=kind,
            submission=submission,
        )

    derived_kinds = ("derived_financials_legacy", "derived_financials_integrated")
    raw_kinds = tuple(k for k in sorted(FINANCIAL_KINDS) if k not in derived_kinds)

    # First pass: process derived kinds (they take precedence per _derived_or_raw)
    derived_records: list[FinancialRecord] = []
    derived_symbols: set[str] = set()
    for kind in derived_kinds:
        for table in tables.get(kind, ()):
            if not table.readable:
                continue
            for row in table.rows:
                record = make(row, table, kind)
                if record is not None:
                    derived_records.append(record)
                    if record.symbol:
                        derived_symbols.add(record.symbol)

    # If derived records exist, return only those (prefer derived over raw).
    # Otherwise, fall through to process raw kinds.
    if derived_records:
        records = derived_records
    else:
        # Second pass: process raw kinds
        for kind in raw_kinds:
            for table in tables.get(kind, ()):
                if not table.readable:
                    continue
                for row in table.rows:
                    record = make(row, table, kind)
                    if record is not None:
                        records.append(record)
    rendered: list[str] = [
        f"{label} {value!r} (line {line} in {source})"
        for source, line, label, value in problems
    ]
    return records, rows_without_period, rendered


def corporate_action_records(
    tables: Mapping[str, Sequence[Table]],
) -> list[CorporateActionRecord]:
    """Collect corporate-action rows."""

    return _corporate_action_records_with_counts(tables)[0]


def _corporate_action_records_with_counts(
    tables: Mapping[str, Sequence[Table]],
) -> tuple[list[CorporateActionRecord], int]:
    """Return action records and the count of rows without a parsable ex date."""

    records: list[CorporateActionRecord] = []
    rows_without_ex_date = 0

    def make(row: Row, table: Table, kind: str) -> CorporateActionRecord:
        del kind  # Column names are identical in raw and derived tables.
        nonlocal rows_without_ex_date
        ex_date = _parse_day(row, CORPORATE_ACTION_EX_DATE_COLUMNS)
        if ex_date is None:
            rows_without_ex_date += 1
        return CorporateActionRecord(
            symbol=text(row, *CORPORATE_ACTION_SYMBOL_COLUMNS),
            company=text(row, *CORPORATE_ACTION_COMPANY_COLUMNS),
            purpose=text(row, *CORPORATE_ACTION_PURPOSE_COLUMNS),
            ex_date=ex_date,
            record_date=_parse_day(row, CORPORATE_ACTION_RECORD_DATE_COLUMNS),
            source=str(table.path),
            row=row.number,
        )

    for kind in sorted(CORPORATE_ACTION_KINDS):
        for table in tables.get(kind, ()):
            if not table.readable:
                continue
            for row in table.rows:
                records.append(make(row, table, kind))
    return records, rows_without_ex_date


def price_records(
    tables: Mapping[str, Sequence[Table]],
) -> list[PriceRecord]:
    """Collect dated price rows; rows without a parsable date are excluded."""

    return _price_records_with_counts(tables)[0]


def _price_records_with_counts(
    tables: Mapping[str, Sequence[Table]],
) -> tuple[list[PriceRecord], int]:
    """Return price records and the number of rows excluded as undated."""

    records: list[PriceRecord] = []
    undated = 0

    def make(row: Row, table: Table, kind: str) -> PriceRecord | None:
        del kind  # Column names are identical in raw and derived tables.
        trade_date = _parse_day(row, PRICE_TRADE_DATE_COLUMNS)
        if trade_date is None:
            return None
        return PriceRecord(
            symbol=text(row, *PRICE_SYMBOL_COLUMNS),
            trade_date=trade_date,
            source=str(table.path),
            row=row.number,
        )

    for kind in sorted(PRICE_KINDS):
        for table in tables.get(kind, ()):
            if not table.readable:
                continue
            for row in table.rows:
                record = make(row, table, kind)
                if record is None:
                    undated += 1
                else:
                    records.append(record)
    return records, undated


def listing_tables(tables: Mapping[str, Sequence[Table]]) -> Table | None:
    """Prefer the normalized current-listing table over the raw snapshot."""

    for kind in ("derived_current_listings", "current_listing"):
        readable = [table for table in tables.get(kind, ()) if table.readable]
        if readable:
            return readable[0]
    return None


def load_relevant_tables(data_root: str | Path) -> dict[str, list[Table]]:
    """Read only the discovered datasets needed by the look-ahead analysis."""

    tables: dict[str, list[Table]] = defaultdict(list)
    root = Path(data_root)
    if not root.exists():
        return {}
    for spec in discover_datasets(root):
        if spec.kind not in LOOKAHEAD_RELEVANT_KINDS:
            continue
        if spec.path is None or not spec.path.is_file():
            continue
        tables[spec.kind].append(read_csv(spec.path))
    return dict(tables)


def attach_table_issues(
    result: DatasetResult,
    tables: Sequence[Table],
    root: Path,
) -> None:
    """Attach loader findings for reference inputs read outside discovery.

    Snapshot CSVs are reference inputs rather than validated datasets of
    their own, so their loader findings are reported on the analysis result
    with the source path prefixed. Structural errors are downgraded to
    warnings: a broken reference input is a coverage limitation of this
    analysis and must not fail the validation run on its own.
    """

    for table in tables:
        source = relative(table.path, root)
        for issue in table.issues:
            severity = (
                Severity.WARNING if issue.severity is Severity.ERROR else issue.severity
            )
            result.add(
                replace(
                    issue,
                    message=f"{source}: {issue.message}",
                    severity=severity,
                )
            )
