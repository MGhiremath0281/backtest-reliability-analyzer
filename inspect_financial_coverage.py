import glob, os
import pandas as pd

folders = [
    "data/reference/financial_results/*.csv",
    "data/reference/financial_results/additional/*.csv"
]

for pattern in folders:
    for f in sorted(glob.glob(pattern)):
        df = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
        df.columns = df.columns.str.replace(r"\s+", " ", regex=True).str.strip()

        date_col = next(
            (c for c in ["PERIOD ENDED", "QUARTER END DATE"] if c in df.columns),
            None
        )
        if date_col is None:
            print(f"\n{os.path.basename(f)}: DATE COLUMN NOT FOUND")
            continue

        dates = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        print(
            f"\n{os.path.basename(f)}"
            f"\n  Rows: {len(df)}"
            f"\n  Date column: {date_col}"
            f"\n  Period range: {dates.min()} to {dates.max()}"
        )

        time_col = next(
            (c for c in ["EXCHANGE DISSEMINATION TIME",
                         "Exchange Dissemination Time"] if c in df.columns),
            None
        )
        if time_col:
            print(f"  Dissemination timestamps present: {df[time_col].notna().sum()} / {len(df)}")
