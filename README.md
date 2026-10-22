# Backtest Reliability Analyzer

A read-only data-quality engine for the NSE datasets collected by this project.
It checks the files a backtest depends on, reports structural and semantic
problems with consistent `PASS` / `WARN` / `FAIL` statuses, and writes a stable
JSON report for later analysis.

This first feature is intentionally about **data validation**. It does not claim
to detect survivorship bias, look-ahead bias, or incorrect corporate-action
adjustments; those are separate features.

## Why backtest reliability matters

A backtest is only as trustworthy as its inputs. Missing prices, duplicate
trading dates, unparseable timestamps, mixed series, or an incomplete historical
universe can silently change returns, drawdowns, and rankings. Validation makes
those risks visible before a strategy is evaluated. It also keeps the
distinction between *what happened* and *when the information became public*,
which is essential for any later look-ahead analysis.

## Current dataset inventory

The repository currently contains NSE-derived data for INFY, RELIANCE, TCS, and
WIPRO, plus listing references and processed delisting exports. The figures
below describe the files present at the time this feature was implemented
(dataset window ending 22-Oct-2026).

| Dataset | Files | Rows | Observed coverage | Notes |
|---|---|---:|---|---|
| Historical prices | `data/raw/*-ALL-N.csv` | 1,257 / 1,259 / 1,251 / 1,263 | 2021-10-22 to 2026-10-22 | Per-symbol files; contains `EQ`, `BL`, and `T0` series. |
| Corporate actions | `data/reference/corporate_actions/*.csv` | 11 / 7 / 22 / 14 | 2021-10-26 to 2026-10-14 | Dividends, buybacks, meetings, demergers, bonus actions, etc. |
| Quarterly financial results | `data/reference/financial_results/CF-FR-*.csv` | 26 / 27 / 26 / 24 | Periods 2021-09-30 to 2024-12-31 | Separate exchange receipt and dissemination timestamps. |
| Integrated financial filings | `data/reference/financial_results/additional/*.csv` | 12 / 12 / 14 / 14 | Periods 2025-03-31 to 2026-09-30 | Headers contain trailing whitespace/newlines in the source. |
| Current listing reference | `data/reference/listing_history/EQUITY_L.csv` | 2,611 | Listing dates 1995-02-08 to 2026-10-22 | Current reference only; **not** the historical listed universe. |
| Company name changes | `data/reference/listing_history/namechange.csv` | 2,329 | 1996-05-01 to 2026-10-15 | Contains exact duplicate records in the collected source. |
| Symbol changes | `data/reference/listing_history/symbolchange.csv` | 1,067 | 1999-09-15 to 2026-10-15 | Historical change reference. |
| Delistings, all boards | `data/processed/delisted_companies_2021-2026.csv` | 77 | 2021-11-26 to 2026-10-16 | Processed 2021-2026 subset; includes main board, SME, and ITP. |
| Delistings, main board | `data/processed/main_board_delistings_2021-2026.csv` | 65 | 2021-11-26 to 2026-10-16 | Processed main-board subset of the file above. |

The `.xlsx` workbook under `data/reference/listing_history/` is retained as
source provenance for the processed delisting CSVs. This validator does not
parse Excel workbooks; it validates the CSV exports.

Sources are NSE historical-data, corporate-action, financial-filing, listing,
and delisting exports as collected in this repository. No network download is
performed by the validator.

## Project architecture

```text
bra/
  __main__.py              python -m bra entry point
  cli.py                   argument parsing and exit codes
  discovery.py             stable dataset discovery (read-only)
  csv_io.py                CSV loading and integrity diagnostics
  parsing.py               date, timestamp, number, and header normalisation
  models.py                Issue / DatasetResult / Report models
  runner.py                validation orchestration
  reporting.py             console and JSON rendering
  validators/
    common.py              shared schema, coverage, duplicate helpers
    prices.py              OHLC and trading-date validation
    corporate_actions.py   action identifiers, dates, duplicates, coverage
    financials.py          reporting period vs dissemination validation
    listings.py            current listings, name/symbol changes, delistings
tests/                     isolated pytest fixtures and tests
```

Validation logic is split by dataset semantics; orchestration, CSV handling, and
reporting stay separate. The engine uses only the Python standard library at
runtime.

## Setup

Requires Python 3.10 or newer. There are no runtime dependencies.

```bash
# Optional: install the package in editable mode with the test dependency
python -m pip install -e ".[dev]"

# Or install only the test runner and run from the project root
python -m pip install pytest
```

## Running validation

From the project root:

```bash
python -m bra
```

This reads `data/`, prints a console summary, and writes
`reports/validation_report.json`.

Useful options:

```bash
# Explicit paths
python -m bra --data-root data --json-report reports/validation_report.json

# Show every occurrence instead of the first few examples per issue code
python -m bra --verbose

# Validate a different read-only data tree
python -m bra --data-root /path/to/data
```

Exit codes:

- `0` — no dataset failed. Warnings alone do not fail the run.
- `1` — at least one dataset has a critical validation error.
- `2` — the JSON report could not be written.

The validator never rewrites, renames, or deletes source datasets. JSON and
console output are deterministic: there is no generation timestamp, and datasets
are sorted in a stable order.

## Reports and interpretation

Console output contains a dataset table, an overall status, and grouped findings.
Each finding has an issue code and, where applicable, a physical CSV line number.

The JSON report has this shape:

```json
{
  "schema_version": 1,
  "tool": "backtest-reliability-analyzer",
  "data_root": "data",
  "overall_status": "FAIL",
  "summary": {
    "dataset_count": 21,
    "pass": 0,
    "warn": 20,
    "fail": 1,
    "error_count": 117,
    "warning_count": 57
  },
  "datasets": [
    {
      "id": "prices:INFY",
      "category": "historical_prices",
      "label": "Historical prices - INFY",
      "path": "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
      "status": "WARN",
      "row_count": 1257,
      "coverage": {
        "date_column": "Date",
        "start": "2021-10-22",
        "end": "2026-10-22"
      },
      "metrics": {},
      "error_count": 0,
      "warning_count": 4,
      "issues": [
        {
          "code": "csv.bom",
          "severity": "warning",
          "message": "File starts with a UTF-8 BOM; it was decoded transparently."
        }
      ]
    }
  ]
}
```

Status meanings:

- `PASS` — no errors and no warnings.
- `WARN` — no critical errors, but quality issues worth reviewing.
- `FAIL` — critical integrity or semantic validation errors.

Typical warnings in the collected data are a UTF-8 BOM, padded or newline-laden
headers, auxiliary-series OHLC anomalies, identifier whitespace, and a malformed
ISIN in one delisting row. A critical failure in the collected data is the
presence of exact duplicate company-name-change records.

## Implemented functionality

CSV integrity:

- Missing, unreadable, empty, header-only, malformed, and non-UTF-8 files.
- Blank and duplicate headers after normalization.
- Missing and unexpected columns.
- UTF-8 BOMs, surrounding whitespace, tabs, and embedded newlines in headers.
- Field-count mismatches, blank lines, and row counts.
- File-level problems are attached to the dataset result; no source file is modified.

Historical prices:

- Date and OHLC numeric parsing with Indian digit grouping.
- Missing, unparseable, and non-positive values.
- Duplicate trading dates per symbol **and series** (different series on the same
  date are legitimate and are reported as a metric, not a duplicate error).
- OHLC relationships: strict errors for the primary `EQ` series and warnings for
  auxiliary series such as `BL` and `T0`.
- Monotonic date ordering per series.
- Large calendar gaps in `EQ`, explicitly **not** classified as missing trading
  sessions without an exchange calendar.
- Overall/per-symbol date ranges, record counts, series counts, and coverage.

Corporate actions:

- Required symbol, purpose, and ex-date; company-name and entitlement-date checks.
- Ex-date, record-date, and book-closure date parsing.
- Duplicate action records by symbol/ex-date/purpose.
- Counts by company, purpose, series, and company-purpose pairs.
- Coverage by symbol and overall. Purposes are preserved verbatim; no action is
  assumed to be a split.

Financial results:

- Both legacy quarterly-results and integrated-filing schemas.
- Reporting-period parsing and exchange dissemination timestamp parsing.
- Missing/unparseable dissemination timestamps.
- Guarantees that the reporting period and dissemination time stay separate.
- Errors when dissemination is recorded before the reporting period ends.
- Warnings for dissemination earlier than receipt/broadcast timestamps.
- Duplicate results, important missing fields, counts/coverage by company, and
  publication-lag metrics.

Listings and delistings:

- Current listing dates, identifiers, ISIN format, series, and duplicate
  symbol/series records.
- Name-change and symbol-change effective dates, identifiers, and exact duplicate
  records.
- Delisting dates, identifiers, board/type, duplicate records, and coverage.
- Current listings and historical delistings are reported as separate dataset
  results; the current listing file is not treated as the historical universe.

Automated tests cover valid/invalid prices, duplicate dates, missing values,
invalid OHLC, malformed/empty CSVs, corporate actions, financial timestamp
parsing, listings/delistings, discovery, report generation, and CLI exit codes.
All test fixtures live in temporary directories.

## Not implemented yet

- Survivorship-bias detection.
- Look-ahead-bias detection or event-time availability analysis.
- Verification or application of corporate-action price adjustments.
- An authoritative NSE trading calendar or holiday-aware session completeness.
- Validation of the binary `.xlsx` delisting workbook.
- Cross-dataset reconciliation (for example, symbol changes vs price history, or
  delisting dates vs last trading dates).
- Fetching or refreshing datasets from NSE.
- A database, API server, frontend, or AI component.

## Assumptions and known limitations

- Files are expected to be UTF-8 (with or without BOM). Invalid UTF-8 is a
  critical failure.
- NSE dates are parsed as day-first (`DD-Mon-YYYY`, ISO, or `DD/MM/YYYY`), not
  as ambiguous US month-first dates.
- Exchange timestamps are treated as recorded local exchange times. The source
  contains no timezone offset, so no timezone conversion is attempted.
- A result is considered potentially public only from its recorded exchange
  dissemination timestamp. The validator checks that this timestamp is not before
  the reporting period end, but it does not model intraday release effects.
- Prices contain multiple market series. Duplicate dates are evaluated within a
  symbol/series pair. OHLC anomalies in auxiliary series are warnings because
  those series can represent special sessions or auction prices.
- No weekend or exchange-holiday completeness check is made. A calendar gap over
  10 days in the `EQ` series is only a warning for human review.
- Delisting CSVs are a processed 2021-2026 subset. Their source workbook is not
  parsed. The main-board file is a subset of the all-boards file, not an
  independent universe.
- The listing reference is a current snapshot. It must not be read as a complete
  historical list of companies that existed at any past date.
- The collected source data already contains quality defects. The validator
  reports them; it does not repair the source files.
- Reports are generated in `reports/`, which is ignored by Git. Source datasets
  under `data/` are preserved.

## Testing

```bash
python -m pytest
```

The suite uses `tmp_path` fixtures and never reads or writes the real `data/`
directory. Linting/formatting is optional:

```bash
ruff check bra tests
ruff format --check bra tests
```

## Recommended next commands

```bash
python -m pytest
python -m bra --verbose
git status
```
