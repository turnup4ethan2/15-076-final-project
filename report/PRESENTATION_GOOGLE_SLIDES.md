# Google Slides deck — full slide-by-slide prompt

Use this document as a **build checklist** and **speaker prompt** for a **~10 minute** 15.076 presentation on the Guadalquivir water project. Duplicate or drop slides to hit your time cap; rehearse once with a timer.

**Global settings**

- **Aspect ratio:** 16:9 (File → Page setup).
- **Typography:** Titles ~28–32 pt; body on figure slides ≥18 pt; avoid dense paragraphs.
- **Figures:** Prefer **PNG from the repo** over screenshots when possible (sharper on projectors).
- **Tables:** Import `data/processed/*.csv` into Google **Sheets**, copy the small range you need, paste into Slides as an editable table.

**Repo figure locations (after you run the pipeline)**

| Artifact | Typical path | Use on slide |
|----------|----------------|--------------|
| Provincial delivery bars | `optimization/figures/deliveries_by_province_<scenario>.png` | Results; stress comparison |
| (Optional) Build in notebook | any matplotlib export you add | Extra sensitivity |

**Repo tables / numbers (paste or import to Sheets first)**

| File | Columns to highlight |
|------|----------------------|
| `data/processed/lp_summary.csv` | `scenario`, `total_demand_hm3`, `total_delivered_hm3`, `shortfall_hm3`, `delta_quantile`, `delta_scale` |
| `data/processed/lp_deliveries.csv` | filter one `scenario`; compare `demand_hm3` vs `delivered_hm3` by `province` |
| `data/processed/lstm_test_metrics.csv` | `horizon_month`, `quantile`, `empirical_coverage`, `pinball_loss` |
| `data/processed/drought_basin_stress.csv` | `event_id`, `start_date`, `end_date`, `mean_delta_hm3_event`, `event_vs_baseline_ratio` (pick 2–3 rows) |

---

## Slide 1 — Title

**Title (large):** Water allocation under uncertainty in the Guadalquivir basin  
**Subtitle:** MIT 15.076 — Analytics for a Better World (Spring 2026)  
**Footer line:** [Your names + `@mit.edu` emails]

**Visual:** Optional static map of Spain / Andalucía (Creative Commons image) or plain text only.

**Speaker prompt (30–40 s):** State the basin, the drought pressure, and that you combine **forecasts + demand + optimization** to suggest allocations under uncertainty.

---

## Slide 2 — The problem (why anyone should care)

**Title:** A stressed basin, rigid rules, and a lot of irrigated agriculture

**Bullets (max 4):**

- Guadalquivir: major irrigated area in southern Spain; recurring **drought** and **low reservoir storage**.
- Water allocation is historically tied to **rights and institutional practice**; your work asks a **complementary analytics question**: how would we **reallocate surface water across provinces** if we explicitly modeled **uncertain net storage change** and **crop-linked demand**?
- Tie to **SDG 6** (clean water) and **SDG 2** (food security) in **one line each**.

**Figure:** None (or one **stock photo / map** if you already have rights cleared).

**Speaker prompt (45–60 s):** Be explicit: you are **not** claiming to replace Spanish water law; you are building a **transparent optimization layer** for discussion and policy learning.

---

## Slide 3 — Research question (precise)

**Title:** What decision are we supporting?

**Bullets:**

- **Decision:** monthly **releases** (hm³) from major reservoirs toward **provinces** over a **short horizon** (aligned with the LSTM quarter view).
- **Uncertainty:** next months’ **net storage change** (from MITECO weekly series, aggregated monthly) summarized by **quantile forecasts** (P10 / P50 / P90).
- **Objective (plain language):** **increase demand-weighted deliveries** subject to **storage balance** and **capacity**, without exceeding **provincial monthly demand** in the model.

**Figure:** None, or a **tiny schematic** (reservoir icons → arrow → province icons) you draw with Slides shapes.

**Speaker prompt (40 s):** Read the three bullets slowly; this slide anchors everything that follows.

---

## Slide 4 — Data sources (credibility slide)

**Title:** Data we actually use

**Content:** A **3×4 table** (read left-to-right):

| Dataset | Source (name on slide) | What you extract | Role in pipeline |
|---------|-------------------------|------------------|------------------|
| Weekly reservoir storage | MITECO Boletín Hidrológico (`BD-Embalses`) | `reservoirs_weekly.csv` | LSTM + LP initial storage |
| Crop areas (irrigated) | MAPA ESYRCE Andalucía workbook | `crops_annual.csv` → `demand_*.csv` | Demand |
| Drought episodes | CSIC Spanish Drought Catalogue v1.0 | `drought_events.csv`, `drought_basin_stress.csv` | Context / narrative |
| (Optional) Weather | AEMET | *deferred in your codebase* | Say explicitly “not used in current LSTM” |

**Footer:** “All primary sources are public; raw files live in `data/raw/` (not in git).”

**Figure:** Optional: **logos** only if allowed by course branding rules; otherwise skip.

**Speaker prompt (45 s):** One sentence per row; emphasize **reproducible scripts** in the repo.

---

## Slide 5 — End-to-end pipeline (the “one diagram” slide)

**Title:** From hydrology and crops to an allocation model

**Diagram (build in Slides):** Left → right boxes:

1. **MITECO weekly** → monthly features  
2. **Quantile LSTM** → P10/P50/P90 **storage deltas**  
3. **ESYRCE + FAO-style coefficients** → **provincial monthly demand**  
4. **JuMP LP (HiGHS)** → **releases + deliveries**  
5. **Outputs** → CSV + figures for slides/report

**Figure:** The diagram **is** the figure; keep it legible from the back row.

**Speaker prompt (50 s):** Point with the laser pointer / cursor in order; say **file handoff** is CSV in `data/processed/`.

---

## Slide 6 — Supply side: LSTM forecast (methods + one result)

**Title:** Quantile forecasts of monthly net storage change

**Bullets (max 5):**

- Target: **capacity-normalized** history + seasonality; **horizon** = 3 months (quarter-ahead framing).
- Outputs: **P10, P50, P90** of **net storage change** per reservoir (same semantic unit the LP uses as “natural” term).
- **Holdout:** time split from your code (e.g. 2023+); report **empirical coverage** vs nominal quantiles from `lstm_test_metrics.csv`.
- **Limitation:** **AEMET not ingested**; model is **reservoir-history-heavy** (say this plainly).

**Figures (pick one or two):**

- **Table:** copy a **2×3** snippet from `lstm_test_metrics.csv` (one horizon, three quantiles) → calibration story.
- **Optional second visual:** if you have a **plot** of one reservoir’s P10–P90 fan (not in repo by default), add it; otherwise **skip** to save time.

**Speaker prompt (60–75 s):** Spend ~20 s on **what P10 means for planning** (pessimistic net refill).

---

## Slide 7 — Demand side: how hm³ by province and month are built

**Title:** Provincial irrigation demand from crop mix

**Bullets:**

- ESYRCE **irrigated hectares** × **crop water requirement** (lookup table `demand/crop_water_requirements.csv`).
- **Basin share** weights (`data/processed/guadalquivir_provinces.csv`) so only the Guadalquivir-attributable fraction counts.
- **Monthly split** via a single southern Spain ET₀ profile (document as a **simplification**).
- Give **one headline number** from your README or `demand_provincial_annual.csv` total (e.g. order **~3–4 km³/yr** after weighting) and optionally compare to **CHG order-of-magnitude** if you state it carefully (“published authorized demand ballpark ~3.3 km³/yr” — only if you are sure of the citation in your report).

**Figure:** Optional **horizontal bar chart** of **annual demand by province** (if you do not have it, use a **small table** from Sheets aggregating `demand_provincial_monthly.csv`).

**Speaker prompt (50 s):** Emphasize **transparent coefficients** vs black-box demand.

---

## Slide 8 — Optimization model (JuMP) in words, not equations

**Title:** A linear program for monthly releases

**Bullets:**

- **Decision variables:** nonnegative **release** from reservoir *r* to province *p* in month *t* (hm³).
- **Allowed arcs:** only edges in `guadalquivir_reservoirs_seed.csv` (each major reservoir assigned to **one** province — **geographic simplification**).
- **Storage dynamics:** storage_t ≈ storage_{t−1} + **forecasted net delta** − **sum of releases**; plus **capacity** upper bounds; initial storage from latest MITECO week.
- **Demand cap:** deliveries cannot exceed **provincial monthly demand** in the LP layer.
- **Objective:** maximize **demand-weighted** total delivery (weights proportional to provincial demand mass).
- **“Robust” framing on this slide:** by default you plan with **P10** natural deltas (or show **P10 vs P50** if you ran both via `LP_SCENARIO`).

**Figure:** None, or reuse the **pipeline** slide with the LP box highlighted.

**Speaker prompt (60 s):** Explicitly list **two things you did not model** (ecological flows, conveyance losses) as **limitations preview**.

---

## Slide 9 — LP setup on the computer (reproducibility micro-slide)

**Title:** How we solve it (reproducibility)

**Bullets:**

- **Solver:** HiGHS via **JuMP** (`optimization/run_lp.jl`).
- **Inputs:** `inflow_forecasts.csv`, `demand_provincial_monthly.csv`, `reservoirs_weekly.csv`, `guadalquivir_reservoirs_seed.csv`.
- **Outputs:** `lp_allocations.csv`, `lp_deliveries.csv`, `lp_summary.csv`.
- **Stress knob:** `LP_STRESS_LIST` multiplies natural deltas across extra scenarios (if you used it).

**Figure:** Optional screenshot of **terminal** showing “Wrote … lp_summary.csv” (blur paths if you care about privacy); **not required**.

**Speaker prompt (25–35 s):** Fast slide; only if you have time.

---

## Slide 10 — Main results: headline table (`lp_summary`)

**Title:** How much demand is met under conservative supply?

**Content:**

- Import `lp_summary.csv` into Sheets.
- Build a **clean table** on the slide with columns: **Scenario | Total demand (hm³) | Delivered (hm³) | Shortfall (hm³) | Notes**  
  Map from file: `scenario`, `total_demand_hm3`, `total_delivered_hm3`, `shortfall_hm3`, and construct “Notes” from `delta_quantile` + `delta_scale`.

**Figure:** The **table is the figure**.

**Speaker prompt (45–60 s):** Read **one** scenario row in full; then summarize pattern across stress scales (“as stress tightens, shortfall rises” — only if true in your numbers).

---

## Slide 11 — Main results: geography (`lp_deliveries` + bar PNG)

**Title:** Where water is delivered in the model

**Bullets (2–3):**

- Under each scenario, deliveries concentrate in **provinces with both high demand and reservoir edges** (tie to seed list).
- Remind audience this is **model output**, not observed administrative releases.

**Figure (primary):** Insert **`optimization/figures/deliveries_by_province_<scenario>.png`**  

- Recommended default for the **main story:** **P10** baseline scenario file (whatever name `plot_allocations.py` produced, e.g. `deliveries_by_province_p10_scale1.0.png`).  
- If you ran `LP_STRESS_LIST`, add a **second slide** or a **two-panel** layout with e.g. `p10_scale1.0` vs `p10_scale0.7` side by side.

**Speaker prompt (50–60 s):** Point to **top two bars**; connect to **olive / rice / irrigated mix** only if you can say it carefully (otherwise stay descriptive).

---

## Slide 12 — Uncertainty / stress story (optional but strong)

**Title:** What changes when we stress supply?

**Content:**

- Same **`lp_summary`** rows, but present **shortfall vs scale** as a **tiny line plot** in Sheets pasted in, or a **3-row table** only.
- One sentence: “Stress scales shrink effective net refill; the LP responds by …” (fill from your numbers).

**Figures:**

- Either **second bar PNG** for another scenario, or the **mini chart** from Sheets.

**Speaker prompt (40 s):** Skip entirely if you are over time; keep Slide 10–11 as the core.

---

## Slide 13 — Drought catalogue (context, not causal proof)

**Title:** Historical droughts vs our weekly storage deltas

**Bullets:**

- CSIC catalogue gives **event windows**; your script `optimization/backtest_summary.py` compares **mean weekly storage delta** during events vs outside.
- **Claim discipline:** this slide is **descriptive context** for why drought matters; it is **not** a full re-simulation of the LP through history.

**Figure / table:**

- Pick **2–3 rows** from `drought_basin_stress.csv` with strong `event_vs_baseline_ratio` or very negative `mean_delta_hm3_event`.
- Optional: **sparkline** or tiny bar chart in Sheets → paste.

**Speaker prompt (35–45 s):** One example event with **dates**; one sentence on **interpretation**.

---

## Slide 14 — Limitations ( graders love this )

**Title:** What this model is *not* (yet)

**Bullets (5–6, short):**

- **District-level infrastructure** and **canal routing** not represented; **province buckets** + **seed reservoir → province** edges only.
- **Ecological flows, spills, groundwater, water quality, hydropower scheduling** not in the LP.
- **Demand** is **coefficient-based** (not the originally proposed climate regression) because **AEMET ingestion was deferred**.
- **“Inflow”** in the learning + LP layer is **net storage change**, not a gauged inflow hydrograph.
- **Policy:** outputs are **exploratory**; institutional constraints are not encoded.

**Figure:** None.

**Speaker prompt (45 s):** End with “these are the next modeling steps we’d prioritize.”

---

## Slide 15 — Contributions + reproducibility

**Title:** Who did what & how to reproduce

**Bullets:**

- **Person A:** data ingest + MITECO pipeline  
- **Person B:** demand + coefficients + tables  
- **Person C:** LSTM + evaluation metrics  
- **Person D:** Julia LP + figures + drought summary (adjust to your team of 3)  
- **Repo:** public scripts; raw data downloaded separately; `environment.yml` + `optimization/Project.toml`.

**Figure:** Optional QR code to **private repo** only if course allows; otherwise omit.

**Speaker prompt (35 s):** Crisp; no overlap between speakers.

---

## Slide 16 — Takeaway + Questions

**Title:** Takeaway

**One-liner (large):** “Under explicit drought-style supply shocks, an optimization layer can quantify **who gets shorted** and **by how much**, given transparent data and constraints.”

**Subtitle:** Questions?

**Figure:** Optional: your **best bar chart** again, small, as a visual anchor.

**Speaker prompt (20 s):** Thank the audience.

---

## Backup slides (do not present unless asked)

**B1 — Math notation:** write the LP compactly for a methods-interested TA.  
**B2 — Full `lp_summary` screenshot** for appendix.  
**B3 — LSTM architecture:** small diagram of inputs/outputs.  
**B4 — Data dictionary:** column names for `reservoirs_weekly.csv`.

---

## Pre-flight checklist (the night before)

- [ ] Every **figure slide** has a **title** that states **scenario** (P10/P50/P90 + scale).  
- [ ] Numbers on slides **match** the CSV you imported (spot-check one cell).  
- [ ] **10-minute dry run** recorded; cut slides 9 and/or 12 if long.  
- [ ] PDF export downloaded; **presenter view** tested if using **Google Meet** screen share.  
- [ ] **Backup internet** plan (PDF on USB / local download).

---

## Prompt you can paste into an LLM to “review” the deck

Paste the following after exporting your slide outline or speaker notes:

> You are a strict technical reviewer for an MIT 15.076 final presentation. The project couples MITECO weekly reservoir data, a quantile LSTM for net storage change, ESYRCE-based provincial demand, and a JuMP LP with HiGHS. Evaluate whether each slide’s claims are supported by the described artifacts (`lp_summary.csv`, bar PNGs, `lstm_test_metrics.csv`, `drought_basin_stress.csv`). Flag any overclaim about policy, causality, or “optimality.” Suggest one slide to cut for a 10-minute cap and one slide to strengthen for clarity.

---

## File → slide quick index

| Slide # | Primary asset |
|--------|----------------|
| 6 | `data/processed/lstm_test_metrics.csv` |
| 7 | `data/processed/demand_provincial_monthly.csv` (aggregate in Sheets) |
| 10 | `data/processed/lp_summary.csv` |
| 11 | `optimization/figures/deliveries_by_province_*.png` |
| 12 | second PNG or derived chart from `lp_summary.csv` |
| 13 | `data/processed/drought_basin_stress.csv` |
