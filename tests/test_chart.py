from helix.chart import _build_svg


def test_build_svg_labels_chart_and_source() -> None:
    svg = _build_svg(
        {
            "Demand": [100.0] * 24,
            "Net load after wind + solar": [60.0] * 24,
            "Residual load after nuclear": [40.0] * 24,
        },
        respondent="CISO",
        y_min=0.0,
        y_max=110.0,
    )

    assert "Helix Duck Curve" in svg
    assert "CISO average hourly profile" in svg
    assert "Net load = demand - wind - solar." in svg
