#!/usr/bin/env python3
"""Reproducible extraction of NSE index snapshot PDFs to CSV.

Uses pdfplumber to extract tables from snapshot PDFs obtained from
NSE/NIFTYIndices monthly "Market Capitalisation & Weightage" ZIPs.
Raw PDFs are treated as provenance evidence; extracted CSVs are convenience samples.

Usage:
  python scripts/extract_index_snapshot_pdfs.py \\
    --pdf data/reference/index_constituents/snapshots_pdfs/NIFTY_50_Sep2026.pdf \\
    --out data/reference/index_constituents/extracted_csv/NIFTY_50_Sep2026.csv \\
    --snapshot-date 2026-09-30 --index-name "NIFTY 50"
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

try:
    import pdfplumber
except ImportError as exc:
    raise SystemExit(f"pdfplumber required: {exc}")


HEADERS = [
    "symbol",
    "security_name",
    "industry",
    "close_price",
    "index_mcap_cr",
    "weightage_pct",
    "snapshot_date",
    "index_name",
    "source_pdf",
]


def extract(pdf_path: Path, snapshot_date: str, index_name: str) -> list[dict[str, str]]:
    rows_out: list[dict[str, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                hdr = [(c or "").replace("\n", " ").strip() for c in table[0]]
                if not hdr or hdr[0].lower() != "symbol":
                    continue
                for r in table[1:]:
                    if not r or not r[0]:
                        continue
                    sym = (r[0] or "").strip()
                    if not sym or not sym[0].isalpha():
                        continue
                    sec = (r[1] or "").replace("\n", " ").strip() if len(r) > 1 else ""
                    if len(r) == 6:
                        industry = (r[2] or "").replace("\n", " ").strip()
                        close = (r[3] or "").strip()
                        mcap = (r[4] or "").replace("\n", " ").strip()
                        wt = (r[5] or "").strip()
                    elif len(r) == 5:
                        industry = (r[2] or "").replace("\n", " ").strip()
                        close = (r[3] or "").strip()
                        mcap = (r[4] or "").strip()
                        wt = ""
                    else:
                        continue
                    rows_out.append(
                        {
                            "symbol": sym,
                            "security_name": sec,
                            "industry": industry,
                            "close_price": close,
                            "index_mcap_cr": mcap,
                            "weightage_pct": wt,
                            "snapshot_date": snapshot_date,
                            "index_name": index_name,
                            "source_pdf": pdf_path.name,
                        }
                    )
    return rows_out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--snapshot-date", required=True)
    p.add_argument("--index-name", required=True)
    args = p.parse_args()
    rows = extract(args.pdf, args.snapshot_date, args.index_name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
