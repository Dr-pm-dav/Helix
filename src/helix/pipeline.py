"""One-month vertical-slice ingestion for Helix."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from helix.config import Settings
from helix.eia import EiaClient
from helix.normalize import normalize_fuel_rows, normalize_outage_rows, normalize_region_rows
from helix.storage import (
    FUEL_KEYS,
    OUTAGE_KEYS,
    REGION_KEYS,
    monthly_partition,
    register_views,
    upsert_parquet,
)


@dataclass(frozen=True)
class IngestResult:
    region_rows: int
    fuel_rows: int
    outage_rows: int
    database_path: Path


def ingest_month(
    settings: Settings,
    *,
    respondent: str,
    start: date,
    end: date,
    client: EiaClient | None = None,
) -> IngestResult:
    if start.year != end.year or start.month != end.month:
        raise ValueError("The MVP ingestion command accepts one calendar month at a time.")
    if end < start:
        raise ValueError("end must be on or after start")

    eia = client or EiaClient(settings.api_key)
    ingested_at_utc = datetime.now(UTC)
    hourly_start = f"{start.isoformat()}T00"
    hourly_end = f"{end.isoformat()}T23"

    region_rows = normalize_region_rows(
        eia.fetch_all(
            "electricity/rto/region-data",
            frequency="hourly",
            data_fields=["value"],
            facets={"respondent": [respondent]},
            start=hourly_start,
            end=hourly_end,
        ),
        ingested_at_utc=ingested_at_utc,
    )
    fuel_rows = normalize_fuel_rows(
        eia.fetch_all(
            "electricity/rto/fuel-type-data",
            frequency="hourly",
            data_fields=["value"],
            facets={"respondent": [respondent]},
            start=hourly_start,
            end=hourly_end,
        ),
        ingested_at_utc=ingested_at_utc,
    )
    outage_rows = normalize_outage_rows(
        eia.fetch_all(
            "nuclear-outages/facility-nuclear-outages",
            frequency="daily",
            data_fields=["capacity", "outage", "percentOutage"],
            start=start.isoformat(),
            end=end.isoformat(),
        ),
        ingested_at_utc=ingested_at_utc,
    )

    region_count = upsert_parquet(
        monthly_partition(
            settings.data_dir,
            "grid_region_hourly",
            respondent=respondent,
            year=start.year,
            month=start.month,
        ),
        region_rows,
        key_columns=REGION_KEYS,
    )
    fuel_count = upsert_parquet(
        monthly_partition(
            settings.data_dir,
            "grid_fuel_hourly",
            respondent=respondent,
            year=start.year,
            month=start.month,
        ),
        fuel_rows,
        key_columns=FUEL_KEYS,
    )
    outage_count = upsert_parquet(
        monthly_partition(
            settings.data_dir,
            "nuclear_facility_daily",
            year=start.year,
            month=start.month,
        ),
        outage_rows,
        key_columns=OUTAGE_KEYS,
    )
    return IngestResult(region_count, fuel_count, outage_count, register_views(settings.data_dir))

