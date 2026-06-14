from datetime import UTC, datetime

import duckdb

from helix.storage import FUEL_KEYS, REGION_KEYS, register_views, upsert_parquet

STAMP = datetime(2025, 5, 1, tzinfo=UTC)


def test_upsert_parquet_replaces_rows_by_key(tmp_path) -> None:
    path = tmp_path / "respondent=CISO" / "rows.parquet"
    first = {"period_utc": STAMP, "respondent": "CISO", "fuel_type": "SUN", "value": 1}
    replacement = {**first, "value": 2}

    assert upsert_parquet(path, [first], key_columns=FUEL_KEYS) == 1
    assert upsert_parquet(path, [replacement], key_columns=FUEL_KEYS) == 1


def test_duck_curve_view(tmp_path) -> None:
    data_dir = tmp_path / "data"
    region_path = (
        data_dir
        / "normalized"
        / "grid_region_hourly"
        / "respondent=CISO"
        / "year=2025"
        / "month=04"
        / "data.parquet"
    )
    fuel_path = (
        data_dir
        / "normalized"
        / "grid_fuel_hourly"
        / "respondent=CISO"
        / "year=2025"
        / "month=04"
        / "data.parquet"
    )
    outage_path = (
        data_dir
        / "normalized"
        / "nuclear_facility_daily"
        / "year=2025"
        / "month=04"
        / "data.parquet"
    )
    upsert_parquet(
        region_path,
        [
            {
                "period_utc": STAMP,
                "respondent": "CISO",
                "metric_type": "D",
                "value_mwh": 100.0,
            }
        ],
        key_columns=REGION_KEYS,
    )
    upsert_parquet(
        fuel_path,
        [
            {
                "period_utc": STAMP,
                "respondent": "CISO",
                "fuel_type": "SUN",
                "generation_mwh": 30.0,
            },
            {
                "period_utc": STAMP,
                "respondent": "CISO",
                "fuel_type": "WND",
                "generation_mwh": 10.0,
            },
            {
                "period_utc": STAMP,
                "respondent": "CISO",
                "fuel_type": "NUC",
                "generation_mwh": 20.0,
            },
        ],
        key_columns=FUEL_KEYS,
    )
    upsert_parquet(
        outage_path,
        [
            {
                "period_date": STAMP.date(),
                "facility": "1",
                "outage_mw": 0.0,
            }
        ],
        key_columns=("period_date", "facility"),
    )

    database_path = register_views(data_dir)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        row = connection.execute(
            "SELECT net_load_mwh, residual_load_after_nuclear_mwh FROM ba_duck_curve_hourly"
        ).fetchone()
    assert row == (60.0, 40.0)
