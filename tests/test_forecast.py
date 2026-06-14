"""Forecaster tests: runs offline on synthetic data and beats persistence."""
from helix import forecast
from helix.synth import synthetic_rows


def test_forecast_returns_valid_metrics():
    rows = synthetic_rows(days=40, seed=3)
    results = forecast.forecast_renewables(rows)
    for series in ("solar", "wind"):
        metrics = results[series]
        assert metrics["n_test"] > 0
        assert metrics["rmse_model"] >= 0
        assert len(metrics["predictions"]) == metrics["n_test"]


def test_forecast_beats_persistence():
    rows = synthetic_rows(days=40, seed=3)
    results = forecast.forecast_renewables(rows)
    # structured diurnal signal: the model should clear seasonal-naive persistence
    assert results["solar"]["skill_score"] > 0.3
    assert results["wind"]["skill_score"] > 0.0
