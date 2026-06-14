"""
Higher-renewables and nuclear-availability scenario modelling.

Scales the renewable and nuclear series on the hourly duck-curve data and
recomputes net load (demand minus wind and solar) and residual load (after
nuclear), then summarises the grid-stress metrics that move under each
scenario:

  - minimum net load: the depth of the midday "belly" of the duck curve;
  - steepest hourly ramp: the largest hour-to-hour change in net load, the
    evening pickup that flexible capacity has to follow;
  - curtailment hours: hours where wind and solar exceed demand (net load
    below zero), a proxy for oversupply that would be curtailed or stored;
  - renewable share: wind-plus-solar generation as a fraction of demand.
"""
from __future__ import annotations


def apply_scenario(rows, *, renewable_multiplier=1.0, nuclear_availability=1.0):
    """Return new rows with renewables and nuclear scaled and loads recomputed."""
    out = []
    for r in rows:
        solar = r["solar_mwh"] * renewable_multiplier
        wind = r["wind_mwh"] * renewable_multiplier
        nuclear = r["nuclear_mwh"] * nuclear_availability
        net = r["demand_mwh"] - solar - wind
        out.append({**r, "solar_mwh": round(solar, 2), "wind_mwh": round(wind, 2),
                    "nuclear_mwh": round(nuclear, 2), "net_load_mwh": round(net, 2),
                    "residual_load_after_nuclear_mwh": round(net - nuclear, 2)})
    return out


def summarize(rows):
    """Grid-stress metrics for one hourly dataset."""
    demand = [r["demand_mwh"] for r in rows]
    net = [r["net_load_mwh"] for r in rows]
    residual = [r["residual_load_after_nuclear_mwh"] for r in rows]
    renew = [r["solar_mwh"] + r["wind_mwh"] for r in rows]
    ramps = [abs(net[i] - net[i - 1]) for i in range(1, len(net))]
    return {
        "hours": len(rows),
        "peak_demand_mwh": round(max(demand), 1),
        "min_net_load_mwh": round(min(net), 1),
        "max_hourly_ramp_mwh": round(max(ramps), 1) if ramps else 0.0,
        "peak_residual_mwh": round(max(residual), 1),
        "curtailment_hours": int(sum(1 for v in net if v < 0)),
        "renewable_share": round(sum(renew) / sum(demand), 4) if sum(demand) else 0.0,
    }


def compare(rows, scenarios):
    """Summaries for the baseline plus each named scenario.

    ``scenarios`` maps a label to keyword arguments for ``apply_scenario``,
    e.g. ``{"+50% renewables": {"renewable_multiplier": 1.5},
            "nuclear at 50%": {"nuclear_availability": 0.5}}``.
    """
    table = {"baseline": summarize(rows)}
    for label, kwargs in scenarios.items():
        table[label] = summarize(apply_scenario(rows, **kwargs))
    return table
