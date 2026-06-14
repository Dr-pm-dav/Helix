"""Ingest one EIA month and export the first Helix duck curve."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from helix.chart import render_duck_curve_svg
from helix.config import load_settings
from helix.pipeline import ingest_month
from helix.storage import describe_counts, export_duck_curve_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--respondent", default="CISO", help="EIA balancing-authority code")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 4, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 4, 30))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    result = ingest_month(
        settings,
        respondent=args.respondent,
        start=args.start,
        end=args.end,
    )
    csv_output_path = args.output or (
        settings.output_dir
        / f"{args.respondent.lower()}-{args.start:%Y-%m}-duck-curve.csv"
    )
    duck_curve_rows = export_duck_curve_csv(
        result.database_path, csv_output_path, respondent=args.respondent
    )
    svg_output_path = csv_output_path.with_suffix(".svg")
    render_duck_curve_svg(
        result.database_path,
        svg_output_path,
        respondent=args.respondent,
    )

    print(f"Stored {result.region_rows} grid-region rows")
    print(f"Stored {result.fuel_rows} grid-fuel rows")
    print(f"Stored {result.outage_rows} nuclear-outage rows")
    for view_name, count in describe_counts(result.database_path):
        print(f"{view_name}: {count} rows")
    print(f"Exported {duck_curve_rows} duck-curve rows to {csv_output_path}")
    print(f"Rendered first duck-curve chart to {svg_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
