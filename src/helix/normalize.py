"""Normalize EIA API records into typed analytical rows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


def parse_hour_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H").replace(tzinfo=UTC)


def normalize_region_rows(
    records: list[dict[str, Any]], *, ingested_at_utc: datetime
) -> list[dict[str, Any]]:
    return [
        {
            "period_utc": parse_hour_utc(row["period"]),
            "respondent": row["respondent"],
            "respondent_name": row["respondent-name"],
            "metric_type": row["type"],
            "metric_name": row["type-name"],
            "value_mwh": float(row["value"]),
            "ingested_at_utc": ingested_at_utc,
        }
        for row in records
    ]


def normalize_fuel_rows(
    records: list[dict[str, Any]], *, ingested_at_utc: datetime
) -> list[dict[str, Any]]:
    return [
        {
            "period_utc": parse_hour_utc(row["period"]),
            "respondent": row["respondent"],
            "respondent_name": row["respondent-name"],
            "fuel_type": row["fueltype"],
            "fuel_name": row["type-name"],
            "generation_mwh": float(row["value"]),
            "ingested_at_utc": ingested_at_utc,
        }
        for row in records
    ]


def normalize_outage_rows(
    records: list[dict[str, Any]], *, ingested_at_utc: datetime
) -> list[dict[str, Any]]:
    return [
        {
            "period_date": date.fromisoformat(row["period"]),
            "facility": row["facility"],
            "facility_name": row["facilityName"],
            "capacity_mw": float(row["capacity"]),
            "outage_mw": float(row["outage"]),
            "percent_outage": float(row["percentOutage"]),
            "ingested_at_utc": ingested_at_utc,
        }
        for row in records
    ]

