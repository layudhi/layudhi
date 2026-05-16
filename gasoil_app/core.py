from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

MOPS_COLUMN = "mops_usd_per_bbl"
DATE_COLUMN = "date"
BBL_TO_LITER = 158.987294928

Row = dict[str, object]


@dataclass(frozen=True)
class PriceFormula:
    """Conversion assumptions for MOPS gasoil into estimated local fuel price."""

    fx_idr_per_usd: float = 16_000.0
    alpha_usd_per_bbl: float = 0.0
    freight_usd_per_bbl: float = 0.0
    distribution_idr_per_liter: float = 0.0
    tax_percent: float = 0.0
    subsidy_idr_per_liter: float = 0.0

    def validate(self) -> None:
        if self.fx_idr_per_usd <= 0:
            raise ValueError("fx_idr_per_usd harus lebih besar dari 0")
        if self.tax_percent < 0:
            raise ValueError("tax_percent tidak boleh negatif")


def parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date().replace(day=1) if fmt == "%Y-%m" else parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ValueError(f"Format tanggal tidak valid: {value}") from exc


def month_add(month_start: date, months: int) -> date:
    month_index = month_start.month - 1 + months
    year = month_start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def load_mops_csv(path: str | Path) -> list[Row]:
    """Load and validate a MOPS CSV file.

    Required columns:
    - date: date string
    - mops_usd_per_bbl: Singapore MOPS gasoil price in USD/barrel
    """

    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = set(reader.fieldnames or [])
        missing = {DATE_COLUMN, MOPS_COLUMN}.difference(fieldnames)
        if missing:
            raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(sorted(missing))}")
        rows_by_date: dict[date, float] = {}
        for raw in reader:
            if not raw.get(DATE_COLUMN) or not raw.get(MOPS_COLUMN):
                continue
            row_date = parse_date(raw[DATE_COLUMN])
            price = float(str(raw[MOPS_COLUMN]).replace(",", ""))
            if price <= 0:
                raise ValueError("Harga MOPS harus lebih besar dari 0")
            rows_by_date[row_date] = price

    if not rows_by_date:
        raise ValueError("Data MOPS kosong setelah validasi")

    return [
        {DATE_COLUMN: row_date, MOPS_COLUMN: rows_by_date[row_date]}
        for row_date in sorted(rows_by_date)
    ]


def estimate_idr_per_liter(
    mops_usd_per_bbl: Iterable[float] | float,
    formula: PriceFormula,
) -> list[float] | float:
    """Estimate IDR/liter from MOPS gasoil USD/barrel and configurable adders."""

    formula.validate()
    is_scalar = isinstance(mops_usd_per_bbl, int | float)
    values = [float(mops_usd_per_bbl)] if is_scalar else [float(value) for value in mops_usd_per_bbl]
    result: list[float] = []
    for value in values:
        base_usd_per_bbl = value + formula.alpha_usd_per_bbl + formula.freight_usd_per_bbl
        base_idr_per_liter = (base_usd_per_bbl * formula.fx_idr_per_usd) / BBL_TO_LITER
        taxed = base_idr_per_liter * (1 + formula.tax_percent / 100)
        estimated = taxed + formula.distribution_idr_per_liter - formula.subsidy_idr_per_liter
        result.append(max(0.0, estimated))
    return result[0] if is_scalar else result


def monthly_average(rows: Iterable[Row]) -> list[Row]:
    """Aggregate daily/weekly MOPS observations into month-start averages."""

    grouped: dict[date, list[float]] = {}
    for row in rows:
        row_date = parse_date(row[DATE_COLUMN])
        month_start = row_date.replace(day=1)
        grouped.setdefault(month_start, []).append(float(row[MOPS_COLUMN]))

    if not grouped:
        return []

    start = min(grouped)
    end = max(grouped)
    output: list[Row] = []
    cursor = start
    last_value: float | None = None
    while cursor <= end:
        values = grouped.get(cursor)
        if values:
            avg = sum(values) / len(values)
            last_value = avg
        elif last_value is not None:
            avg = last_value
        else:
            avg = 0.0
        output.append({DATE_COLUMN: cursor, MOPS_COLUMN: avg})
        cursor = month_add(cursor, 1)

    first_non_zero = next((float(row[MOPS_COLUMN]) for row in output if float(row[MOPS_COLUMN]) > 0), 0.0)
    for row in output:
        if float(row[MOPS_COLUMN]) == 0.0:
            row[MOPS_COLUMN] = first_non_zero
    return output


def _linear_forecast(values: list[float], periods: int) -> list[float]:
    n = len(values)
    if n == 1:
        return [values[-1]] * periods
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((idx - x_mean) * (value - y_mean) for idx, value in enumerate(values))
    denominator = sum((idx - x_mean) ** 2 for idx in range(n))
    slope = numerator / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    return [intercept + slope * idx for idx in range(n, n + periods)]


def _damped_trend_forecast(values: list[float], periods: int, damping: float = 0.65) -> list[float]:
    if len(values) < 3:
        return _linear_forecast(values, periods)

    recent_window = min(6, len(values) - 1)
    recent_trend = (values[-1] - values[-recent_window - 1]) / recent_window
    long_trend = (values[-1] - values[0]) / (len(values) - 1)
    trend = 0.7 * recent_trend + 0.3 * long_trend
    forecasts: list[float] = []
    current = values[-1]
    for step in range(1, periods + 1):
        current += trend * (damping ** (step - 1))
        forecasts.append(current)
    return forecasts


def _sample_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def forecast_mops(rows: Iterable[Row], months: int = 12, method: str = "damped_trend") -> list[Row]:
    """Forecast monthly MOPS gasoil prices."""

    if months < 1 or months > 60:
        raise ValueError("months harus berada pada rentang 1 sampai 60")

    monthly = monthly_average(rows)
    if not monthly:
        raise ValueError("Data MOPS kosong")
    values = [float(row[MOPS_COLUMN]) for row in monthly]

    if method == "damped_trend":
        yhat = _damped_trend_forecast(values, months)
    elif method == "linear":
        yhat = _linear_forecast(values, months)
    elif method == "naive":
        yhat = [values[-1]] * months
    else:
        raise ValueError("method harus salah satu dari: damped_trend, linear, naive")

    fitted_linear = _linear_forecast(values, len(values))
    residual = [actual - fitted for actual, fitted in zip(values, fitted_linear, strict=True)]
    volatility = _sample_std(residual) if len(residual) > 2 else _sample_std(values)
    if not math.isfinite(volatility) or volatility == 0:
        volatility = max(values[-1] * 0.05, 1.0)

    last_date = parse_date(monthly[-1][DATE_COLUMN]).replace(day=1)
    forecast: list[Row] = []
    for idx, value in enumerate(yhat, start=1):
        point = max(0.01, value)
        interval = 1.64 * volatility * math.sqrt(idx)
        forecast.append(
            {
                DATE_COLUMN: month_add(last_date, idx),
                "forecast_mops_usd_per_bbl": point,
                "low_90": max(0.01, point - interval),
                "high_90": point + interval,
                "method": method,
            }
        )
    return forecast


def build_analysis(
    rows: Iterable[Row], formula: PriceFormula, forecast_months: int, method: str
) -> tuple[list[Row], list[Row]]:
    """Return historical monthly analysis and forecast with IDR/liter estimates."""

    source_rows = list(rows)
    monthly = monthly_average(source_rows)
    monthly_prices = [float(row[MOPS_COLUMN]) for row in monthly]
    monthly_estimates = estimate_idr_per_liter(monthly_prices, formula)
    assert isinstance(monthly_estimates, list)
    for row, estimate in zip(monthly, monthly_estimates, strict=True):
        row["estimated_idr_per_liter"] = round(estimate, 2)

    forecast = forecast_mops(source_rows, months=forecast_months, method=method)
    forecast_prices = [float(row["forecast_mops_usd_per_bbl"]) for row in forecast]
    forecast_estimates = estimate_idr_per_liter(forecast_prices, formula)
    low_estimates = estimate_idr_per_liter([float(row["low_90"]) for row in forecast], formula)
    high_estimates = estimate_idr_per_liter([float(row["high_90"]) for row in forecast], formula)
    assert isinstance(forecast_estimates, list)
    assert isinstance(low_estimates, list)
    assert isinstance(high_estimates, list)
    for row, estimate, low, high in zip(
        forecast, forecast_estimates, low_estimates, high_estimates, strict=True
    ):
        row["estimated_idr_per_liter"] = round(estimate, 2)
        row["low_90_idr_per_liter"] = round(low, 2)
        row["high_90_idr_per_liter"] = round(high, 2)
    return monthly, forecast


def write_csv(path: str | Path, rows: Iterable[Row]) -> None:
    rows = list(rows)
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
