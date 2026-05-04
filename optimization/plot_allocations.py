"""Bar charts from lp_deliveries.csv (output of run_lp.jl).

Usage:
  conda activate water
  python optimization/plot_allocations.py

Writes optimization/figures/deliveries_by_province.png (and _by_scenario if
multiple scenarios are present).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DELIV = ROOT / "data" / "processed" / "lp_deliveries.csv"
OUT_DIR = Path(__file__).resolve().parent / "figures"


def main() -> None:
    if not DELIV.is_file():
        print(f"Missing {DELIV} — run Julia `run_lp.jl` first.")
        return
    df = pd.read_csv(DELIV, parse_dates=["forecast_month"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for scenario, g in df.groupby("scenario"):
        tot = (
            g.groupby("province", as_index=False)["delivered_hm3"]
            .sum()
            .sort_values("delivered_hm3", ascending=False)
        )
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(tot["province"], tot["delivered_hm3"], color="steelblue")
        ax.set_ylabel("Delivered water (hm³)")
        ax.set_title(f"Cumulative deliveries by province — {scenario}")
        plt.xticks(rotation=35, ha="right")
        fig.tight_layout()
        safe = scenario.replace("/", "_")
        out = OUT_DIR / f"deliveries_by_province_{safe}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
