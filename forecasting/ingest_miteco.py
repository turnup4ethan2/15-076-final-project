"""Ingest MITECO Boletín Hidrológico Semanal historical reservoir data.

Reads either:
  - data/raw/miteco/BD-Embalses.csv (manual export), or
  - data/raw/miteco/BD-Embalses.mdb (from the official BD-Embalses.zip), using
    the `mdb-export` CLI from mdbtools (macOS: `brew install mdbtools`).

Filters to the Guadalquivir basin, normalizes Spanish formatting, and writes
data/processed/reservoirs_weekly.csv.

Net inflow is approximated as week-over-week storage delta — MITECO does not
publish gross inflow, and outflow data is not available here either.
"""

from __future__ import annotations

import shutil
import subprocess
from io import StringIO
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "miteco" / "BD-Embalses.csv"
RAW_MDB = PROJECT_ROOT / "data" / "raw" / "miteco" / "BD-Embalses.mdb"
OUT = PROJECT_ROOT / "data" / "processed" / "reservoirs_weekly.csv"
BASIN = "Guadalquivir"


def _embalses_table_name(mdb_path: Path) -> str:
    out = subprocess.check_output(
        ["mdb-tables", "-1", str(mdb_path)],
        text=True,
    ).strip()
    if not out:
        raise RuntimeError(f"No tables found in {mdb_path}")
    return out


def _read_embalses_from_mdb(mdb_path: Path) -> pd.DataFrame:
    mdb_export = shutil.which("mdb-export")
    if not mdb_export:
        raise FileNotFoundError(
            "BD-Embalses.mdb is present but `mdb-export` was not found. "
            "Install mdbtools (e.g. `brew install mdbtools`) or export the "
            "main table to BD-Embalses.csv manually from Microsoft Access."
        )
    table = _embalses_table_name(mdb_path)
    proc = subprocess.run(
        [mdb_export, str(mdb_path), table],
        check=True,
        capture_output=True,
        text=True,
    )
    return pd.read_csv(StringIO(proc.stdout))


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def main() -> None:
    if RAW_CSV.is_file():
        df = pd.read_csv(
            RAW_CSV,
            parse_dates=["FECHA"],
            date_format="%m/%d/%y %H:%M:%S",
        )
    elif RAW_MDB.is_file():
        df = _read_embalses_from_mdb(RAW_MDB)
        df["FECHA"] = pd.to_datetime(df["FECHA"], format="%m/%d/%y %H:%M:%S")
    else:
        raise FileNotFoundError(
            f"Expected {RAW_CSV} or {RAW_MDB}. "
            "Download BD-Embalses.zip from the MITECO Boletín Hidrológico page, "
            "unzip BD-Embalses.mdb into data/raw/miteco/, or place an exported "
            "BD-Embalses.csv there."
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
