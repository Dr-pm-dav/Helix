"""Dependency-light SVG rendering for the first Helix duck curve."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import duckdb

WIDTH = 1120
HEIGHT = 680
LEFT = 92
RIGHT = 40
TOP = 92
BOTTOM = 104
COLORS = {
    "Demand": "#20324a",
    "Net load after wind + solar": "#db6b3d",
    "Residual load after nuclear": "#7267d9",
}


def render_duck_curve_svg(
    database_path: Path,
    output_path: Path,
    *,
    respondent: str,
    timezone_name: str = "America/Los_Angeles",
) -> None:
    rows = _load_rows(database_path, respondent=respondent)
    if not rows:
        raise ValueError(f"No duck-curve rows found for {respondent}")

    timezone = ZoneInfo(timezone_name)
    grouped: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for period_utc, demand, net_load, residual_load in rows:
        hour = period_utc.astimezone(timezone).hour
        grouped[hour]["Demand"].append(demand)
        grouped[hour]["Net load after wind + solar"].append(net_load)
        grouped[hour]["Residual load after nuclear"].append(residual_load)

    series = {
        label: [mean(grouped[hour][label]) for hour in range(24)] for label in COLORS
    }
    all_values = [value for values in series.values() for value in values]
    y_min = min(0.0, min(all_values))
    y_max = max(all_values) * 1.08
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _build_svg(series, respondent=respondent, y_min=y_min, y_max=y_max),
        encoding="utf-8",
    )


def _load_rows(database_path: Path, *, respondent: str) -> list[tuple[datetime, float, float, float]]:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT
                period_utc,
                demand_mwh,
                net_load_mwh,
                residual_load_after_nuclear_mwh
            FROM ba_duck_curve_hourly
            WHERE respondent = ?
            ORDER BY period_utc
            """,
            [respondent],
        ).fetchall()


def _build_svg(
    series: dict[str, list[float]], *, respondent: str, y_min: float, y_max: float
) -> str:
    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM

    def x(hour: int) -> float:
        return LEFT + plot_width * hour / 23

    def y(value: float) -> float:
        return TOP + plot_height * (y_max - value) / (y_max - y_min)

    grid_max = int(y_max // 5000 + 1) * 5000
    y_ticks = list(range(0, grid_max + 1, 5000))

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #20324a; }",
        ".muted { fill: #627083; }",
        ".axis { stroke: #9ba8b8; stroke-width: 1; }",
        ".grid { stroke: #e6e9ef; stroke-width: 1; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fbfaf7"/>',
        '<text x="56" y="45" font-size="26" font-weight="700">Helix Duck Curve</text>',
        f'<text x="56" y="70" font-size="15" class="muted">{escape(respondent)} average hourly '
        "profile | April 2025 | Pacific time</text>",
    ]

    for tick in y_ticks:
        tick_y = y(tick)
        elements.extend(
            [
                f'<line x1="{LEFT}" y1="{tick_y:.1f}" x2="{WIDTH - RIGHT}" '
                f'y2="{tick_y:.1f}" class="grid"/>',
                f'<text x="{LEFT - 14}" y="{tick_y + 5:.1f}" font-size="12" '
                f'text-anchor="end" class="muted">{tick // 1000}k</text>',
            ]
        )

    for hour in range(0, 24, 3):
        tick_x = x(hour)
        elements.extend(
            [
                f'<line x1="{tick_x:.1f}" y1="{TOP}" x2="{tick_x:.1f}" '
                f'y2="{HEIGHT - BOTTOM}" class="grid"/>',
                f'<text x="{tick_x:.1f}" y="{HEIGHT - BOTTOM + 27}" font-size="12" '
                f'text-anchor="middle" class="muted">{hour:02d}:00</text>',
            ]
        )

    elements.extend(
        [
            f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{HEIGHT - BOTTOM}" class="axis"/>',
            f'<line x1="{LEFT}" y1="{HEIGHT - BOTTOM}" x2="{WIDTH - RIGHT}" '
            f'y2="{HEIGHT - BOTTOM}" class="axis"/>',
            f'<text x="22" y="{TOP + plot_height / 2:.1f}" font-size="13" '
            'transform="rotate(-90 22 334)" text-anchor="middle" class="muted">'
            "Average hourly energy (MWh)</text>",
            f'<text x="{LEFT + plot_width / 2:.1f}" y="{HEIGHT - 43}" font-size="13" '
            'text-anchor="middle" class="muted">Hour of day (Pacific time)</text>',
        ]
    )

    for label, values in series.items():
        points = " ".join(f"{x(hour):.1f},{y(value):.1f}" for hour, value in enumerate(values))
        elements.append(
            f'<polyline points="{points}" fill="none" stroke="{COLORS[label]}" '
            'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    legend_x = 615
    for index, (label, color) in enumerate(COLORS.items()):
        legend_y = 37 + index * 22
        elements.extend(
            [
                f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 34}" '
                f'y2="{legend_y}" stroke="{color}" stroke-width="4"/>',
                f'<text x="{legend_x + 44}" y="{legend_y + 5}" font-size="13">'
                f"{escape(label)}</text>",
            ]
        )

    elements.extend(
        [
            f'<text x="{LEFT}" y="{HEIGHT - 14}" font-size="11" class="muted">'
            "Source: U.S. EIA Hourly Electric Grid Monitor (Form EIA-930). "
            "Net load = demand - wind - solar.</text>",
            "</svg>",
        ]
    )
    return "\n".join(elements)
