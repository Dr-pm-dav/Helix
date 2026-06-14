"""
Hour-ahead wind and solar generation forecasting with a skill score.

Each renewable series is predicted from calendar encodings (hour sin/cos,
day-of-week, day-of-year sin/cos) and autoregressive features (the value one
hour and 24 hours earlier, plus a 24-hour rolling mean). A gradient-boosted
regressor is trained on the earlier part of the timeline and scored on the
held-out tail. Skill is reported against a seasonal-naive persistence baseline
(the value 24 hours earlier), so a positive skill score means the model beats
"tomorrow looks like yesterday":

    skill = 1 - RMSE_model / RMSE_persistence
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

LAG_SHORT, LAG_DAY = 1, 24


def _series(rows, col):
    return np.array([float(r[col]) for r in rows], dtype="float64")


def _hours(rows):
    return [datetime.fromisoformat(r["period_utc"]) for r in rows]


def build_design(rows, target_col):
    """Return X, y, persistence prediction, and the row index for each sample."""
    y_full = _series(rows, target_col)
    times = _hours(rows)
    hod = np.array([t.hour for t in times])
    dow = np.array([t.weekday() for t in times])
    doy = np.array([t.timetuple().tm_yday for t in times])

    X, y, persist, idx = [], [], [], []
    for t in range(LAG_DAY, len(rows)):
        roll = y_full[t - LAG_DAY:t].mean()
        X.append([
            np.sin(2 * np.pi * hod[t] / 24), np.cos(2 * np.pi * hod[t] / 24),
            float(dow[t]),
            np.sin(2 * np.pi * doy[t] / 365.25), np.cos(2 * np.pi * doy[t] / 365.25),
            y_full[t - LAG_SHORT], y_full[t - LAG_DAY], roll,
        ])
        y.append(y_full[t])
        persist.append(y_full[t - LAG_DAY])
        idx.append(t)
    return np.array(X), np.array(y), np.array(persist), np.array(idx)


def _rmse(a, b):
    return float(np.sqrt(mean_squared_error(a, b)))


def train_score(rows, target_col, *, test_frac=0.25, seed=0):
    """Fit the forecaster on the leading window, score on the trailing tail."""
    X, y, persist, _ = build_design(rows, target_col)
    if len(y) < 48:
        raise ValueError("need at least ~3 days of hourly data to forecast")
    split = int(len(y) * (1 - test_frac))
    model = HistGradientBoostingRegressor(max_depth=4, learning_rate=0.08,
                                          max_iter=300, random_state=seed)
    model.fit(X[:split], y[:split])
    pred = np.clip(model.predict(X[split:]), 0, None)
    truth, base = y[split:], persist[split:]
    rmse_model, rmse_base = _rmse(truth, pred), _rmse(truth, base)
    skill = 1.0 - rmse_model / rmse_base if rmse_base > 0 else float("nan")
    return {
        "target": target_col, "n_train": int(split), "n_test": int(len(truth)),
        "rmse_model": rmse_model, "rmse_persistence": rmse_base,
        "mae_model": float(mean_absolute_error(truth, pred)),
        "skill_score": float(skill),
        "predictions": pred.tolist(), "truth": truth.tolist(),
    }


def forecast_renewables(rows, **kwargs):
    """Forecast both solar and wind generation; return per-series metrics."""
    return {"solar": train_score(rows, "solar_mwh", **kwargs),
            "wind": train_score(rows, "wind_mwh", **kwargs)}
