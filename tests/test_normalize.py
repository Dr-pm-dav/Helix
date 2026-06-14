from datetime import UTC, datetime

from helix.normalize import normalize_fuel_rows, normalize_outage_rows, normalize_region_rows

INGESTED_AT = datetime(2025, 5, 1, tzinfo=UTC)


def test_normalize_region_rows() -> None:
    rows = normalize_region_rows(
        [
            {
                "period": "2025-04-01T01",
                "respondent": "CISO",
                "respondent-name": "California Independent System Operator",
                "type": "D",
                "type-name": "Demand",
                "value": "24545",
            }
        ],
        ingested_at_utc=INGESTED_AT,
    )

    assert rows[0]["metric_type"] == "D"
    assert rows[0]["value_mwh"] == 24545.0
    assert rows[0]["period_utc"] == datetime(2025, 4, 1, 1, tzinfo=UTC)


def test_normalize_fuel_rows_allows_negative_generation() -> None:
    rows = normalize_fuel_rows(
        [
            {
                "period": "2025-04-01T03",
                "respondent": "CISO",
                "respondent-name": "California Independent System Operator",
                "fueltype": "COL",
                "type-name": "Coal",
                "value": "-3",
            }
        ],
        ingested_at_utc=INGESTED_AT,
    )

    assert rows[0]["generation_mwh"] == -3.0


def test_normalize_outage_rows() -> None:
    rows = normalize_outage_rows(
        [
            {
                "period": "2025-04-02",
                "facility": "46",
                "facilityName": "Browns Ferry",
                "capacity": "3661.7",
                "outage": "1207.7",
                "percentOutage": "32.98",
            }
        ],
        ingested_at_utc=INGESTED_AT,
    )

    assert rows[0]["facility_name"] == "Browns Ferry"
    assert rows[0]["outage_mw"] == 1207.7

