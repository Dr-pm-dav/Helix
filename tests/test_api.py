from __future__ import annotations

from datetime import UTC, datetime

import duckdb
from fastapi.testclient import TestClient

from helix.api import create_app

STAMP = datetime(2025, 4, 1, 12, tzinfo=UTC)


def make_database(path) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE ba_duck_curve_hourly (
                period_utc TIMESTAMPTZ,
                respondent VARCHAR,
                demand_mwh DOUBLE,
                solar_mwh DOUBLE,
                wind_mwh DOUBLE,
                nuclear_mwh DOUBLE,
                net_load_mwh DOUBLE,
                residual_load_after_nuclear_mwh DOUBLE
            );
            CREATE TABLE grid_fuel_hourly (
                period_utc TIMESTAMPTZ,
                respondent VARCHAR,
                fuel_type VARCHAR,
                fuel_name VARCHAR,
                generation_mwh DOUBLE
            );
            CREATE TABLE nuclear_facility_daily (
                period_date DATE,
                capacity_mw DOUBLE,
                outage_mw DOUBLE
            );
            CREATE TABLE grid_region_hourly (
                respondent VARCHAR,
                ingested_at_utc TIMESTAMPTZ
            );
            """
        )
        connection.execute(
            """
            INSERT INTO ba_duck_curve_hourly VALUES
                (?, 'CISO', 100, 30, 10, 20, 60, 40),
                (? + INTERVAL 1 HOUR, 'CISO', 120, 25, 15, 20, 80, 60)
            """,
            [STAMP, STAMP],
        )
        connection.execute(
            """
            INSERT INTO grid_fuel_hourly VALUES
                (?, 'CISO', 'SUN', 'Solar', 30),
                (? + INTERVAL 1 HOUR, 'CISO', 'SUN', 'Solar', 25)
            """,
            [STAMP, STAMP],
        )
        connection.execute(
            "INSERT INTO nuclear_facility_daily VALUES ('2025-04-01', 1000, 125)"
        )
        connection.execute(
            "INSERT INTO grid_region_hourly VALUES ('CISO', ?)",
            [STAMP],
        )


def test_dashboard_api_returns_profiles_and_summary(tmp_path) -> None:
    database_path = tmp_path / "helix.duckdb"
    make_database(database_path)
    client = TestClient(create_app(database_path=database_path))

    response = client.get("/api/dashboard?respondent=CISO&start=2025-04-01&end=2025-04-01")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["peakDemandMwh"] == 120.0
    assert payload["summary"]["minimumNetLoadMwh"] == 60.0
    assert payload["summary"]["steepestHourlyRampMwh"] == 20.0
    assert len(payload["duckCurveProfile"]) == 24
    assert payload["outageContext"]["maximumOutageMw"] == 125.0


def test_dashboard_api_rejects_reversed_range(tmp_path) -> None:
    database_path = tmp_path / "helix.duckdb"
    make_database(database_path)
    client = TestClient(create_app(database_path=database_path))

    response = client.get("/api/dashboard?start=2025-04-02&end=2025-04-01")

    assert response.status_code == 400
    assert response.json()["detail"] == "end must be on or after start"
