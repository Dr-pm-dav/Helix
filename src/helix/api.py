"""FastAPI surface for the first Helix dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

RESPONDENT_TIMEZONES = {"CISO": "America/Los_Angeles"}


def create_app(
    *,
    database_path: Path | None = None,
    web_dir: Path | None = None,
) -> FastAPI:
    root = Path(__file__).resolve().parents[2]
    database = database_path or root / "data" / "helix.duckdb"
    web = web_dir or root / "web"
    app = FastAPI(title="Helix API", version="0.1.0")
    app.mount("/static", StaticFiles(directory=web / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(web / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        _require_database(database)
        return {"status": "ok"}

    @app.get("/api/authorities")
    def authorities() -> list[dict[str, str]]:
        _require_database(database)
        with duckdb.connect(str(database), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT
                    respondent,
                    MIN(period_utc),
                    MAX(period_utc)
                FROM ba_duck_curve_hourly
                GROUP BY respondent
                ORDER BY respondent
                """
            ).fetchall()
        return [
            {
                "respondent": respondent,
                "start": _utc_iso(start),
                "end": _utc_iso(end),
                "timezone": RESPONDENT_TIMEZONES.get(respondent, "UTC"),
            }
            for respondent, start, end in rows
        ]

    @app.get("/api/dashboard")
    def dashboard_data(
        respondent: str = Query("CISO", min_length=2, max_length=12),
        start: date = Query(date(2025, 4, 1)),
        end: date = Query(date(2025, 4, 30)),
    ) -> dict[str, object]:
        _require_database(database)
        if end < start:
            raise HTTPException(status_code=400, detail="end must be on or after start")

        timezone_name = RESPONDENT_TIMEZONES.get(respondent, "UTC")
        start_utc = datetime.combine(start, time.min, tzinfo=UTC)
        end_utc = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
        with duckdb.connect(str(database), read_only=True) as connection:
            duck_rows = connection.execute(
                """
                SELECT
                    period_utc,
                    demand_mwh,
                    solar_mwh,
                    wind_mwh,
                    nuclear_mwh,
                    net_load_mwh,
                    residual_load_after_nuclear_mwh
                FROM ba_duck_curve_hourly
                WHERE respondent = ?
                  AND period_utc >= ?
                  AND period_utc < ?
                ORDER BY period_utc
                """,
                [respondent, start_utc, end_utc],
            ).fetchall()
            if not duck_rows:
                raise HTTPException(status_code=404, detail="No duck-curve rows for selection")

            fuel_rows = connection.execute(
                """
                SELECT period_utc, fuel_type, fuel_name, generation_mwh
                FROM grid_fuel_hourly
                WHERE respondent = ?
                  AND period_utc >= ?
                  AND period_utc < ?
                ORDER BY period_utc, fuel_type
                """,
                [respondent, start_utc, end_utc],
            ).fetchall()
            outage_rows = connection.execute(
                """
                SELECT period_date, SUM(capacity_mw), SUM(outage_mw)
                FROM nuclear_facility_daily
                WHERE period_date >= ?::DATE
                  AND period_date <= ?::DATE
                GROUP BY period_date
                ORDER BY period_date
                """,
                [start.isoformat(), end.isoformat()],
            ).fetchall()
            freshness = connection.execute(
                """
                SELECT MAX(ingested_at_utc)
                FROM grid_region_hourly
                WHERE respondent = ?
                """,
                [respondent],
            ).fetchone()[0]

        return _dashboard_payload(
            respondent=respondent,
            timezone_name=timezone_name,
            duck_rows=duck_rows,
            fuel_rows=fuel_rows,
            outage_rows=outage_rows,
            freshness=freshness,
        )

    return app


def _dashboard_payload(
    *,
    respondent: str,
    timezone_name: str,
    duck_rows: list[tuple[datetime, float, float, float, float, float, float]],
    fuel_rows: list[tuple[datetime, str, str, float]],
    outage_rows: list[tuple[date, float, float]],
    freshness: datetime,
) -> dict[str, object]:
    timezone = ZoneInfo(timezone_name)
    duck_profile: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for period, demand, solar, wind, nuclear, net_load, residual in duck_rows:
        hour = period.astimezone(timezone).hour
        duck_profile[hour]["demand"].append(demand)
        duck_profile[hour]["solar"].append(solar)
        duck_profile[hour]["wind"].append(wind)
        duck_profile[hour]["nuclear"].append(nuclear)
        duck_profile[hour]["netLoad"].append(net_load)
        duck_profile[hour]["residualAfterNuclear"].append(residual)

    profile = [
        {
            "hour": hour,
            **{name: round(mean(values), 2) for name, values in duck_profile[hour].items()},
        }
        for hour in range(24)
    ]
    fuel_profile: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for period, fuel_type, fuel_name, generation in fuel_rows:
        fuel_profile[(fuel_type, fuel_name)][period.astimezone(timezone).hour].append(generation)

    hourly_net_load = [row[5] for row in duck_rows]
    ramps = [abs(current - previous) for previous, current in zip(hourly_net_load, hourly_net_load[1:])]
    outages = [
        {
            "date": period.isoformat(),
            "capacityMw": round(capacity, 2),
            "outageMw": round(outage, 2),
            "availableMw": round(capacity - outage, 2),
        }
        for period, capacity, outage in outage_rows
    ]
    return {
        "respondent": respondent,
        "timezone": timezone_name,
        "freshness": _utc_iso(freshness),
        "coverage": {
            "hourlyRows": len(duck_rows),
            "start": _utc_iso(duck_rows[0][0]),
            "end": _utc_iso(duck_rows[-1][0]),
        },
        "summary": {
            "peakDemandMwh": round(max(row[1] for row in duck_rows), 2),
            "minimumNetLoadMwh": round(min(hourly_net_load), 2),
            "steepestHourlyRampMwh": round(max(ramps, default=0.0), 2),
            "averageNuclearMwh": round(mean(row[4] for row in duck_rows), 2),
        },
        "duckCurveProfile": profile,
        "generationMixProfile": [
            {
                "fuelType": fuel_type,
                "fuelName": fuel_name,
                "values": [
                    round(mean(hour_values.get(hour, [0.0])), 2) for hour in range(24)
                ],
            }
            for (fuel_type, fuel_name), hour_values in sorted(fuel_profile.items())
        ],
        "outageContext": {
            "scope": "U.S. nuclear fleet context",
            "maximumOutageMw": round(max((row[2] for row in outage_rows), default=0.0), 2),
            "days": outages,
        },
    }


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_database(database_path: Path) -> None:
    if not database_path.exists():
        raise HTTPException(status_code=503, detail="Helix data has not been ingested yet")
