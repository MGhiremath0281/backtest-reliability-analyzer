# Backtest Reliability Analyzer (BRA) — Complete API Documentation

> **Specification Version:** 0.1.0  
> **OpenAPI Specification:** 3.1.0  
> **FastAPI Backend Server:** `http://localhost:8000` (Default Port `8000`)  
> **Interactive Swagger UI:** [`http://localhost:8000/docs`](http://localhost:8000/docs)  
> **Alternative ReDoc UI:** [`http://localhost:8000/redoc`](http://localhost:8000/redoc)  
> **OpenAPI Schema Document:** [`http://localhost:8000/openapi.json`](http://localhost:8000/openapi.json)

---

## 1. Executive Summary & Architecture

The **Backtest Reliability Analyzer (BRA) REST API** provides quantitative traders, data engineers, and risk officers with an automated, audit-grade verification service for backtest datasets. The API evaluates historical market data to detect:

1. **Survivorship Bias:** Reconstructs point-in-time index constituent histories, audits delisted security coverage, tracks symbol changes and ticker reassignments, and validates that backtests do not restrict their historical security universes to contemporary survivors.
2. **Look-Ahead Bias:** Analyzes temporal sequencing between trading decision timestamps, period-end financial boundaries, exchange public dissemination times, and corporate action entitlement declarations to prevent predictive leakage.
3. **Corporate Actions Consistency:** Verifies cash dividends, stock splits, bonuses, and rights issues; validates entitlement ordering (Record Date vs. Ex-Date); audits pre/post price continuity; and flags anomalous price drops and unadjusted split shocks.
4. **Data Integrity & Schema Conformance:** Validates file formats, structural integrity, duplicate timestamps, date sequencing, missing mandatory columns, and non-numeric price data across 9 canonical market schemas.

### Architectural Principles

- **Zero Hardcoded Data:** All findings, severity classifications, coverage metrics, and data summaries are dynamically computed from uploaded datasets or discovered canonical repository files.
- **Isolated Multi-Tenant Storage:** Uploaded datasets are partitioned in discrete directories (`storage/datasets/{dataset_id}/`) containing separate `uploads/` and `prepared/` subtrees. Datasets never mutate adjacent collections.
- **Immutability of Source Files:** Raw uploaded CSV files are preserved byte-for-byte in their original state. Schema mapping and data normalization outputs are written to dedicated working directories (`prepared/`).
- **Read-Only Canonical Dataset (`existing-data`):** The repository's pre-collected NSE equity and corporate action data is exposed as a virtual dataset (`existing-data`). It is strictly read-only and protected against deletion or modification.
- **Restart Persistence:** Dataset metadata, mappings, validations, analysis runs, and generated reports are persisted as structured JSON artifacts on disk and survive server restarts.

---

## 2. Master Endpoint Inventory Table

The BRA API exposes **46 operations across 43 unique URL paths**, categorized into 9 functional modules:

| # | Tag / Category | Method | Path | Summary / Operation | Request Body / Query | Status Codes |
|---|----------------|--------|------|---------------------|----------------------|--------------|
| 1 | Health & System | `GET` | `/health` | Root service health check | None | `200` |
| 2 | Health & System | `GET` | `/api/v1/health` | Detailed dependency health check | None | `200` |
| 3 | Health & System | `GET` | `/api/v1/metadata` | System capabilities and registered schemas | None | `200` |
| 4 | Dataset Management | `POST` | `/api/v1/datasets/upload` | Upload and register CSV dataset files | `multipart/form-data` | `201`, `400`, `413`, `415`, `422` |
| 5 | Dataset Management | `GET` | `/api/v1/datasets` | List available datasets (uploaded & canonical) | Query (`include_existing`, `limit`, `offset`) | `200`, `422` |
| 6 | Dataset Management | `GET` | `/api/v1/datasets/{dataset_id}` | Retrieve dataset details and file inventory | Path (`dataset_id`) | `200`, `404`, `422` |
| 7 | Dataset Management | `DELETE` | `/api/v1/datasets/{dataset_id}` | Delete an uploaded dataset | Path (`dataset_id`) | `200`, `400`, `404`, `422` |
| 8 | Dataset Management | `POST` | `/api/v1/datasets/{dataset_id}/delete-request` | Request safe deletion of uploaded dataset | Path (`dataset_id`) | `200`, `400`, `404`, `422` |
| 9 | Dataset Management | `GET` | `/api/v1/datasets/{dataset_id}/preview` | Preview paginated rows from a dataset file | Path (`dataset_id`), Query (`file_id`, `limit`, `offset`) | `200`, `400`, `404`, `422` |
| 10 | Dataset Management | `GET` | `/api/v1/datasets/{dataset_id}/schema` | Inspect inferred types and auto-detected schemas | Path (`dataset_id`) | `200`, `404`, `422` |
| 11 | Dataset Management | `POST` | `/api/v1/datasets/{dataset_id}/validate` | Execute structural validation on dataset | Path (`dataset_id`) | `200`, `404`, `422` |
| 12 | Dataset Management | `GET` | `/api/v1/datasets/{dataset_id}/validation` | Retrieve latest validation results for dataset | Path (`dataset_id`) | `200`, `404`, `422` |
| 13 | Dataset Management | `GET` | `/api/v1/datasets/{dataset_id}/quality-summary` | Overall data quality score and metric counts | Path (`dataset_id`) | `200`, `404`, `422` |
| 14 | Schema Mapping & Prep | `GET` | `/api/v1/schemas` | List all 9 canonical schema definitions | None | `200` |
| 15 | Schema Mapping & Prep | `GET` | `/api/v1/schemas/{schema_type}` | Retrieve specification for single schema | Path (`schema_type`) | `200`, `404`, `422` |
| 16 | Schema Mapping & Prep | `GET` | `/api/v1/datasets/{dataset_id}/mapping` | Inspect column mappings & auto-suggestions | Path (`dataset_id`) | `200`, `404`, `422` |
| 17 | Schema Mapping & Prep | `POST` | `/api/v1/datasets/{dataset_id}/mapping` | Define custom column mappings for dataset | Path (`dataset_id`), JSON (`SetMappingRequest`) | `200`, `404`, `422` |
| 18 | Schema Mapping & Prep | `POST` | `/api/v1/datasets/{dataset_id}/prepare` | Normalize and prepare canonical working tables | Path (`dataset_id`) | `200`, `400`, `404`, `422` |
| 19 | Schema Mapping & Prep | `GET` | `/api/v1/datasets/{dataset_id}/preparation` | Retrieve preparation status and prepared file inventory | Path (`dataset_id`) | `200`, `404`, `422` |
| 20 | General Validation | `POST` | `/api/v1/validate` | Execute comprehensive validation across dataset | JSON (`ValidationRequest`) | `200`, `400`, `404`, `422` |
| 21 | General Validation | `GET` | `/api/v1/validations/{validation_id}` | Retrieve complete validation by validation ID | Path (`validation_id`) | `200`, `404`, `422` |
| 22 | General Validation | `GET` | `/api/v1/validations/{validation_id}/findings` | Retrieve filtered findings from validation | Path (`validation_id`), Query (`severity`, `analyzer`, `limit`, `offset`) | `200`, `404`, `422` |
| 23 | General Validation | `GET` | `/api/v1/validations/{validation_id}/summary` | Retrieve summary metrics for validation | Path (`validation_id`) | `200`, `404`, `422` |
| 24 | Survivorship Bias | `POST` | `/api/v1/analyze/survivorship` | Execute survivorship bias analyzer | JSON (`SurvivorshipAnalysisRequest`) | `201`, `404`, `422` |
| 25 | Survivorship Bias | `GET` | `/api/v1/analyze/survivorship/{analysis_id}` | Retrieve complete survivorship analysis | Path (`analysis_id`) | `200`, `404`, `422` |
| 26 | Survivorship Bias | `GET` | `/api/v1/analyze/survivorship/{analysis_id}/universe` | Inspect universe reconstruction & membership | Path (`analysis_id`) | `200`, `404`, `422` |
| 27 | Survivorship Bias | `GET` | `/api/v1/analyze/survivorship/{analysis_id}/delisted` | Delisted securities reconciliation & price coverage | Path (`analysis_id`) | `200`, `404`, `422` |
| 28 | Survivorship Bias | `GET` | `/api/v1/analyze/survivorship/{analysis_id}/findings` | Filtered survivorship bias findings & risks | Path (`analysis_id`), Query (`severity`, `kind`, `limit`, `offset`) | `200`, `404`, `422` |
| 29 | Look-Ahead Bias | `POST` | `/api/v1/analyze/lookahead` | Execute look-ahead bias analyzer | JSON (`LookaheadAnalysisRequest`) | `201`, `404`, `422` |
| 30 | Look-Ahead Bias | `GET` | `/api/v1/analyze/lookahead/{analysis_id}` | Retrieve complete look-ahead analysis | Path (`analysis_id`) | `200`, `404`, `422` |
| 31 | Look-Ahead Bias | `GET` | `/api/v1/analyze/lookahead/{analysis_id}/findings` | Temporal ordering findings and violations | Path (`analysis_id`), Query (`severity`, `classification`, `limit`, `offset`) | `200`, `404`, `422` |
| 32 | Look-Ahead Bias | `GET` | `/api/v1/analyze/lookahead/{analysis_id}/timeline` | Chronological event availability timeline | Path (`analysis_id`) | `200`, `404`, `422` |
| 33 | Corporate Actions | `POST` | `/api/v1/analyze/corporate-actions` | Execute corporate actions analyzer | JSON (`CorporateActionsAnalysisRequest`) | `201`, `404`, `422` |
| 34 | Corporate Actions | `GET` | `/api/v1/analyze/corporate-actions/{analysis_id}` | Retrieve complete corporate actions analysis | Path (`analysis_id`) | `200`, `404`, `422` |
| 35 | Corporate Actions | `GET` | `/api/v1/analyze/corporate-actions/{analysis_id}/findings` | Inconsistencies & price discontinuity findings | Path (`analysis_id`), Query (`severity`, `code`, `limit`, `offset`) | `200`, `404`, `422` |
| 36 | Corporate Actions | `GET` | `/api/v1/analyze/corporate-actions/{analysis_id}/coverage` | Action breakdown by symbol, purpose, and series | Path (`analysis_id`) | `200`, `404`, `422` |
| 37 | Analysis Runs | `POST` | `/api/v1/analysis-runs` | Orchestrate multi-analyzer combined run | JSON (`AnalysisRunRequest`) | `201`, `404`, `422` |
| 38 | Analysis Runs | `GET` | `/api/v1/analysis-runs` | List historical analysis runs | Query (`dataset_id`, `limit`, `offset`) | `200`, `422` |
| 39 | Analysis Runs | `GET` | `/api/v1/analysis-runs/{run_id}` | Retrieve complete details of an analysis run | Path (`run_id`) | `200`, `404`, `422` |
| 40 | Analysis Runs | `GET` | `/api/v1/analysis-runs/{run_id}/findings` | Consolidated findings from an analysis run | Path (`run_id`), Query (`severity`, `analyzer`, `limit`, `offset`) | `200`, `404`, `422` |
| 41 | Analysis Runs | `GET` | `/api/v1/analysis-runs/{run_id}/summary` | Consolidated summary counts & status | Path (`run_id`) | `200`, `404`, `422` |
| 42 | Analysis Runs | `POST` | `/api/v1/analysis-runs/{run_id}/cancel` | Request cancellation of an analysis run | Path (`run_id`) | `200`, `404`, `422` |
| 43 | Analysis Runs | `GET` | `/api/v1/analysis-runs/{run_id}/events` | Execution lifecycle events log | Path (`run_id`) | `200`, `404`, `422` |
| 44 | Reports & Exports | `GET` | `/api/v1/reports` | List generated reliability audit reports | Query (`limit`, `offset`) | `200`, `422` |
| 45 | Reports & Exports | `GET` | `/api/v1/reports/{report_id}` | Retrieve report summary and findings | Path (`report_id`) | `200`, `404`, `422` |
| 46 | Reports & Exports | `GET` | `/api/v1/reports/{report_id}/download` | Download report file (`json`, `csv`, `pdf`) | Path (`report_id`), Query (`format`) | `200`, `400`, `404`, `422`, `501` |

---

## 3. End-to-End API Workflows & Call Sequences

### Workflow 1: Dataset Ingestion, Mapping, and Normalization

```text
  [Client]
     |
     |-- 1. POST /api/v1/datasets/upload (Upload CSVs: prices, corporate actions, delistings)
     |   --> Returns: dataset_id, file inventory, auto-detected schemas
     |
     |-- 2. GET /api/v1/datasets/{dataset_id}/mapping
     |   --> Returns: detected schema types, column matches, auto-suggestions
     |
     |-- 3. (Optional) POST /api/v1/datasets/{dataset_id}/mapping
     |   --> Supply custom column mappings if non-standard headers were used
     |
     |-- 4. POST /api/v1/datasets/{dataset_id}/prepare
     |   --> Normalizes dates, standardizes column names, writes canonical files to prepared/
     |
     |-- 5. GET /api/v1/datasets/{dataset_id}/quality-summary
     |   --> Returns overall quality score (0-100), issue counts, supported analyses
     v
```

### Workflow 2: Dedicated Bias Analyzer Execution (Individual Engines)

Each bias analyzer engine can be triggered independently for focused testing:

- **Survivorship Bias:**
  1. `POST /api/v1/analyze/survivorship` with optional `BacktestConfig` (`target_index`, `start_date`, `end_date`, `universe_symbols`, `min_price_coverage`).
  2. Query `GET /api/v1/analyze/survivorship/{analysis_id}` for metrics.
  3. Query `GET /api/v1/analyze/survivorship/{analysis_id}/universe` for index constituent coverage.
  4. Query `GET /api/v1/analyze/survivorship/{analysis_id}/delisted` for delisted securities reconciliation.
  5. Query `GET /api/v1/analyze/survivorship/{analysis_id}/findings` to view categorized risks and limitations.

- **Look-Ahead Bias:**
  1. `POST /api/v1/analyze/lookahead` with optional `LookaheadConfig` (`decision_dates`, `lookback_days`, `target_index`).
  2. Query `GET /api/v1/analyze/lookahead/{analysis_id}` for coverage metrics.
  3. Query `GET /api/v1/analyze/lookahead/{analysis_id}/timeline` for the chronologically sorted event timeline.
  4. Query `GET /api/v1/analyze/lookahead/{analysis_id}/findings` to inspect confirmed violations and suspicious publication times.

- **Corporate Actions Consistency:**
  1. `POST /api/v1/analyze/corporate-actions` with optional `expected_symbol`.
  2. Query `GET /api/v1/analyze/corporate-actions/{analysis_id}` for execution summary.
  3. Query `GET /api/v1/analyze/corporate-actions/{analysis_id}/coverage` for purpose, symbol, and series distributions.
  4. Query `GET /api/v1/analyze/corporate-actions/{analysis_id}/findings` for entitlement inversions and price shocks.

### Workflow 3: Orchestrated Multi-Analyzer Analysis Run & Report Generation

```text
  [Client]
     |
     |-- 1. POST /api/v1/analysis-runs
     |      Payload: dataset_id, analyzers: ["survivorship", "lookahead", "corporate_actions"],
     |               optional backtest & lookahead configs
     |      --> Returns: run_id, report_id, status="completed", summary
     |
     |-- 2. GET /api/v1/analysis-runs/{run_id}/summary
     |      --> Inspect overall status (PASS, WARN, FAIL) and error/warning counts
     |
     |-- 3. GET /api/v1/analysis-runs/{run_id}/findings?severity=error
     |      --> Retrieve actionable findings requiring remediation
     |
     |-- 4. GET /api/v1/analysis-runs/{run_id}/events
     |      --> Review step-by-step execution lifecycle timestamps
     |
     |-- 5. GET /api/v1/reports/{report_id}/download?format=pdf
     |      --> Download final executive PDF audit report
     |
     |-- 6. GET /api/v1/reports/{report_id}/download?format=csv
     |      --> Download tabular findings spreadsheet for quantitative QA tracking
     v
```

---

## 4. Canonical Schemas Specification

The BRA engine recognizes **9 canonical market schema types**. When source datasets use different vendor column names, the API's auto-mapping and normalization layer maps source columns to these canonical fields:

### 1. `prices` (Daily OHLCV Equities)
- **Primary Key:** `("Symbol", "Series", "Date")`
- **Required Columns:**
  - `Symbol` (`string`): Security ticker/identifier. (Aliases: `symbol`, `ticker`, `tradingsymbol`, `code`)
  - `Date` (`date`): Trading session date (`YYYY-MM-DD`). (Aliases: `date`, `trade_date`, `tradedate`, `timestamp`)
  - `Open Price` (`float`): Session opening price. (Aliases: `open`, `open_price`, `opening_price`)
  - `High Price` (`float`): Session highest traded price. (Aliases: `high`, `high_price`)
  - `Low Price` (`float`): Session lowest traded price. (Aliases: `low`, `low_price`)
  - `Close Price` (`float`): Session official closing price. (Aliases: `close`, `close_price`, `closing_price`, `last_price`, `adj_close`)
- **Optional Columns:** `Series` (`string`, default: `"EQ"`), `Prev Close` (`float`), `Last Price` (`float`), `Average Price` (`float`), `Total Traded Quantity` (`int`), `Turnover ₹` (`float`), `No. of Trades` (`int`), `Deliverable Qty` (`int`), `% Dly Qt to Traded Qty` (`float`).

### 2. `corporate_actions` (Corporate Actions & Entitlements)
- **Primary Key:** `("SYMBOL", "EX-DATE", "PURPOSE")`
- **Required Columns:**
  - `SYMBOL` (`string`): Security trading symbol. (Aliases: `symbol`, `ticker`, `security`)
  - `COMPANY NAME` (`string`): Corporate issuer name. (Aliases: `company_name`, `company`, `issuer`)
  - `PURPOSE` (`string`): Action description and terms (e.g., `Dividend Rs 15`, `Split 1:1`). (Aliases: `purpose`, `action`, `description`, `event`)
  - `EX-DATE` (`date`): First trading date without entitlement. (Aliases: `ex_date`, `exdate`, `effective_date`)
- **Optional Columns:** `SERIES` (`string`), `FACE VALUE` (`float`), `RECORD DATE` (`date`), `BOOK CLOSURE START DATE` (`date`), `BOOK CLOSURE END DATE` (`date`).

### 3. `financials_legacy` (Financial Filings — Legacy NSE Format)
- **Required Columns:**
  - `COMPANY NAME` (`string`): Corporate issuer name.
  - `PERIOD ENDED` (`date`): Accounting period end date (`YYYY-MM-DD`).
  - `Exchange Dissemination Time` (`timestamp`): Exact public announcement timestamp (`YYYY-MM-DD HH:MM:SS`).
- **Optional Columns:** `AUDITED / UNAUDITED`, `CUMULATIVE / NON-CUMULATIVE`, `CONSOLIDATED / NON-CONSOLIDATED`, `IND AS/ NON IND AS`, `BROADCAST DATE/TIME`.

### 4. `financials_integrated` (Modern Integrated Financial Results)
- **Required Columns:**
  - `Symbol` (`string`): Standard equity symbol.
  - `Period End Date` (`date`): Financial reporting period end.
  - `Dissemination Timestamp` (`timestamp`): Feed availability timestamp.
- **Optional Columns:** `Revenue`, `Operating Profit`, `Net Profit`, `EPS`, `Filing Type`.

### 5. `current_listing` (Active Listed Securities Master)
- **Required Columns:**
  - `Symbol` (`string`): Active trading symbol.
  - `Company Name` (`string`): Registered corporate name.
  - `Listing Date` (`date`): Initial exchange listing date.
- **Optional Columns:** `Series`, `ISIN`, `Face Value`, `Industry`, `Paid Up Value`.

### 6. `delistings` (Historical Delisted Securities Register)
- **Required Columns:**
  - `Symbol` (`string`): Symbol at delisting time.
  - `Company Name` (`string`): Legal name of delisted issuer.
  - `Delisted Date` (`date`): Effective delisting cutoff date.
- **Optional Columns:** `ISIN`, `Series`, `Reason for Delisting`, `Type of Delisting` (`Compulsory`, `Voluntary`, `Suspension`).

### 7. `name_changes` (Historical Company Name Transitions)
- **Required Columns:**
  - `Symbol` (`string`): Equity symbol.
  - `Former Name` (`string`): Prior legal entity name.
  - `New Name` (`string`): Revised legal entity name.
  - `Effective Date` (`date`): Change effective date.

### 8. `symbol_changes` (Historical Ticker Reassignments)
- **Required Columns:**
  - `Company Name` (`string`): Corporate entity name.
  - `Old Symbol` (`string`): Prior trading symbol.
  - `New Symbol` (`string`): Revised trading symbol.
  - `Effective Date` (`date`): Transition date.

### 9. `index_snapshot` (Point-in-Time Index Membership)
- **Required Columns:**
  - `Index Name` (`string`): Index identifier (e.g., `NIFTY 50`, `NIFTY BANK`).
  - `Snapshot Date` (`date`): Rebalancing or observation cutoff date.
  - `Symbol` (`string`): Constituent equity symbol.
- **Optional Columns:** `Weight`, `Industry`, `Free Float Market Cap`.

---

## 5. Detailed Endpoint Documentation

### 5.1 Health & System Module

#### 1. `GET /health`
- **Summary:** Root service health check.
- **Purpose:** Quick liveness and readiness probe for load balancers and orchestrators.
- **Path Parameters:** None.
- **Query Parameters:** None.
- **Request Body:** None.
- **Response `200 OK`:**
  ```json
  {
    "status": "ok",
    "app": "backtest-reliability-analyzer",
    "version": "0.1.0",
    "storage": "healthy",
    "analyzers": {
      "survivorship": "available",
      "lookahead": "available",
      "corporate_actions": "available"
    }
  }
  ```
  - `status` (`string`): `"ok"` if storage directories exist; `"degraded"` if storage is inaccessible.
  - `storage` (`string`): `"healthy"` or `"storage_unavailable"`.
  - `analyzers` (`object`): Dictionary mapping analyzer keys to availability state (`"available"`).

---

#### 2. `GET /api/v1/health`
- **Summary:** API v1 detailed dependency health check.
- **Purpose:** Identical to `/health`, provided under the `/api/v1` namespace for API version consistency.
- **Response `200 OK`:** Matches `/health`.

---

#### 3. `GET /api/v1/metadata`
- **Summary:** System metadata reporting actual registered capabilities.
- **Purpose:** Allows clients and frontend interfaces to dynamically discover registered analyzers, supported schemas, upload limits, and file handling constraints without hardcoding capabilities.
- **Response `200 OK`:**
  ```json
  {
    "version": "0.1.0",
    "app_name": "backtest-reliability-analyzer",
    "registered_analyzers": [
      {
        "name": "survivorship",
        "label": "Survivorship Bias Analyzer",
        "description": "Evaluates historical universe reconstruction, delisted securities reconciliation, price coverage, and backtest-specific universe membership integrity.",
        "supported_inputs": [
          "prices",
          "delistings",
          "current_listing",
          "name_changes",
          "symbol_changes",
          "index_snapshot"
        ],
        "supports_backtest_config": true
      },
      {
        "name": "lookahead",
        "label": "Look-Ahead Bias Analyzer",
        "description": "Measures temporal ordering between decision dates, reporting periods, and availability timestamps across financial results, corporate actions, and price series.",
        "supported_inputs": [
          "financials_legacy",
          "financials_integrated",
          "corporate_actions",
          "prices",
          "index_snapshot"
        ],
        "supports_backtest_config": true
      },
      {
        "name": "corporate_actions",
        "label": "Corporate Actions Consistency Analyzer",
        "description": "Validates entitlement dates, record date vs ex-date ordering, pre/post event price coverage, and suspicious price discontinuities around split and bonus events.",
        "supported_inputs": [
          "corporate_actions",
          "prices"
        ],
        "supports_backtest_config": false
      }
    ],
    "supported_schemas": [
      {
        "schema_type": "prices",
        "label": "Historical Prices",
        "required_columns": ["Symbol", "Date", "Open Price", "High Price", "Low Price", "Close Price"],
        "key_columns": ["Symbol", "Series", "Date"]
      }
    ],
    "file_handling": {
      "max_upload_size_bytes": 104857600,
      "max_upload_size_mb": 100,
      "supported_extensions": [".csv"],
      "supported_encodings": ["utf-8", "utf-8-sig", "windows-1252"],
      "csv_delimiter": ","
    },
    "application_config": {
      "app_name": "backtest-reliability-analyzer",
      "version": "0.1.0",
      "storage_mode": "isolated_directory",
      "read_only_canonical": true
    }
  }
  ```

---

### 5.2 Dataset Management Module

#### 4. `POST /api/v1/datasets/upload`
- **Summary:** Upload and register CSV dataset files.
- **Purpose:** Ingests one or more CSV files into a newly created isolated dataset directory (`storage/datasets/{dataset_id}/uploads/`). Inspects headers, counts rows, and automatically detects candidate schemas.
- **Headers:** `Content-Type: multipart/form-data`
- **Form Fields:**
  - `files` (`list[UploadFile]`, **Required**): One or more CSV files to upload.
  - `name` (`string`, *Optional*): Human-readable name for the dataset.
  - `description` (`string`, *Optional*): Description of the dataset source or vendor.
- **Response `201 Created`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "message": "Successfully registered 2 file(s).",
    "files": [
      {
        "file_id": "f_98a72b14",
        "original_filename": "infy_prices.csv",
        "stored_filename": "f_98a72b14_infy_prices.csv",
        "size_bytes": 209593,
        "row_count": 1240,
        "headers": ["Symbol", "Series", "Date", "Open Price", "High Price", "Low Price", "Close Price"],
        "detected_schema": "prices",
        "confidence": 1.0,
        "uploaded_at": "2026-10-24T02:15:30.123456+00:00"
      },
      {
        "file_id": "f_3c71a90d",
        "original_filename": "infy_actions.csv",
        "stored_filename": "f_3c71a90d_infy_actions.csv",
        "size_bytes": 1351,
        "row_count": 14,
        "headers": ["SYMBOL", "COMPANY NAME", "PURPOSE", "EX-DATE", "RECORD DATE"],
        "detected_schema": "corporate_actions",
        "confidence": 1.0,
        "uploaded_at": "2026-10-24T02:15:30.123456+00:00"
      }
    ]
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "At least one file must be uploaded."}`
  - `413 Payload Too Large`: `{"detail": "File 'large_prices.csv' (150000000 bytes) exceeds the configured limit of 104857600 bytes."}`
  - `415 Unsupported Media Type`: `{"detail": "Unsupported file type '.xlsx' for 'data.xlsx'. Supported extensions: .csv."}`

---

#### 5. `GET /api/v1/datasets`
- **Summary:** List available datasets (uploaded and canonical).
- **Purpose:** Enumerates all registered datasets on disk. Includes virtual metadata for the canonical repository dataset (`existing-data`) unless filtered out.
- **Query Parameters:**
  - `include_existing` (`boolean`, *Optional*, Default: `true`): Include virtual `existing-data` entry.
  - `limit` (`integer`, *Optional*, Default: `50`, Range: `1`–`200`): Maximum results to return.
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`): Pagination offset.
- **Response `200 OK`:**
  ```json
  [
    {
      "dataset_id": "existing-data",
      "name": "Canonical Repository Dataset",
      "description": "Pre-collected NSE historical data tree from the repository data directory.",
      "is_existing": true,
      "file_count": 12,
      "total_rows": 0,
      "created_at": "canonical",
      "status": "ready",
      "mapping_status": "mapped",
      "preparation_status": "prepared"
    },
    {
      "dataset_id": "ds-e48f76329a1b",
      "name": "Provider A Historical Feed",
      "description": "Daily OHLCV equities and corporate actions 2021-2026",
      "is_existing": false,
      "file_count": 2,
      "total_rows": 1254,
      "created_at": "2026-10-24T02:15:30.123456+00:00",
      "status": "uploaded",
      "mapping_status": "unmapped",
      "preparation_status": "unprepared"
    }
  ]
  ```

---

#### 6. `GET /api/v1/datasets/{dataset_id}`
- **Summary:** Retrieve dataset details and file inventory.
- **Path Parameters:**
  - `dataset_id` (`string`, **Required**): Target dataset identifier.
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "name": "Provider A Historical Feed",
    "description": "Daily OHLCV equities and corporate actions 2021-2026",
    "is_existing": false,
    "file_count": 2,
    "total_rows": 1254,
    "created_at": "2026-10-24T02:15:30.123456+00:00",
    "status": "uploaded",
    "mapping_status": "unmapped",
    "preparation_status": "unprepared",
    "files": [
      {
        "file_id": "f_98a72b14",
        "original_filename": "infy_prices.csv",
        "stored_filename": "f_98a72b14_infy_prices.csv",
        "size_bytes": 209593,
        "row_count": 1240,
        "headers": ["Symbol", "Series", "Date", "Open Price", "High Price", "Low Price", "Close Price"],
        "detected_schema": "prices",
        "confidence": 1.0,
        "uploaded_at": "2026-10-24T02:15:30.123456+00:00"
      }
    ]
  }
  ```
- **Error Responses:**
  - `404 Not Found`: `{"detail": "Dataset 'ds-nonexistent' not found."}`

---

#### 7. `DELETE /api/v1/datasets/{dataset_id}`
- **Summary:** Delete an uploaded dataset.
- **Purpose:** Safely removes an uploaded dataset and all its associated directories and files from disk. Protects the canonical dataset from accidental deletion.
- **Path Parameters:**
  - `dataset_id` (`string`, **Required**): Dataset to delete.
- **Response `200 OK`:**
  ```json
  {
    "message": "Dataset ds-e48f76329a1b deleted successfully."
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "Cannot delete canonical repository dataset."}`
  - `404 Not Found`: `{"detail": "Dataset 'ds-e48f76329a1b' not found."}`

---

#### 8. `POST /api/v1/datasets/{dataset_id}/delete-request`
- **Summary:** Request safe deletion of an uploaded dataset.
- **Purpose:** Idempotent deletion endpoint for UI forms and webhook environments that cannot issue HTTP DELETE requests.
- **Response `200 OK`:** Matches `DELETE /api/v1/datasets/{dataset_id}`.

---

#### 9. `GET /api/v1/datasets/{dataset_id}/preview`
- **Summary:** Preview paginated rows from a dataset file.
- **Path Parameters:**
  - `dataset_id` (`string`, **Required**): Target dataset ID.
- **Query Parameters:**
  - `file_id` (`string`, *Optional*): Target file ID. Defaults to first file if omitted.
  - `limit` (`integer`, *Optional*, Default: `50`, Range: `1`–`500`): Max rows.
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`): Row offset.
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "file_id": "f_98a72b14",
    "filename": "infy_prices.csv",
    "headers": ["Symbol", "Series", "Date", "Open Price", "High Price", "Low Price", "Close Price"],
    "rows": [
      {
        "Symbol": "INFY",
        "Series": "EQ",
        "Date": "2021-10-22",
        "Open Price": "1710.0",
        "High Price": "1730.0",
        "Low Price": "1701.0",
        "Close Price": "1715.5"
      }
    ],
    "total_rows": 1240,
    "limit": 1,
    "offset": 0
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "Dataset contains no files."}`
  - `404 Not Found`: `{"detail": "File 'f_9999' not found in dataset 'ds-e48f76329a1b'."}`

---

#### 10. `GET /api/v1/datasets/{dataset_id}/schema`
- **Summary:** Inspect actual column names and inferred types for all dataset files.
- **Purpose:** Analyzes the first 100 rows of each file to infer column types (`string`, `date`, `timestamp`, `float`, `int`).
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "files": [
      {
        "file_id": "f_98a72b14",
        "filename": "infy_prices.csv",
        "headers": ["Symbol", "Series", "Date", "Open Price", "Close Price"],
        "inferred_types": {
          "Symbol": "string",
          "Series": "string",
          "Date": "date",
          "Open Price": "float",
          "Close Price": "float"
        },
        "detected_schema": "prices",
        "confidence": 1.0
      }
    ]
  }
  ```

---

#### 11. `POST /api/v1/datasets/{dataset_id}/validate`
- **Summary:** Run structural integrity and schema validation on the dataset.
- **Purpose:** Executes structural checks (delimiters, ragged rows, blanks, duplicates, column presence) and returns a comprehensive `ValidationResponse`.
- **Response `200 OK`:**
  ```json
  {
    "validation_id": "val-8f9210c4a123",
    "dataset_id": "ds-e48f76329a1b",
    "status": "PASS",
    "summary": {
      "status": "PASS",
      "error_count": 0,
      "warning_count": 0,
      "pass_count": 5,
      "dataset_count": 2
    },
    "findings": [],
    "supported_analyses": ["survivorship", "lookahead", "corporate_actions"],
    "missing_evidence": [],
    "created_at": "2026-10-24T02:16:00.000000+00:00"
  }
  ```

---

#### 12. `GET /api/v1/datasets/{dataset_id}/validation`
- **Summary:** Retrieve latest validation results for a dataset.
- **Purpose:** Retrieves the most recently executed validation artifact for the dataset. If none exists, it executes validation automatically on the fly.
- **Response `200 OK`:** Matches `POST /api/v1/datasets/{dataset_id}/validate`.

---

#### 13. `GET /api/v1/datasets/{dataset_id}/quality-summary`
- **Summary:** Calculate an overall data quality summary and score for the dataset.
- **Purpose:** Calculates a deterministic quality score (`0.0`–`100.0`) deducting 5 points per structural error/warning, reporting blank row counts, missing required column counts, and duplicate rows.
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "file_count": 2,
    "total_rows": 1254,
    "quality_score": 100.0,
    "blank_row_counts": {
      "infy_prices.csv": 0,
      "infy_actions.csv": 0
    },
    "missing_required_counts": {
      "infy_prices.csv": 0,
      "infy_actions.csv": 0
    },
    "duplicate_counts": {
      "infy_prices.csv": 0,
      "infy_actions.csv": 0
    },
    "supported_analyzers": ["survivorship", "lookahead", "corporate_actions"],
    "missing_evidence": []
  }
  ```

---

### 5.3 Schema Mapping & Preparation Module

#### 14. `GET /api/v1/schemas`
- **Summary:** List all supported canonical BRA schema definitions.
- **Response `200 OK`:** Returns array of all 9 canonical schemas (`prices`, `corporate_actions`, `financials_legacy`, `financials_integrated`, `current_listing`, `delistings`, `name_changes`, `symbol_changes`, `index_snapshot`) with their full column definitions, data types, required flags, aliases, and primary key columns.

---

#### 15. `GET /api/v1/schemas/{schema_type}`
- **Summary:** Retrieve detailed specification for a canonical schema type.
- **Path Parameters:**
  - `schema_type` (`string`, **Required**): Canonical schema identifier (e.g., `prices`).
- **Response `200 OK`:**
  ```json
  {
    "schema_type": "prices",
    "label": "Historical Prices",
    "description": "Daily OHLCV equity price history.",
    "required_columns": [
      "Symbol",
      "Date",
      "Open Price",
      "High Price",
      "Low Price",
      "Close Price"
    ],
    "optional_columns": [
      "Series",
      "Prev Close",
      "Last Price",
      "Average Price",
      "Total Traded Quantity",
      "Turnover ₹",
      "No. of Trades",
      "Deliverable Qty",
      "% Dly Qt to Traded Qty"
    ],
    "date_columns": ["Date"],
    "numeric_columns": ["Open Price", "High Price", "Low Price", "Close Price"],
    "key_columns": ["Symbol", "Series", "Date"],
    "columns": [
      {
        "name": "Symbol",
        "data_type": "string",
        "required": true,
        "description": "Security trading symbol",
        "aliases": ["symbol", "ticker", "tradingsymbol", "code"]
      }
    ]
  }
  ```
- **Error Responses:**
  - `404 Not Found`: `{"detail": "Schema type 'unknown_schema' not found. Available schemas: prices, corporate_actions, financials_legacy, financials_integrated, current_listing, delistings, name_changes, symbol_changes, index_snapshot."}`

---

#### 16. `GET /api/v1/datasets/{dataset_id}/mapping`
- **Summary:** Inspect current column mappings and auto-suggestions for a dataset.
- **Purpose:** Returns the current column-to-canonical mappings alongside auto-suggestions for unmapped source columns based on known schema aliases.
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "mappings": [
      {
        "file_id": "f_98a72b14",
        "filename": "infy_prices.csv",
        "schema_type": "prices",
        "column_mapping": {
          "Symbol": "Symbol",
          "Series": "Series",
          "Date": "Date",
          "Open Price": "Open Price",
          "High Price": "High Price",
          "Low Price": "Low Price",
          "Close Price": "Close Price"
        },
        "unmapped_source_columns": [],
        "missing_required_columns": [],
        "valid": true,
        "errors": []
      }
    ],
    "all_valid": true,
    "auto_suggestions": {
      "f_98a72b14": {
        "Symbol": "Symbol",
        "Series": "Series",
        "Date": "Date",
        "Open Price": "Open Price",
        "High Price": "High Price",
        "Low Price": "Low Price",
        "Close Price": "Close Price"
      }
    }
  }
  ```

---

#### 17. `POST /api/v1/datasets/{dataset_id}/mapping`
- **Summary:** Set or auto-generate column mappings for an uploaded dataset.
- **Purpose:** Allows users to map vendor column names (e.g., `trade_date`, `closing_val`, `ticker`) to canonical BRA schema names (`Date`, `Close Price`, `Symbol`).
- **Request Body JSON (`SetMappingRequest`):**
  ```json
  {
    "mappings": [
      {
        "file_id": "f_98a72b14",
        "schema_type": "prices",
        "column_mapping": {
          "ticker": "Symbol",
          "trade_date": "Date",
          "opening_val": "Open Price",
          "high_val": "High Price",
          "low_val": "Low Price",
          "closing_val": "Close Price"
        }
      }
    ],
    "auto_suggest": false
  }
  ```
  - `mappings` (`list[FileMappingItem]`): List of mapping definitions per file.
  - `auto_suggest` (`boolean`, Default: `false`): If `true`, fills unmapped files with auto-detected suggestions.
- **Response `200 OK`:** Returns `DatasetMappingResponse` indicating `all_valid: true/false` and missing required columns if invalid.

---

#### 18. `POST /api/v1/datasets/{dataset_id}/prepare`
- **Summary:** Normalize and prepare working datasets using the defined column mappings.
- **Purpose:** Reads raw uploads, applies column mappings, standardizes column names, supplies default series values (`EQ`), sorts chronologically, and writes normalized CSV tables to `storage/datasets/{dataset_id}/prepared/`. **Leaves original uploaded files completely untouched.**
- **Response `200 OK`:**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "status": "prepared",
    "prepared_files": [
      {
        "filename": "prices.csv",
        "schema_type": "prices",
        "row_count": 1240,
        "columns": ["Symbol", "Series", "Date", "Open Price", "High Price", "Low Price", "Close Price"]
      },
      {
        "filename": "corporate_actions.csv",
        "schema_type": "corporate_actions",
        "row_count": 14,
        "columns": ["SYMBOL", "COMPANY NAME", "PURPOSE", "EX-DATE", "RECORD DATE"]
      }
    ],
    "total_records": 1254,
    "review_flags": {},
    "warnings": []
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "Preparation failed: Missing required columns..."}`

---

#### 19. `GET /api/v1/datasets/{dataset_id}/preparation`
- **Summary:** Inspect preparation status and normalized working datasets.
- **Response `200 OK`:** Returns `PreparationResponse` if the dataset has been prepared.
- **Error Responses:**
  - `404 Not Found`: `{"detail": "Dataset 'ds-e48f76329a1b' has not been prepared yet."}`

---

### 5.4 General Validation Module

#### 20. `POST /api/v1/validate`
- **Summary:** Trigger comprehensive validation across an uploaded or canonical dataset.
- **Purpose:** Orchestrates structural table validation, header audits, date parsing checks, and missing evidence identification.
- **Request Body JSON (`ValidationRequest`):**
  ```json
  {
    "dataset_id": "ds-e48f76329a1b",
    "run_id": null,
    "analyzers": ["survivorship", "lookahead", "corporate_actions"],
    "backtest": {
      "target_index": "NIFTY 50",
      "universe_symbols": ["INFY", "TCS", "WIPRO"],
      "start_date": "2021-01-01",
      "end_date": "2025-12-31",
      "min_price_coverage": 0.95
    },
    "lookahead_config": {
      "decision_dates": ["2022-01-01", "2023-01-01"],
      "lookback_days": 90
    }
  }
  ```
- **Response `200 OK`:** Returns `ValidationResponse` (see section 5.2, endpoint 11).
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "Either dataset_id or run_id must be provided."}`

---

#### 21. `GET /api/v1/validations/{validation_id}`
- **Summary:** Retrieve full validation result by ID.
- **Response `200 OK`:** Returns complete `ValidationResponse`.
- **Error Responses:**
  - `404 Not Found`: `{"detail": "Validation 'val-nonexistent' not found."}`

---

#### 22. `GET /api/v1/validations/{validation_id}/findings`
- **Summary:** Retrieve filtered and paginated findings from a validation.
- **Query Parameters:**
  - `severity` (`string`, *Optional*): Filter by severity: `"error"`, `"warning"`, `"info"`.
  - `analyzer` (`string`, *Optional*): Filter by analyzer: `"survivorship"`, `"lookahead"`, `"corporate_actions"`, `"csv"`.
  - `limit` (`integer`, *Optional*, Default: `100`, Range: `1`–`500`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:**
  ```json
  [
    {
      "id": "fnd-1a2b3c4d",
      "analyzer": "csv",
      "code": "csv.missing_columns",
      "classification": "violation",
      "severity": "error",
      "message": "Missing required price columns: Close Price",
      "row": null,
      "column": "Close Price",
      "symbol": null,
      "date": null,
      "evidence": null,
      "limitations": null,
      "remediation": "Add Close Price column to prices table or update column mapping."
    }
  ]
  ```

---

#### 23. `GET /api/v1/validations/{validation_id}/summary`
- **Summary:** Retrieve summary metrics and status for a validation.
- **Response `200 OK`:**
  ```json
  {
    "status": "PASS",
    "error_count": 0,
    "warning_count": 0,
    "pass_count": 5,
    "dataset_count": 2
  }
  ```

---

### 5.5 Survivorship Bias Module

#### 24. `POST /api/v1/analyze/survivorship`
- **Summary:** Execute survivorship bias analyzer against the specified dataset.
- **Request Body JSON (`SurvivorshipAnalysisRequest`):**
  ```json
  {
    "dataset_id": "existing-data",
    "target_index": "NIFTY 50",
    "start_date": "2021-01-01",
    "end_date": "2025-12-31",
    "universe_symbols": ["INFY", "TCS", "RELIANCE"],
    "min_price_coverage": 0.95
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "analysis_id": "surv-8b1e42a0f12c",
    "dataset_id": "existing-data",
    "status": "PASS",
    "error_count": 0,
    "warning_count": 0,
    "findings_count": 3,
    "created_at": "2026-10-24T02:18:00.000000+00:00"
  }
  ```

---

#### 25. `GET /api/v1/analyze/survivorship/{analysis_id}`
- **Summary:** Retrieve complete survivorship analysis results.
- **Response `200 OK`:** Returns full analysis dictionary containing `analysis_id`, `type`: `"survivorship"`, `dataset_id`, `status`, `row_count`, `coverage`, `metrics`, `findings`, and `created_at`.

---

#### 26. `GET /api/v1/analyze/survivorship/{analysis_id}/universe`
- **Summary:** Inspect historical universe reconstruction and membership metrics.
- **Response `200 OK`:**
  ```json
  {
    "analysis_id": "surv-8b1e42a0f12c",
    "dataset_id": "existing-data",
    "membership": {
      "target_index": "NIFTY 50",
      "total_historical_constituents": 52,
      "current_constituents": 50,
      "rebalancing_snapshot_count": 8
    },
    "universe_coverage": {
      "configured_symbols": 3,
      "covered_symbols": 3,
      "coverage_ratio": 1.0
    },
    "current_listings": {
      "active_count": 2100,
      "reconciled_count": 2100
    },
    "index_membership": {},
    "universe_price_coverage": {},
    "current_listing_snapshot": {},
    "price_coverage": {}
  }
  ```

---

#### 27. `GET /api/v1/analyze/survivorship/{analysis_id}/delisted`
- **Summary:** Inspect delisted security reconciliation, match classes, and price coverage.
- **Response `200 OK`:**
  ```json
  {
    "analysis_id": "surv-8b1e42a0f12c",
    "dataset_id": "existing-data",
    "delisted_coverage": {
      "delisted_total": 45,
      "reconciled_delistings": 45,
      "with_price_history_until_delisting": 42,
      "missing_price_history": 3
    },
    "delisted_price_coverage": {},
    "symbol_changes": {
      "tracked_changes": 12,
      "reconciled_tickers": 12
    },
    "identifier_reuse": {
      "reused_symbol_count": 0,
      "conflicts": []
    },
    "delisting_symbol_reuse": {}
  }
  ```

---

#### 28. `GET /api/v1/analyze/survivorship/{analysis_id}/findings`
- **Summary:** Inspect findings, risks, and evidence from a survivorship analysis.
- **Query Parameters:**
  - `severity` (`string`, *Optional*): `"error"`, `"warning"`, `"info"`.
  - `kind` (`string`, *Optional*): Classification kind: `"fact"`, `"risk"`, `"limitation"`, `"check"`.
  - `limit` (`integer`, *Optional*, Default: `100`, Range: `1`–`500`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:** Returns array of `FindingModel` objects.

---

### 5.6 Look-Ahead Bias Module

#### 29. `POST /api/v1/analyze/lookahead`
- **Summary:** Execute look-ahead bias detection against the specified dataset.
- **Request Body JSON (`LookaheadAnalysisRequest`):**
  ```json
  {
    "dataset_id": "existing-data",
    "decision_dates": ["2022-04-01", "2023-04-01", "2024-04-01"],
    "target_index": "NIFTY 50",
    "start_date": "2021-01-01",
    "end_date": "2025-12-31",
    "universe_symbols": ["INFY", "TCS"],
    "lookback_days": 90
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "analysis_id": "look-1f2e3d4c5b6a",
    "dataset_id": "existing-data",
    "status": "PASS",
    "error_count": 0,
    "warning_count": 0,
    "findings_count": 2,
    "created_at": "2026-10-24T02:18:30.000000+00:00"
  }
  ```

---

#### 30. `GET /api/v1/analyze/lookahead/{analysis_id}`
- **Summary:** Retrieve complete look-ahead analysis results.
- **Response `200 OK`:** Returns full look-ahead analysis record.

---

#### 31. `GET /api/v1/analyze/lookahead/{analysis_id}/findings`
- **Summary:** Inspect temporal ordering findings, violations, and evidence.
- **Query Parameters:**
  - `severity` (`string`, *Optional*): `"error"`, `"warning"`, `"info"`.
  - `classification` (`string`, *Optional*): `"confirmed"`, `"suspicious"`, `"insufficient"`, `"check"`.
  - `limit` (`integer`, *Optional*, Default: `100`, Range: `1`–`500`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:** Returns list of `FindingModel` items.

---

#### 32. `GET /api/v1/analyze/lookahead/{analysis_id}/timeline`
- **Summary:** Inspect event availability timelines and chronological entries.
- **Purpose:** Extracts chronological events across decision dates, index constituent snapshots, and corporate financial publication timestamps.
- **Response `200 OK`:**
  ```json
  {
    "analysis_id": "look-1f2e3d4c5b6a",
    "dataset_id": "existing-data",
    "event_count": 3,
    "events": [
      {
        "date": "2022-04-01",
        "event_type": "decision_date",
        "symbol": null,
        "description": "Backtest decision boundary 2022-04-01: 12/12 relying records available on or before decision (0 published after)",
        "classification": "ok",
        "details": {
          "relying_records": 12,
          "published_by_decision": 12,
          "published_after_decision": 0
        }
      },
      {
        "date": "2022-05-15 18:30:00",
        "event_type": "financial_publication",
        "symbol": "INFY",
        "description": "INFY financial result for period 2022-03-31 published at 2022-05-15 18:30:00",
        "classification": "ok",
        "details": {
          "period_end": "2022-03-31",
          "decision_date": "2022-04-01"
        }
      }
    ],
    "financial_publication": {},
    "financial_revisions": {},
    "corporate_action_timing": {},
    "point_in_time_universe": {},
    "price_availability": {}
  }
  ```

---

### 5.7 Corporate Actions Module

#### 33. `POST /api/v1/analyze/corporate-actions`
- **Summary:** Execute corporate actions validation against the specified dataset.
- **Request Body JSON (`CorporateActionsAnalysisRequest`):**
  ```json
  {
    "dataset_id": "existing-data",
    "expected_symbol": "INFY"
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "analysis_id": "ca-7a8b9c0d1e2f",
    "dataset_id": "existing-data",
    "status": "PASS",
    "error_count": 0,
    "warning_count": 0,
    "findings_count": 1,
    "created_at": "2026-10-24T02:19:00.000000+00:00"
  }
  ```

---

#### 34. `GET /api/v1/analyze/corporate-actions/{analysis_id}`
- **Summary:** Retrieve complete corporate actions analysis results.
- **Response `200 OK`:** Full corporate actions analysis record.

---

#### 35. `GET /api/v1/analyze/corporate-actions/{analysis_id}/findings`
- **Summary:** Inspect corporate actions inconsistencies and price-discontinuity findings.
- **Query Parameters:**
  - `severity` (`string`, *Optional*): `"error"`, `"warning"`, `"info"`.
  - `code` (`string`, *Optional*): Substring match on finding code (e.g., `"confirmed_inconsistency"`, `"ex_date_inversion"`).
  - `limit` (`integer`, *Optional*, Default: `100`, Range: `1`–`500`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:** List of `FindingModel` records.

---

#### 36. `GET /api/v1/analyze/corporate-actions/{analysis_id}/coverage`
- **Summary:** Inspect corporate action coverage, symbol summaries, and action breakdowns.
- **Response `200 OK`:**
  ```json
  {
    "analysis_id": "ca-7a8b9c0d1e2f",
    "dataset_id": "existing-data",
    "coverage": 1.0,
    "by_symbol": {
      "INFY": 14
    },
    "by_purpose": {
      "DIVIDEND": 12,
      "BONUS": 1,
      "BUYBACK": 1
    },
    "by_series": {
      "EQ": 14
    },
    "duplicate_records": 0
  }
  ```

---

### 5.8 Analysis Runs Module

#### 37. `POST /api/v1/analysis-runs`
- **Summary:** Execute a multi-analyzer reliability analysis run against a dataset.
- **Purpose:** Central pipeline entry point. Executes requested analyzers, aggregates findings, builds chronological lifecycle events, and registers an exportable audit report.
- **Request Body JSON (`AnalysisRunRequest`):**
  ```json
  {
    "dataset_id": "existing-data",
    "analyzers": ["survivorship", "lookahead", "corporate_actions"],
    "backtest": {
      "target_index": "NIFTY 50",
      "universe_symbols": ["INFY", "TCS", "WIPRO"],
      "start_date": "2021-01-01",
      "end_date": "2025-12-31",
      "min_price_coverage": 0.95
    },
    "lookahead": {
      "decision_dates": ["2022-01-01", "2023-01-01", "2024-01-01"],
      "target_index": "NIFTY 50",
      "universe_symbols": ["INFY", "TCS"],
      "start_date": "2021-01-01",
      "end_date": "2025-12-31",
      "lookback_days": 90
    },
    "corporate_actions": {
      "dataset_id": "existing-data",
      "expected_symbol": null
    }
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "run_id": "run-3f4a5b6c7d8e",
    "dataset_id": "existing-data",
    "status": "completed",
    "created_at": "2026-10-24T02:19:30.000000+00:00",
    "completed_at": "2026-10-24T02:19:32.500000+00:00",
    "analyzers_requested": ["survivorship", "lookahead", "corporate_actions"],
    "analyzers_executed": ["survivorship", "lookahead", "corporate_actions"],
    "analyzers_skipped": [],
    "error_count": 0,
    "warning_count": 0,
    "findings_count": 6,
    "summary": {
      "overall_status": "PASS",
      "total_analyzers": 3,
      "executed_count": 3,
      "skipped_count": 0,
      "error_count": 0,
      "warning_count": 0,
      "findings_count": 6,
      "by_analyzer": {
        "survivorship": {"status": "PASS", "errors": 0, "warnings": 0},
        "lookahead": {"status": "PASS", "errors": 0, "warnings": 0},
        "corporate_actions": {"status": "PASS", "errors": 0, "warnings": 0}
      }
    },
    "report_id": "rep-9a8b7c6d5e4f"
  }
  ```

---

#### 38. `GET /api/v1/analysis-runs`
- **Summary:** List historical analysis runs.
- **Query Parameters:**
  - `dataset_id` (`string`, *Optional*): Filter runs by dataset ID.
  - `limit` (`integer`, *Optional*, Default: `50`, Range: `1`–`200`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:**
  ```json
  [
    {
      "run_id": "run-3f4a5b6c7d8e",
      "dataset_id": "existing-data",
      "status": "completed",
      "created_at": "2026-10-24T02:19:30.000000+00:00",
      "completed_at": "2026-10-24T02:19:32.500000+00:00",
      "analyzers_executed": ["survivorship", "lookahead", "corporate_actions"],
      "findings_count": 6,
      "report_id": "rep-9a8b7c6d5e4f"
    }
  ]
  ```

---

#### 39. `GET /api/v1/analysis-runs/{run_id}`
- **Summary:** Retrieve full details of an analysis run.
- **Response `200 OK`:** Returns full run dictionary including `analyzers_executed`, `analyzer_results`, `findings`, `limitations`, `events`, and `summary`.

---

#### 40. `GET /api/v1/analysis-runs/{run_id}/findings`
- **Summary:** Retrieve consolidated findings from an analysis run.
- **Query Parameters:**
  - `severity` (`string`, *Optional*): `"error"`, `"warning"`, `"info"`.
  - `analyzer` (`string`, *Optional*): `"survivorship"`, `"lookahead"`, `"corporate_actions"`.
  - `limit` (`integer`, *Optional*, Default: `100`, Range: `1`–`500`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:** Array of consolidated `FindingModel` records across all executed analyzers.

---

#### 41. `GET /api/v1/analysis-runs/{run_id}/summary`
- **Summary:** Retrieve consolidated summary counts and completion status for an analysis run.
- **Response `200 OK`:**
  ```json
  {
    "overall_status": "PASS",
    "total_analyzers": 3,
    "executed_count": 3,
    "skipped_count": 0,
    "error_count": 0,
    "warning_count": 0,
    "findings_count": 6,
    "by_analyzer": {
      "survivorship": {"status": "PASS", "errors": 0, "warnings": 0},
      "lookahead": {"status": "PASS", "errors": 0, "warnings": 0},
      "corporate_actions": {"status": "PASS", "errors": 0, "warnings": 0}
    }
  }
  ```

---

#### 42. `POST /api/v1/analysis-runs/{run_id}/cancel`
- **Summary:** Request cancellation of an analysis run.
- **Purpose:** Idempotent cancellation endpoint. Because runs execute synchronously in BRA, returns status message noting run completion.
- **Response `200 OK`:**
  ```json
  {
    "run_id": "run-3f4a5b6c7d8e",
    "status": "completed",
    "cancellable": false,
    "message": "Run run-3f4a5b6c7d8e has already completed execution."
  }
  ```

---

#### 43. `GET /api/v1/analysis-runs/{run_id}/events`
- **Summary:** Retrieve execution lifecycle events for an analysis run.
- **Response `200 OK`:**
  ```json
  [
    {"timestamp": "2026-10-24T02:19:30.000000+00:00", "event": "run_initialized", "run_id": "run-3f4a5b6c7d8e"},
    {"timestamp": "2026-10-24T02:19:30.100000+00:00", "event": "survivorship_started"},
    {"timestamp": "2026-10-24T02:19:31.200000+00:00", "event": "lookahead_started"},
    {"timestamp": "2026-10-24T02:19:32.000000+00:00", "event": "corporate_actions_started"},
    {"timestamp": "2026-10-24T02:19:32.500000+00:00", "event": "run_completed"}
  ]
  ```

---

### 5.9 Reports & Exports Module

#### 44. `GET /api/v1/reports`
- **Summary:** List all available generated reliability reports.
- **Query Parameters:**
  - `limit` (`integer`, *Optional*, Default: `50`, Range: `1`–`200`).
  - `offset` (`integer`, *Optional*, Default: `0`, Min: `0`).
- **Response `200 OK`:**
  ```json
  [
    {
      "report_id": "rep-9a8b7c6d5e4f",
      "run_id": "run-3f4a5b6c7d8e",
      "dataset_id": "existing-data",
      "created_at": "2026-10-24T02:19:32.500000+00:00",
      "overall_status": "PASS",
      "error_count": 0,
      "warning_count": 0,
      "available_formats": ["json", "csv", "pdf"]
    }
  ]
  ```

---

#### 45. `GET /api/v1/reports/{report_id}`
- **Summary:** Retrieve report metadata, findings summary, and limitations.
- **Path Parameters:**
  - `report_id` (`string`, **Required**): Target report identifier.
- **Response `200 OK`:**
  ```json
  {
    "report_id": "rep-9a8b7c6d5e4f",
    "run_id": "run-3f4a5b6c7d8e",
    "dataset_id": "existing-data",
    "created_at": "2026-10-24T02:19:32.500000+00:00",
    "overall_status": "PASS",
    "summary": {
      "overall_status": "PASS",
      "total_analyzers": 3,
      "executed_count": 3,
      "skipped_count": 0,
      "error_count": 0,
      "warning_count": 0,
      "findings_count": 6
    },
    "analyzers": ["survivorship", "lookahead", "corporate_actions"],
    "findings": [
      {
        "id": "fnd-10293847",
        "analyzer": "survivorship",
        "code": "survivorship.matched_coverage",
        "classification": "fact",
        "severity": "info",
        "message": "Index constituent membership coverage confirmed at 100.0%",
        "row": null,
        "column": null,
        "symbol": null,
        "date": null,
        "evidence": null,
        "limitations": null,
        "remediation": null
      }
    ],
    "limitations": [],
    "available_formats": ["json", "csv", "pdf"]
  }
  ```

---

#### 46. `GET /api/v1/reports/{report_id}/download`
- **Summary:** Download analysis report in JSON, CSV, or PDF format.
- **Purpose:** Generates or streams the final audit deliverable in the requested format.
- **Path Parameters:**
  - `report_id` (`string`, **Required**): Target report identifier.
- **Query Parameters:**
  - `format` (`string`, *Optional*, Default: `"json"`): Export format: `"json"`, `"csv"`, `"pdf"`, `"xlsx"`.
- **Response Headers & Media Types:**
  - For `format=json`: `Content-Type: application/json`, attachment `report_{report_id}.json`.
  - For `format=csv`: `Content-Type: text/csv`, attachment `report_{report_id}.csv`.
  - For `format=pdf`: `Content-Type: application/pdf`, attachment `report_{report_id}.pdf`.
- **Error Responses:**
  - `400 Bad Request`: `{"detail": "Unsupported format 'xml'. Supported formats: 'json', 'csv', 'pdf'."}`
  - `404 Not Found`: `{"detail": "Report 'rep-nonexistent' not found."}`
  - `501 Not Implemented`:
    ```json
    {
      "detail": "XLSX export is not supported. The repository's Excel support is read-only without external spreadsheet generation dependencies."
    }
    ```

---

## 6. Global Error Handling & HTTP Status Code Matrix

The BRA API enforces strict error boundary hygiene. Unhandled server exceptions never leak absolute local file system paths, stack traces, or environment secrets to clients.

### Standard Error Formats

1. **Standard `HTTPException` Format (4xx / 5xx):**
   ```json
   {
     "detail": "Dataset 'ds-982341' not found."
   }
   ```

2. **Pydantic Validation Error Format (`422 Unprocessable Entity`):**
   ```json
   {
     "detail": "Request validation failed.",
     "errors": [
       {
         "type": "greater_than_equal",
         "loc": ["query", "limit"],
         "msg": "Input should be greater than or equal to 1",
         "input": 0,
         "ctx": {"ge": 1}
       }
     ]
   }
   ```

3. **Unhandled Internal Server Error (`500 Internal Server Error`):**
   ```json
   {
     "detail": "An internal server error occurred while processing the request."
   }
   ```

### Status Code Matrix

| Status Code | Reason / Meaning | Common Occurrence Scenarios |
|-------------|------------------|-----------------------------|
| `200 OK` | Request succeeded | `GET` queries, data preparation, dataset validation |
| `201 Created` | Resource created | File uploads (`/upload`), analyzer executions, combined runs |
| `400 Bad Request` | Client logical violation | Empty upload batch; attempting to delete canonical dataset `existing-data`; missing both `dataset_id` and `run_id` |
| `404 Not Found` | Resource nonexistent | Unknown `dataset_id`, `analysis_id`, `run_id`, `report_id`, or `schema_type` |
| `413 Payload Too Large` | Exceeded file limit | Uploaded file size > `max_upload_size_bytes` (Default: 100 MB) |
| `415 Unsupported Media` | Invalid extension | Non-CSV file uploaded (e.g., `.xlsx`, `.txt`, `.parquet`) |
| `422 Unprocessable Entity` | Schema validation error | Invalid JSON schema, malformed query parameter range (e.g. `limit < 1`) |
| `500 Internal Server Error` | Unhandled error | Captured by global exception handler; logged with internal stack trace |
| `501 Not Implemented` | Unsupported feature | Requesting `format=xlsx` report export |

---

## 7. Known Assumptions, Limitations & Unsupported Features

To ensure complete transparency during audits and quantitative integrations, the following boundaries and architectural constraints are explicitly documented:

1. **Quantification of Survivorship-Bias Return Impact (P&L Delta):**
   - *Status:* **Not Implemented.**
   - *Detail:* The survivorship analyzer reports coverage ratios, matching evidence, delisted symbol reconciliation, and identifier reuse. It does not compute a simulated P&L difference between a survivorship-biased portfolio and a point-in-time portfolio.

2. **Point-in-Time Financial Results Database Engine:**
   - *Status:* **Out of Scope / Temporal Boundary Only.**
   - *Detail:* The BRA API is not a point-in-time financial database engine. It verifies temporal ordering between declared backtest decision timestamps and corporate result dissemination timestamps to detect look-ahead leakage.

3. **Excel Spreadsheet (XLSX) Export:**
   - *Status:* **Unsupported (HTTP 501 Not Implemented).**
   - *Detail:* BRA enforces a zero-external-spreadsheet-dependency footprint in production. Excel file handling in the repository is strictly read-only for inspection. Reports are exported exclusively as JSON, CSV, and PDF.

4. **Background Task Queue & In-Flight Cancellation:**
   - *Status:* **Synchronous Execution.**
   - *Detail:* The API executes analysis runs synchronously within the request lifespan. The cancellation endpoint (`POST /analysis-runs/{run_id}/cancel`) is provided for workflow parity and returns the finalized run state.

5. **Server-Sent Events (SSE) Streaming:**
   - *Status:* **Polled Event Model.**
   - *Detail:* Real-time run progression is tracked via the event polling endpoint `GET /api/v1/analysis-runs/{run_id}/events`.
