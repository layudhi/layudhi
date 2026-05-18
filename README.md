# Gasoil MOPS Singapore Checker & Forecast

Aplikasi Python siap pakai untuk:

- mengambil data harga online dari sumber publik/proxy ketika Anda belum memiliki data MOPS;
- membaca data **MOPS Singapura** jika Anda sudah punya CSV resmi/berlisensi;
- mengonversi harga `USD/barrel` menjadi estimasi `IDR/liter` dengan parameter kurs, alpha/premium, freight, distribusi, pajak, dan subsidi;
- membuat prediksi harga gasoil ke depan untuk 1 bulan, 2 bulan, 3 bulan, 12 bulan, atau horizon lain melalui CLI.

> Penting: MOPS resmi adalah assessment berlisensi dari Platts/S&P Global. Aplikasi ini tidak membobol paywall dan tidak scraping data berlisensi secara ilegal. Jika belum punya MOPS, gunakan sumber publik/proxy seperti Heating Oil futures, Brent futures, ICE Low Sulphur Gasoil futures bila tersedia, atau URL CSV publik lain. Hasil proxy bukan MOPS resmi dan harus divalidasi sebelum keputusan komersial.

## Sumber data yang didukung

### 1. Online publik/proxy

CLI dapat mengambil data online langsung:

- `yahoo_heating_oil`: Yahoo Finance Heating Oil Futures `HO=F`, dikonversi dari `USD/gal` ke `USD/bbl`. Ini proxy publik yang paling dekat dengan distillate/diesel, tetapi bukan MOPS Singapura.
- `yahoo_brent`: Yahoo Finance Brent Futures `BZ=F` dalam `USD/bbl`. Ini proxy crude oil global.
- `yahoo_low_sulphur_gasoil`: Yahoo Finance Low Sulphur Gasoil `LGO=F` bila simbol tersedia, dikonversi dari `USD/MT` ke `USD/bbl` dengan faktor 7.46 bbl/MT.
- `datahub_brent_daily` / `datahub_wti_daily`: CSV publik dari DataHub oil-prices (`https://datahub.io/core/oil-prices`) untuk Brent/WTI harian dalam `USD/bbl`.
- `datahub_brent_monthly` / `datahub_wti_monthly`: CSV publik dari DataHub oil-prices untuk Brent/WTI bulanan dalam `USD/bbl`.
- `eia_ultra_low_sulfur_diesel_ny`: halaman publik EIA DNav (`https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm`) untuk Ultra-Low-Sulfur No. 2 Diesel, New York Harbor, dikonversi dari `USD/gal` ke `USD/bbl`.
- `eia_ultra_low_sulfur_diesel_usgc`: EIA Ultra-Low-Sulfur No. 2 Diesel, U.S. Gulf Coast, dikonversi dari `USD/gal` ke `USD/bbl`.
- `eia_heating_oil_ny`: EIA No. 2 Heating Oil, New York Harbor, dikonversi dari `USD/gal` ke `USD/bbl`.
- `eia_jet_fuel_usgc`: EIA Kerosene-Type Jet Fuel, U.S. Gulf Coast, dikonversi dari `USD/gal` ke `USD/bbl`.
- `csv_url`: URL CSV publik milik Anda, misalnya dari vendor/data portal yang menyediakan kolom tanggal dan harga.
- `orb_markets`: scraper sederhana untuk halaman markets publik ORB sebagai benchmark indikatif satu titik data.

### 2. CSV MOPS resmi/berlisensi

Jika Anda sudah punya data MOPS, gunakan CSV lokal dengan kolom wajib:

```csv
date,mops_usd_per_bbl
2025-01-01,96.20
2025-02-01,94.75
```

- `date`: tanggal observasi; boleh harian, mingguan, atau bulanan.
- `mops_usd_per_bbl`: harga gasoil MOPS Singapura dalam USD/barrel.

Contoh data lokal tersedia di [`examples/mops_sample.csv`](examples/mops_sample.csv).

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Core CLI hanya memakai Python standard library. `streamlit` dan `pandas` diperlukan untuk aplikasi web.

## Menjalankan aplikasi web

Dari folder root repository, jalankan salah satu perintah berikut:

```bash
streamlit run gasoil_app/app.py
```

Atau, di Windows/PowerShell jika perintah `streamlit` belum masuk `PATH`:

```powershell
python -m streamlit run gasoil_app/app.py
```

`app.py` juga sudah dibuat aman dari error `attempted relative import with no known parent package` saat dijalankan langsung dari path file. Namun untuk pengalaman web yang benar, tetap disarankan menjalankannya melalui `streamlit run` atau `python -m streamlit run`.

Di sidebar, pilih:

1. **Ambil online** jika ingin otomatis mengambil proxy publik; atau
2. **Upload CSV** jika sudah punya data MOPS/vendor.

Aplikasi akan menampilkan data sumber, riwayat bulanan, estimasi harga IDR/liter, prediksi, grafik, dan tombol download forecast.


## Jaringan kantor dengan login proxy

Jika internet kantor membutuhkan proxy/login, ada dua cara yang didukung.

### Opsi A: lewat environment variable

Cara ini lebih aman karena password tidak muncul di argumen command history:

```bash
export HTTPS_PROXY="http://proxy.company.local:8080"
export HTTP_PROXY="http://proxy.company.local:8080"
export GASOIL_PROXY_USER="DOMAIN\username"
export GASOIL_PROXY_PASSWORD="password-proxy-anda"

python -m gasoil_app.cli --source yahoo_heating_oil --months 3
```

Jika proxy Anda menerima credential langsung di URL, format ini juga bisa dipakai:

```bash
export HTTPS_PROXY="http://DOMAIN%5Cusername:password@proxy.company.local:8080"
python -m gasoil_app.cli --source yahoo_heating_oil --months 3
```

### Opsi B: lewat argumen CLI

```bash
python -m gasoil_app.cli \
  --source yahoo_heating_oil \
  --proxy-url "http://proxy.company.local:8080" \
  --proxy-user "DOMAIN\username" \
  --proxy-password "password-proxy-anda" \
  --months 3
```

Untuk Streamlit, isi bagian **Proxy Kantor** di sidebar, atau jalankan Streamlit setelah environment variable di atas di-set.

Jika ingin memastikan aplikasi tidak memakai proxy environment, tambahkan `--no-proxy` pada CLI.

## Menjalankan dari CLI tanpa data MOPS

Contoh mengambil Heating Oil futures publik sebagai proxy diesel/gasoil:

```bash
python -m gasoil_app.cli \
  --source yahoo_heating_oil \
  --months 3 \
  --fx 16000 \
  --alpha 1.5 \
  --freight 2.0 \
  --distribution 500 \
  --tax 11 \
  --output outputs
```

Contoh Brent futures sebagai proxy crude:

```bash
python -m gasoil_app.cli --source yahoo_brent --months 12
```

Contoh Low Sulphur Gasoil futures jika simbol tersedia di Yahoo Finance:

```bash
python -m gasoil_app.cli --source yahoo_low_sulphur_gasoil --months 12
```

Contoh DataHub Brent/WTI public dataset:

```bash
python -m gasoil_app.cli --source datahub_brent_daily --months 3
python -m gasoil_app.cli --source datahub_wti_monthly --months 12
```

Contoh EIA DNav Spot Prices untuk produk diesel/jet fuel publik:

```bash
python -m gasoil_app.cli --source eia_ultra_low_sulfur_diesel_ny --months 3
python -m gasoil_app.cli --source eia_ultra_low_sulfur_diesel_usgc --months 3
python -m gasoil_app.cli --source eia_jet_fuel_usgc --months 3
```

Contoh URL CSV publik:

```bash
python -m gasoil_app.cli \
  --source csv_url \
  --url "https://contoh-domain/data.csv" \
  --date-col Date \
  --price-col Close \
  --unit usd_per_bbl \
  --months 3
```

## Menjalankan dari CLI dengan CSV lokal

```bash
python -m gasoil_app.cli \
  --csv examples/mops_sample.csv \
  --months 12 \
  --fx 16000 \
  --alpha 1.5 \
  --freight 2.0 \
  --distribution 500 \
  --tax 11 \
  --output outputs
```

Prediksi 1, 2, atau 3 bulan:

```bash
python -m gasoil_app.cli --source yahoo_heating_oil --months 1
python -m gasoil_app.cli --source yahoo_heating_oil --months 2
python -m gasoil_app.cli --source yahoo_heating_oil --months 3
```

Output:

- `outputs/source_data.csv`: data mentah/hasil fetch yang sudah dinormalisasi ke `USD/bbl`.
- `outputs/monthly_analysis.csv`: rata-rata bulanan dan estimasi IDR/liter.
- `outputs/forecast.csv`: prediksi, interval indikatif 90%, dan estimasi IDR/liter.

## Rumus estimasi harga

```text
base_usd_per_bbl = mops_usd_per_bbl + alpha_usd_per_bbl + freight_usd_per_bbl
base_idr_per_liter = base_usd_per_bbl * fx_idr_per_usd / 158.987294928
estimated_idr_per_liter = base_idr_per_liter * (1 + tax_percent/100)
                          + distribution_idr_per_liter
                          - subsidy_idr_per_liter
```

Sesuaikan parameter sesuai formula komersial/internal perusahaan Anda.

## Metode prediksi

Tersedia tiga metode sederhana:

- `damped_trend` (default): memproyeksikan tren terbaru dan tren jangka panjang secara konservatif.
- `linear`: regresi tren linear.
- `naive`: mengulang nilai rata-rata bulanan terakhir.

Prediksi ini bersifat indikatif, bukan rekomendasi jual-beli atau keputusan finansial. Untuk produksi, sebaiknya tambahkan variabel eksternal seperti kurs forward, crack spread, inventory, Brent/Dubai crude, freight market, kebijakan pajak/subsidi, dan skenario geopolitik.

## Pengujian

```bash
pytest
```
