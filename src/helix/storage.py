"""Parquet upserts and DuckDB analytical views for the Helix MVP."""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

REGION_KEYS = ("period_utc", "respondent", "metric_type")
FUEL_KEYS = ("period_utc", "respondent", "fuel_type")
OUTAGE_KEYS = ("period_date", "facility")


def upsert_parquet(
    path: Path,
    rows: Sequence[dict[str, Any]],
    *,
    key_columns: Sequence[str],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = pq.ParquetFile(path).read().to_pylist() if path.exists() else []
    keyed_rows = {
        tuple(row[column] for column in key_columns): row for row in [*existing_rows, *rows]
    }
    merged_rows = list(keyed_rows.values())
    merged_rows.sort(key=lambda row: tuple(row[column] for column in key_columns))
    table = pa.Table.from_pylist(merged_rows)
    temp_path = path.with_suffix(".tmp.parquet")
    pq.write_table(table, temp_path, compression="zstd")
    os.replace(temp_path, path)
    return len(merged_rows)


def monthly_partition(
    data_dir: Path,
    dataset: str,
    *,
    year: int,
    month: int,
    respondent: str | None = None,
) -> Path:
    path = data_dir / "normalized" / dataset
    if respondent:
        path /= f"respondent={respondent}"
    return path / f"year={year:04d}" / f"month={month:02d}" / "data.parquet"


def register_views(data_dir: Path) -> Path:
    database_path = data_dir / "helix.duckdb"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    region_glob = _sql_path(data_dir / "normalized" / "grid_region_hourly" / "**" / "*.parquet")
    fuel_glob = _sql_path(data_dir / "normalized" / "grid_fuel_hourly" / "**" / "*.parquet")
    outage_glob = _sql_path(
        data_dir / "normalized" / "nuclear_facility_daily" / "**" / "*.parquet"
    )

    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            f"""
            CREATE OR REPLACE VIEW grid_region_hourly AS
            SELECT * FROM read_parquet('{region_glob}', hive_partitioning = false);

            CREATE OR REPLACE VIEW grid_fuel_hourly AS
            SELECT * FROM read_parquet('{fuel_glob}', hive_partitioning = false);

            CREATE OR REPLACE VIEW nuclear_facility_daily AS
            SELECT * FROM read_parquet('{outage_glob}', hive_partitioning = false);

            CREATE OR REPLACE VIEW ba_duck_curve_hourly AS
            WITH demand AS (
                SELECT period_utc, respondent, value_mwh AS demand_mwh
                FROM grid_region_hourly
                WHERE metric_type = 'D'
            ),
            fuel AS (
                SELECT
                    period_utc,
                    respondent,
                    SUM(CASE WHEN fuel_type = 'SUN' THEN generation_mwh ELSE 0 END) AS solar_mwh,
                    SUM(CASE WHEN fuel_type = 'WND' THEN generation_mwh ELSE 0 END) AS wind_mwh,
                    SUM(CASE WHEN fuel_type = 'NUC' THEN generation_mwh ELSE 0 END) AS nuclear_mwh
                FROM grid_fuel_hourly
                GROUP BY period_utc, respondent
            )
            SELECT
                demand.period_utc,
                demand.respondent,
                demand.demand_mwh,
                fuel.solar_mwh,
                fuel.wind_mwh,
                fuel.nuclear_mwh,
                demand.demand_mwh - fuel.solar_mwh - fuel.wind_mwh AS net_load_mwh,
                demand.demand_mwh - fuel.solar_mwh - fuel.wind_mwh - fuel.nuclear_mwh
                    AS residual_load_after_nuclear_mwh
            FROM demand
            INNER JOIN fuel USING (period_utc, respondent);
            """
        )
    return database_path


def export_duck_curve_csv(database_path: Path, output_path: Path, *, respondent: str) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path), read_only=True) as connection:
        cursor = connection.execute(
            """
            SELECT
                period_utc,
                respondent,
                demand_mwh,
                solar_mwh,
                wind_mwh,
                nuclear_mwh,
                net_load_mwh,
                residual_load_after_nuclear_mwh
            FROM ba_duck_curve_hourly
            WHERE respondent = ?
            ORDER BY period_utc
            """,
            [respondent],
        )
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(columns)
        writer.writerows(rows)
    return len(rows)


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def describe_counts(database_path: Path) -> Iterable[tuple[str, int]]:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        for view_name in (
            "grid_region_hourly",
            "grid_fuel_hourly",
            "nuclear_facility_daily",
            "ba_duck_curve_hourly",
        ):
            count = connection.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
            yield view_name, count


def read_duck_curve_rows(database_path: Path, respondent: str) -> list[dict]:
    """Return ba_duck_curve_hourly rows as dicts for the forecast/scenario tools."""
    with duckdb.connect(str(database_path), read_only=True) as connection:
        cursor = connection.execute(
            """
            SELECT period_utc, respondent, demand_mwh, solar_mwh, wind_mwh,
                   nuclear_mwh, net_load_mwh, residual_load_after_nuclear_mwh
            FROM ba_duck_curve_hourly WHERE respondent = ? ORDER BY period_utc
            """,
            [respondent],
        )
        columns = [description[0] for description in cursor.description]
        rows = []
        for record in cursor.fetchall():
            row = dict(zip(columns, record))
            stamp = row["period_utc"]
            row["period_utc"] = stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)
            rows.append(row)
        return rows
