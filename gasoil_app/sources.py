from __future__ import annotations

import csv
import html
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Iterable
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .core import DATE_COLUMN, MOPS_COLUMN, Row, parse_date

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
ORB_MARKETS_URL = "https://orb.group/in/markets"
DATAHUB_OIL_PRICES_URL = "https://datahub.io/core/oil-prices"
EIA_SPOT_PRICES_URL = "https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm"
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
    "datahub_brent_daily": PublicSource(
        key="datahub_brent_daily",
        label="DataHub Brent daily CSV",
        default_symbol=None,
        default_unit="usd_per_bbl",
        description="Brent spot daily dari DataHub oil-prices public dataset.",
    ),
    "datahub_wti_daily": PublicSource(
        key="datahub_wti_daily",
        label="DataHub WTI daily CSV",
        default_symbol=None,
        default_unit="usd_per_bbl",
        description="WTI spot daily dari DataHub oil-prices public dataset.",
    ),
    "datahub_brent_monthly": PublicSource(
        key="datahub_brent_monthly",
        label="DataHub Brent monthly CSV",
        default_symbol=None,
        default_unit="usd_per_bbl",
        description="Brent spot monthly dari DataHub oil-prices public dataset.",
    ),
    "datahub_wti_monthly": PublicSource(
        key="datahub_wti_monthly",
        label="DataHub WTI monthly CSV",
        default_symbol=None,
        default_unit="usd_per_bbl",
        description="WTI spot monthly dari DataHub oil-prices public dataset.",
    ),
    "eia_ultra_low_sulfur_diesel_ny": PublicSource(
        key="eia_ultra_low_sulfur_diesel_ny",
        label="EIA ULSD New York Harbor spot",
        default_symbol="EER_EPD2DXL0_PF4_Y35NY_DPG",
        default_unit="usd_per_gal",
        description="EIA DNav spot page: Ultra-Low-Sulfur No. 2 Diesel, New York Harbor.",
    ),
    "eia_ultra_low_sulfur_diesel_usgc": PublicSource(
        key="eia_ultra_low_sulfur_diesel_usgc",
        label="EIA ULSD U.S. Gulf Coast spot",
        default_symbol="EER_EPD2DXL0_PF4_RGC_DPG",
        default_unit="usd_per_gal",
        description="EIA DNav spot page: Ultra-Low-Sulfur No. 2 Diesel, U.S. Gulf Coast.",
    ),
    "eia_heating_oil_ny": PublicSource(
        key="eia_heating_oil_ny",
        label="EIA Heating Oil New York Harbor spot",
        default_symbol="EER_EPD2F_PF4_Y35NY_DPG",
        default_unit="usd_per_gal",
        description="EIA DNav spot page: No. 2 Heating Oil, New York Harbor.",
    ),
    "eia_jet_fuel_usgc": PublicSource(
        key="eia_jet_fuel_usgc",
        label="EIA Jet Fuel U.S. Gulf Coast spot",
        default_symbol="EER_EPJK_PF4_RGC_DPG",
        default_unit="usd_per_gal",
        description="EIA DNav spot page: Kerosene-Type Jet Fuel, U.S. Gulf Coast.",
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


DATAHUB_OIL_PRICE_CSV_URLS = {
    "datahub_brent_daily": "https://datahub.io/core/oil-prices/_r/-/data/brent-daily.csv",
    "datahub_wti_daily": "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv",
    "datahub_brent_monthly": "https://datahub.io/core/oil-prices/_r/-/data/brent-monthly.csv",
    "datahub_wti_monthly": "https://datahub.io/core/oil-prices/_r/-/data/wti-monthly.csv",
}

EIA_HISTORY_SERIES = {
    "eia_ultra_low_sulfur_diesel_ny": "EER_EPD2DXL0_PF4_Y35NY_DPG",
    "eia_ultra_low_sulfur_diesel_usgc": "EER_EPD2DXL0_PF4_RGC_DPG",
    "eia_heating_oil_ny": "EER_EPD2F_PF4_Y35NY_DPG",
    "eia_jet_fuel_usgc": "EER_EPJK_PF4_RGC_DPG",
}

MONTH_ABBR = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def fetch_datahub_oil_prices(source: str, timeout: int = 30, proxy: ProxyConfig | None = None) -> list[Row]:
    """Fetch Brent/WTI public CSVs from DataHub's core oil-prices dataset."""

    if source not in DATAHUB_OIL_PRICE_CSV_URLS:
        raise ValueError(f"DataHub source tidak dikenal: {source}")
    return fetch_csv_url(
        DATAHUB_OIL_PRICE_CSV_URLS[source],
        date_col="Date",
        price_col="Price",
        quote_unit="usd_per_bbl",
        timeout=timeout,
        proxy=proxy,
    )


def eia_history_url(series_id: str) -> str:
    return f"https://www.eia.gov/dnav/pet/hist/{series_id}D.htm"


def parse_eia_history_html(html_text: str, quote_unit: str = "usd_per_gal") -> list[Row]:
    """Parse an EIA DNav daily history page into normalized rows."""

    text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
    text = re.sub(r"\s+", " ", text)
    row_pattern = re.compile(
        r"(?P<year>\d{4})\s+"
        r"(?P<start_month>[A-Z][a-z]{2})-\s*(?P<start_day>\d{1,2})\s+to\s+"
        r"(?P<end_month>[A-Z][a-z]{2})-\s*(?P<end_day>\d{1,2})\s+"
        r"(?P<values>(?:[0-9]+(?:\.[0-9]+)?\s*){1,5})"
    )
    rows_by_date: dict[date, float] = {}
    for match in row_pattern.finditer(text):
        year = int(match.group("year"))
        start_month = MONTH_ABBR[match.group("start_month")]
        start_day = int(match.group("start_day"))
        current = date(year, start_month, start_day)
        for raw_value in match.group("values").split():
            rows_by_date[current] = convert_to_usd_per_bbl(float(raw_value), quote_unit)
            current += timedelta(days=1)
            while current.weekday() >= 5:
                current += timedelta(days=1)

    if not rows_by_date:
        raise ValueError("Halaman EIA tidak menghasilkan data harga harian yang bisa diparse")
    return [{DATE_COLUMN: row_date, MOPS_COLUMN: rows_by_date[row_date]} for row_date in sorted(rows_by_date)]


def fetch_eia_history(
    source: str, timeout: int = 30, proxy: ProxyConfig | None = None, quote_unit: str = "usd_per_gal"
) -> list[Row]:
    """Fetch a public EIA DNav spot-price history page and normalize to USD/bbl."""

    series_id = EIA_HISTORY_SERIES.get(source, source)
    html_text = _read_url(eia_history_url(series_id), timeout=timeout, proxy=proxy).decode("utf-8", errors="replace")
    return parse_eia_history_html(html_text, quote_unit=quote_unit)


ORB_SYMBOL_ALIASES = {
    "WTI Crude Oil": "CL=F",
    "Brent Crude Oil": "BZ=F",
    "Natural Gas": "NG=F",
    "Heating Oil": "HO=F",
    "Gasoline (RBOB)": "RB=F",
}


def _normalize_orb_unit(unit: str | None, symbol: str | None = None) -> str:
    normalized = (unit or "").strip().lower()
    if normalized in {"usd/gal", "usd_per_gal"}:
        return "usd_per_gal"
    if normalized in {"usd/mt", "usd_per_mt"}:
        return "usd_per_mt"
    if normalized in {"usd/bbl", "usd_per_bbl"}:
        return "usd_per_bbl"
    return "usd_per_gal" if symbol == "HO=F" or symbol == "RB=F" else "usd_per_bbl"


def _parse_float_text(value: str) -> float:
    return float(value.replace("~", "").replace(",", "").strip())


def _orb_error(benchmark: str) -> ValueError:
    choices = ", ".join([*ORB_SYMBOL_ALIASES.keys(), "Jet Fuel A-1 (Singapore MOPS)", "EN590 Diesel 10ppm (Rotterdam CIF)"])
    return ValueError(
        f"Benchmark '{benchmark}' tidak ditemukan di halaman ORB. "
        f"Coba salah satu benchmark: {choices}."
    )


def parse_orb_markets(html: str, benchmark: str = "Heating Oil") -> Row:
    """Parse one benchmark quote from ORB's public markets HTML page.

    ORB's public page has changed layout several times. This parser handles both
    the compact table form (``Heating Oil HO=F 3.96 ... USD/gal``) and the card
    form (``HO=F · USD/gal ... 3.96``), plus physical indicative rows such as
    ``Jet Fuel A-1 (Singapore MOPS) ... ~1,351 ... USD/MT``.
    """

    compact = re.sub(r"\s+", " ", html)
    escaped_benchmark = re.escape(benchmark)
    symbol = ORB_SYMBOL_ALIASES.get(benchmark)

    if symbol:
        escaped_symbol = re.escape(symbol)
        patterns = [
            rf"{escaped_benchmark}\s+{escaped_symbol}\s+~?([0-9][0-9,.]*)[^A-Z]*(USD/[A-Za-z0-9³]+)?",
            rf"{escaped_symbol}\s*[·-]\s*(USD/[A-Za-z0-9³]+)\s+~?([0-9][0-9,.]*)",
            rf"{escaped_symbol}\s+~?([0-9][0-9,.]*)",
        ]
        for idx, pattern in enumerate(patterns):
            match = re.search(pattern, compact)
            if not match:
                continue
            if idx == 1:
                unit = _normalize_orb_unit(match.group(1), symbol)
                value = _parse_float_text(match.group(2))
            else:
                value = _parse_float_text(match.group(1))
                unit_match = re.search(rf"{escaped_symbol}.*?(USD/[A-Za-z0-9³]+)", compact)
                unit = _normalize_orb_unit(unit_match.group(1) if unit_match else None, symbol)
            return {
                DATE_COLUMN: date.today(),
                MOPS_COLUMN: convert_to_usd_per_bbl(value, unit),
                "source_symbol": symbol,
                "source_unit": unit,
                "source_benchmark": benchmark,
            }

    physical_pattern = rf"{escaped_benchmark}.*?~?([0-9][0-9,.]*)[^U]*(USD/[A-Za-z0-9³]+)"
    physical_match = re.search(physical_pattern, compact)
    if physical_match:
        value = _parse_float_text(physical_match.group(1))
        unit = _normalize_orb_unit(physical_match.group(2))
        return {
            DATE_COLUMN: date.today(),
            MOPS_COLUMN: convert_to_usd_per_bbl(value, unit),
            "source_symbol": "ORB",
            "source_unit": unit,
            "source_benchmark": benchmark,
        }

    raise _orb_error(benchmark)


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

    if source in DATAHUB_OIL_PRICE_CSV_URLS:
        return fetch_datahub_oil_prices(source, proxy=proxy)

    if source in EIA_HISTORY_SERIES:
        preset = PUBLIC_SOURCES[source]
        return fetch_eia_history(source, proxy=proxy, quote_unit=quote_unit or preset.default_unit)

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
    lines.append(f"- DataHub oil-prices: {DATAHUB_OIL_PRICES_URL}")
    lines.append(f"- EIA spot prices DNav: {EIA_SPOT_PRICES_URL}")
    lines.append("- csv_url: ambil CSV publik dengan parameter --url, --date-col, --price-col, --unit")
    return lines
