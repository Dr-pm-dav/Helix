# Portfolio Run Instructions: Helix

Helix is the nuclear-plus-renewable grid intelligence demo. Use it in the
portfolio to show public EIA ingestion, DuckDB-backed normalization, duck-curve
exports, and a local FastAPI dashboard.

## Recommended Demo Path

1. Start from this folder:

   ```powershell
   cd "I:\Schools & Learnings\Projects\Projects\a-nuclear-plus-renewable-grid-intelligence"
   ```

2. Create and install the local environment. This project requires Python 3.12
   or newer.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -e .[dev]
   ```

3. Add an EIA API key before ingesting live data.

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   .\.venv\Scripts\python scripts\verify_eia.py
   ```

4. Build the April 2025 California ISO demo slice.

   ```powershell
   .\.venv\Scripts\python scripts\ingest_slice.py `
     --respondent CISO `
     --start 2025-04-01 `
     --end 2025-04-30
   ```

5. Launch the dashboard.

   ```powershell
   .\.venv\Scripts\python scripts\run_dashboard.py
   ```

6. Open the portfolio demo at:

   ```text
   http://127.0.0.1:8000
   ```

## What To Show

- The dashboard landing view in `web/index.html`.
- The duck-curve SVG in `outputs/ciso-2025-04-duck-curve.svg`.
- The exported CSV in `outputs/ciso-2025-04-duck-curve.csv` after ingestion.
- The MVP plan in `outputs/helix-mvp-plan.md`.

## Verification Before Presenting

Run the test suite:

```powershell
.\.venv\Scripts\python -m pytest
```

Run the dashboard smoke test while the dashboard is available:

```powershell
.\.venv\Scripts\python scripts\smoke_dashboard.py
```

## Smooth Portfolio Checklist

- Keep `.env` local and never commit the EIA key.
- Run the ingestion command before the demo so the DuckDB database and chart
  artifacts are already warm.
- Keep the dashboard terminal open while presenting.
- If live EIA access is unreliable, present the existing generated SVG and CSV
  artifacts from `outputs/`.
- Use this framing: "Helix combines public grid-monitor data with nuclear
  outage signals, then turns it into an operator-style local intelligence view."

## Troubleshooting

- If `verify_eia.py` fails, check that `.env` contains the expected EIA key
  variable and that the shell was opened from this project folder.
- If the dashboard cannot start on port 8000, close the existing process using
  that port or edit `scripts/run_dashboard.py` to use another local port.
- If imports fail, reinstall with `.\.venv\Scripts\python -m pip install -e .[dev]`.
- If ingestion returns no rows, verify the respondent code and date range.

