from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .core import DATE_COLUMN, MOPS_COLUMN, Row, parse_date

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
ORB_MARKETS_URL = "https://orb.group/in/markets"
GALLONS_PER_BBL = 42.0
LS_GASOIL_MT_PER_BBL = 7.46


@dataclass(frozen=True)
class ProxyConfig:
    """Optional proxy settings for office networks that require login."""

    url: str | None = None
    username: str | None = None
    password: str | None = None
    disabled: bool = False

    def with_auth_url(self) -> str | None:
        """Return proxy URL with credentials embedded when supplied separately."""

        if not self.url:
            return None

        parsed = urlsplit(self.url)
        if parsed.username or not self.username:
            return self.url

        host = parsed.hostname or parsed.netloc
        if parsed.port:
            host = f"{host}:{parsed.port}"
        username = quote_plus(self.username)
        password = quote_plus(self.password or "")
        netloc = f"{username}:{password}@{host}"
        return urlunsplit((parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment))


def _open_request(request: Request, timeout: int, proxy: ProxyConfig | None = None) -> bytes:
    if proxy and proxy.disabled:
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return response.read()

    proxy_url = proxy.with_auth_url() if proxy else None
    if proxy_url:
        opener = build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}))
        with opener.open(request, timeout=timeout) as response:
            return response.read()

    with urlopen(request, timeout=timeout) as response:
        return response.read()


@dataclass(frozen=True)
class PublicSource:
    key: str
    label: str
    default_symbol: str | None
    default_unit: str
    description: str


PUBLIC_SOURCES: dict[str, PublicSource] = {
    "yahoo_heating_oil": PublicSource(
        key="yahoo_heating_oil",
        label="Yahoo Finance Heating Oil Futures (HO=F)",
        default_symbol="HO=F",
        default_unit="usd_per_gal",
        description="Proxy publik untuk diesel/gasoil; dikonversi dari USD/gal ke USD/bbl.",
    ),
    "yahoo_brent": PublicSource(
        key="yahoo_brent",
        label="Yahoo Finance Brent Futures (BZ=F)",
        default_symbol="BZ=F",
        default_unit="usd_per_bbl",
        description="Proxy crude oil global; bukan MOPS gasoil, tetapi berguna bila data produk tidak tersedia.",
    ),
    "yahoo_low_sulphur_gasoil": PublicSource(
        key="yahoo_low_sulphur_gasoil",
        label="Yahoo Finance Low Sulphur Gasoil Futures (LGO=F)",
        default_symbol="LGO=F",
        default_unit="usd_per_mt",
        description="Proxy ICE low sulphur gasoil bila simbol tersedia; dikonversi dari USD/MT ke USD/bbl.",
    ),
    "orb_markets": PublicSource(
        key="orb_markets",
        label="ORB public markets page",
        default_symbol=None,
        default_unit="usd_per_gal",
        description="Scrape nilai indikatif halaman publik ORB untuk benchmark seperti Heating Oil.",
    ),
}


ONLINE_SOURCE_CHOICES = [*PUBLIC_SOURCES.keys(), "csv_url"]


def convert_to_usd_per_bbl(value: float, unit: str) -> float:
    """Convert a public market quote into USD/barrel equivalent."""

    normalized = unit.strip().lower()
    if normalized in {"usd_per_bbl", "usd/bbl", "bbl"}:
        return value
    if normalized in {"usd_per_gal", "usd/gal", "gal"}:
        return value * GALLONS_PER_BBL
    if normalized in {"usd_per_mt", "usd/mt", "mt"}:
        return value / LS_GASOIL_MT_PER_BBL
    raise ValueError("unit harus salah satu dari: usd_per_bbl, usd_per_gal, usd_per_mt")


def _read_url(url: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; gasoil-mops-checker/0.2; +https://github.com/layudhi)",
            "Accept": "text/csv,application/json,text/html;q=0.9,*/*;q=0.8",
        },
    )
    return _open_request(request, timeout=timeout, proxy=proxy)


def fetch_yahoo_chart(
    symbol: str,
    quote_unit: str,
    range_: str = "2y",
    interval: str = "1d",
    timeout: int = 30,
    proxy: ProxyConfig | None = None,
) -> list[Row]:
    """Fetch historical public futures data from Yahoo Finance chart endpoint."""

    url = YAHOO_CHART_URL.format(symbol=quote(symbol, safe=""), range_=range_, interval=interval)
    payload = json.loads(_read_url(url, timeout=timeout, proxy=proxy).decode("utf-8"))
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise ValueError(f"Yahoo Finance tidak mengembalikan data untuk {symbol}: {error}")

    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote_data.get("close") or []
    if not timestamps or not closes:
        raise ValueError(f"Yahoo Finance tidak memiliki harga penutupan untuk {symbol}")

    rows_by_date: dict[date, float] = {}
    for timestamp, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        row_date = datetime.fromtimestamp(int(timestamp), tz=UTC).date()
        rows_by_date[row_date] = convert_to_usd_per_bbl(float(close), quote_unit)

    if not rows_by_date:
        raise ValueError(f"Tidak ada data harga valid untuk {symbol}")
    return [{DATE_COLUMN: row_date, MOPS_COLUMN: rows_by_date[row_date]} for row_date in sorted(rows_by_date)]


def fetch_csv_url(
    url: str,
    date_col: str = "date",
    price_col: str = "close",
    quote_unit: str = "usd_per_bbl",
    timeout: int = 30,
    proxy: ProxyConfig | None = None,
) -> list[Row]:
    """Fetch a generic public CSV URL and normalize it into app rows."""

    content = _read_url(url, timeout=timeout, proxy=proxy).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])
    missing = {date_col, price_col}.difference(fieldnames)
    if missing:
        raise ValueError(f"Kolom CSV URL tidak ditemukan: {', '.join(sorted(missing))}")

    rows_by_date: dict[date, float] = {}
    for raw in reader:
        if not raw.get(date_col) or not raw.get(price_col):
            continue
        value = float(str(raw[price_col]).replace(",", ""))
        rows_by_date[parse_date(raw[date_col])] = convert_to_usd_per_bbl(value, quote_unit)

    if not rows_by_date:
        raise ValueError("CSV URL tidak menghasilkan data harga valid")
    return [{DATE_COLUMN: row_date, MOPS_COLUMN: rows_by_date[row_date]} for row_date in sorted(rows_by_date)]


def parse_orb_markets(html: str, benchmark: str = "Heating Oil") -> Row:
    """Parse one benchmark quote from ORB's public markets HTML page."""

    escaped = re.escape(benchmark)
    pattern = rf"{escaped}\s+([A-Z0-9=^.-]+)\s+([0-9][0-9,.]*)[▲▼+-]?"
    match = re.search(pattern, html)
    if not match:
        compact = re.sub(r"\s+", " ", html)
        match = re.search(pattern, compact)
    if not match:
        raise ValueError(f"Benchmark '{benchmark}' tidak ditemukan di halaman ORB")

    symbol = match.group(1)
    value = float(match.group(2).replace(",", ""))
    unit = "usd_per_gal" if symbol == "HO=F" else "usd_per_bbl"
    return {
        DATE_COLUMN: date.today(),
        MOPS_COLUMN: convert_to_usd_per_bbl(value, unit),
        "source_symbol": symbol,
        "source_unit": unit,
        "source_benchmark": benchmark,
    }


def fetch_orb_markets(
    benchmark: str = "Heating Oil", timeout: int = 30, proxy: ProxyConfig | None = None
) -> list[Row]:
    html = _read_url(ORB_MARKETS_URL, timeout=timeout, proxy=proxy).decode("utf-8", errors="replace")
    return [parse_orb_markets(html, benchmark=benchmark)]


def fetch_public_source(
    source: str,
    symbol: str | None = None,
    quote_unit: str | None = None,
    range_: str = "2y",
    interval: str = "1d",
    url: str | None = None,
    date_col: str = "date",
    price_col: str = "close",
    orb_benchmark: str = "Heating Oil",
    proxy: ProxyConfig | None = None,
) -> list[Row]:
    """Fetch data from a configured public source or a generic CSV URL."""

    if source == "csv_url":
        if not url:
            raise ValueError("--url wajib diisi untuk source csv_url")
        return fetch_csv_url(
            url, date_col=date_col, price_col=price_col, quote_unit=quote_unit or "usd_per_bbl", proxy=proxy
        )

    if source == "orb_markets":
        return fetch_orb_markets(benchmark=orb_benchmark, proxy=proxy)

    if source not in PUBLIC_SOURCES:
        valid = ", ".join(ONLINE_SOURCE_CHOICES)
        raise ValueError(f"source tidak dikenal. Pilihan: {valid}")

    preset = PUBLIC_SOURCES[source]
    return fetch_yahoo_chart(
        symbol=symbol or preset.default_symbol or "HO=F",
        quote_unit=quote_unit or preset.default_unit,
        range_=range_,
        interval=interval,
        proxy=proxy,
    )


def source_help_lines() -> list[str]:
    lines = []
    for source in PUBLIC_SOURCES.values():
        symbol = f" default symbol {source.default_symbol};" if source.default_symbol else ""
        lines.append(f"- {source.key}: {source.label};{symbol} {source.description}")
    lines.append("- csv_url: ambil CSV publik dengan parameter --url, --date-col, --price-col, --unit")
    return lines
