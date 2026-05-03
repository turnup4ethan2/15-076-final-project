"""Build per-province monthly water demand from ESYRCE crop areas.

Pipeline:
1. Load crops_annual.csv (irrigated hectares by province × crop).
2. Drop ESYRCE parent categories (e.g. "OLIVAR (OL)") and the
   "SUPERFICIE GEOGRAFICA" pseudo-row to avoid double-counting.
3. Join with crop_water_requirements.csv (FAO-56 based; assumptions explicit
   in that file). Unmapped crops get a default rate with a flag.
4. Annual demand_hm3 = irrigated_ha × water_req_m3_per_ha_yr / 1e6.
5. Distribute across 12 months using a single ETo profile for southern
   Spain (single profile is a documented simplification — heterogeneity
   across crops is averaged out).
6. Write data/processed/demand_provincial_monthly.csv.

Methodological note: this is a fixed-coefficient demand model, not the
regression on climate covariates the proposal originally described. We
moved to fixed coefficients because AEMET weather ingestion was deferred
on the project timeline. The LP is still meaningful — it allocates a
realistic provincial demand under inflow uncertainty.
"""

from pathlib import Path
import re
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CROPS = PROJECT_ROOT / "data" / "processed" / "crops_annual.csv"
PROVINCES = PROJECT_ROOT / "data" / "processed" / "guadalquivir_provinces.csv"
CWR = Path(__file__).resolve().parent / "crop_water_requirements.csv"
OUT_MONTHLY = PROJECT_ROOT / "data" / "processed" / "demand_provincial_monthly.csv"
OUT_ANNUAL = PROJECT_ROOT / "data" / "processed" / "demand_provincial_annual.csv"

# ESYRCE parent-category names end with "(XX)" where XX is 1-3 uppercase letters.
PARENT_PATTERN = re.compile(r"\([A-Z]{1,3}\)\s*$")
EXCLUDE_NAMES = {"SUPERFICIE GEOGRAFICA"}

# Fallback coefficient for crops not present in the lookup.
DEFAULT_WATER_REQ_M3_HA = 5000

# Monthly ETo-weighted distribution for southern Spain (Cordoba reference).
# Sums to 1.0 — applied uniformly across crops as a documented simplification.
MONTHLY_PROFILE = {
    1: 0.03, 2: 0.04, 3: 0.06, 4: 0.09, 5: 0.12, 6: 0.14,
    7: 0.16, 8: 0.15, 9: 0.10, 10: 0.06, 11: 0.03, 12: 0.02,
}


def is_leaf_crop(name: str) -> bool:
    s = str(name).strip()
    if s in EXCLUDE_NAMES:
        return False
    if PARENT_PATTERN.search(s):
        return False
    return True


def main() -> None:
    crops = pd.read_csv(CROPS)
    cwr = pd.read_csv(CWR)

    # 1. Filter to leaf crops and rows with positive irrigated area
    crops = crops[crops["crop"].apply(is_leaf_crop)].copy()
    crops = crops[crops["irrigated_ha"] > 0].copy()

    # 2. Join with water-requirement coefficients
    merged = crops.merge(cwr[["crop", "water_req_m3_ha_yr"]], on="crop", how="left")
    merged["coefficient_source"] = merged["water_req_m3_ha_yr"].notna().map(
        {True: "lookup", False: "default"}
    )
    merged["water_req_m3_ha_yr"] = merged["water_req_m3_ha_yr"].fillna(
        DEFAULT_WATER_REQ_M3_HA
    )

    # 3. Annual demand per (province, crop), pre-basin-share
    merged["annual_demand_hm3"] = (
        merged["irrigated_ha"] * merged["water_req_m3_ha_yr"] / 1_000_000
    )

    # 4. Apply basin-share weighting: only the Guadalquivir portion of each
    # province feeds from this basin's reservoirs.
    provinces = pd.read_csv(PROVINCES)[["province", "basin_share"]]
    annual = (
        merged.groupby("province", as_index=False)["annual_demand_hm3"]
        .sum()
        .merge(provinces, on="province", how="left")
    )
    annual["basin_share"] = annual["basin_share"].fillna(0.0)
    annual["annual_demand_hm3"] = annual["annual_demand_hm3"] * annual["basin_share"]
    annual = annual[["province", "basin_share", "annual_demand_hm3"]]
    OUT_ANNUAL.parent.mkdir(parents=True, exist_ok=True)
    annual.to_csv(OUT_ANNUAL, index=False)

    # 5. Distribute across months using the single ETo profile
    monthly_rows = []
    for _, row in annual.iterrows():
        for month, share in MONTHLY_PROFILE.items():
            monthly_rows.append(
                {
                    "province": row["province"],
                    "month": month,
                    "demand_hm3": row["annual_demand_hm3"] * share,
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(OUT_MONTHLY, index=False)

    # 6. Reporting
    coverage = merged["coefficient_source"].value_counts(normalize=True)
    by_province = annual.sort_values("annual_demand_hm3", ascending=False)
    print(f"Wrote annual:  {OUT_ANNUAL.relative_to(PROJECT_ROOT)} ({len(annual)} rows)")
    print(f"Wrote monthly: {OUT_MONTHLY.relative_to(PROJECT_ROOT)} ({len(monthly)} rows)")
    print()
    print("Crop coverage by water-requirement source:")
    for src, frac in coverage.items():
        print(f"  {src:<8} {frac:.1%}")
    print()
    print("Annual demand by province (hm³/yr):")
    for _, r in by_province.iterrows():
        print(f"  {r['province']:<10}  {r['annual_demand_hm3']:>8.1f}")
    total = annual["annual_demand_hm3"].sum()
    print(f"  {'TOTAL':<10}  {total:>8.1f} hm³/yr (≈ {total/1000:.2f} km³/yr)")


if __name__ == "__main__":
    main()
