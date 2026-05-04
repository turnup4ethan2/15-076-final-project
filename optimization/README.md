# Guadalquivir allocation LP (Julia)

`run_lp.jl` implements a **linear program** that maximizes **demand-weighted water deliveries** over the LSTM forecast horizon (typically three months), subject to **reservoir mass balance** and **capacity** constraints. Natural storage changes follow the LSTM **quantile** you choose (`LP_SCENARIO=p10` by default for conservative planning).

**Simplifications (document in report):**

- **Geography:** Releases are allowed only on edges from `guadalquivir_reservoirs_seed.csv` (each listed reservoir → its province). Reservoirs in MITECO but not in the seed list are dropped from the LP network.
- **Ecology / spills / conveyance losses:** Not modeled explicitly; net storage change from the LSTM plays the role of an exogenous “natural” term.
- **Demand:** Uses `demand_provincial_monthly.csv` from the Python pipeline (provinces, not fine-scale irrigation districts).

## Prerequisites

1. Julia **1.9+** with `Pkg` network access once, to download HiGHS and dependencies.
2. Python pipeline outputs in `data/processed/`:
   - `inflow_forecasts.csv` (`forecasting/lstm_inflow.py`)
   - `demand_provincial_monthly.csv` (`demand/build_demand.py`)
   - `reservoirs_weekly.csv` (`forecasting/ingest_miteco.py`)
   - `guadalquivir_reservoirs_seed.csv` (reference, committed)

## First-time setup

From `optimization/`:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

That resolves JuMP, HiGHS, CSV, and DataFrames from `Project.toml` and writes a local `Manifest.toml` (ignored by git in this repo).

## Run the model

From the **repository root**:

```bash
cd optimization
julia --project=. run_lp.jl
```

Optional environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `LP_SCENARIO` | `p10` | Forecast column: `p10`, `p50`, or `p90` storage deltas |
| `DELTA_SCALE` | `1.0` | Multiplier on all natural deltas |
| `LP_STRESS_LIST` | *(empty)* | Extra scales, e.g. `1.0,0.85,0.7` — runs one solve per value |

Outputs (under `data/processed/`):

- `lp_allocations.csv` — positive releases by scenario / reservoir / province / month
- `lp_deliveries.csv` — demand vs. delivered by province and month
- `lp_summary.csv` — scenario-level totals and shortfall

## Figures and drought summary

```bash
conda activate water
python optimization/plot_allocations.py
python optimization/backtest_summary.py
```

Figures go to `optimization/figures/`. `backtest_summary.py` writes `drought_basin_stress.csv` for overlap events vs. weekly MITECO deltas.
