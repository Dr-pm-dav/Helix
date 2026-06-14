"""
Deterministic synthetic hourly grid data for offline demos and tests.

Produces rows with the same columns as the ``ba_duck_curve_hourly`` DuckDB view
(period_utc, demand_mwh, solar_mwh, wind_mwh, nuclear_mwh, net_load_mwh,
residual_load_after_nuclear_mwh) so the forecast, scenario, and dispatch tools
run without an EIA key or network. The shapes are deliberately duck-curve-like
(midday solar, morning and evening demand peaks, variable wind, near-baseload
nuclear with occasional outages). This is clearly synthetic; for real analysis,
ingest with ``scripts/ingest_slice.py`` and pass the DuckDB rows instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

COLUMNS = ["period_utc", "respondent", "demand_mwh", "solar_mwh", "wind_mwh",
           "nuclear_mwh", "net_load_mwh", "residual_load_after_nuclear_mwh"]


def synthetic_rows(*, days: int = 45, respondent: str = "DEMO",
                   start: datetime | None = None, seed: int = 0) -> list[dict]:
    """Return ``days * 24`` hourly rows of synthetic duck-curve data."""
    rng = np.random.default_rng(seed)
    start = start or datetime(2025, 4, 1, tzinfo=timezone.utc)
    n = days * 24
    hours = np.arange(n)
    hod = hours % 24
    day_idx = hours // 24
    dow = (day_idx + 1) % 7                       # 0..6, arbitrary phase
    weekday = (dow < 5).astype(float)

    # demand (MWh): morning shoulder + evening peak, lower on weekends, seasonal drift
    morning = np.exp(-0.5 * ((hod - 8) / 2.2) ** 2)
    evening = np.exp(-0.5 * ((hod - 19) / 2.6) ** 2)
    seasonal = 1.0 + 0.05 * np.sin(2 * np.pi * day_idx / 365.0)
    demand = (22000 + 5200 * evening + 2600 * morning) * seasonal
    demand *= 0.92 + 0.08 * weekday
    demand += rng.normal(0, 350, n)

    # solar (MWh): daytime bell, daily cloudiness factor
    daylight = np.clip(np.sin(np.pi * (hod - 6) / 12.0), 0, None)
    cloud = np.repeat(np.clip(rng.normal(0.85, 0.18, days), 0.25, 1.1), 24)
    solar = 12500 * daylight * cloud
    solar = np.clip(solar + rng.normal(0, 120, n), 0, None)

    # wind (MWh): stationary AR(1) fluctuation around a mild diurnal mean
    diurnal_wind = 2600 + 500 * np.cos(np.pi * (hod - 3) / 12.0)
    phi, fluct = 0.88, np.zeros(n)
    shocks = rng.normal(0, 340, n)
    for t in range(1, n):
        fluct[t] = phi * fluct[t - 1] + shocks[t]
    wind = np.clip(diurnal_wind + fluct + rng.normal(0, 80, n), 0, None)

    # nuclear (MWh): ~2.25 GW baseload, occasional multi-day outage on one unit
    nuclear = np.full(n, 2250.0)
    for _ in range(max(1, days // 20)):
        d0 = int(rng.integers(0, max(1, days - 4)))
        nuclear[d0 * 24:(d0 + 3) * 24] *= 0.5
    nuclear += rng.normal(0, 15, n)

    net = demand - solar - wind
    residual = net - nuclear

    rows = []
    for i in range(n):
        ts = (start + timedelta(hours=int(i))).isoformat()
        rows.append({"period_utc": ts, "respondent": respondent,
                     "demand_mwh": round(float(demand[i]), 2),
                     "solar_mwh": round(float(solar[i]), 2),
                     "wind_mwh": round(float(wind[i]), 2),
                     "nuclear_mwh": round(float(nuclear[i]), 2),
                     "net_load_mwh": round(float(net[i]), 2),
                     "residual_load_after_nuclear_mwh": round(float(residual[i]), 2)})
    return rows
