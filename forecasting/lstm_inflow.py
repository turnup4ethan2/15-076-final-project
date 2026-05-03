"""Quantile LSTM for monthly storage-delta forecasting.

Trains one shared LSTM across all Guadalquivir reservoirs. Inputs are
12 months of (capacity-normalized storage delta, normalized fill level,
month sin/cos). Output is 3-month-ahead quantile predictions (P10/P50/P90)
of normalized storage delta — the quantile spread becomes the
uncertainty set the robust LP plans against.

Deferred AEMET weather; the model uses only reservoir history and
seasonality features. Documented as a limitation.

Run:
    python forecasting/lstm_inflow.py

Outputs:
    data/processed/inflow_forecasts.csv      — per (reservoir, horizon, quantile)
    data/processed/lstm_test_metrics.csv     — pinball + calibration on holdout
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

warnings.filterwarnings("ignore", category=UserWarning, module="torch")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESERVOIRS = PROJECT_ROOT / "data" / "processed" / "reservoirs_weekly.csv"
OUT_FORECASTS = PROJECT_ROOT / "data" / "processed" / "inflow_forecasts.csv"
OUT_METRICS = PROJECT_ROOT / "data" / "processed" / "lstm_test_metrics.csv"

LOOKBACK = 12  # months of history fed to the model
HORIZON = 3    # months forecast ahead (one quarter, per proposal)
QUANTILES = (0.10, 0.50, 0.90)
HIDDEN = 32
EPOCHS = 60
BATCH = 128
LR = 1e-3
TEST_CUTOFF = pd.Timestamp("2023-01-01")  # holdout: 2023-01 onward
SEED = 42

torch.manual_seed(SEED)
np.random.seed(SEED)


# --------------------------------------------------------------------------
# Data prep
# --------------------------------------------------------------------------

def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month_start"] = df["week_ending"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        df.groupby(["reservoir_name", "month_start"])
        .agg(
            capacity_hm3=("capacity_hm3", "last"),
            volume_hm3=("volume_hm3", "last"),
            storage_delta_hm3=("storage_delta_hm3", "sum"),
        )
        .reset_index()
    )
    return monthly


def build_sequences(monthly: pd.DataFrame):
    inputs, targets, meta = [], [], []
    for resv, g in monthly.groupby("reservoir_name"):
        g = g.sort_values("month_start").reset_index(drop=True)
        cap = float(g["capacity_hm3"].median())
        if not np.isfinite(cap) or cap <= 5:
            continue  # skip very small reservoirs (MITECO threshold)
        # Capacity-normalized features keep different reservoirs on the same scale
        norm_delta = (g["storage_delta_hm3"] / cap).values.astype(np.float32)
        norm_vol = (g["volume_hm3"] / cap).values.astype(np.float32)
        month = g["month_start"].dt.month.values
        sin = np.sin(2 * np.pi * month / 12).astype(np.float32)
        cos = np.cos(2 * np.pi * month / 12).astype(np.float32)
        feat = np.stack([norm_delta, norm_vol, sin, cos], axis=1)

        for i in range(LOOKBACK, len(g) - HORIZON):
            x = feat[i - LOOKBACK : i]
            y = norm_delta[i : i + HORIZON]
            if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
                continue
            inputs.append(x)
            targets.append(y)
            meta.append(
                {
                    "reservoir_name": resv,
                    "forecast_start": g["month_start"].iloc[i],
                    "capacity_hm3": cap,
                }
            )
    return np.array(inputs, dtype=np.float32), np.array(targets, dtype=np.float32), meta


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

class QuantileLSTM(nn.Module):
    def __init__(self, in_dim=4, hidden=HIDDEN, horizon=HORIZON, n_q=len(QUANTILES)):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, batch_first=True)
        self.head = nn.Linear(hidden, horizon * n_q)
        self.horizon = horizon
        self.n_q = n_q

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        out = self.head(h.squeeze(0))
        return out.view(-1, self.horizon, self.n_q)


def pinball_loss(pred: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    # pred: (B, H, Q), y: (B, H)
    losses = []
    for i, q in enumerate(QUANTILES):
        diff = y - pred[..., i]
        losses.append(torch.maximum(q * diff, (q - 1) * diff).mean())
    return torch.stack(losses).mean()


# --------------------------------------------------------------------------
# Train / evaluate
# --------------------------------------------------------------------------

def train(model, X_train, y_train):
    model.train()
    optim = torch.optim.Adam(model.parameters(), lr=LR)
    n = len(X_train)
    for ep in range(EPOCHS):
        perm = torch.randperm(n)
        running = 0.0
        for i in range(0, n, BATCH):
            idx = perm[i : i + BATCH]
            xb, yb = X_train[idx], y_train[idx]
            pred = model(xb)
            loss = pinball_loss(pred, yb)
            optim.zero_grad()
            loss.backward()
            optim.step()
            running += loss.item() * len(idx)
        if (ep + 1) % 10 == 0:
            print(f"  epoch {ep+1:3d}  pinball={running / n:.5f}")


def evaluate(model, X_test, y_test):
    model.eval()
    with torch.no_grad():
        pred = model(X_test).numpy()
    y_np = y_test.numpy()
    rows = []
    for h in range(HORIZON):
        for qi, q in enumerate(QUANTILES):
            diff = y_np[:, h] - pred[:, h, qi]
            pinball = np.maximum(q * diff, (q - 1) * diff).mean()
            empirical_coverage = (y_np[:, h] <= pred[:, h, qi]).mean()
            rows.append(
                {
                    "horizon_month": h + 1,
                    "quantile": q,
                    "pinball_loss": float(pinball),
                    "empirical_coverage": float(empirical_coverage),
                }
            )
    return pred, pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Forecast generation for the LP
# --------------------------------------------------------------------------

def generate_latest_forecasts(model, monthly: pd.DataFrame) -> pd.DataFrame:
    """For each reservoir, produce the next-3-month forecast from the most
    recent observed window."""
    rows = []
    for resv, g in monthly.groupby("reservoir_name"):
        g = g.sort_values("month_start").reset_index(drop=True)
        cap = float(g["capacity_hm3"].median())
        if not np.isfinite(cap) or cap <= 5:
            continue
        if len(g) < LOOKBACK:
            continue
        last_window = g.tail(LOOKBACK)
        if last_window["storage_delta_hm3"].isna().any():
            continue
        norm_delta = (last_window["storage_delta_hm3"] / cap).values.astype(np.float32)
        norm_vol = (last_window["volume_hm3"] / cap).values.astype(np.float32)
        month = last_window["month_start"].dt.month.values
        sin = np.sin(2 * np.pi * month / 12).astype(np.float32)
        cos = np.cos(2 * np.pi * month / 12).astype(np.float32)
        feat = np.stack([norm_delta, norm_vol, sin, cos], axis=1)[None, :, :]
        with torch.no_grad():
            pred = model(torch.tensor(feat)).numpy()[0]  # (H, Q)
        last_month = last_window["month_start"].iloc[-1]
        for h in range(HORIZON):
            forecast_month = last_month + pd.DateOffset(months=h + 1)
            rows.append(
                {
                    "reservoir_name": resv,
                    "forecast_month": forecast_month,
                    "horizon_months": h + 1,
                    "p10_storage_delta_hm3": float(pred[h, 0]) * cap,
                    "p50_storage_delta_hm3": float(pred[h, 1]) * cap,
                    "p90_storage_delta_hm3": float(pred[h, 2]) * cap,
                    "capacity_hm3": cap,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    print("Loading and aggregating MITECO data...")
    df = pd.read_csv(RESERVOIRS, parse_dates=["week_ending"])
    monthly = aggregate_monthly(df)
    print(f"  {len(monthly):,} monthly records across {monthly['reservoir_name'].nunique()} reservoirs")

    print("Building sequences...")
    X, y, meta = build_sequences(monthly)
    forecast_starts = pd.Series([m["forecast_start"] for m in meta])
    train_mask = forecast_starts < TEST_CUTOFF
    print(f"  total samples: {len(X):,}   train: {train_mask.sum():,}   test: {(~train_mask).sum():,}")

    X_train = torch.tensor(X[train_mask])
    y_train = torch.tensor(y[train_mask])
    X_test = torch.tensor(X[~train_mask])
    y_test = torch.tensor(y[~train_mask])

    print(f"Training quantile LSTM ({EPOCHS} epochs, hidden={HIDDEN})...")
    model = QuantileLSTM()
    train(model, X_train, y_train)

    print("Evaluating on holdout (2023-01 onward)...")
    _, metrics = evaluate(model, X_test, y_test)
    metrics.to_csv(OUT_METRICS, index=False)
    print(metrics.to_string(index=False))

    print("Generating forecasts for the next quarter...")
    forecasts = generate_latest_forecasts(model, monthly)
    OUT_FORECASTS.parent.mkdir(parents=True, exist_ok=True)
    forecasts.to_csv(OUT_FORECASTS, index=False)
    print(f"  wrote {len(forecasts)} forecasts to {OUT_FORECASTS.relative_to(PROJECT_ROOT)}")
    print()
    print("Top-10 reservoirs by capacity — next-quarter forecast (hm³):")
    summary = (
        forecasts.groupby("reservoir_name")
        .agg(
            cap=("capacity_hm3", "first"),
            p10=("p10_storage_delta_hm3", "sum"),
            p50=("p50_storage_delta_hm3", "sum"),
            p90=("p90_storage_delta_hm3", "sum"),
        )
        .sort_values("cap", ascending=False)
        .head(10)
    )
    print(summary.to_string())


if __name__ == "__main__":
    main()
