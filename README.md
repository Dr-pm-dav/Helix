# Helix

Helix is a nuclear-plus-renewable grid intelligence platform built on the U.S.
Energy Information Administration's Hourly Electric Grid Monitor and nuclear
outage feeds.

Helix implements an end-to-end slice that:

- ingests hourly balancing-authority demand and generation by fuel type from the
  EIA Open Data API;
- fuses daily nuclear outage data;
- registers DuckDB views and serves duck curves and residual-load-after-nuclear
  in a local dashboard;
- forecasts wind and solar generation, scored against a persistence baseline;
- models higher-renewables and nuclear-availability scenarios; and
- compares a deliberately small QAOA dispatch experiment with a classical
  optimizer, without making a production quantum-advantage claim.

The forecasting, scenario, and dispatch tools (see [Analytics](#analytics)) run
on bundled synthetic demo data by default, so they work offline; the ingestion
and dashboard paths use the live EIA API. The original delivery plan is in
[`outputs/helix-mvp-plan.md`](outputs/helix-mvp-plan.md).

## Local setup

The EIA key belongs in `.env`, which is ignored by Git. Use `.env.example` as
the shareable template.

Validate API access:

```powershell
python scripts/verify_eia.py
```

## First vertical slice

Install the package into a local virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
```

Ingest California ISO data for April 2025, write normalized Parquet files,
register DuckDB views, and export the first duck curve as CSV and SVG:

```powershell
.\.venv\Scripts\python scripts/ingest_slice.py `
  --respondent CISO `
  --start 2025-04-01 `
  --end 2025-04-30
```

Launch the first local dashboard:

```powershell
.\.venv\Scripts\python scripts/run_dashboard.py
```

Then open `http://127.0.0.1:8000`.

Run a self-contained HTTP smoke test:

```powershell
.\.venv\Scripts\python scripts/smoke_dashboard.py
```

## Analytics

The forecasting, scenario, and dispatch tools run on bundled synthetic demo
data by default, so they work offline without an EIA key. Pass
`--db data/helix.duckdb --respondent CISO` to run any of them on data you have
ingested. Each writes a small artifact to `outputs/`.

Forecast wind and solar generation and report skill against a seasonal-naive
persistence baseline (`skill = 1 - RMSE_model / RMSE_persistence`, so positive
means the model beats "today looks like 24 hours ago"):

```powershell
python scripts/run_forecast.py
```

On the synthetic demo, solar clears persistence comfortably and the model also
beats the harder wind series; metrics are written to
`outputs/forecast_metrics.json`.

Model higher-renewables and nuclear-availability scenarios and summarize the
grid-stress metrics that move (midday net-load belly, steepest hourly ramp,
curtailment hours, renewable share):

```powershell
python scripts/run_scenarios.py
```

The comparison table is written to `outputs/scenario_comparison.csv`.

Compare a deliberately small QAOA dispatch experiment with the classical
optimum. A unit-commitment QUBO (cover a target load at minimum cost) is solved
exactly by enumeration and again with a compact statevector QAOA, and the script
reports whether QAOA recovered the optimum:

```powershell
python scripts/run_dispatch.py
```

The QAOA is a from-scratch statevector simulation sized so the exact optimum is
known; it makes no quantum-advantage claim and can be swapped for a qiskit or
hardware backend behind the same interface. The result is written to
`outputs/dispatch_result.json`.

## Data sources

- [EIA Hourly Electric Grid Monitor](https://www.eia.gov/electricity/gridmonitor/about)
- [EIA Open Data API](https://www.eia.gov/opendata/)
- [EIA nuclear outages browser](https://www.eia.gov/opendata/browser/nuclear-outages/us-nuclear-outages)
