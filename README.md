# Saham Monitor

Bot monitoring saham IDX yang berjalan otomatis via GitHub Actions. Bot mengambil harga dari Yahoo Finance, membandingkan dengan threshold yang Anda tetapkan di Google Sheets, dan mengirim notifikasi ke Telegram ketika kondisi terpenuhi.

## Cara Kerja

1. **Baca watchlist** dari Google Sheets
2. **Ambil harga** dari Yahoo Finance (via `yfinance`)
3. **Bandingkan** harga dengan threshold berbasis persentase
4. **Kirim notifikasi** ke Telegram jika ada rule yang terpicu

Bot **tidak mengeksekusi order**. Eksekusi jual/beli tetap dilakukan manual di aplikasi sekuritas Anda.

## Jadwal Berjalan

Bot berjalan otomatis 2× sehari via GitHub Actions:

| Waktu WIB | Waktu UTC | Cron |
|---|---|---|
| 08:00 | 01:00 | `0 1 * * *` |
| 15:00 | 08:00 | `0 8 * * *` |

Bisa juga dijalankan manual via tab **Actions** → **Run workflow**.

## Cara Update Watchlist

**Edit langsung di Google Sheets** — tidak perlu commit ke repositori.

Spreadsheet: `https://docs.google.com/spreadsheets/d/1yHSEchupXWJoEysKrvD8m77SxcKcPz6fgSr3v92eHTM/edit`

### Format Kolom

| Kolom | Arti | Contoh |
|---|---|---|
| `ticker` | Kode saham tanpa `.JK` | `BBCA` |
| `reference_price` | Harga acuan (harga beli atau harga pasar) | `5925` |
| `watch_down` | % zona pantau (turun) | `-2` |
| `watch_up` | % zona pantau (naik) | `2` |
| `action_down` | % zona aksi (turun) | `-5` |
| `action_up` | % zona aksi (naik) | `5` |
| `panic_down` | % zona darurat (turun) | `-8` |
| `panic_up` | % zona darurat (naik) | `8` |

**Isi `0` untuk menonaktifkan zona tertentu.** Misalnya, jika Anda tidak ingin notifikasi saat harga naik, isi `watch_up`, `action_up`, dan `panic_up` dengan `0`.

### Cara Menghitung Threshold

Bot menghitung threshold dari `reference_price`:
