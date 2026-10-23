# // BRA — Backtest Reliability Analyzer Frontend

A production-quality financial analytics and quant audit dashboard for detecting **survivorship bias**, **look-ahead bias**, **corporate actions distortions**, and **historical dataset quality issues** in backtesting data.

Built with **React 19**, **Vite**, **TypeScript**, **Tailwind CSS**, **TanStack Query v5**, **Recharts**, and **Axios**, faithfully recreating the **Devlab editorial design language** (minimalist light-grey canvas, crisp 1px black borders, Space Grotesk editorial typography, bold oversized headings, vibrant red and muted blue accents, brutal drop shadows, and abstract geometric SVG artwork).

---

## Architecture & Design Principles

- **Zero-Hardcoding Principle**: Never fakes business metrics, synthetic records, or dummy runs. Every number, chart, status badge, and finding directly binds to real responses from the FastAPI backend (`http://localhost:8000`).
- **Devlab Editorial Aesthetic**:
  - Off-white canvas (`#f8f9fa`) with pure black typography and crisp `border-black` grids.
  - Brutal drop shadows (`3px 3px 0px 0px #000000`).
  - Space Grotesk for editorial headings, JetBrains Mono for financial tickers and timestamps.
  - Vibrant `#ff3b30` red and `#4a8b9f` muted blue accents.
  - Bespoke geometric visual graphics (wireframe nodes, red triangle, blue pill toggle, directional arrow, starbursts).
- **Honest Status & Error Reporting**:
  - Real status states: `PASS`, `WARN`, `FAIL`, `COMPLETED`, `PARTIAL FAILURE`.
  - Unsupported capabilities (such as Excel `.xlsx` downloads) communicate `HTTP 501 Not Implemented` with clear fallback guidance to PDF, CSV, or JSON.
  - Canonical read-only dataset protection (`existing-data` cannot be deleted).

---

## Quick Start

### 1. Start the Backend API (FastAPI)
In the repository root:
```powershell
.venv\Scripts\python -m bra.api --host 127.0.0.1 --port 8000
```
Backend will be active at `http://localhost:8000` (Swagger docs at `http://localhost:8000/docs`).

### 2. Start the Frontend Development Server
In the `frontend/` directory:
```bash
npm run dev
```
The application will be live at `http://localhost:5173`.

---

## Commands & Verification

| Command | Description |
| :--- | :--- |
| `npm run dev` | Starts Vite development server at `http://localhost:5173` |
| `npm test` | Runs the Vitest unit & integration test suite (22 tests passing) |
| `npm run build` | Compiles TypeScript and creates optimized production bundle in `dist/` |
| `npx tsc --noEmit` | Verifies TypeScript types without emitting files |
| `npm run lint` | Runs the Oxlint static analyzer |

---

## Integrated Pages & Backend Endpoints

### 1. Overview Dashboard (`/`)
- Hero section with bespoke Devlab geometric visual art and platform metrics.
- 4-column metric ribbon: Datasets, Executed Runs, Flagged Findings, Generated Reports.
- Engine summary cards for Survivorship, Look-Ahead, and Corporate Actions.
- Execution frequency distribution chart (Recharts) and Recent Runs table.
- Direct links to launch analyses and inspect datasets.

### 2. Datasets Management (`/datasets`, `/datasets/:datasetId`)
- **Endpoints**: `GET /api/v1/datasets`, `GET /api/v1/datasets/{id}`, `POST /api/v1/datasets/upload`, `DELETE /api/v1/datasets/{id}`, `GET /api/v1/datasets/{id}/preview`, `GET /api/v1/datasets/{id}/schema`, `GET /api/v1/datasets/{id}/mapping`, `POST /api/v1/datasets/{id}/mapping`, `POST /api/v1/datasets/{id}/prepare`, `GET /api/v1/datasets/{id}/quality-summary`.
- Multi-CSV drag-and-drop file upload.
- Canonical dataset distinction: `existing-data` is marked as read-only and protected from accidental deletion.
- In-depth detail view with 5 tabs: File Inventory, Paginated Data Preview, Inferred Schema, Prepared Dataset Normalization, and 0–100 Data Quality Score gauge.
- Interactive Column Mapping modal with auto-suggest.

### 3. Data Validation (`/validation`)
- **Endpoints**: `POST /api/v1/validate`, `GET /api/v1/validations/{id}`, `GET /api/v1/validations/{id}/summary`, `GET /api/v1/validations/{id}/findings`.
- Comprehensive structural validation trigger supporting dataset selection and strictness levels.
- Visual PASS / WARN / FAIL status banner, error counts, and filterable findings.

### 4. Survivorship Bias Analysis (`/survivorship`)
- **Endpoints**: `POST /api/v1/analyze/survivorship`, `GET /api/v1/analyze/survivorship/{id}/universe`, `GET /api/v1/analyze/survivorship/{id}/delisted`, `GET /api/v1/analyze/survivorship/{id}/findings`.
- Audit form supporting Target Benchmark Index, Date Range, Universe Symbols, and Min Price Coverage.
- Displays Historical Universe Coverage, Delisted Security Price History Coverage, and Symbol Reuse Anomaly findings.

### 5. Look-Ahead Bias Analysis (`/lookahead`)
- **Endpoints**: `POST /api/v1/analyze/lookahead`, `GET /api/v1/analyze/lookahead/{id}/timeline`, `GET /api/v1/analyze/lookahead/{id}/findings`.
- Audit configuration for Decision Dates, Target Index, and Lookback Window.
- Chronological event timeline showing financial publication releases vs. strategy decision moments, highlighting look-ahead leaks and unannounced earnings revisions.

### 6. Corporate Actions Analysis (`/corporate-actions`)
- **Endpoints**: `POST /api/v1/analyze/corporate-actions`, `GET /api/v1/analyze/corporate-actions/{id}/coverage`, `GET /api/v1/analyze/corporate-actions/{id}/findings`.
- Configuration form with optional symbol filter.
- Visual breakdown of detected splits, bonus issues, dividends, and anomalous price leaps with unadjusted trading volume.

### 7. Analysis Runs (`/runs`, `/runs/:runId`)
- **Endpoints**: `GET /api/v1/analysis-runs`, `POST /api/v1/analysis-runs`, `GET /api/v1/analysis-runs/{id}`, `GET /api/v1/analysis-runs/{id}/summary`, `GET /api/v1/analysis-runs/{id}/findings`, `GET /api/v1/analysis-runs/{id}/events`, `POST /api/v1/analysis-runs/{id}/cancel`.
- Full execution registry with status filtering, multi-engine run orchestration modal, cancellation trigger, telemetry event log, and consolidated findings.

### 8. Findings Explorer (`/findings`)
- Multi-faceted global audit explorer.
- Filters by Run Source, Severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`), Engine (`survivorship`, `lookahead`, `corporate_actions`, `validation`), and keyword search.
- Slide-over inspection drawer for granular evidence payloads and recommended remediations.
- Export findings as JSON.

### 9. Reports & Compliance Exports (`/reports`)
- **Endpoints**: `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, `GET /api/v1/reports/{id}/download?format=pdf|csv|json|xlsx`.
- Formal audit dossier downloads:
  - **PDF Report**: Fully formatted visual document generated with ReportLab.
  - **CSV Flat**: Tabular findings file for Pandas / Excel analysis.
  - **JSON Schema**: Full structured telemetry and findings hierarchy.
  - **Excel (.xlsx)**: Transparently communicates `HTTP 501 Not Implemented` with prompt user notification.

### 10. System & API Status (`/status`, `/system`)
- **Endpoints**: `GET /health`, `GET /api/v1/health`, `GET /api/v1/metadata`, `GET /api/v1/schemas`.
- Live API health telemetry with ping latency benchmark.
- Storage subsystem health, active engines registry, canonical schemas, and file ingestion constraints.

---

## Environment Configuration

Create a `.env` or `.env.local` file in `frontend/` if connecting to a remote backend:

```env
VITE_API_BASE_URL=http://localhost:8000
```
Default fallback is `http://localhost:8000`.
