# SOP Portal - Aplikasi Sosialisasi Dokumen Perusahaan

SOP Portal adalah aplikasi web berbasis **Python Django** dan **SQLite** untuk mengelola dokumen perusahaan, data karyawan, sosialisasi mandiri, dan event sosialisasi.

## Ringkasan

Aplikasi ini dibuat untuk kebutuhan sosialisasi SOP, materi kerja, instruksi kerja, kebijakan, dan dokumen internal perusahaan. Admin dapat mengupload dokumen dan menentukan masa berlaku dokumen. Karyawan hanya dapat memilih dokumen yang masih aktif untuk dibaca atau disosialisasikan.

## Fitur Utama

### 1. Manajemen Dokumen

Admin dapat mengelola dokumen perusahaan dengan informasi:

- judul dokumen;
- tema dokumen;
- deskripsi singkat;
- file dokumen;
- tanggal mulai berlaku;
- tanggal expired.

Aturan dokumen:

- dokumen aktif dapat dipilih untuk sosialisasi;
- dokumen expired tidak dapat dipilih lagi untuk sosialisasi mandiri;
- dokumen expired tidak muncul sebagai pilihan materi saat membuat event baru;
- dokumen expired tetap tersimpan sebagai arsip.

### 2. Manajemen User/Karyawan

Admin dapat mengupload data karyawan menggunakan file CSV.

Format CSV:

```csv
NAME,IDBadge,SECTION,DEPT
Budi Santoso,B12345,Line A,Produksi
Siti Aminah,B12346,Incoming,Quality
```

Data yang disimpan:

- `NAME` sebagai nama karyawan yang ditampilkan setelah login;
- `IDBadge` sebagai ID badge sekaligus satu-satunya input login user biasa;
- `SECTION` sebagai section;
- `DEPT` sebagai departemen.

Contoh login user biasa setelah upload CSV:

```text
ID Badge: B12345
Nama yang terbaca sistem: Budi Santoso
```

Jika ID Badge belum ada di data karyawan, aplikasi akan menampilkan popup bahwa user belum terdaftar dan diminta menghubungi Superadmin.

### 3. Sosialisasi Mandiri

Alur sosialisasi mandiri:

1. user login ke aplikasi;
2. user membuka menu **Mandiri**;
3. user memilih tema;
4. user memilih materi yang masih aktif;
5. aplikasi menampilkan materi;
6. user wajib scroll sampai bawah;
7. tombol selesai baru aktif setelah user scroll sampai bawah;
8. sistem mencatat bahwa user sudah membaca dan sudah tersosialisasi.

### 4. Sosialisasi Event

Admin dapat membuat event sosialisasi dengan data:

- judul event;
- divisi peserta;
- tempat pelaksanaan;
- waktu pelaksanaan;
- nama pembawa materi;
- daftar materi yang disosialisasikan;
- catatan tambahan.

Materi event hanya dapat dipilih dari dokumen yang masih aktif.

### 5. Monitoring Belum Sosialisasi

Admin/staff dapat membuka menu **Belum Sosialisasi** untuk:

- memilih laporan per SOP/materi;
- memilih laporan per event;
- melihat daftar user yang belum sosialisasi;
- menandai user sebagai `N/A` jika user tidak relevan dengan SOP/materi atau event tersebut;
- download daftar user yang belum sosialisasi, sudah sosialisasi, dan N/A dalam format Excel lengkap dengan metode Mandiri/Event, waktu sosialisasi format UTC+8, detail event, dan keterangan.

User yang ditandai `N/A` tetap tersimpan di database sebagai pengecualian dan tidak lagi muncul di daftar user yang belum sosialisasi untuk target tersebut.

### 6. Dashboard

Dashboard menampilkan:

- total dokumen;
- total dokumen aktif;
- total user/karyawan;
- total user yang sudah mengikuti sosialisasi;
- grafik ringkasan untuk laporan Manager;
- tingkat kepatuhan berdasarkan section;
- shortcut ke sosialisasi mandiri;
- shortcut ke daftar event;
- riwayat sosialisasi terbaru.

## Struktur Aplikasi

```text
manage.py
sop_portal/
  settings.py
  urls.py
  asgi.py
  wsgi.py
training/
  admin.py
  forms.py
  models.py
  urls.py
  views.py
  migrations/
templates/sop_portal/
static/sop_portal/
media/documents/
```

Keterangan singkat:

- `sop_portal/` berisi konfigurasi project Django;
- `training/` berisi fitur utama aplikasi SOP Portal;
- `templates/sop_portal/` berisi halaman HTML;
- `static/sop_portal/` berisi styling CSS;
- `media/documents/` digunakan untuk menyimpan file dokumen yang diupload.

## Instalasi

Buat virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Siapkan database:

```bash
python manage.py migrate
```

Buat user admin:

```bash
python manage.py createsuperuser
```

## Menjalankan Aplikasi

Jalankan server Django:

```bash
python manage.py runserver
```

Buka browser ke alamat:

```text
http://127.0.0.1:8000/
```

## Cara Pakai Singkat

### Untuk Admin

1. Login menggunakan akun admin/staff.
2. Buka menu **Upload Dokumen** untuk menambahkan SOP atau materi.
3. Buka menu **Upload User** untuk import data karyawan dari CSV.
4. Buka menu **Buat Event** jika ingin membuat jadwal sosialisasi event.
5. Buka menu **Belum Sosialisasi** untuk monitoring per SOP atau per event.
6. Download laporan Excel untuk daftar belum sosialisasi, sudah sosialisasi, atau N/A.
7. Gunakan tombol N/A jika user tidak relevan dengan SOP/materi atau event tersebut.
8. Gunakan Django Admin untuk pengelolaan data lanjutan.

### Untuk User/Karyawan

1. Login cukup menggunakan `IDBadge`; sistem otomatis lookup nama karyawan yang terdaftar.
2. Buka menu **Mandiri**.
3. Pilih tema dan materi.
4. Baca materi sampai bawah.
5. Klik tombol selesai setelah tombol aktif.


### Login Superadmin

Superadmin/admin/staff tetap login menggunakan username dan password Django melalui menu **Login Superadmin dengan Username & Password** atau URL:

```text
/superadmin/login/
```

Login ID Badge hanya berlaku untuk user/karyawan biasa.

## Hak Akses

| Role | Akses |
| --- | --- |
| Admin/staff | Upload dokumen, upload user, membuat event, melihat dashboard, mengelola data melalui Django Admin |
| User/karyawan | Melihat dokumen aktif, mengikuti sosialisasi mandiri, melihat daftar event |

## Pengujian

Jalankan test aplikasi:

```bash
python manage.py test training
```

## Catatan Produksi

Sebelum digunakan di lingkungan produksi:

- ubah `SECRET_KEY`;
- set `DEBUG = False`;
- batasi `ALLOWED_HOSTS`;
- siapkan konfigurasi static dan media file;
- siapkan backup database;
- pastikan akses file dokumen sesuai kebijakan keamanan perusahaan.

## Deployment Production Tanpa Akses Administrator

> Catatan penting: aplikasi Django tidak otomatis berjalan hanya dengan dicopy ke `inetpub` seperti HTML statis. Jika IIS kantor belum dikonfigurasi oleh administrator untuk reverse proxy/FastCGI, aplikasi tetap perlu dijalankan sebagai proses Python. Script berikut dibuat agar bisa dijalankan oleh user biasa selama server sudah memiliki Python dan akses network/port yang diizinkan kantor.

### Opsi Praktis: Copy Folder + Jalankan Waitress

1. Copy seluruh folder repository ke folder server, misalnya:

   ```text
   C:\inetpub\sop_portal
   ```

2. Buka Command Prompt dari folder tersebut.
3. Jalankan:

   ```bat
   scripts\run_production.bat
   ```

Script tersebut akan:

- membuat virtual environment `.venv` jika belum ada;
- install dependency dari `requirements.txt`;
- menjalankan migrasi database SQLite;
- menjalankan `collectstatic`;
- menjalankan aplikasi dengan Waitress pada port default `8000`.

Aplikasi kemudian dapat dibuka dari:

```text
http://nama-server:8000/
```

Jika ingin memakai port lain tanpa akses admin, set variable `PORT` sebelum menjalankan script:

```bat
set PORT=8080
scripts\run_production.bat
```

### Environment Variable Production

Variable yang bisa diset sebelum menjalankan script:

```bat
set DJANGO_SECRET_KEY=isi-secret-key-internal
set DJANGO_DEBUG=False
set DJANGO_ALLOWED_HOSTS=nama-server,ip-server,localhost
set SERVE_MEDIA_IN_PRODUCTION=True
set PORT=8000
```

### Jika Harus Lewat URL IIS Standar

Jika aplikasi harus dibuka lewat URL IIS standar seperti `http://nama-server/sop/` atau port 80/443, maka tetap diperlukan bantuan administrator IT untuk salah satu opsi berikut:

- membuat reverse proxy IIS ke port Waitress aplikasi;
- membuka firewall/port yang digunakan aplikasi;
- menjalankan aplikasi sebagai Windows Service;
- mengatur SSL certificate bila menggunakan HTTPS.

Tanpa konfigurasi tersebut, user biasa biasanya hanya bisa menjalankan aplikasi pada port yang diizinkan, misalnya `8000` atau `8080`.
