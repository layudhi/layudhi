import json
from datetime import date

import pytest

from gasoil_app.sources import (
    DATAHUB_OIL_PRICE_CSV_URLS,
    EIA_HISTORY_SERIES,
    ONLINE_SOURCE_CHOICES,
    convert_to_usd_per_bbl,
    ProxyConfig,
    fetch_csv_url,
    fetch_datahub_oil_prices,
    fetch_eia_history,
    fetch_yahoo_chart,
    parse_eia_history_html,
    parse_orb_markets,
)


def test_convert_to_usd_per_bbl() -> None:
    assert convert_to_usd_per_bbl(2.5, "usd_per_gal") == pytest.approx(105.0)
    assert convert_to_usd_per_bbl(746.0, "usd_per_mt") == pytest.approx(100.0)
    assert convert_to_usd_per_bbl(95.0, "usd_per_bbl") == pytest.approx(95.0)


def test_fetch_yahoo_chart_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1735689600, 1735776000],
                    "indicators": {"quote": [{"close": [2.5, None]}]},
                }
            ],
            "error": None,
        }
    }

    def fake_read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
        assert "HO%3DF" in url
        return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("gasoil_app.sources._read_url", fake_read_url)

    rows = fetch_yahoo_chart("HO=F", "usd_per_gal")

    assert rows == [{"date": date(2025, 1, 1), "mops_usd_per_bbl": pytest.approx(105.0)}]


def test_fetch_csv_url_parses_generic_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
        return b"Date,Close\n2025-01-01,100\n2025-02-01,105\n"

    monkeypatch.setattr("gasoil_app.sources._read_url", fake_read_url)

    rows = fetch_csv_url("https://example.test/data.csv", date_col="Date", price_col="Close")

    assert [row["mops_usd_per_bbl"] for row in rows] == [100, 105]




def test_fetch_datahub_oil_prices_uses_public_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
        assert url == DATAHUB_OIL_PRICE_CSV_URLS["datahub_brent_daily"]
        return b"Date,Price\n2026-05-01,65.5\n"

    monkeypatch.setattr("gasoil_app.sources._read_url", fake_read_url)

    rows = fetch_datahub_oil_prices("datahub_brent_daily")

    assert rows == [{"date": date(2026, 5, 1), "mops_usd_per_bbl": 65.5}]


def test_parse_eia_history_html_converts_product_gallons_to_barrels() -> None:
    html = """
    <tr><td>2026 May- 4 to May- 8</td><td>4.091</td><td>4.114</td><td>3.843</td><td>3.926</td><td>3.927</td></tr>
    <tr><td>2026 May-11 to May-15</td><td>4.051</td><td>4.052</td></tr>
    """

    rows = parse_eia_history_html(html)

    assert rows[0] == {"date": date(2026, 5, 4), "mops_usd_per_bbl": pytest.approx(4.091 * 42)}
    assert rows[-1] == {"date": date(2026, 5, 12), "mops_usd_per_bbl": pytest.approx(4.052 * 42)}


def test_fetch_eia_history_uses_public_series(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
        assert EIA_HISTORY_SERIES["eia_ultra_low_sulfur_diesel_ny"] in url
        return b"2026 May- 4 to May- 8 4.091 4.114"

    monkeypatch.setattr("gasoil_app.sources._read_url", fake_read_url)

    rows = fetch_eia_history("eia_ultra_low_sulfur_diesel_ny")

    assert rows == [
        {"date": date(2026, 5, 4), "mops_usd_per_bbl": pytest.approx(4.091 * 42)},
        {"date": date(2026, 5, 5), "mops_usd_per_bbl": pytest.approx(4.114 * 42)},
    ]

def test_parse_orb_markets_extracts_heating_oil_proxy() -> None:
    html = "Benchmark Prices Heating Oil HO=F 4.02▲ 0.12 USD/gal Last updated"

    row = parse_orb_markets(html, benchmark="Heating Oil")

    assert row["source_symbol"] == "HO=F"
    assert row["mops_usd_per_bbl"] == pytest.approx(168.84)




def test_parse_orb_markets_extracts_card_layout() -> None:
    html = "Heating Oil\n\nHO=F · USD/gal\n\n3.96\n\n▼ 0.00"

    row = parse_orb_markets(html, benchmark="Heating Oil")

    assert row["source_symbol"] == "HO=F"
    assert row["mops_usd_per_bbl"] == pytest.approx(166.32)


def test_parse_orb_markets_extracts_physical_mops_layout() -> None:
    html = "Jet Fuel A-1 (Singapore MOPS)Singapore MOPS~1,351 EIA 11 May 2026 USD/MT"

    row = parse_orb_markets(html, benchmark="Jet Fuel A-1 (Singapore MOPS)")

    assert row["source_symbol"] == "ORB"
    assert row["source_unit"] == "usd_per_mt"
    assert row["mops_usd_per_bbl"] == pytest.approx(1351 / 7.46)

def test_proxy_config_embeds_separate_credentials() -> None:
    proxy = ProxyConfig(
        url="http://proxy.company.local:8080",
        username="DOMAIN\\user@example.com",
        password="p@ ss",
    )

    assert proxy.with_auth_url() == "http://DOMAIN%5Cuser%40example.com:p%40+ss@proxy.company.local:8080"


def test_fetch_yahoo_chart_forwards_proxy_config(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1735689600],
                    "indicators": {"quote": [{"close": [100.0]}]},
                }
            ],
            "error": None,
        }
    }
    proxy = ProxyConfig(url="http://proxy.local:8080", username="user", password="secret")

    def fake_read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
        assert proxy == proxy_config
        return json.dumps(payload).encode("utf-8")

    proxy_config = proxy
    monkeypatch.setattr("gasoil_app.sources._read_url", fake_read_url)

    rows = fetch_yahoo_chart("BZ=F", "usd_per_bbl", proxy=proxy_config)

    assert rows == [{"date": date(2025, 1, 1), "mops_usd_per_bbl": 100.0}]


def test_online_source_choices_include_public_links() -> None:
    assert "orb_markets" in ONLINE_SOURCE_CHOICES
    assert "datahub_brent_daily" in ONLINE_SOURCE_CHOICES
    assert "eia_ultra_low_sulfur_diesel_ny" in ONLINE_SOURCE_CHOICES
    assert "csv_url" in ONLINE_SOURCE_CHOICES
