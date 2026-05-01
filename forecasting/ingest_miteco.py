"""Ingest MITECO Boletín Hidrológico Semanal historical reservoir data.

Reads BD-Embalses.csv (exported from the Access DB at data/raw/miteco/),
filters to the Guadalquivir basin, normalizes Spanish formatting, and writes
a long-format table to data/processed/reservoirs_weekly.csv.

Net inflow is approximated as week-over-week storage delta — MITECO does not
publish gross inflow, and outflow data is not available here either.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw" / "miteco" / "BD-Embalses.csv"
OUT = PROJECT_ROOT / "data" / "processed" / "reservoirs_weekly.csv"
BASIN = "Guadalquivir"


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def main() -> None:
    df = pd.read_csv(
        RAW,
        parse_dates=["FECHA"],
        date_format="%m/%d/%y %H:%M:%S",
    )
    df = df[df["AMBITO_NOMBRE"] == BASIN].copy()

    df = df.rename(
        columns={
            "AMBITO_NOMBRE": "basin",
            "EMBALSE_NOMBRE": "reservoir_name",
            "FECHA": "week_ending",
            "AGUA_TOTAL": "capacity_hm3",
            "AGUA_ACTUAL": "volume_hm3",
            "ELECTRICO_FLAG": "is_hydroelectric",
        }
    )
    df["capacity_hm3"] = to_float(df["capacity_hm3"])
    df["volume_hm3"] = to_float(df["volume_hm3"])
    df["is_hydroelectric"] = df["is_hydroelectric"].fillna(0).astype(int)

    df = df.sort_values(["reservoir_name", "week_ending"]).reset_index(drop=True)
    df["storage_delta_hm3"] = df.groupby("reservoir_name")["volume_hm3"].diff()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    print(f"Wrote {len(df):,} rows to {OUT.relative_to(PROJECT_ROOT)}")
    print(f"Reservoirs: {df['reservoir_name'].nunique()}")
    print(
        f"Date range: {df['week_ending'].min().date()} → "
        f"{df['week_ending'].max().date()}"
    )
    print(f"Hydroelectric flagged: {df['is_hydroelectric'].sum() / len(df):.1%} of rows")


if __name__ == "__main__":
    main()
