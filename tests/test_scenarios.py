"""Scenario tests: higher renewables deepen the belly; lower nuclear raises residual."""
from helix import scenarios
from helix.synth import synthetic_rows


def test_higher_renewables_deepen_belly_and_curtailment():
    rows = synthetic_rows(days=30, seed=2)
    base = scenarios.summarize(rows)
    high = scenarios.summarize(scenarios.apply_scenario(rows, renewable_multiplier=1.6))
    assert high["min_net_load_mwh"] < base["min_net_load_mwh"]
    assert high["curtailment_hours"] >= base["curtailment_hours"]
    assert high["renewable_share"] > base["renewable_share"]


def test_lower_nuclear_raises_residual():
    rows = synthetic_rows(days=20, seed=2)
    base = scenarios.summarize(rows)
    low = scenarios.summarize(scenarios.apply_scenario(rows, nuclear_availability=0.4))
    assert low["peak_residual_mwh"] > base["peak_residual_mwh"]
    # net load (pre-nuclear) is unchanged by a nuclear-only scenario
    assert low["min_net_load_mwh"] == base["min_net_load_mwh"]
