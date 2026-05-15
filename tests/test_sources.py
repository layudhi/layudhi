import json
from datetime import date

import pytest

from gasoil_app.sources import (
    convert_to_usd_per_bbl,
    ProxyConfig,
    fetch_csv_url,
    fetch_yahoo_chart,
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


def test_parse_orb_markets_extracts_heating_oil_proxy() -> None:
    html = "Benchmark Prices Heating Oil HO=F 4.02▲ 0.12 USD/gal Last updated"

    row = parse_orb_markets(html, benchmark="Heating Oil")

    assert row["source_symbol"] == "HO=F"
    assert row["mops_usd_per_bbl"] == pytest.approx(168.84)


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
