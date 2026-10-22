# Delisted-security price samples (feasibility)

## Verified sources
- **Legacy CM bhavcopy (old format)**: `https://nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MMM/cmDDMONYYYYbhav.csv.zip` (e.g., 1999, 2014 verified).
- **Modern CMTS bhavcopy**: `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` (e.g., 20240708 verified).
- **Full-day bhavcopy (older aggregate)**: `https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv` (retrievable in samples; format differs).
- **NSE "List of delisted Companies" reference CSV**: `https://nsearchives.nseindia.com/content/equities/delisted.csv` (328 rows, 2002–Nov 2020; **old format, incomplete** — missing RANBAXY, CAIRN, IDFC, HDFC, SESAGOA etc. per verification).

## Included samples
- Zips in `bhavcopy_zips/`: `legacy_19990105.zip`, `legacy_20140101.zip`, `legacy_20140102.zip`, `modern_20240708.zip` (downloaded during verification).
- `delisted.csv` (NSE old-format reference, as downloaded).
- Verification performed: RANBAXY appears on 23-Oct-2014 and again on 27-Oct-2014; 24-Oct-2014 has no bhavcopy because it was a market holiday (Diwali-adjacent), so that gap is **not** evidence of a delisting date and must not be read as one. SESAGOA appears until 01-Aug-2013, renamed to SSLT (VEDL context) — price history is retrievable up to delisting/rename via bhavcopy. Actual delisting dates must be reconciled against the official delisting workbook, never inferred from a missing bhavcopy day.

## Limitations
- Bhavcopy coverage depends on trading days; delisting/last-trade details need reconciliation with official delisting lists.
- Official authoritative delisting list is the **"List of delisted Companies" workbook** on nsearchives/media (verified byte-identical to repo copy under `data/reference/listing_history/`), not the old `delisted.csv`.

## Related
- `data/reference/listing_history/` contains the full-history delisting workbook (primary `delisted` sheet 460 rows) and current `EQUITY_L.csv`.
- See `docs/historical-universe-gap.md` for full analysis.
