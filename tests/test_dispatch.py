"""Dispatch tests: exact QUBO optimum is well-defined and QAOA recovers it."""
import pytest

from helix import dispatch

SMALL_UNITS = [
    {"name": "A", "capacity": 4.0, "cost": 12.0},
    {"name": "B", "capacity": 3.0, "cost": 31.0},
    {"name": "C", "capacity": 2.0, "cost": 20.0},
    {"name": "D", "capacity": 5.0, "cost": 42.0},
]


def test_brute_force_covers_target():
    Q, const = dispatch.build_qubo(SMALL_UNITS, target_load=6.0, penalty=10.0)
    best = dispatch.brute_force(Q, const, len(SMALL_UNITS))
    assert len(best["bitstring"]) == len(SMALL_UNITS)
    served = sum(u["capacity"] for u, b in zip(SMALL_UNITS, best["bitstring"]) if b)
    assert served >= 6.0          # the optimum covers the target


def test_qaoa_recovers_small_optimum():
    result = dispatch.dispatch_experiment(units=SMALL_UNITS, target_load=6.0, seed=0)
    assert result["optimum_recovered"] is True
    assert result["qaoa"]["cost"] == pytest.approx(result["exact"]["cost"])


def test_default_instance_runs():
    result = dispatch.dispatch_experiment(seed=0)
    assert result["n_units"] == len(dispatch.DEFAULT_UNITS)
    assert result["exact"]["cost"] <= result["qaoa"]["cost"] + 1e-9
