from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from .core import PriceFormula, build_analysis, load_mops_csv
from .sources import PUBLIC_SOURCES, ProxyConfig, fetch_public_source

st.set_page_config(page_title="Gasoil MOPS Singapore", layout="wide")
st.title("Pengecekan & Prediksi Harga Gasoil Berbasis MOPS/Proxy Publik")
st.caption(
    "MOPS resmi adalah data berlisensi. Jika Anda belum punya data MOPS, gunakan sumber publik/proxy seperti Heating Oil/Brent, atau masukkan URL CSV publik."
)

with st.sidebar:
    st.header("Sumber Data")
    input_mode = st.radio("Mode", ["Ambil online", "Upload CSV"], index=0)
    source = st.selectbox(
        "Sumber online",
        ["yahoo_heating_oil", "yahoo_brent", "yahoo_low_sulphur_gasoil", "csv_url"],
        disabled=input_mode != "Ambil online",
    )
    symbol = st.text_input(
        "Override simbol Yahoo (opsional)",
        value=PUBLIC_SOURCES.get(source).default_symbol if source in PUBLIC_SOURCES and PUBLIC_SOURCES[source].default_symbol else "",
        disabled=input_mode != "Ambil online" or source == "csv_url",
    )
    csv_url = st.text_input("URL CSV publik", disabled=input_mode != "Ambil online" or source != "csv_url")
    unit = st.selectbox("Unit sumber", ["usd_per_bbl", "usd_per_gal", "usd_per_mt"], index=1)
    yahoo_range = st.selectbox("Range data online", ["6mo", "1y", "2y", "5y"], index=2)

    st.header("Proxy Kantor")
    use_proxy = st.checkbox("Gunakan proxy/login kantor", value=bool(os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")))
    proxy_url = st.text_input(
        "Proxy URL",
        value=os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or "",
        placeholder="http://proxy.company:8080",
        disabled=input_mode != "Ambil online" or not use_proxy,
    )
    proxy_user = st.text_input(
        "Username proxy",
        value=os.getenv("GASOIL_PROXY_USER") or "",
        disabled=input_mode != "Ambil online" or not use_proxy,
    )
    proxy_password = st.text_input(
        "Password proxy",
        value=os.getenv("GASOIL_PROXY_PASSWORD") or "",
        type="password",
        disabled=input_mode != "Ambil online" or not use_proxy,
    )

    st.header("Parameter Harga")
    months = st.selectbox("Horizon prediksi", [1, 2, 3, 12], index=3)
    method = st.selectbox("Metode", ["damped_trend", "linear", "naive"], index=0)
    fx = st.number_input("Kurs IDR/USD", min_value=1.0, value=16_000.0, step=100.0)
    alpha = st.number_input("Alpha/premium (USD/bbl)", value=0.0, step=0.5)
    freight = st.number_input("Freight (USD/bbl)", value=0.0, step=0.5)
    distribution = st.number_input("Distribusi (IDR/liter)", value=0.0, step=50.0)
    tax = st.number_input("Pajak (%)", min_value=0.0, value=0.0, step=0.5)
    subsidy = st.number_input("Subsidi (IDR/liter)", min_value=0.0, value=0.0, step=50.0)

uploaded = None
if input_mode == "Upload CSV":
    uploaded = st.file_uploader("Upload CSV MOPS", type=["csv"])
    if uploaded is None:
        st.info("Upload CSV dengan kolom wajib: `date` dan `mops_usd_per_bbl`.")
        st.code("date,mops_usd_per_bbl\n2025-01-01,95.1\n2025-02-01,97.3", language="csv")
        st.stop()

try:
    if input_mode == "Upload CSV":
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as temp_file:
            temp_file.write(uploaded.getvalue())
            temp_path = temp_file.name
        rows = load_mops_csv(temp_path)
        source_label = "Upload CSV"
    else:
        if source == "csv_url" and not csv_url:
            st.info("Masukkan URL CSV publik, atau pilih sumber Yahoo Finance.")
            st.stop()
        selected_unit = unit
        if source in PUBLIC_SOURCES:
            selected_unit = PUBLIC_SOURCES[source].default_unit
        proxy = ProxyConfig(
            url=proxy_url or None,
            username=proxy_user or None,
            password=proxy_password or None,
        ) if use_proxy else None
        rows = fetch_public_source(
            source,
            symbol=symbol or None,
            quote_unit=selected_unit,
            range_=yahoo_range,
            url=csv_url or None,
            proxy=proxy,
        )
        source_label = source

    formula = PriceFormula(
        fx_idr_per_usd=fx,
        alpha_usd_per_bbl=alpha,
        freight_usd_per_bbl=freight,
        distribution_idr_per_liter=distribution,
        tax_percent=tax,
        subsidy_idr_per_liter=subsidy,
    )
    monthly_rows, forecast_rows = build_analysis(rows, formula, int(months), method)
    source_df = pd.DataFrame(rows)
    monthly = pd.DataFrame(monthly_rows)
    forecast = pd.DataFrame(forecast_rows)
except Exception as exc:  # Streamlit boundary: show user-friendly validation errors.
    st.error(f"Gagal memproses data: {exc}")
    st.info("Jika jaringan kantor memakai login proxy, isi bagian Proxy Kantor atau set HTTPS_PROXY/GASOIL_PROXY_USER/GASOIL_PROXY_PASSWORD sebelum menjalankan Streamlit.")
    st.stop()

st.warning(
    "Jika sumbernya proxy publik, hasil bukan MOPS resmi. Gunakan hanya sebagai indikasi awal dan validasi dengan data berlisensi untuk keputusan komersial."
)
st.write(f"Sumber data: `{source_label}`")

col1, col2, col3 = st.columns(3)
col1.metric("Harga terakhir", f"{monthly.iloc[-1]['mops_usd_per_bbl']:.2f} USD/bbl")
col2.metric("Estimasi harga terakhir", f"{monthly.iloc[-1]['estimated_idr_per_liter']:,.0f} IDR/l")
col3.metric("Prediksi akhir horizon", f"{forecast.iloc[-1]['estimated_idr_per_liter']:,.0f} IDR/l")

st.subheader("Data Sumber")
st.dataframe(source_df.tail(30), use_container_width=True)

st.subheader("Riwayat Bulanan")
st.dataframe(monthly, use_container_width=True)
st.line_chart(monthly.set_index("date")[["mops_usd_per_bbl", "estimated_idr_per_liter"]])

st.subheader("Prediksi")
st.dataframe(forecast, use_container_width=True)
st.line_chart(forecast.set_index("date")[["forecast_mops_usd_per_bbl", "low_90", "high_90"]])

st.download_button(
    "Download forecast.csv",
    forecast.to_csv(index=False),
    file_name="forecast.csv",
    mime="text/csv",
)
