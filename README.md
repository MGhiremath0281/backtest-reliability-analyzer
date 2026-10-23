# Backtest Reliability Analyzer

A read-only data-quality engine for the NSE datasets collected by this project.
It checks the files a backtest depends on, reports structural and semantic
problems with consistent `PASS` / `WARN` / `FAIL` statuses, and writes a stable
JSON report for later analysis.

The project is intentionally about **data validation, reproducible preparation,
and evidence-based coverage analysis**. It builds normalized, derived datasets,
audits whether the data can support survivorship-bias, look-ahead-bias, and
corporate-action analysis, and includes a read-only Survivorship-Bias Analyzer.
That analyzer measures point-in-time universe and price coverage, delisted
security matching, and identifier risks; it does **not** claim that
survivorship bias is absent or quantify its return impact. Raw source files are
never modified; every normalized output is derived from them and can be
regenerated.

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

Feasibility samples collected for the historical-universe investigation (hashes
recorded in the manifests; source files are never rewritten):

| Reference sample | Files | Coverage / rows | Notes |
|---|---|---|---|
| Point-in-time index constituents | `data/reference/index_constituents/` | Jun 2013, Sep 2013, Mar 2022, Sep 2026 | Monthly ZIPs of per-index PDFs plus parsed NIFTY 50 CSVs; month-end constituent membership. |
| Index-change press releases | `data/reference/index_constituents/snapshots_pdfs/` | Sep 2013 → Sep 2026 (samples) | Effective dates and IN/OUT symbols; see the caveat about soft-404 responses. |
| Delisted-security price samples | `data/reference/price_samples/bhavcopy_zips/` | 1999-01-05, 2014-01-01/02, 2024-07-08 | Legacy and modern bhavcopies; confirm delisted symbols are retrievable. |
| Legacy delisted reference CSV | `data/reference/price_samples/delisted.csv` | 328 rows, 2002 → Nov 2020 | Windows-1252 encoded and **incomplete**; rejected in favor of the official workbook. |

The full source-by-source comparison, exact coverage, feasibility verdicts, and
the recommended collection plan are documented in
[`docs/historical-universe-gap.md`](docs/historical-universe-gap.md).

The `.xlsx` workbook under `data/reference/listing_history/` is retained as
source provenance for the processed delisting CSVs. It is now read directly by
the preparation pipeline; its primary `delisted` sheet is the full-history event
list, and its auxiliary sheets are audited but not merged.

### Normalized derived datasets

`python -m bra.prepare` writes these files under `data/processed/normalized/`.
They retain source traceability (`source_file`, `source_line`/`source_row`) and
review flags. Existing processed delisting CSVs are not overwritten.

| Derived dataset | Output file | Input rows | Output rows |
|---|---|---:|---:|
| Prices | `prices.csv` | 5,030 | 5,030 |
| Corporate actions | `corporate_actions.csv` | 54 | 54 |
| Legacy financial results | `financial_results_legacy.csv` | 103 | 103 |
| Integrated financial filings | `financial_results_integrated.csv` | 52 | 52 |
| Current listings | `current_listings.csv` | 2,611 | 2,611 |
| Name changes | `name_changes.csv` | 2,329 | 2,078 |
| Symbol changes | `symbol_changes.csv` | 1,067 | 1,067 |
| Delistings | `delistings.csv` | 460 | 460 |

The only row-count reduction is the name-change event dataset: 251 exact
duplicate copies are represented once. Every collapsed source line is recorded
in `source_lines`, and `source_record_count` records the group size. Conflicting
spellings and events shared across symbols are retained and flagged.

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
  xlsx_io.py               read-only standard-library XLSX reader
  parsing.py               date, timestamp, number, and header normalisation
  derived_schema.py        shared derived headers, keys, and review flags
  models.py                Issue / DatasetResult / Report models
  runner.py                validation orchestration
  reporting.py             console and JSON rendering
  prepare/
    __main__.py            python -m bra.prepare entry point
    common.py              atomic writer, hashing, normalization helpers
    market.py              price, corporate-action, financial transforms
    reference.py           listing, change-history, delisting transforms
    inventory.py           raw/derived file and workbook-sheet inventory
    audit.py               cross-dataset audit and Markdown rendering
    runner.py              prepare orchestration
  validators/
    common.py              shared schema, coverage, duplicate helpers
    prices.py              OHLC and trading-date validation
    corporate_actions.py   action identifiers, dates, duplicates, coverage
    financials.py          reporting period vs dissemination validation
    listings.py            current listings, name/symbol changes, delistings
    derived.py             independent validation of normalized outputs
    survivorship/
      core.py              shared records, constants, read-only parsing
      universe.py          dated membership snapshots and coverage gaps
      matching.py          price coverage, delisted match classes, identifiers
      backtest.py          BacktestConfig and backtest-specific checks
      analysis.py          orchestration, metrics, and structured findings
    lookahead/
      core.py              lookahead findings, records, and timeline structures
      engine.py            financial dissemination and price availability audit
  api/
    __main__.py            python -m bra.api entry point
    app.py                 FastAPI application factory, CORS, exception handlers
    config.py              ApiConfig with BRA_STORAGE_DIR / BRA_DATA_ROOT
    schemas.py             canonical schema definitions, aliases, type inference
    models.py              Pydantic request & response models
    storage.py             StorageManager (isolated datasets, analyses, runs, reports)
    mapping.py             column mapping validator and auto-suggester
    preparation.py         dataset normalizer generating prepared tables
    adapters.py            unified bridge to underlying analysis & validation engine
    routers/               versioned routers (health, datasets, schemas, validation,
                           survivorship, lookahead, corporate_actions, runs, reports)
tests/                     isolated pytest fixtures and tests
```

Validation and preparation logic is split by dataset semantics; orchestration,
CSV/XLSX handling, reporting, and API routers stay cleanly separated. The core CLI
engine uses only the Python standard library at runtime; the API layer uses FastAPI
and Pydantic.

## Setup

Requires Python 3.10 or newer.

```bash
# Install the package in editable mode with development & API dependencies
python -m pip install -e ".[dev]"

# Or run tests directly
python -m pytest
```

## Running preparation and validation

Build the normalized derived datasets and the audit first. This step is
read-only with respect to every source file:

```bash
python -m bra.prepare
```

It writes eight CSVs to `data/processed/normalized/`, a machine-readable audit
to `reports/data_audit.json` (git-ignored), and a tracked human-readable audit
to `docs/data-audit.md`. It refuses to publish if a source hash changes during
the run.

Then run validation. Derived datasets are discovered automatically **only when
they exist**, so validation works with or without a preparation run:

```bash
python -m bra
```

This reads `data/`, prints a console summary, and writes
`reports/validation_report.json`.

Useful options:

```bash
# Explicit paths
python -m bra --data-root data --json-report reports/validation_report.json

# Preparation with explicit paths
python -m bra.prepare --data-root data \
  --output-dir data/processed/normalized \
  --audit-json reports/data_audit.json \
  --audit-doc docs/data-audit.md

# Show every occurrence instead of the first few examples per issue code
python -m bra --verbose

# Validate a different read-only data tree
python -m bra --data-root /path/to/data
```

### Survivorship-Bias Analyzer

The analyzer always runs as the extra dataset `survivorship:analysis` when any
relevant input is present. Without backtest flags it performs the general
data-coverage audit. Supplying backtest flags enables the backtest-specific
checks; anything the collected evidence cannot support is reported as
`unavailable` with the reason and the source that would be required.

```bash
# General data-coverage audit (the default)
python -m bra

# Assess one index backtest over an explicit interval
python -m bra --backtest-index "NIFTY 50" \
  --backtest-start 2022-01-01 --backtest-end 2022-12-31

# Explicit universe, with a required per-symbol price-coverage ratio
python -m bra --backtest-symbol INFY --backtest-symbol TCS \
  --backtest-start 2022-01-01 --backtest-end 2022-12-31 \
  --backtest-min-price-coverage 0.9
```

The analyzer reads dated index-constituent CSVs from
`data/reference/index_constituents/extracted_csv/` as reference inputs. It never
interpolates membership between snapshots, never treats current listings,
delisting events, symbol equality, or price history as proof of historical index
membership, and never writes to any source dataset. Invalid backtest
configuration (for example a missing interval) is reported as a warning in the
report; an unparseable CLI date is a usage error and exits with code `2`.

For requested membership snapshot dates, rebalancing dates, and identifier
mappings, construct `survivorship.BacktestConfig` (or use
`survivorship.build_backtest_config`) from Python and pass it as
`run_validation(..., backtest=config)` or `survivorship.analyze(...,
backtest=config)`. Missing evidence is reported per check instead of being
substituted with price symbols or present-day listings.

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
    "dataset_count": 30,
    "pass": 3,
    "warn": 26,
    "fail": 1,
    "error_count": 117,
    "warning_count": 98
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

The `survivorship:analysis` dataset adds these metric blocks:

| Block | Meaning |
|---|---|
| `analysis` | Mode (`general_data_coverage_audit` or `backtest_specific_assessment`), inputs read, and the explicit no-magnitude conclusion. |
| `current_listing_snapshot` | Present-day listing counts and the `is_point_in_time_universe: false` limit. |
| `price_coverage` | Symbols, rows, and actual date ranges in the collected price data. |
| `delisted_price_coverage` | Per-security match classes (`confirmed`, `candidate`, `ambiguous`, `unmatched`) with explicit denominators and bounded examples. |
| `index_membership` | Dated snapshot counts, discovered indexes, exact snapshot dates, sparse-coverage gaps, and the September 2013 archive floor. |
| `universe_price_coverage` | Price coverage for the reconstructed historical universe, measured against observed priced trading days. |
| `identifier_reuse`, `delisting_symbol_reuse`, `symbol_changes`, `continuity_evidence` | Relisting, identifier-reuse, ambiguous mapping, and symbol/name continuity evidence. |
| `backtest_assessment` | Backtest config summary, per-check `status`/`reason`, universe resolution, membership and price coverage inside the interval, delisted securities in the interval, rebalancing-date verification, and the unavailable bias-impact inputs. |
| `findings` | Separated confirmed facts, potential risks, coverage limitations, passed checks, unverifiable conclusions, and backtest results. |

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
- **Record-date / ex-date ordering**: when both are present and valid, a record
  date that precedes the ex-date is flagged as a confirmed inconsistency
  (`corporate_actions.confirmed_inconsistency`), since standard semantics place
  the ex-date before the record date.
- **Price-coverage matching**: corporate actions are matched against available
  price data by symbol and date. When pre-event or post-event price rows are not
  found near the ex-date, a `corporate_actions.price_coverage` warning is issued
  as a data limitation. Missing coverage does not imply incorrect prices.
- **Suspicious price discontinuities** around split and bonus events: the
  pre-event close price and post-event close price are compared. The expected
  price ratio is derived from the purpose text (e.g. ``Bonus 1:1`` → ratio ≈ 0.5).
  A 20% tolerance band is used; if the actual ratio falls outside the band by
  more than 2× the expected ratio, the finding is classified as
  `corporate_actions.suspicious_adjustment`; if within the band, it is
  `insufficient_evidence`. The classification is never presented as a definitive
  claim of incorrect adjustment when the source data cannot establish whether
  prices are adjusted or when the action became public.
- **Classification of findings**: confirmed inconsistency (record before ex-date),
  suspicious adjustment (price move inconsistent with the action's expected effect),
  and insufficient evidence (cannot determine one way or the other because price
  data is missing or the action's semantics are ambiguous). Severity is always
  `warning` for coverage and discontinuity findings; only the record-before-ex-date
  check produces an `error`.

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

Survivorship-bias coverage analysis:

- Present-day listing snapshot limits, with `is_point_in_time_universe: false`
  and no use of listing dates as historical index membership.
- Reconstruction of the historical universe only from dated, authoritative
  index-constituent snapshots, with per-index dates and explicit gap reporting.
- No interpolation between snapshots and no inference from current listings,
  delisting events, symbol equality, or price presence.
- Delisted-security matching classified as `confirmed` (ISIN continuity plus
  temporally consistent price rows), `candidate` (symbol or dated symbol-change
  chain), `ambiguous` (conflicting evidence), or `unmatched`.
- Price coverage for the reconstructed universe, with explicit denominators,
  observed trading days, bounded examples, and no silent member dropping.
- Identifier-reuse, reused delisting symbol, ambiguous symbol-change mapping,
  and symbol/name continuity evidence, each reported as evidence rather than
  identity proof.
- Optional `BacktestConfig` or CLI assessment of a target index or explicit
  universe, interval, requested membership snapshots, rebalancing dates,
  identifier mappings, and a minimum price-coverage ratio.
- Every backtest check reports `ok`, `unavailable` with the missing source,
  `not_applicable`, or `invalid`; the return impact of survivorship bias is
  never fabricated from coverage data.
- Structured findings separate confirmed facts, potential risks, coverage
  limitations, passed checks, and unverifiable conclusions.

Reproducible preparation:

- Read-only standard-library XLSX reading, including all workbook sheets and
  document properties.
- Normalization of column names, ISO dates/timestamps, Indian-grouped numbers,
  and harmless identifier whitespace in derived data only.
- Stable column mappings and per-row `source_file` / `source_line` traceability.
- Exact-duplicate collapse for name-change events with every source line kept.
- Retention and flagging of conflicting spellings, shared events, no-op symbol
  changes, malformed ISINs, auxiliary-sheet conflicts, and relisted identifiers.
- Atomic, deterministic CSV writes; reruns over unchanged inputs are byte-identical.
- A source-hash guard that refuses to publish an audit if a source changed.
- `reports/data_audit.json` plus tracked `docs/data-audit.md`.

Derived-data validation:

- Independent schema, key, date, timestamp, identifier, ISIN, and coverage checks.
- Duplicate-key detection on the documented natural key for each derived dataset.
- OHLC relationships rechecked from normalized prices.
- Publication-lag recomputation for both financial schemas.
- Name-change source-line/count consistency checks.
- Review flags are surfaced as warnings, never silently discarded.

Automated tests cover valid/invalid prices, duplicate dates, missing values,
invalid OHLC, malformed/empty CSVs, corporate actions, financial timestamp
parsing, listings/delistings, discovery, report generation, CLI exit codes, the
Survivorship-Bias Analyzer's snapshot/universe reconstruction, match classes,
identifier risks, backtest configuration and assessment, JSON output, and
deterministic reruns. All test fixtures live in temporary directories; the
collected datasets under `data/` are never read or modified by the tests.

## Data audit findings

The full evidence is in `docs/data-audit.md` and `reports/data_audit.json`.
Headline facts from the collected files:

- Prices: 5,030 rows across 4 symbols and 3 series (`EQ`, `BL`, `T0`); EQ
  coverage is 2021-10-22 to 2026-10-22 with 1,240 dates per symbol.
- Corporate actions: 54 rows; all 54 ex-dates match an EQ trading date.
- Financial results: 103 legacy rows (periods 2021-09-30 to 2024-12-31) and 52
  integrated rows (2025-03-31 to 2026-09-30), with dissemination timestamps.
- Current listings: 2,611 rows; 2,609 distinct symbols/ISINs (two ISINs are
  shared across series). This is a snapshot, not a historical universe.
- Name changes: 2,329 raw rows; 117 exact duplicate groups (251 extra records),
  5 same-symbol/date spelling-variant groups, and 12 shared-event groups. Exact
  copies are collapsed only in the derived event file; all conflicts are kept.
- Symbol changes: 1,067 rows; 10 no-op changes, 9 shared new-symbol targets, and
  17 same-company/date multi-record groups. All are retained and flagged.
- Delistings: the workbook primary sheet has 460 rows (2002-04-15 to
  2026-10-16) and exactly contains the 77 processed 2021-2026 rows. The
  auxiliary compulsory-delisting sheet has one date conflict (`AUSTRAL`), which
  remains flagged and unmerged.

Assessment:

- **A. Survivorship bias — cannot be detected or quantified from the current
  data.** The analyzer verifies only three dated membership snapshots (Jun 2013,
  Mar 2022, Sep 2026) and finds no price match for any of the 454 grouped
  delisted securities in the processed history; 73 of the 77 recorded universe
  symbols also lack complete price coverage. There is therefore no continuous
  point-in-time universe and no delisted-security return history from which to
  measure bias. The current listing file must not be used as a historical
  universe. The analyzer reports these coverage limits explicitly rather than
  treating missing data as evidence of no bias.
- **B. Look-ahead bias — partially supported for event timing only.** Financial
  dissemination timestamps and effective dates exist, but corporate-action
  announcement times, historical universe membership, and availability
  timestamps on prices do not.
- **C. Corporate actions — event dates supported; adjustments not verifiable.**
  Ex-dates are present and consistent with trading dates, but there are no
  adjustment factors or adjusted prices, and action ratios exist only in free
  text.

## REST API Layer (FastAPI)

BRA includes a production-ready, asynchronous REST API layer built on FastAPI and Pydantic. It exposes all core validation and analyzer engines (data quality, survivorship bias, look-ahead bias, corporate actions, and combined analysis runs) via structured endpoints.

### Key Capabilities
- **Zero hardcoding**: All findings, summaries, metrics, and identifiers are dynamically derived from actual dataset files and real analyzer engines.
- **Dual dataset support**: Works seamlessly with both canonical repository datasets (`existing-data`) and newly uploaded custom CSV files from diverse data providers.
- **Dynamic schema mapping & preparation**: Automatically detects candidate schemas, provides safe column mapping suggestions, and normalizes datasets into prepared tables without mutating source uploads.
- **Dataset isolation & security**: Strict path traversal prevention, isolated UUID storage per dataset, configurable upload size limits, and sanitization of internal exception traces.
- **Persistence without heavy dependencies**: File-backed JSON and CSV persistence across API restarts without external database or message broker requirements.
- **OpenAPI / Swagger documentation**: Interactive API explorer automatically generated at `/docs` and ReDoc at `/redoc`.

---

### Starting the API

Run the API using either the module runner or Uvicorn:

```bash
# Using the module entry point (defaults to 127.0.0.1:8000)
python -m bra.api --host 0.0.0.0 --port 8000

# Or directly with uvicorn
uvicorn bra.api.app:app --host 0.0.0.0 --port 8000 --reload
```

#### Environment Configuration

| Variable | Default | Description |
|---|---|---|
| `BRA_STORAGE_DIR` | `<repo_root>/storage` | Root path for isolated datasets, analyses, runs, and reports. |
| `BRA_DATA_ROOT` | `<repo_root>/data` | Path to canonical repository data. |
| `BRA_MAX_UPLOAD_SIZE_BYTES` | `104857600` (100 MB) | Maximum upload payload size in bytes. |

---

### Complete Endpoint Reference

#### 1. Health & System
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic application health check. |
| `GET` | `/api/v1/health` | Service health including storage accessibility. |
| `GET` | `/api/v1/metadata` | Registered analyzers, supported schemas, and system capabilities. |

#### 2. Dataset Management
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/datasets/upload` | Upload one or multiple CSV files to create a new dataset. |
| `GET` | `/api/v1/datasets` | List all available datasets (including canonical `existing-data`). |
| `GET` | `/api/v1/datasets/{id}` | Get dataset metadata, files, and status. |
| `GET` | `/api/v1/datasets/{id}/preview` | Preview real rows and columns with pagination (`limit`, `offset`, `file_id`). |
| `GET` | `/api/v1/datasets/{id}/schema` | Detected candidate schemas, column types, and candidate matches. |
| `POST` | `/api/v1/datasets/{id}/validate` | Run structural and semantic data-quality checks on raw files. |
| `GET` | `/api/v1/datasets/{id}/validation` | Retrieve current validation results for a dataset. |
| `GET` | `/api/v1/datasets/{id}/quality-summary` | Summary of dataset validation results and status. |
| `DELETE` | `/api/v1/datasets/{id}` | Delete an uploaded dataset (canonical datasets are protected). |
| `POST` | `/api/v1/datasets/{id}/delete-request` | Soft deletion request / validation endpoint. |

#### 3. Schema Mapping & Preparation
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/schemas` | List all canonical schema definitions (prices, corporate actions, etc.). |
| `GET` | `/api/v1/schemas/{type}` | Retrieve details, required fields, and column aliases for a schema. |
| `POST` | `/api/v1/datasets/{id}/mapping` | Save or auto-suggest (`auto_suggest=true`) provider-to-canonical mappings. |
| `GET` | `/api/v1/datasets/{id}/mapping` | Retrieve configured column mappings for a dataset. |
| `POST` | `/api/v1/datasets/{id}/prepare` | Generate normalized derived working tables from mapped CSVs. |
| `GET` | `/api/v1/datasets/{id}/preparation` | Retrieve preparation status, generated files, and warnings. |

#### 4. General Validation
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/validate` | Execute general data-quality validation across raw or prepared files. |
| `GET` | `/api/v1/validations/{id}` | Retrieve general validation record and results. |
| `GET` | `/api/v1/validations/{id}/findings` | Retrieve individual findings with optional severity filter. |
| `GET` | `/api/v1/validations/{id}/summary` | Aggregate finding counts by severity and issue classification. |

#### 5. Survivorship Bias Analyzer
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/analyze/survivorship` | Execute survivorship-bias audit on historical universe & delistings. |
| `GET` | `/api/v1/analyze/survivorship/{id}` | Retrieve survivorship analysis summary, coverage, and metrics. |
| `GET` | `/api/v1/analyze/survivorship/{id}/universe` | Point-in-time universe snapshot coverage and gap details. |
| `GET` | `/api/v1/analyze/survivorship/{id}/delisted` | Delisted security matching rates, prices, and identifier checks. |
| `GET` | `/api/v1/analyze/survivorship/{id}/findings` | Findings specifically generated by survivorship validator. |

#### 6. Look-Ahead Bias Analyzer
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/analyze/lookahead` | Execute look-ahead bias audit (publication timing vs backtest dates). |
| `GET` | `/api/v1/analyze/lookahead/{id}` | Retrieve lookahead audit summary, verified metrics, and limitations. |
| `GET` | `/api/v1/analyze/lookahead/{id}/findings` | Findings (leakage, timing mismatches, missing timestamps). |
| `GET` | `/api/v1/analyze/lookahead/{id}/timeline` | Ordered publication timeline across financial and price events. |

#### 7. Corporate Actions Analyzer
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/analyze/corporate-actions` | Execute corporate actions consistency and price coverage audit. |
| `GET` | `/api/v1/analyze/corporate-actions/{id}` | Retrieve corporate actions audit summary and findings. |
| `GET` | `/api/v1/analyze/corporate-actions/{id}/findings` | Findings (date mismatches, missing prices around ex-dates). |
| `GET` | `/api/v1/analyze/corporate-actions/{id}/coverage` | Symbol-level corporate action coverage metrics. |

#### 8. Combined Analysis Runs
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/analysis-runs` | Orchestrate multi-analyzer runs (survivorship, lookahead, corporate actions). |
| `GET` | `/api/v1/analysis-runs` | List analysis runs with completion status and timestamps. |
| `GET` | `/api/v1/analysis-runs/{id}` | Retrieve run metadata, analyzer statuses, and consolidated summary. |
| `GET` | `/api/v1/analysis-runs/{id}/findings` | Combined findings from all executed analyzers. |
| `GET` | `/api/v1/analysis-runs/{id}/summary` | Consolidated severity and finding counts. |
| `POST` | `/api/v1/analysis-runs/{id}/cancel` | Cancel an in-flight analysis run. |
| `GET` | `/api/v1/analysis-runs/{id}/events` | Retrieve lifecycle event log for the run. |

#### 9. Reports & Exports
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/reports` | List all generated reports across runs and analyses. |
| `GET` | `/api/v1/reports/{id}` | Retrieve report metadata, summary, and download URLs. |
| `GET` | `/api/v1/reports/{id}/download?format=json` | Download full report as structured JSON. |
| `GET` | `/api/v1/reports/{id}/download?format=csv` | Download findings as a tabular CSV. |
| `GET` | `/api/v1/reports/{id}/download?format=pdf` | Returns HTTP 501 with format requirements. |
| `GET` | `/api/v1/reports/{id}/download?format=xlsx` | Returns HTTP 501 with format requirements. |

---

### Step-by-Step Workflow Examples

#### 1. Uploading Custom Provider CSVs

Upload one or more CSV files from a market data provider:

```bash
curl -X POST "http://localhost:8000/api/v1/datasets/upload" \
  -F "files=@my_prices.csv" \
  -F "files=@my_corporate_actions.csv" \
  -F "name=Vendor-X-2026"
```

Response:
```json
{
  "dataset_id": "782f0542-a728-4e50-a924-a3f24bf71a5c",
  "name": "Vendor-X-2026",
  "files": [
    {
      "file_id": "93eb5a43-85f0-48e0-a7d1-e630cf5ad58f",
      "filename": "my_prices.csv",
      "file_size": 245000,
      "row_count": 5200,
      "columns": ["trade_date", "ticker", "close_price", "open_price", "high_price", "low_price", "vol"]
    }
  ],
  "status": "uploaded"
}
```

#### 2. Inspecting Detected Schema and Auto-Mapping

Inspect what BRA detected:

```bash
curl "http://localhost:8000/api/v1/datasets/782f0542-a728-4e50-a924-a3f24bf71a5c/schema"
```

Generate safe mapping suggestions automatically:

```bash
curl -X POST "http://localhost:8000/api/v1/datasets/782f0542-a728-4e50-a924-a3f24bf71a5c/mapping" \
  -H "Content-Type: application/json" \
  -d '{"auto_suggest": true}'
```

#### 3. Preparing the Normalized Dataset

Transform the mapped files into standardized tables without modifying original uploads:

```bash
curl -X POST "http://localhost:8000/api/v1/datasets/782f0542-a728-4e50-a924-a3f24bf71a5c/prepare"
```

#### 4. Executing a Combined Analysis Run

Run selected analyzers against the prepared dataset:

```bash
curl -X POST "http://localhost:8000/api/v1/analysis-runs" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "782f0542-a728-4e50-a924-a3f24bf71a5c",
    "analyzers": ["survivorship", "lookahead", "corporate_actions"],
    "config": {
      "start_date": "2022-01-01",
      "end_date": "2026-10-01"
    }
  }'
```

Response:
```json
{
  "run_id": "98124b61-9c88-444a-912f-6825e3646399",
  "dataset_id": "782f0542-a728-4e50-a924-a3f24bf71a5c",
  "status": "completed",
  "analyzer_statuses": {
    "survivorship": "completed",
    "lookahead": "completed",
    "corporate_actions": "completed"
  },
  "summary": {
    "total_findings": 3,
    "severity_counts": {"FAIL": 1, "WARN": 2, "INFO": 0}
  },
  "report_id": "841b897f-dfa2-4a0b-93ff-eb80c85b1a62"
}
```

#### 5. Exporting Findings to CSV or JSON

Download the full audit report as CSV:

```bash
curl "http://localhost:8000/api/v1/reports/841b897f-dfa2-4a0b-93ff-eb80c85b1a62/download?format=csv" -o findings.csv
```

Or as JSON:

```bash
curl "http://localhost:8000/api/v1/reports/841b897f-dfa2-4a0b-93ff-eb80c85b1a62/download?format=json" -o report.json
```

#### 6. Analyzing Existing Repository Data

To analyze the canonical repository datasets directly without re-uploading, pass `dataset_id = "existing-data"`:

```bash
curl -X POST "http://localhost:8000/api/v1/analysis-runs" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "existing-data",
    "analyzers": ["survivorship", "lookahead", "corporate_actions"]
  }'
```

---

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
- Delisting CSVs are a processed 2021-2026 subset. The delisting workbook is
  read directly for the full-history event list; its auxiliary sheets are audited
  but not merged because they overlap the primary sheet and contain a date
  conflict. The main-board file is a subset of the all-boards file, not an
  independent universe.
- Derived data is written separately under `data/processed/normalized/`. Raw
  files and the existing processed delisting CSVs are never rewritten.
- The listing reference is a current snapshot. It must not be read as a complete
  historical list of companies that existed at any past date. A symbol/ISIN that
  appears in both the current snapshot and the delisting history is retained in
  both and flagged as a time-dependent identifier.
- The collected source data already contains quality defects. The validator
  reports them; it does not repair the source files.
- Reports are generated in `reports/`, which is ignored by Git. The tracked
  audit document is `docs/data-audit.md`. Source datasets under `data/` are
  preserved.

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

## Continuous integration

CI is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and
runs on every push to any branch, on pull requests targeting `main`, and on
manual workflow dispatch. Each run installs the project with its development
dependencies on Python 3.12 (with pip caching) and then performs, in order:

1. `ruff check bra tests` — lint the package and tests with the repository's
   Ruff configuration.
2. `python -m pytest` — the complete test suite. Fixtures are isolated in
   temporary directories; the real `data/` tree is never touched.
3. `python -m bra.prepare` — regenerate the normalized datasets and the audit
   (raw files are only read), then verify with `git diff` that the outputs are
   byte-identical to the committed derived datasets.
4. `python scripts/ci_validate.py` — run `python -m bra` and gate its result.

Validation exits `1` because of one documented finding: the raw `namechange.csv`
contains 117 groups of exact duplicate records (`listings.duplicate_record`;
see [`docs/data-audit.md`](docs/data-audit.md)). CI never edits raw data and
never converts that finding into a silent pass: the gate tolerates exactly that
dataset, issue code, and group count, surfaces it as a warning annotation in
the run summary, and fails for any other failing dataset, any other issue on a
failing dataset, or any change in the duplicate-group count.

No secrets, API keys, network downloads, or files outside Git are required.

When a run fails, open the failed job under the Actions tab: each check is a
separate step with its own log. The workflow also uploads
`reports/validation_report.json` and `reports/data_audit.json` as the
`json-reports` artifact for machine-readable diagnosis. Every step can be
reproduced locally with the commands shown above.

## Recommended next commands

```bash
python -m pytest
python -m bra.prepare
python -m bra --verbose
git status
```
