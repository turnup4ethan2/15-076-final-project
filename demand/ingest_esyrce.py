"""Ingest ESYRCE 2025 Andalucía crop survey.

The Andalucía workbook has one sheet per province with crop area in hectares
broken into rainfed (Secano), irrigated (Regadío), and greenhouse (Invernadero).
We keep the 8 Andalusian provinces — these are the same set listed in our
Guadalquivir reference. Output: long-format table at
data/processed/crops_annual.csv with one row per (province, crop).

Note: ESYRCE only releases province-level data publicly for the most recent
year via the Andalucía workbook. Older years aggregate to autonomous-community
level. For our demand model that's fine — we use current crop mix, not trend.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw" / "esyrce" / "andalucia_2025.xlsx"
OUT = PROJECT_ROOT / "data" / "processed" / "crops_annual.csv"

PROVINCE_NAME_MAP = {
    "ALMERIA": "Almería",
    "CADIZ": "Cádiz",
    "CORDOBA": "Córdoba",
    "GRANADA": "Granada",
    "HUELVA": "Huelva",
    "JAEN": "Jaén",
    "MALAGA": "Málaga",
    "SEVILLA": "Sevilla",
}

YEAR = 2025


def ingest_province(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, header=2)
    df = df.rename(
        columns={
            "Cultivo o cubierta": "crop",
            "Secano": "rainfed_ha",
            "Regadío": "irrigated_ha",
            "Invernadero": "greenhouse_ha",
            "Total": "total_ha",
        }
    )
    df = df.dropna(subset=["crop"]).reset_index(drop=True)
    df["crop"] = df["crop"].astype(str).str.strip()
    df = df[~df["crop"].str.upper().str.startswith(("TOTAL", "SUBTOTAL"))]
    df["province"] = PROVINCE_NAME_MAP[sheet]
    df["year"] = YEAR

    for c in ("rainfed_ha", "irrigated_ha", "greenhouse_ha", "total_ha"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df[["year", "province", "crop", "rainfed_ha",
               "irrigated_ha", "greenhouse_ha", "total_ha"]]


def main() -> None:
    frames = [ingest_province(RAW, sheet) for sheet in PROVINCE_NAME_MAP]
    out = pd.concat(frames, ignore_index=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print(f"Wrote {len(out)} rows to {OUT.relative_to(PROJECT_ROOT)}")
    print(f"Provinces: {sorted(out['province'].unique())}")
    print(f"Total irrigated area (ha): {out['irrigated_ha'].sum():,.0f}")
    print()
    print("Top 15 irrigated crops across the 8 provinces:")
    top = (out.groupby("crop")["irrigated_ha"].sum()
              .sort_values(ascending=False).head(15))
    for crop, ha in top.items():
        print(f"  {ha:>12,.0f} ha  {crop}")


if __name__ == "__main__":
    main()
