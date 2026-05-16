from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gasoil_app.core import PriceFormula, build_analysis, load_mops_csv, write_csv
from gasoil_app.sources import ONLINE_SOURCE_CHOICES, ProxyConfig, fetch_public_source, source_help_lines


def build_parser() -> argparse.ArgumentParser:
    source_help = "\n".join(source_help_lines())
    parser = argparse.ArgumentParser(
        description="Cek harga gasoil berbasis MOPS/proxy publik dan buat prediksi bulanan.",
        epilog=f"Sumber online publik:\n{source_help}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--csv", help="Path CSV lokal berisi kolom date,mops_usd_per_bbl")
    input_group.add_argument(
        "--source",
        choices=ONLINE_SOURCE_CHOICES,
        help="Ambil data online dari sumber publik/proxy",
    )
    parser.add_argument("--symbol", help="Override simbol Yahoo Finance, contoh HO=F atau BZ=F")
    parser.add_argument(
        "--unit",
        choices=["usd_per_bbl", "usd_per_gal", "usd_per_mt"],
        help="Unit quote sumber sebelum dikonversi ke USD/bbl",
    )
    parser.add_argument("--range", default="2y", help="Range Yahoo Finance, contoh 6mo, 1y, 2y, 5y")
    parser.add_argument("--interval", default="1d", help="Interval Yahoo Finance, contoh 1d, 1wk, 1mo")
    parser.add_argument("--url", help="URL CSV publik untuk --source csv_url")
    parser.add_argument("--date-col", default="date", help="Nama kolom tanggal untuk --source csv_url")
    parser.add_argument("--price-col", default="close", help="Nama kolom harga untuk --source csv_url")
    parser.add_argument("--orb-benchmark", default="Heating Oil", help="Benchmark ORB yang akan di-scrape")
    parser.add_argument(
        "--proxy-url",
        default=os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),
        help="URL proxy kantor, contoh http://proxy.company:8080. Default membaca HTTPS_PROXY/HTTP_PROXY.",
    )
    parser.add_argument(
        "--proxy-user",
        default=os.getenv("GASOIL_PROXY_USER"),
        help="Username proxy jika proxy memerlukan login. Bisa juga pakai env GASOIL_PROXY_USER.",
    )
    parser.add_argument(
        "--proxy-password",
        default=os.getenv("GASOIL_PROXY_PASSWORD"),
        help="Password proxy. Disarankan pakai env GASOIL_PROXY_PASSWORD agar tidak tersimpan di shell history.",
    )
    parser.add_argument("--no-proxy", action="store_true", help="Abaikan proxy dan koneksi langsung")
    parser.add_argument("--months", type=int, default=12, help="Horizon prediksi: 1-60 bulan")
    parser.add_argument(
        "--method",
        choices=["damped_trend", "linear", "naive"],
        default="damped_trend",
        help="Metode prediksi sederhana",
    )
    parser.add_argument("--fx", type=float, default=16_000, help="Kurs IDR per USD")
    parser.add_argument("--alpha", type=float, default=0, help="Alpha/premium USD per barrel")
    parser.add_argument("--freight", type=float, default=0, help="Freight USD per barrel")
    parser.add_argument("--distribution", type=float, default=0, help="Biaya distribusi IDR per liter")
    parser.add_argument("--tax", type=float, default=0, help="Pajak dalam persen")
    parser.add_argument("--subsidy", type=float, default=0, help="Subsidi IDR per liter")
    parser.add_argument("--output", default="outputs", help="Folder output CSV hasil analisis")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.csv:
        rows = load_mops_csv(args.csv)
        source_label = args.csv
    else:
        proxy = ProxyConfig(
            url=args.proxy_url,
            username=args.proxy_user,
            password=args.proxy_password,
            disabled=args.no_proxy,
        )
        try:
            rows = fetch_public_source(
                args.source,
                symbol=args.symbol,
                quote_unit=args.unit,
                range_=args.range,
                interval=args.interval,
                url=args.url,
                date_col=args.date_col,
                price_col=args.price_col,
                orb_benchmark=args.orb_benchmark,
                proxy=proxy,
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            raise SystemExit(
                "Gagal mengambil data online. Cek koneksi internet, login proxy kantor "
                "(--proxy-url/--proxy-user/--proxy-password atau HTTPS_PROXY), atau gunakan --csv. "
                f"Detail: {exc}"
            ) from exc
        source_label = args.source
    formula = PriceFormula(
        fx_idr_per_usd=args.fx,
        alpha_usd_per_bbl=args.alpha,
        freight_usd_per_bbl=args.freight,
        distribution_idr_per_liter=args.distribution,
        tax_percent=args.tax,
        subsidy_idr_per_liter=args.subsidy,
    )
    monthly, forecast = build_analysis(rows, formula, args.months, args.method)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "source_data.csv"
    monthly_path = output_dir / "monthly_analysis.csv"
    forecast_path = output_dir / "forecast.csv"
    write_csv(raw_path, rows)
    write_csv(monthly_path, monthly)
    write_csv(forecast_path, forecast)

    latest = monthly[-1]
    next_month = forecast[0]
    print("Ringkasan Gasoil MOPS / Proxy Publik")
    print(f"Sumber data: {source_label}")
    print(f"Data historis sampai: {latest['date']}")
    print(f"Harga rata-rata terakhir: {latest['mops_usd_per_bbl']:.2f} USD/bbl")
    print(f"Estimasi harga terakhir: {latest['estimated_idr_per_liter']:,.2f} IDR/liter")
    print(f"Prediksi bulan depan: {next_month['forecast_mops_usd_per_bbl']:.2f} USD/bbl")
    print(f"Estimasi bulan depan: {next_month['estimated_idr_per_liter']:,.2f} IDR/liter")
    print(f"File tersimpan: {raw_path}, {monthly_path}, dan {forecast_path}")


if __name__ == "__main__":
    main()
