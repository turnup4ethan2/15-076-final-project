"""Summarize basin storage stress during CSIC catalogue droughts vs baseline.

Reads:
  data/processed/drought_events.csv
  data/processed/reservoirs_weekly.csv

Writes:
  data/processed/drought_basin_stress.csv — one row per catalogue event that
    overlaps the MITECO weekly window; compares mean weekly storage delta
    during the event to the same reservoirs' mean outside events.

This is a *descriptive* backtest layer for slides/report — it does not
re-run the LP. Use LP_STRESS_LIST in run_lp.jl for counterfactual supply
scaling on top of LSTM quantiles.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DROUGHT = ROOT / "data" / "processed" / "drought_events.csv"
WEEKLY = ROOT / "data" / "processed" / "reservoirs_weekly.csv"
OUT = ROOT / "data" / "processed" / "drought_basin_stress.csv"


def main() -> None:
    if not DROUGHT.is_file() or not WEEKLY.is_file():
        print("Need drought_events.csv and reservoirs_weekly.csv under data/processed/.")
        return
    ev = pd.read_csv(DROUGHT, parse_dates=["start_date", "end_date"])
    wk = pd.read_csv(WEEKLY, parse_dates=["week_ending"])
    wk = wk.dropna(subset=["storage_delta_hm3"])

    tmin, tmax = wk["week_ending"].min(), wk["week_ending"].max()
    ev = ev[ev["end_date"] >= tmin].copy()

    baseline = float(wk["storage_delta_hm3"].mean())
    rows = []
    for _, e in ev.iterrows():
        s, en = e["start_date"], e["end_date"]
        if pd.isna(s) or pd.isna(en):
            continue
        mask_evt = (wk["week_ending"] >= s) & (wk["week_ending"] <= en)
        if not mask_evt.any():
            continue
        mu_evt = float(wk.loc[mask_evt, "storage_delta_hm3"].mean())
        mu_out = float(wk.loc[~mask_evt, "storage_delta_hm3"].mean())
        rows.append(
            {
                "event_id": int(e["event_id"]),
                "start_date": s,
                "end_date": en,
                "duration_months": e.get("duration_months"),
                "mean_intensity_spi12": e.get("mean_intensity_spi12"),
                "mean_delta_hm3_event": mu_evt,
                "mean_delta_hm3_non_event": mu_out,
                "mean_delta_hm3_baseline_all": baseline,
                "event_vs_baseline_ratio": mu_evt / baseline if baseline else None,
            }
        )
    out = pd.DataFrame(rows).sort_values("start_date")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(out)} events with overlapping weekly data)")


if __name__ == "__main__":
    main()
