# Helix MVP Plan

## Product thesis

Helix is a nuclear-plus-renewable grid intelligence platform. It uses public
U.S. Energy Information Administration data to show how nuclear availability,
wind, solar, demand, and net load interact across the Lower 48 electric grid.

The product story has two layers:

1. A credible grid analytics application built over a substantial public
   dataset.
2. A clearly labeled exploratory quantum-versus-classical dispatch benchmark.

The quantum work is a differentiator, not the product's foundation. Helix must
remain useful even if every quantum result is slower or less accurate than its
classical baseline.

## Verified EIA sources

The MVP uses the EIA Open Data API v2 routes below. Route metadata was validated
against EIA API version `2.1.12` on May 31, 2026.

| Source | Route | Frequency | Key fields | MVP use |
| --- | --- | --- | --- | --- |
| Grid operations | `electricity/rto/region-data` | Hourly UTC | respondent, metric type, value | Demand, demand forecast, net generation, interchange |
| Generation mix | `electricity/rto/fuel-type-data` | Hourly UTC | respondent, fuel type, value | Wind, solar, nuclear, and other generation |
| Nuclear facilities | `nuclear-outages/facility-nuclear-outages` | Daily | facility, capacity, outage, percent outage | Nuclear availability scenarios and overlays |
| Nuclear generators | `nuclear-outages/generator-nuclear-outages` | Daily | generator, capacity, outage, percent outage | Later drill-down |
| U.S. nuclear fleet | `nuclear-outages/us-nuclear-outages` | Daily | capacity, outage, percent outage | National context |

Important ingestion boundary: the Hourly Electric Grid Monitor API and
interactive site expose historical submissions beginning on January 1, 2019.
EIA separately publishes downloadable flat files for earlier submissions.
Helix should ingest API data first and add the older flat-file path only after
the core experience works.

## MVP user journey

The first release should answer one question well:

> When renewable generation changes through the day, how does nuclear
> availability affect the remaining load the grid must serve?

A user selects a balancing authority and a date range, then:

1. Sees demand and generation mix over time.
2. Opens a duck-curve view with demand, wind, solar, nuclear, and net load.
3. Compares actual renewable generation with a short-horizon forecast.
4. Adjusts wind, solar, and nuclear-availability assumptions.
5. Views the modeled residual load and dispatch requirement.
6. Opens the lab to compare a small classical dispatch optimization with QAOA.

## Release scope

### Include

- Data ingestion for hourly grid operations and generation by fuel type.
- Daily facility-level nuclear outage ingestion.
- A balancing-authority selector and date-range controls.
- Duck-curve chart with a clear net-load definition.
- Generation-mix chart and nuclear-outage overlay.
- Wind and solar forecast baseline with backtest metrics.
- Scenario sliders for wind, solar, and nuclear availability.
- Classical dispatch optimizer for a small illustrative generator fleet.
- QAOA dispatch experiment with the same small problem definition.
- Benchmark table with cost, feasibility, runtime, and problem size.

### Defer

- Real-time alerting and notifications.
- Full production-grade unit commitment across the national fleet.
- Weather-provider integration and advanced probabilistic forecasting.
- Transmission topology, power-flow modeling, and nodal prices.
- Generator-level nuclear outage drill-down in the primary UI.
- Claims that quantum optimization is operationally competitive.

## Recommended architecture

```text
EIA API and flat files
        |
        v
Python ingestion jobs ---> raw JSON/Parquet snapshots
        |
        v
normalized Parquet + DuckDB
        |
        +--> FastAPI analytics endpoints
        |         |
        |         v
        |     Next.js dashboard
        |
        +--> forecasting pipeline
        |
        +--> dispatch lab
              |--> classical baseline
              +--> Qiskit QAOA experiment
```

Use DuckDB and partitioned Parquet for the portfolio MVP. The dataset is large
enough to demonstrate real ingestion and analytical work, while this stack is
simple to run locally and easy to migrate later. Use PostgreSQL only if a
hosted multi-user deployment becomes a near-term requirement.

### Suggested stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Ingestion and analytics | Python 3.12, Polars, DuckDB, PyArrow | Efficient local analytical workflow |
| API | FastAPI, Pydantic | Typed, lightweight backend for charts and experiments |
| Frontend | Next.js, TypeScript, Plotly | Good charting surface for dense interactive time series |
| Forecasting | scikit-learn baseline first | Reproducible baseline before adding model complexity |
| Classical optimization | OR-Tools or SciPy MILP | Clear benchmark and small local footprint |
| Quantum experiment | Qiskit, Qiskit Optimization | Explicit QUBO/QAOA workflow |
| Quality | pytest, Ruff, mypy, Vitest | Focused test coverage and fast feedback |

## Data model

Store all timestamps in UTC. Convert to local balancing-authority time only at
the presentation layer.

### `grid_region_hourly`

| Column | Type | Notes |
| --- | --- | --- |
| `period_utc` | timestamp | Canonical hourly key |
| `respondent` | string | Balancing authority or region code |
| `metric_type` | string | Demand, demand forecast, net generation, interchange |
| `value_mwh` | double | EIA value |
| `ingested_at_utc` | timestamp | Lineage |

### `grid_fuel_hourly`

| Column | Type | Notes |
| --- | --- | --- |
| `period_utc` | timestamp | Canonical hourly key |
| `respondent` | string | Balancing authority or region code |
| `fuel_type` | string | EIA energy-source facet |
| `generation_mwh` | double | Net generation |
| `ingested_at_utc` | timestamp | Lineage |

### `nuclear_facility_daily`

| Column | Type | Notes |
| --- | --- | --- |
| `period_date` | date | Daily observation |
| `facility` | string | EIA plant-code facet |
| `capacity_mw` | double | Available nameplate context |
| `outage_mw` | double | Reported unavailable capacity |
| `percent_outage` | double | Reported percentage |
| `ingested_at_utc` | timestamp | Lineage |

### Derived analytical views

| View | Definition |
| --- | --- |
| `ba_generation_mix_hourly` | Fuel categories pivoted by BA and hour |
| `ba_duck_curve_hourly` | Demand minus wind minus solar |
| `ba_residual_load_hourly` | Demand minus wind minus solar minus nuclear |
| `nuclear_availability_daily` | Capacity minus outage MW |
| `forecast_backtest_hourly` | Actual, predicted, residual, and evaluation fold |

## Analytics definitions

Use explicit definitions in the UI:

- **Net load** = demand - wind generation - solar generation.
- **Residual load after nuclear** = demand - wind - solar - nuclear.
- **Nuclear availability** = reported nuclear capacity - reported outage MW.
- **Renewable forecast error** = actual renewable generation - forecast.

The facility outage feed and balancing-authority fuel mix are different
geographies. The MVP should present national nuclear-outage overlays as context
unless a documented facility-to-balancing-authority mapping is added. Do not
imply a facility-level causal relationship from an unsupported join.

## Forecast baseline

Start with separate wind and solar models for each selected balancing
authority.

### Features

- Hour of day, day of week, month, and daylight-saving-safe UTC timestamp.
- Lagged generation at 1, 24, 48, and 168 hours.
- Rolling means and standard deviations over 24 and 168 hours.
- Optional demand lags for a simple correlated signal.

### Evaluation

- Rolling time-series backtest.
- Compare against persistence and same-hour-prior-day baselines.
- Report MAE, RMSE, and normalized MAE.
- Plot actual versus forecast with confidence language kept modest.

Weather integration belongs in a later forecast iteration. The initial model
should establish a reproducible benchmark before introducing another external
data source.

## Scenario simulator

The simulator is intentionally transparent:

```text
scenario_wind = actual_wind * wind_multiplier
scenario_solar = actual_solar * solar_multiplier
scenario_nuclear = actual_nuclear * nuclear_availability_multiplier
scenario_residual_load =
    demand - scenario_wind - scenario_solar - scenario_nuclear
```

Controls:

- Wind generation: `0%` to `250%`.
- Solar generation: `0%` to `400%`.
- Nuclear availability: `0%` to `100%`.
- Optional battery discharge: deferred until the core story is clear.

The chart should highlight ramp size, peak residual load, minimum residual
load, and hours with renewable surplus.

## Dispatch lab: classical and quantum

The dispatch lab uses a deliberately small synthetic fleet derived from a
selected demand slice. It is an educational benchmark, not a system-operator
model.

### Problem definition

For each generator `i`, choose binary commitment `x_i` and dispatched output
`p_i`:

```text
minimize:
    sum(variable_cost_i * p_i + startup_cost_i * x_i)

subject to:
    sum(p_i) >= residual_load
    min_output_i * x_i <= p_i <= max_output_i * x_i
```

For the QAOA experiment, discretize dispatch into a small binary formulation
and convert the constrained problem to a QUBO. Keep the first demo to roughly
four to eight binary decisions so it remains understandable and runnable on a
simulator.

### Benchmark report

Always show:

| Metric | Classical | QAOA |
| --- | --- | --- |
| Objective cost | Value | Value |
| Feasible solution | Yes or no | Yes or no |
| Runtime | Wall-clock duration | Wall-clock duration |
| Decision variables | Count | Count |
| Optimization backend | Solver name | Simulator or hardware name |
| Approximation gap | Baseline | Difference from classical optimum |

Required framing:

> QAOA is evaluated as a small exploratory benchmark. Helix does not claim a
> present-day quantum advantage for operational grid dispatch.

## UI surface

### Dashboard

- Header with Helix name, BA selector, date range, and freshness timestamp.
- Summary cards: demand peak, renewable share, nuclear generation, and steepest
  net-load ramp.
- Duck-curve chart.
- Generation-mix stacked area chart.
- Nuclear-outage contextual overlay.

### Forecast page

- Wind and solar model selector.
- Actual-versus-predicted chart.
- Error cards and rolling backtest table.
- Baseline comparison.

### Scenario page

- Wind, solar, and nuclear sliders.
- Residual-load chart with before-and-after lines.
- Ramp, peak, and surplus summaries.

### Dispatch lab

- Small fleet editor or presets.
- Classical run button and QAOA run button.
- Shared benchmark table.
- Plain-language caveat panel.

## Delivery milestones

### Milestone 0: foundation

- Create project structure and developer setup.
- Add environment-variable handling for `EIA_API_KEY`.
- Add route-verification script.
- Document the MVP boundary and data-source caveats.

Exit criterion: a developer can validate access to the required EIA routes
without exposing the API key.

### Milestone 1: ingestion and storage

- Implement paginated ingestion for grid operations and fuel-type generation.
- Implement daily facility-level nuclear outage ingestion.
- Normalize UTC timestamps and source facets.
- Write partitioned Parquet and register DuckDB views.
- Add idempotency and row-count checks.

Exit criterion: Helix can ingest one balancing authority for one month, then
repeat the run without duplicate records.

### Milestone 2: first dashboard

- Add FastAPI query endpoints.
- Add BA/date controls.
- Render generation mix and duck curve.
- Add freshness and data-coverage indicators.
- Add national nuclear-outage contextual overlay.

Exit criterion: a user can select a BA and inspect a month of hourly behavior
without touching code.

### Milestone 3: forecasting

- Build persistence and same-hour-prior-day baselines.
- Add one reproducible wind model and one solar model.
- Run rolling backtests and expose metrics.
- Render actual-versus-forecast charts.

Exit criterion: the UI reports model performance relative to naive baselines.

### Milestone 4: scenarios

- Implement wind, solar, and nuclear multipliers.
- Calculate ramp, peak residual load, and surplus-hour summaries.
- Add before-and-after scenario chart.

Exit criterion: the impact of renewable growth and nuclear availability is
visually legible in under a minute.

### Milestone 5: dispatch lab

- Build the shared small dispatch problem.
- Add classical optimizer and test feasibility.
- Add QUBO conversion and QAOA simulator run.
- Display the benchmark table and caveat panel.

Exit criterion: both approaches run against the same documented input and
Helix reports runtime, feasibility, cost, and approximation gap.

## Implementation order

Build vertically:

1. Ingest a single BA and one month of fuel and demand data.
2. Render one trustworthy duck curve.
3. Add the outage context overlay.
4. Expand ingestion and date coverage.
5. Add forecast baselines before trained models.
6. Add scenario controls.
7. Add the classical dispatch model.
8. Add QAOA last, against the already-tested classical formulation.

This order keeps the core product useful throughout development and gives the
quantum comparison a stable baseline.

## Portfolio-ready success criteria

Helix is ready to present when it can demonstrate:

- Reproducible ingestion over a meaningful multi-year EIA slice.
- Interactive exploration across balancing authorities and time ranges.
- A duck curve and scenario model with definitions visible in the UI.
- Renewable forecasts evaluated against naive baselines.
- Nuclear-outage context presented without overstating geographic linkage.
- A small, candid QAOA-versus-classical dispatch benchmark.
- A concise README with local setup, architecture, and screenshots.

## Immediate backlog

1. Scaffold `api`, `web`, `pipelines`, and `quantum` packages.
2. Implement a paginated EIA client with retries and response validation.
3. Add fixtures for one BA, one week, and each required route.
4. Implement Parquet writes and DuckDB analytical views.
5. Build the first FastAPI endpoint for duck-curve data.
6. Render the first dashboard chart.

