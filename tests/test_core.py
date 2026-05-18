from pathlib import Path

import pytest

from gasoil_app.core import PriceFormula, build_analysis, estimate_idr_per_liter, forecast_mops, load_mops_csv


def test_load_mops_csv_validates_and_sorts(tmp_path: Path) -> None:
    csv = tmp_path / "mops.csv"
    csv.write_text("date,mops_usd_per_bbl\n2025-02-01,90\n2025-01-01,95\n", encoding="utf-8")

    rows = load_mops_csv(csv)

    assert [row["mops_usd_per_bbl"] for row in rows] == [95, 90]


def test_load_mops_csv_requires_columns(tmp_path: Path) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("date,price\n2025-01-01,95\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Kolom wajib"):
        load_mops_csv(csv)


def test_estimate_idr_per_liter_uses_formula() -> None:
    formula = PriceFormula(
        fx_idr_per_usd=16_000,
        alpha_usd_per_bbl=1,
        freight_usd_per_bbl=2,
        distribution_idr_per_liter=500,
        tax_percent=10,
        subsidy_idr_per_liter=100,
    )

    result = estimate_idr_per_liter(100, formula)

    assert result == pytest.approx(((103 * 16_000) / 158.987294928) * 1.1 + 400)


def test_forecast_mops_returns_requested_months() -> None:
    rows = [
        {"date": f"2025-{month:02d}-01", "mops_usd_per_bbl": price}
        for month, price in enumerate([90, 91, 92, 93, 94, 93, 95, 96, 97, 98, 99, 100], start=1)
    ]

    forecast = forecast_mops(rows, months=3)

    assert len(forecast) == 3
    assert min(row["forecast_mops_usd_per_bbl"] for row in forecast) > 0
    assert {"low_90", "high_90", "method"}.issubset(forecast[0])


def test_build_analysis_adds_idr_estimates() -> None:
    rows = load_mops_csv("examples/mops_sample.csv")
    monthly, forecast = build_analysis(rows, PriceFormula(), forecast_months=2, method="naive")

    assert "estimated_idr_per_liter" in monthly[0]
    assert len(forecast) == 2
    assert "high_90_idr_per_liter" in forecast[0]


def test_damped_trend_forecast_uses_recent_price_floor() -> None:
    rows = [
        {"date": f"2025-{month:02d}-01", "mops_usd_per_bbl": price}
        for month, price in enumerate([180, 175, 170, 165, 150, 130, 110, 90, 70, 50, 30, 10], start=1)
    ]

    forecast = forecast_mops(rows, months=1, method="damped_trend")

    recent_prices = [float(row["mops_usd_per_bbl"]) for row in rows]
    median_recent = (recent_prices[5] + recent_prices[6]) / 2
    assert forecast[0]["forecast_mops_usd_per_bbl"] >= median_recent * 0.35


def test_build_analysis_adds_clear_output_aliases() -> None:
    rows = load_mops_csv("examples/mops_sample.csv")
    monthly, forecast = build_analysis(rows, PriceFormula(), forecast_months=1, method="naive")

    assert "source_price_usd_per_bbl" in monthly[0]
    assert "estimated_fuel_price_idr_per_liter" in monthly[0]
    assert "forecast_source_price_usd_per_bbl" in forecast[0]
    assert "forecast_fuel_price_idr_per_liter" in forecast[0]


def test_damped_trend_forecast_uses_recent_price_cap() -> None:
    rows = [
        {"date": f"2025-{month:02d}-01", "mops_usd_per_bbl": price}
        for month, price in enumerate([10, 30, 50, 70, 90, 110, 130, 150, 165, 170, 175, 180], start=1)
    ]

    forecast = forecast_mops(rows, months=1, method="damped_trend")

    recent_prices = [float(row["mops_usd_per_bbl"]) for row in rows]
    median_recent = (recent_prices[5] + recent_prices[6]) / 2
    assert forecast[0]["forecast_mops_usd_per_bbl"] <= median_recent * 2.5
