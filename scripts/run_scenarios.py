"""
Model higher-renewables and nuclear-availability scenarios on the grid data.

Runs on synthetic demo data by default; pass ``--db``/``--respondent`` for real
ingested data.

    python scripts/run_scenarios.py
    python scripts/run_scenarios.py --db data/helix.duckdb --respondent CISO
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from helix.scenarios import compare
from helix.synth import synthetic_rows

SCENARIOS = {
    "+50% renewables": {"renewable_multiplier": 1.5},
    "2x renewables": {"renewable_multiplier": 2.0},
    "nuclear at 50%": {"nuclear_availability": 0.5},
    "2x renewables, nuclear 50%": {"renewable_multiplier": 2.0, "nuclear_availability": 0.5},
}
FIELDS = ["peak_demand_mwh", "min_net_load_mwh", "max_hourly_ramp_mwh",
          "peak_residual_mwh", "curtailment_hours", "renewable_share"]


def _load_rows(args):
    if args.db:
        from helix.storage import read_duck_curve_rows
        return read_duck_curve_rows(Path(args.db), args.respondent), \
            f"DuckDB {args.db} [{args.respondent}]"
    return synthetic_rows(days=args.days, seed=args.seed), f"synthetic demo ({args.days} days)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Higher-renewables / nuclear-availability scenarios")
    parser.add_argument("--db")
    parser.add_argument("--respondent", default="CISO")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    rows, source = _load_rows(args)
    print(f"Scenarios on {source}: {len(rows)} hourly rows\n")
    table = compare(rows, SCENARIOS)

    header = f"{'scenario':<28}{'min_net':>10}{'curtail_h':>11}{'max_ramp':>10}{'pk_resid':>10}{'renew%':>9}"
    print(header)
    print("-" * len(header))
    for label, s in table.items():
        print(f"{label:<28}{s['min_net_load_mwh']:>10.0f}{s['curtailment_hours']:>11d}"
              f"{s['max_hourly_ramp_mwh']:>10.0f}{s['peak_residual_mwh']:>10.0f}"
              f"{s['renewable_share'] * 100:>8.1f}%")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "scenario_comparison.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scenario", *FIELDS])
        for label, s in table.items():
            writer.writerow([label, *[s[f] for f in FIELDS]])
    print(f"\n  wrote {out / 'scenario_comparison.csv'}")
    if not args.db:
        print("  NOTE: synthetic demo data; pass --db/--respondent for real EIA data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
