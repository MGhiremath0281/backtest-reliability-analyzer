# Historical universe data gap

This document records the investigation into the data required for reliable
survivorship-bias analysis: the point-in-time equity universe, historical index
constituent membership, and delisted-security price history. It answers what is
missing, which authoritative sources supply it, whether those sources are
actually reachable, and the smallest defensible collection plan for the
prototype.

Every claim below is either verified against a file in this repository (with its
SHA-256 recorded in `data/reference/index_constituents/manifest_samples.csv`)
or verified live against the source during this investigation. Where a source
could not be verified, that is stated explicitly. No source URL here is
inferred from pattern guessing alone.

Raw source files were downloaded into `data/reference/` and are never rewritten
or normalized in place. Normalized outputs are separate derived files under
`data/processed/normalized/`. This investigation does **not** implement
survivorship-bias detection; it only establishes whether the required data can
be collected.

## 1. What is missing

The audit (`docs/data-audit.md`) records the current position: survivorship-bias
analysis is `not_supported_by_current_data`. The concrete gaps are:

- **No point-in-time universe.** `EQUITY_L.csv` is a present-day snapshot (2,611
  rows). It contains only companies still listed today and structurally cannot
  represent companies that have since delisted or left an index.
- **No historical index membership.** There is no record of which securities
  belonged to NIFTY 50 (or any index) on a past date. Current constituents must
  never be substituted for historical membership.
- **No delisted-security price history.** Price data covers 4 symbols (INFY,
  RELIANCE, TCS, WIPRO), all currently listed. Delisted names have no return
  series, so post-delisting returns — the very quantity survivorship bias
  measures — cannot be computed.
- **No index-reconstitution / announcement history.** The dates on which
  securities entered or left an index are absent, so a rebalancing-aware
  backtest cannot be constructed.

The delisting event list itself *is* present and complete (460 rows,
2002-04-15 → 2026-10-16, from the official workbook). What is missing is the
membership timeline and the prices, not the event list.

## 2. Candidate sources and verification status

### 2.1 NSE Indices monthly constituent archive — primary source for membership

- **URL:** `https://www.niftyindices.com/reports/historical-data/Index/`
- **Access:** HTTP POST with JSON body
  `{"SelectedReportType":"4","SelectedDate":"","MonthYear":"Mon YYYY"}` returns
  `{"success":true,"reportName":"Indices - Market Capitalisation & Weightage","data":[{"DownloadLink":"/Indices_-_Market_Capitalisation_and_Weightage/indices_dataMonYYYY.zip",...}]}`.
  A direct GET of `https://www.niftyindices.com` + the returned `DownloadLink`
  then yields the ZIP. **Verified live** for Mar 2020 (POST returned a valid
  link; GET returned a 5,343,814-byte ZIP containing 40 per-index PDFs).
- **Format:** monthly ZIP of per-index PDFs. Each PDF is a month-end
  point-in-time constituent table with columns `Symbol`, `Security Name`,
  `Industry`, `Close Price`, `Index Mcap (Rs. Crores)`, `Weightage (%)`. The
  NIFTY 50 file is named `NIFTY_50_MonYYYY.pdf` (naming confirmed consistent
  across Mar 2020, Mar 2022, and Sep 2026 samples).
- **Coverage:** Sep 2013 → present. Verified lower boundary: Sep 2012 and Aug
  2012 both return `{"success":false,"message":"No Data Found"}`; Sep 2013
  succeeds. There is therefore a hard floor at **Sep 2013** for this archive.
- **Access requirements:** none beyond a standard browser-like User-Agent; no
  login, no API key, no rate-limit tokens observed on the sampled requests.
- **Provenance in repo:** four ZIPs under
  `data/reference/index_constituents/` (Jun 2013, Sep 2013, Mar 2022, Sep
  2026), seven extracted snapshot PDFs under `snapshots_pdfs/`, and three
  table-parsed CSVs under `extracted_csv/`. SHA-256 for every artifact is in
  `manifest_samples.csv`; all 19 hashes were re-verified during this
  investigation (19 ok, 0 mismatch).
- **Extraction reproducibility:** the CSVs were produced with `pdfplumber`
  table extraction on pages whose header row starts with `Symbol`, merging
  multi-line security names from table cells. Re-extracting
  `NIFTY_50_Mar2022.pdf` reproduced the checked-in CSV exactly (50 symbols,
  identical order and set).
- **Limitations:**
  - Coverage starts Sep 2013; anything earlier needs a different source.
  - PDFs are the observed format; NSE may change layout. Table-based parsing is
    required, not regex over raw text.
  - These are month-end snapshots. Membership effective dates are implied by
    the snapshot month but should be confirmed against index-change press
    releases (§2.2) before being treated as exact rebalance dates.
  - Index scope varies over time (Jun/Sep 2013 ZIPs carry fewer indices than
    Mar 2022's 41). Parse the specific index PDF needed; do not assume a fixed
    index list.

### 2.2 NSE Indices index-change press releases — for effective dates

- **URL pattern:** `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf`
- **Listing page (authoritative enumeration):**
  `https://www.niftyindices.com/press-release` — a 662 KB page carrying 1,515
  `ind_prs*.pdf` links spanning **1998-09-02 → 2026-10-22** (1,236 distinct
  dates). Enumerate real dates from this page; do not guess date strings.
- **Content (verified):** each PDF states the index, the effective date, and
  the IN/OUT company names and symbols. Verified example —
  `ind_prs22102026.pdf` (323,949 bytes, starts with `%PDF-`): "Inclusion in
  Nifty IPO index … effective from October 27, 2026 … HDF Fire Protect Ltd.
  HDFIRE".
- **Critical caveat (verified):** this host returns **HTTP 200 with an HTML
  "Error 404" page** for any date that has no release — a soft-404. HTTP status
  alone is not proof of a PDF. A date probed during this investigation
  (22-06-2012) returned 200 but an HTML body, not a PDF. Always confirm the
  response begins with `%PDF-` before treating it as a press release.
- **Use:** pair each monthly snapshot (§2.1) with the intervening press releases
  to obtain exact reconstitution effective dates, which snapshots alone only
  imply.

### 2.3 NSE historical bhavcopy — for delisted-security prices

- **Legacy format (pre-2020s):**
  `https://nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MMM/cmDDMONYYYYbhav.csv.zip`
  — **verified live** for many dates, including dates never collected into the
  repo (e.g. 2016-06-15 returned HTTP 200, 59,793 bytes).
- **Modern CMTS format:**
  `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`
  — **verified** (2024-07-08 sample, 2,815 rows, ISO 20022-style columns
  `TradDt`, `BizDt`, `ISIN`, `TckrSymb`, `SctySrs`, …).
- **Delisted-symbol feasibility (verified from repo samples):** the legacy
  bhavcopies already collected contain delisted names. `cm05JAN1999bhav.csv`
  (1,140 rows) contains RANBAXY and SESAGOA; `cm01JAN2014bhav.csv` (1,457 rows)
  and `cm02JAN2014bhav.csv` (1,468 rows) contain RANBAXY and CAIRN. This is the
  direct proof that historical prices for delisted securities are retrievable
  from this source up to their delisting/rename date.
- **Access requirements:** no login. A browser-like User-Agent is required;
  `nsearchives.nseindia.com` refuses some requests without one.
- **Limitations (verified and important):**
  - A missing bhavcopy for a date usually means a **market holiday**, not a
    delisting. Verified case: 24-Oct-2014 has no bhavcopy (holiday) while
    RANBAXY appears on both 23-Oct-2014 and 27-Oct-2014. A naive "last seen"
    heuristic would wrongly infer a delisting on 24-Oct-2014. Delisting dates
    must be reconciled against the official delisting workbook, never inferred
    from an absent bhavcopy day.
  - Coverage is per trading day and requires iterating over every trading date
    in the window; there is no per-symbol historical endpoint in these sources.

### 2.4 NSE "List of delisted Companies" CSV — rejected as incomplete

- **URL:** `https://nsearchives.nseindia.com/content/equities/delisted.csv`
- **Verified content:** 328 rows, delisting dates 2002 → Nov 2020 (repo copy in
  `data/reference/price_samples/delisted.csv`, SHA-256 in the manifest).
- **Why rejected (verified):** it is an old, incomplete export. RANBAXY, CAIRN,
  IDFC, HDFC, and SESAGOA are all **absent** from it, yet all are known
  delistings. It must not be used as the authoritative delisting list.
- **Authoritative alternative (verified):** the official "List of delisted
  Companies" workbook under `data/reference/listing_history/` — primary
  `delisted` sheet, 460 rows, 2002-04-15 → 2026-10-16. The repo copy
  `official_delisted.xlsx` is byte-identical (same SHA-256
  `8b5844a2adb402e…`) to the long-named `Copy_of_List_of_delisted_Companies_…xlsx`
  already present, confirming provenance.

### 2.5 Encoded-source handling note

The legacy `delisted.csv` is ISO-8859/Windows-1252 encoded (it contains byte
`0xA0`, a non-breaking space), not UTF-8. The read-only CSV loader was extended
to decode such files as Windows-1252 with a transparent `csv.encoding`
**warning** rather than discarding them, and it never rewrites the source file.
This is why the file now inventories with 328 rows instead of 0. The
`csv.header_blank` error reported against it is a genuine property of that
source (real trailing empty columns) and is intentionally left unfixed.

## 3. Feasibility conclusion

Both required source classes are accessible and permitted for a small
feasibility sample, and the samples are already collected and hash-verified in
this repository:

- **Membership:** reachable back to Sep 2013 via the POST flow; snapshots are
  parseable to CSV with a reproducible table extractor.
- **Delisted prices:** reachable per trading day from the legacy bhavcopy; a
  delisted symbol (RANBAXY, CAIRN, SESAGOA) is confirmed present in historical
  files.

## 4. Required datasets, sources, coverage, and next action

| # | Required dataset | Authoritative source | Exact coverage | Collection feasibility | Unresolved gap | Recommended next action |
|---|---|---|---|---|---|---|
| 1 | Point-in-time NIFTY 50 membership (month-end) | NSE Indices monthly archive, `https://www.niftyindices.com/reports/historical-data/Index/` (POST → DownloadLink → ZIP) | Sep 2013 → present (Sep 2012 = "No Data Found", verified) | **Feasible.** Verified live; samples collected + hash-verified; PDF→CSV extraction reproducible | Pre-Sep-2013 membership unavailable from this archive | Collect NIFTY_50 PDFs for every month Sep 2013 → present; parse to CSV with the verified table extractor |
| 2 | Index-reconstitution effective dates | NSE Indices press releases, `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf`; enumerate via `https://www.niftyindices.com/press-release` | 1998-09-02 → present (1,515 PDFs, verified) | **Feasible with care.** PDFs verified to carry effective date + IN/OUT symbols | Soft-404s return HTTP 200 with HTML; must validate `%PDF-` magic, not status codes | Enumerate dates from the listing page; download only listed dates; record effective dates keyed by index and date |
| 3 | Delisted-security daily prices | NSE legacy bhavcopy, `https://nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MMM/cmDDMONYYYYbhav.csv.zip` | Per trading day; verified across 1999, 2014, 2016 (incl. uncollected dates) | **Feasible.** Delisted symbols confirmed present in historical files | Must iterate every trading date; holidays look like gaps | For each delisted symbol, pull bhavcopies from listing to delisting date (from dataset 5); reconcile last-trade date against the workbook |
| 4 | Delisted-security prices, modern era | NSE CMTS bhavcopy, `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | Verified 2024-07-08 sample | **Feasible.** Different (ISO 20022) schema | Schema differs from legacy; needs a second parser and ISIN-based join | Implement the CMTS parser; join on ISIN to bridge legacy↔modern and to the delisting workbook |
| 5 | Authoritative delisting event list | Official "List of delisted Companies" workbook, `data/reference/listing_history/official_delisted.xlsx` (primary `delisted` sheet) | 2002-04-15 → 2026-10-16, 460 rows | **Already collected.** Byte-identical provenance confirmed | 6 malformed ISINs (e.g. "Not Available"); 1 date conflict with the auxiliary sheet | Use as the authority for delisting dates; carry malformed ISINs verbatim and resolve symbols via name/symbol-change history |
| 6 | Broad listed-universe membership (beyond NIFTY 50) | NSE Indices monthly archive, larger indices (NIFTY 500, Midcap 150, Smallcap 250) | Sep 2013 → present, same archive | **Feasible.** Mar 2022 samples for 500/Midcap150/Smallcap250 already collected | Same Sep 2013 floor; more PDFs per month | If the prototype universe is wider than NIFTY 50, add these indices to the month-by-month collection |

## 5. Recommended smallest defensible collection plan

For a prototype that must demonstrate survivorship-bias measurement without
over-collecting:

1. **Universe = NIFTY 50 only.** It is the smallest defensible index for a
   prototype, it is present in every monthly ZIP, and the membership changes
   are large enough to matter (see §6).
2. **Window = Sep 2013 → present.** This is the exact, verified floor of the
   archive. Do not attempt to reach earlier through this source; if pre-2013 is
   ever required, treat it as a separate, explicitly-scoped gap.
3. **Collect dataset 1 (monthly NIFTY 50 PDFs) and parse to CSV**, reusing the
   already-verified `pdfplumber` table extractor so results stay reproducible.
4. **Collect dataset 3 (legacy bhavcopy) for the delisted symbols** that appear
   in the membership history, pulling every trading day from listing to the
   workbook's delisting date. Reconcile last-trade dates against dataset 5.
5. **Add dataset 2 (press releases) only as needed** to pin exact effective
   dates where a monthly snapshot implies a change but the precise rebalance
   day matters.
6. **Preserve provenance throughout.** Keep every raw ZIP/PDF/CSV as-is with a
   SHA-256 manifest entry, as done for the current samples. Never overwrite or
   silently normalize a source file; write derived outputs separately.

This plan yields a point-in-time NIFTY 50 membership series and matching
delisted-security price history — the two things the audit currently reports as
missing — while collecting the minimum number of source files.

## 6. Evidence that membership changes materially

From the three verified NIFTY 50 snapshots in this repo (each 50 symbols):

- **Mar 2022 → Sep 2026:** 10 in, 10 out. Entered: ADANIENT, BEL, BSE,
  ETERNAL, INDIGO, JIOFIN, MAXHEALTH, SHRIRAMFIN, TMPV, TRENT. Left: BPCL,
  BRITANNIA, DIVISLAB, HDFC, HEROMOTOCO, INDUSINDBK, SHREECEM, TATAMOTORS,
  UPL, WIPRO.
- **Jun 2013 → Sep 2026:** 22 names left the index, including RANBAXY, CAIRN,
  IDFC, SESAGOA, and HDFC — several of which are also delisted.

These are exactly the names a survivorship-biased "buy-and-hold the current
index" backtest would silently omit, which is why current constituents cannot
substitute for the historical membership collected here.

## 7. Verification log

Every statement in this document was checked during the investigation:

- Manifest integrity: all 19 SHA-256 entries re-verified (19 ok, 0 mismatch).
- Archive POST flow: Mar 2020 returned a valid `DownloadLink`; the ZIP GET
  returned 5,343,814 bytes / 40 PDFs.
- Archive lower boundary: Sep 2012 and Aug 2012 → "No Data Found"; Sep 2013 →
  success.
- PDF extraction: re-extracting `NIFTY_50_Mar2022.pdf` reproduced the checked-in
  CSV exactly (50 symbols, identical order and set).
- Press-release listing page: 662 KB, 1,515 `ind_prs*.pdf` links,
  1998-09-02 → 2026-10-22.
- Press-release soft-404: an unlisted date returned HTTP 200 with an HTML body
  (not `%PDF-`); a listed date (`ind_prs22102026.pdf`) returned a real 323,949
  byte PDF whose text carries the effective date and IN/OUT symbols.
- Bhavcopy: 2016-06-15 (uncollected) returned HTTP 200; RANBAXY confirmed
  present on 23-Oct-2014 and 27-Oct-2014, with 24-Oct-2014 being a holiday
  (HTML, no bhavcopy).
- Legacy `delisted.csv`: 328 rows; RANBAXY, CAIRN, IDFC, HDFC, SESAGOA all
  absent, confirming it is incomplete and rejected.
- Provenance: `official_delisted.xlsx` is byte-identical (same SHA-256) to the
  existing `Copy_of_List_of_delisted_Companies_…xlsx`.
