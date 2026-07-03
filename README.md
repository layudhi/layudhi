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

- `NAME` sebagai nama karyawan sekaligus username login user biasa;
- `IDBadge` sebagai ID badge sekaligus password awal user biasa;
- `SECTION` sebagai section;
- `DEPT` sebagai departemen.

Contoh login user biasa setelah upload CSV:

```text
Username: Budi Santoso
Password: B12345
```

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

### 5. Dashboard

Dashboard menampilkan:

- total dokumen;
- total dokumen aktif;
- total user/karyawan;
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
5. Gunakan Django Admin untuk pengelolaan data lanjutan.

### Untuk User/Karyawan

1. Login menggunakan `NAME` sebagai username dan `IDBadge` sebagai password awal.
2. Buka menu **Mandiri**.
3. Pilih tema dan materi.
4. Baca materi sampai bawah.
5. Klik tombol selesai setelah tombol aktif.

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
