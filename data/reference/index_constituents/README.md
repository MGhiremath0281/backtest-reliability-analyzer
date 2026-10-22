# Index constituents / historical universe samples (point-in-time)

This directory contains **verified, minimal samples** of NSE/NIFTY index-constituent point-in-time snapshots used to assess feasibility for survivorship-bias analysis. They are **evidence samples**, not a complete historical universe.

## Primary authoritative source (verified)
- **NSE Indices "Indices – Market Capitalisation & Weightage" monthly archive**: `https://www.niftyindices.com/reports/historical-data/Index/` (POST with `{"SelectedReportType":"4","SelectedDate":"","MonthYear":"Mon YYYY"}` returns `DownloadLink` to a zip). Direct zip GETs also work.
- **Coverage observed**: Sep 2013 → Sep 2026 available via this flow (Sep 2012 = "No Data Found").
- **Format**: Monthly ZIP containing per-index PDFs (snapshot PDFs) with columns: `Symbol`, `Security Name`, `Industry`, `Close Price`, `Index Mcap (Rs. Crores)`, `Weightage (%)`. Each snapshot is a **month-end point-in-time constituent list**.
- **Note on scope**: Earlier months (e.g., Mar 2022) include many indices (25–41); later months (e.g., Sep 2026) include fewer (~7). "NIFTY 50" membership changes over time (reconstitutions) — this is exactly what is needed for survivorship analysis, but current constituents cannot substitute.

## Included samples (SHA-256 in manifest_samples.csv)
- Zips: `indices_dataJun2013.zip`, `indices_dataSep2013.zip`, `indices_dataMar2022.zip`, `indices_dataSep2026.zip` (downloaded via the verified POST/direct flow).
- Snapshot PDFs (extracted): `snapshots_pdfs/` — CNX NIFTY Jun/Sep 2013, NIFTY 50/500/Midcap 150/Smallcap 250 Mar 2022, NIFTY 50 Sep 2026.
- Extracted CSVs (table-parsed): `extracted_csv/` — `cnxnifty_Jun2013.csv`, `NIFTY_50_Mar2022.csv`, `NIFTY_50_Sep2026.csv` (parser: `pdfplumber` table extraction on pages with header `Symbol`; multi-line names merged by table cells). These are **convenience extracts** for quick inspection; **raw PDFs are the provenance evidence**.

## Limitations
- Snapshot PDFs are the observed format in these samples; NSE may change layout over time. Parsing must be robust (table-based preferred over regex).
- No announcement dates/rebalancing schedules captured here — membership effective dates are implied by the snapshot month but need confirmation against index-change press releases.
- This is a **small feasibility sample** collected under the constraints of this task (no guessing, verified retrieval only).

## Related
- Index-change press releases (verified): `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf` (1,515 PDFs listed on the real index page `https://www.niftyindices.com/press-release`; coverage observed 1998-09-02 → current; each PDF carries the effective date plus IN/OUT symbols and names). **Caveat:** this host returns HTTP 200 with an HTML "Error 404" page for any date without a release (a soft-404), so HTTP status alone is not proof of a PDF — always verify the response starts with `%PDF-` and enumerate real dates from the listing page instead of guessing them.
- See `docs/historical-universe-gap.md` for full source inventory, gaps, and required deliverables table.
