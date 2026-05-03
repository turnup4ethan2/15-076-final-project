"""Ingest the CSIC Spanish Drought Catalogue v1.0 event-level table.

Reads Identification_and_characteristics.xlsx (Events sheet), skips the
metadata header rows, parses month.year dates, normalizes columns, and
writes data/processed/drought_events.csv.

The catalogue covers Spain as a whole (40 droughts, 1916-2020). For our
backtest we use events that overlap our MITECO window (1988-present);
overlap is computed at use time, not here.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw" / "csic_drought" / "Identification_and_characteristics.xlsx"
OUT = PROJECT_ROOT / "data" / "processed" / "drought_events.csv"

# The catalogue's time series begins January 1916 (month index 1).
TIME_SERIES_BASE = pd.Timestamp("1916-01-01")


def month_index_to_date(idx) -> pd.Timestamp | None:
    if pd.isna(idx):
        return None
    return TIME_SERIES_BASE + pd.DateOffset(months=int(idx) - 1)


def main() -> None:
    df = pd.read_excel(RAW, sheet_name="Events")
    df = df.dropna(subset=["Event number"]).reset_index(drop=True)
    df["Event number"] = df["Event number"].astype(int)

    df = df.rename(
        columns={
            "Event number": "event_id",
            "Start month": "start_month_idx",
            "End month": "end_month_idx",
            "Start date": "start_date_raw",
            "End date": "end_date_raw",
            "Arrival time": "arrival_time",
            "Seasonality (start-end)": "seasonality",
            "Duration (months)": "duration_months",
            "Mean intensity (SPI-12)\xa0": "mean_intensity_spi12",
            "Area affected (% grid cells)": "area_affected_pct",
            "Months with area > 50%": "months_above_50pct",
            "Propagation": "propagation",
        }
    )

    df["start_date"] = df["start_month_idx"].apply(month_index_to_date)
    df["end_date"] = df["end_month_idx"].apply(month_index_to_date)

    keep = [
        "event_id",
        "start_date",
        "end_date",
        "duration_months",
        "mean_intensity_spi12",
        "area_affected_pct",
        "months_above_50pct",
        "seasonality",
        "propagation",
    ]
    out = df[keep].copy()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    overlap = out[out["end_date"] >= "1988-01-01"]
    print(f"Wrote {len(out)} events to {OUT.relative_to(PROJECT_ROOT)}")
    print(f"Date range: {out['start_date'].min().date()} → {out['end_date'].max().date()}")
    print(f"Events overlapping MITECO window (≥1988): {len(overlap)}")
    print()
    print("MITECO-overlap events (relevant for backtest):")
    print(overlap[["event_id", "start_date", "end_date", "duration_months",
                   "mean_intensity_spi12", "area_affected_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
