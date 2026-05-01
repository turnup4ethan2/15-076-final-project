# 15.076 Final Project — Water Allocation Optimization for the Guadalquivir Basin

## Project overview

MIT **15.076 Analytics for a Better World** final project. Spain's Guadalquivir basin irrigates 800,000+ hectares of farmland but is in its worst drought cycle in decades; reservoirs frequently sit below 30% capacity while allocations follow rigid historical water rights. The project asks: **how do we optimally allocate water from multiple reservoirs across irrigation districts to maximize agricultural yield under deeply uncertain supply?** The framework combines deep-learning inflow forecasts with a robust LP so allocations are defensible under worst-case drought scenarios. Aligned with SDG 6 (water) and SDG 2 (zero hunger).

## Team

- Ethan Nguyen — ethan204@mit.edu
- Elaine Wang — elainelw@mit.edu
- Lara Bernard — larab@mit.edu

## Methodology

Three components feed each other:

1. **LSTM inflow forecasting** — train on MITECO weekly reservoir series (with AEMET weather as covariates) to predict seasonal inflows one quarter ahead. Output is the forecast distribution that defines the uncertainty set for the optimizer.
2. **Demand estimation** — regress ESYRCE crop-mix and climate covariates to estimate each irrigation district's seasonal water demand. Forms the demand-side constraints.
3. **Robust LP** — decision variables are monthly hm³ releases per (reservoir, district) pair. Maximize aggregate yield subject to reservoir capacity, ecological flow, and demand constraints. Robust formulation incorporates the LSTM's uncertainty bounds.

## Datasets

| Dataset | Source | Coverage | Use |
|---|---|---|---|
| MITECO Boletín Hidrológico Semanal | miteco.gob.es/es/agua/temas/evaluacion-de-los-recursos-hidricos/boletin-hidrologico.html | Weekly, 1988–present, every reservoir >5 hm³ | LSTM training; supply input to LP |
| ESYRCE | mapa.gob.es/es/estadistica/temas/estadisticas-agrarias/agricultura/esyrce | Annual, 1990–2023, by province × crop | Demand regression |
| Spanish Drought Catalogue v1.0 | digital.csic.es/handle/10261/331384 | 40 droughts 1916–2020, 10×10 km SPI | Uncertainty set; backtest scenarios |
| AEMET OpenData | opendata.aemet.es/opendata/api | Daily precipitation/temperature | LSTM weather features |

## Tech stack

Python for data/ML, Julia for optimization.

- **Python**: PyTorch (LSTM), pandas/NumPy, scikit-learn or statsmodels (demand regression), matplotlib for figures.
- **Julia**: JuMP + HiGHS by default (Gurobi if available) for the robust LP.
- **Handoff**: Python writes forecast and demand artifacts to `data/processed/` as CSV or Parquet; Julia reads them in. No in-process bridge — files are the contract.

## Environment setup

Python env is defined in `environment.yml` at the repo root. To create it:

```
conda env create -f environment.yml
conda activate water
```

PyTorch is commented out until the LSTM phase begins — uncomment in `environment.yml` and run `conda env update -f environment.yml` to add it. Julia is installed separately (not via conda).

## Secrets

API keys live in `.env` at the repo root, loaded into `os.environ` at script start. `.env.example` shows the expected variables. **Never commit `.env`** — when `.gitignore` is added, `.env` must be the first entry.

Currently expected keys:
- `AEMET_API_KEY` — for the AEMET OpenData REST API.

## Reference data

Canonical Guadalquivir filters live in `data/processed/`:
- `guadalquivir_provinces.csv` — provinces with basin coverage (full/partial).
- `guadalquivir_reservoirs_seed.csv` — hand-curated list of ~35 major reservoirs. Treat as a *starter*; replace with the authoritative MITECO list (`cuenca == "Guadalquivir"`) once that ingestion is done.

Every dataset script should `pd.read_csv` from these files rather than hardcoding lists, so updates propagate automatically.

## Proposed directory layout

```
data/
  raw/            # downloaded MITECO, ESYRCE, AEMET, drought-catalogue files
  processed/      # cleaned tables, forecast outputs, uncertainty sets
forecasting/      # Python — LSTM training, evaluation, inflow forecasts
demand/           # Python — crop-mix regressions, district demand estimates
optimization/     # Julia — JuMP model, robust LP, scenario runs
notebooks/        # Exploratory analysis, figures
report/           # LaTeX source for final report and slides
```

## Deliverables and dates

- **Proposal** — due 2026-03-30 (submitted; pass/fail).
- **Presentation slides** — due 2026-05-01.
- **In-class presentation** — 2026-05-04, -06, or -11 (10 min, all members present).
- **Final report** — due 2026-05-08, ≤8 pages excluding appendices, conference-style (ICML/AAAI/NeurIPS). Must include problem motivation, methodology, results, and per-member contributions.

## Final report evaluation criteria

Soundness of claims (theoretical + empirical), significance/novelty, relevance, clarity, relation to prior work, reproducibility, ability to articulate limitations.

## Source documents

- `15.076 Project Proposal.pdf` — team's specific proposal (authoritative for scope, datasets, methodology).
- `ABW_proposal (1).pdf` — course-wide guidelines (authoritative for deadlines and rubric).
