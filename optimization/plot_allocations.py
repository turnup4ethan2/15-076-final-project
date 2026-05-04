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


def plot_delivered_only(df: pd.DataFrame) -> None:
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


def plot_demand_vs_delivered(df: pd.DataFrame) -> None:
    """Grouped bars: demand and delivered, side-by-side, per province."""
    import numpy as np

    for scenario, g in df.groupby("scenario"):
        tot = (
            g.groupby("province", as_index=False)
            .agg(demand_hm3=("demand_hm3", "sum"),
                 delivered_hm3=("delivered_hm3", "sum"))
            .sort_values("demand_hm3", ascending=False)
            .reset_index(drop=True)
        )
        provinces = tot["province"].tolist()
        x = np.arange(len(provinces))
        width = 0.38

        fig, ax = plt.subplots(figsize=(9, 5))
        bars_dem = ax.bar(x - width/2, tot["demand_hm3"], width,
                          label="Demand", color="#c9d6e3", edgecolor="#5c7a99")
        bars_del = ax.bar(x + width/2, tot["delivered_hm3"], width,
                          label="Delivered", color="steelblue")

        # Percentage labels on the delivered bars
        for i, (d, met) in enumerate(zip(tot["demand_hm3"], tot["delivered_hm3"])):
            pct = 100 * met / d if d > 0 else 0
            ax.text(x[i] + width/2, met + max(tot["demand_hm3"]) * 0.015,
                    f"{pct:.0f}%", ha="center", fontsize=9, color="#1f4e79")

        ax.set_ylabel("Water (hm³)")
        ax.set_title(f"Demand vs. delivered by province — {scenario}")
        ax.set_xticks(x)
        ax.set_xticklabels(provinces, rotation=20, ha="right")
        ax.legend(frameon=False, loc="upper right")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        safe = scenario.replace("/", "_")
        out = OUT_DIR / f"demand_vs_delivered_{safe}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"Wrote {out.relative_to(ROOT)}")


def main() -> None:
    if not DELIV.is_file():
        print(f"Missing {DELIV} — run Julia `run_lp.jl` first.")
        return
    df = pd.read_csv(DELIV, parse_dates=["forecast_month"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_delivered_only(df)
    plot_demand_vs_delivered(df)


if __name__ == "__main__":
    main()
