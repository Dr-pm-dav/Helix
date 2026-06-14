"""
Forecast wind and solar generation and report skill against persistence.

Runs on synthetic demo data by default so it works without an EIA key; pass
``--db <helix.duckdb> --respondent <BA>`` to forecast on real ingested data.

    python scripts/run_forecast.py
    python scripts/run_forecast.py --db data/helix.duckdb --respondent CISO
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from helix.forecast import forecast_renewables
from helix.synth import synthetic_rows


def _load_rows(args):
    if args.db:
        from helix.storage import read_duck_curve_rows
        return read_duck_curve_rows(Path(args.db), args.respondent), \
            f"DuckDB {args.db} [{args.respondent}]"
    return synthetic_rows(days=args.days, seed=args.seed), f"synthetic demo ({args.days} days)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Wind/solar generation forecast with skill score")
    parser.add_argument("--db", help="path to a helix.duckdb populated by ingest_slice.py")
    parser.add_argument("--respondent", default="CISO")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    rows, source = _load_rows(args)
    print(f"Forecasting on {source}: {len(rows)} hourly rows")
    results = forecast_renewables(rows)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for series in ("solar", "wind"):
        metrics = results[series]
        print(f"  {series:6s} skill {metrics['skill_score']:+.3f}   "
              f"RMSE model {metrics['rmse_model']:.0f} vs persistence "
              f"{metrics['rmse_persistence']:.0f} MWh   (test n={metrics['n_test']})")
        summary[series] = {k: metrics[k] for k in
                           ("skill_score", "rmse_model", "rmse_persistence",
                            "mae_model", "n_train", "n_test")}
    json.dump(summary, open(out / "forecast_metrics.json", "w"), indent=2)
    print(f"  wrote {out / 'forecast_metrics.json'}")
    if not args.db:
        print("  NOTE: synthetic demo data; pass --db/--respondent for real EIA data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
