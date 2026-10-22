"""Validation for quarterly financial-results and integrated-filing exports.

The reporting period (``PERIOD ENDED`` / ``QUARTER END DATE``) and the exchange
dissemination timestamp are deliberately kept separate. A row disseminated
before the end of its reporting period is treated as an error, because such a
result could otherwise appear available before the information existed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ..csv_io import Row, Table
from ..models import DatasetResult
from ..parsing import (
    clean,
    format_date,
    format_timestamp,
    is_blank,
    parse_date,
    parse_timestamp,
)
from .common import add_duplicate_issues, check_schema, date_coverage


@dataclass(frozen=True)
class FinancialSchema:
    """Column layout for one financial-results export variant."""

    name: str
    required: tuple[str, ...]
    known: tuple[str, ...]
    period_column: str
    dissemination_column: str
    consolidation_column: str
    important_columns: tuple[str, ...]
    symbol_column: str | None = None
    submission_column: str | None = None
    secondary_timestamps: tuple[str, ...] = ()


LEGACY_SCHEMA = FinancialSchema(
    name="financial_results",
    required=(
        "COMPANY NAME",
        "PERIOD ENDED",
        "Exchange Dissemination Time",
    ),
    known=(
        "COMPANY NAME",
        "AUDITED / UNAUDITED",
        "CUMULATIVE / NON-CUMULATIVE",
        "CONSOLIDATED / NON-CONSOLIDATED",
        "IND AS/ NON IND AS",
        "PERIOD",
        "PERIOD ENDED",
        "RELATING TO",
        "** XBRL",
        "Exchange Received Time",
        "Exchange Dissemination Time",
        "Time Taken",
    ),
    period_column="PERIOD ENDED",
    dissemination_column="Exchange Dissemination Time",
    consolidation_column="CONSOLIDATED / NON-CONSOLIDATED",
    important_columns=(
        "AUDITED / UNAUDITED",
        "CONSOLIDATED / NON-CONSOLIDATED",
        "PERIOD",
        "RELATING TO",
    ),
    secondary_timestamps=("Exchange Received Time",),
)

INTEGRATED_SCHEMA = FinancialSchema(
    name="integrated_financials",
    required=(
        "SYMBOL",
        "COMPANY NAME",
        "QUARTER END DATE",
        "EXCHANGE DISSEMINATION TIME",
    ),
    known=(
        "SYMBOL",
        "COMPANY NAME",
        "QUARTER END DATE",
        "TYPE OF SUBMISSION",
        "AUDITED / UNAUDITED",
        "CONSOLIDATED / STANDALONE",
        "DETAILS",
        "XBRL",
        "BROADCAST DATE/TIME",
        "REVISED DATE/TIME",
        "REVISION REMARKS",
        "EXCHANGE DISSEMINATION TIME",
        "TIME TAKEN",
    ),
    period_column="QUARTER END DATE",
    dissemination_column="EXCHANGE DISSEMINATION TIME",
    consolidation_column="CONSOLIDATED / STANDALONE",
    important_columns=(
        "AUDITED / UNAUDITED",
        "CONSOLIDATED / STANDALONE",
        "TYPE OF SUBMISSION",
    ),
    symbol_column="SYMBOL",
    submission_column="TYPE OF SUBMISSION",
    secondary_timestamps=("BROADCAST DATE/TIME", "REVISED DATE/TIME"),
)


def detect_schema(table: Table) -> FinancialSchema:
    """Choose the known schema for a financial-results table."""

    headers = set(table.headers)
    if "QUARTER END DATE" in headers or "EXCHANGE DISSEMINATION TIME" in headers:
        return INTEGRATED_SCHEMA
    return LEGACY_SCHEMA


def _by_company_metrics(
    rows: list[Row],
    periods: dict[str, list[date]],
    disseminations: dict[str, list[datetime]],
) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        company = clean(row.get("COMPANY NAME"))
        if company:
            counts[company] += 1

    summary: dict[str, Any] = {}
    for company in sorted(counts):
        period_values = periods.get(company, [])
        dissemination_values = disseminations.get(company, [])
        summary[company] = {
            "records": counts[company],
            "period_start": format_date(min(period_values)) if period_values else None,
            "period_end": format_date(max(period_values)) if period_values else None,
            "first_dissemination": (
                format_timestamp(min(dissemination_values))
                if dissemination_values
                else None
            ),
            "last_dissemination": (
                format_timestamp(max(dissemination_values))
                if dissemination_values
                else None
            ),
        }
    return summary


def validate(
    table: Table,
    result: DatasetResult,
    expected_symbol: str | None = None,
) -> None:
    """Validate a parsed financial-results table."""

    schema = detect_schema(table)
    check_schema(
        table,
        result,
        required=schema.required,
        known=schema.known,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    expected = expected_symbol.upper() if expected_symbol else None
    parsed_periods: list[date] = []
    parsed_disseminations: list[datetime] = []
    periods_by_company: dict[str, list[date]] = defaultdict(list)
    disseminations_by_company: dict[str, list[datetime]] = defaultdict(list)
    publication_lags: list[int] = []
    duplicate_keys: dict[tuple[str, str, str, str], list[Row]] = defaultdict(list)

    for row in table.rows:
        company = clean(row.get("COMPANY NAME"))
        symbol = clean(row.get(schema.symbol_column)) if schema.symbol_column else ""
        period_text = row.get(schema.period_column)
        dissemination_text = row.get(schema.dissemination_column)

        if not company:
            result.add_error(
                "financials.company_missing",
                "Row has no company name.",
                row=row.number,
                column="COMPANY NAME",
            )

        if schema.symbol_column:
            if not symbol:
                result.add_error(
                    "financials.symbol_missing",
                    "Row has no symbol.",
                    row=row.number,
                    column=schema.symbol_column,
                )
            elif expected and symbol.upper() != expected:
                result.add_error(
                    "financials.symbol_mismatch",
                    (
                        f"Symbol {symbol!r} does not match the expected symbol "
                        f"{expected!r} from the filename."
                    ),
                    row=row.number,
                    column=schema.symbol_column,
                )

        period: date | None = None
        if is_blank(period_text):
            result.add_error(
                "financials.period_missing",
                f"Reporting-period date ({schema.period_column}) is missing.",
                row=row.number,
                column=schema.period_column,
            )
        else:
            period = parse_date(period_text)
            if period is None:
                result.add_error(
                    "financials.period_invalid",
                    f"Unparseable reporting-period date: {period_text!r}.",
                    row=row.number,
                    column=schema.period_column,
                )
            else:
                parsed_periods.append(period)
                if company:
                    periods_by_company[company].append(period)

        dissemination: datetime | None = None
        if is_blank(dissemination_text):
            result.add_error(
                "financials.dissemination_missing",
                (
                    "Exchange dissemination timestamp is missing; the result's "
                    "public availability cannot be established."
                ),
                row=row.number,
                column=schema.dissemination_column,
            )
        else:
            dissemination = parse_timestamp(dissemination_text)
            if dissemination is None:
                result.add_error(
                    "financials.dissemination_invalid",
                    (
                        "Unparseable exchange dissemination timestamp: "
                        f"{dissemination_text!r}."
                    ),
                    row=row.number,
                    column=schema.dissemination_column,
                )
            else:
                parsed_disseminations.append(dissemination)
                if company:
                    disseminations_by_company[company].append(dissemination)

        if period and dissemination:
            if dissemination.date() < period:
                result.add_error(
                    "financials.disseminated_before_period",
                    (
                        "Result was disseminated before its reporting period "
                        f"ended ({period.isoformat()}): "
                        f"{format_timestamp(dissemination)}."
                    ),
                    row=row.number,
                )
            else:
                publication_lags.append((dissemination.date() - period).days)

        for column in schema.secondary_timestamps:
            value = row.get(column)
            if is_blank(value):
                continue
            parsed_value = parse_timestamp(value)
            if parsed_value is None:
                result.add_warning(
                    "financials.secondary_timestamp_invalid",
                    f"{column} is not a valid timestamp: {value!r}.",
                    row=row.number,
                    column=column,
                )
            elif (
                dissemination is not None
                and column in {"Exchange Received Time", "BROADCAST DATE/TIME"}
                and dissemination < parsed_value
            ):
                result.add_warning(
                    "financials.dissemination_before_secondary_timestamp",
                    (
                        f"Exchange dissemination time is earlier than {column}: "
                        f"{format_timestamp(dissemination)} < "
                        f"{format_timestamp(parsed_value)}."
                    ),
                    row=row.number,
                )

        for column in schema.important_columns:
            if is_blank(row.get(column)):
                result.add_warning(
                    "financials.important_field_missing",
                    f"Important field {column} is empty.",
                    row=row.number,
                    column=column,
                )

        identity = symbol or company
        consolidation = clean(row.get(schema.consolidation_column))
        submission = (
            clean(row.get(schema.submission_column)) if schema.submission_column else ""
        )
        if identity and period:
            key = (
                identity,
                period.isoformat(),
                consolidation,
                submission,
            )
            duplicate_keys[key].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="financials.duplicate_record",
        label="financial result",
        preview=lambda key: (
            f"{key[0]} for period {key[1]} "
            f"({key[2] or 'consolidation not specified'}"
            f"{', ' + key[3] if key[3] else ''})"
        ),
    )

    dissemination_dates = [timestamp.date() for timestamp in parsed_disseminations]

    result.coverage = date_coverage(parsed_periods, schema.period_column)
    result.metrics.update(
        {
            "schema": schema.name,
            "expected_symbol": expected_symbol,
            "reporting_period_coverage": date_coverage(
                parsed_periods, schema.period_column
            ),
            "dissemination_coverage": date_coverage(
                dissemination_dates, schema.dissemination_column
            ),
            "publication_lag_days": {
                "min": min(publication_lags) if publication_lags else None,
                "max": max(publication_lags) if publication_lags else None,
            },
            "by_company": _by_company_metrics(
                table.rows,
                periods_by_company,
                disseminations_by_company,
            ),
            "duplicate_records": duplicate_extra_rows,
        }
    )
