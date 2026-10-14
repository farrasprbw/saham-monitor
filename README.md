Baik, ini `README.md` final yang **sudah disesuaikan** dengan `webhook.py` versi terbaru (tanpa fitur riwayat).

### `README.md` Final

```markdown
# 📈 Saham Monitor

Bot Telegram untuk memantau saham IDX dengan analisis otomatis dan alert threshold.

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Platform](https://img.shields.io/badge/platform-Vercel-black)

## ✨ Fitur

| Fitur | Deskripsi |
|---|---|
| 🔍 **Cek Saham** | Harga, PE, PBV, dividend, zona beli dari 100+ saham IDX |
| 📊 **Analisis AI** | Analisis fundamental + teknikal dengan narasi dari AI |
| ⚖️ **Bandingkan** | Bandingkan 2 saham side-by-side |
| 📋 **Watchlist** | Kelola daftar saham pantau dengan threshold kustom |
| 🔔 **Alert Otomatis** | Notifikasi jika harga menyentuh threshold (2x sehari) |
| 📈 **Rekomendasi Harian** | Top 5 saham terbaik dari screening 100 saham (07:00 WIB) |

## 🏗️ Arsitektur

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐         ┌──────────────────┐
│  Vercel (webhook)   │◄───────►│   GitHub Gist    │
│   api/webhook.py    │         │  - watchlist.json│
│                     │         │  - all_stocks    │
└─────────┬───────────┘         └──────────────────┘
          │
          ▼
┌─────────────────────┐
│   Yahoo Finance     │
│   Groq / Gemini     │
└─────────────────────┘

┌─────────────────────┐
│  GitHub Actions     │
│  - suggest.yml      │  ← Rekomendasi harian 07:00 WIB
│  - alert.yml        │  ← Alert threshold 16:00 WIB
└─────────────────────┘
```

## 📁 Struktur Repositori

```
saham-monitor/
├── .github/
│   └── workflows/
│       ├── suggest.yml         # Rekomendasi harian
│       └── alert.yml           # Alert threshold
├── api/
│   └── webhook.py              # Bot Telegram (Vercel)
├── main.py                     # Skrip alert threshold
├── suggest.py                  # Skrip rekomendasi harian
├── requirements.txt
├── vercel.json
└── README.md
```

## 🤖 Perintah Bot

### Kelola Watchlist

| Command | Contoh | Deskripsi |
|---|---|---|
| `/list` | `/list` | Lihat daftar pantau |
| `/add` | `/add BBCA 5500` | Tambah saham dengan harga acuan |
| `/remove` | `/remove BBRI` | Hapus saham |
| `/ref` | `/ref BBCA 5800` | Ubah harga acuan |
| `/zone` | `/zone BBCA watch -5 +10` | Ubah threshold zona |

### Cari & Cek

| Command | Contoh | Deskripsi |
|---|---|---|
| `/cari` | `/cari Bank Mandiri` | Cari saham berdasarkan nama |
| `/cek` | `/cek ANTM` | Cek harga & zona beli |
| `/bandingkan` | `/bandingkan ANTM MDKA` | Bandingkan 2 saham |

### Analisis

| Command | Contoh | Deskripsi |
|---|---|---|
| `/analisa` | `/analisa ANTM` | Analisis lengkap dengan AI |
| `/rekomendasi` | `/rekomendasi` | Minta rekomendasi Top 5 sekarang |

## 🚀 Setup

### Prasyarat

- Akun GitHub
- Akun Vercel (gratis)
- Akun Telegram
- Bot Telegram (dibuat via @BotFather)
- Groq API Key (gratis) — https://console.groq.com
- Gemini API Key (opsional) — https://aistudio.google.com

### 1. Fork / Clone Repositori

```bash
git clone https://github.com/username/saham-monitor.git
cd saham-monitor
```

### 2. Buat Bot Telegram

1. Chat **@BotFather** di Telegram
2. Kirim `/newbot`, ikuti instruksi
3. Simpan **Token** yang diberikan
4. Dapatkan **Chat ID** via **@userinfobot**

### 3. Buat GitHub Gist

Buat dua Gist (secret):

**a. `watchlist.json`** — isi awal:
```json
[]
```

**b. `all_stocks.json`** — database saham:
```json
[
  {"ticker": "BBCA", "name": "Bank Central Asia"},
  {"ticker": "BBRI", "name": "Bank Rakyat Indonesia"},
  {"ticker": "BMRI", "name": "Bank Mandiri"},
  {"ticker": "TLKM", "name": "Telkom Indonesia"},
  {"ticker": "ASII", "name": "Astra International"}
]
```

Catat **Gist ID** masing-masing (dari URL).

### 4. Buat Personal Access Token

Buat **dua** token di https://github.com/settings/tokens:

| Token | Scope | Untuk |
|---|---|---|
| `GIST_TOKEN` | `gist` | Baca/tulis Gist |
| `GITHUB_PAT` | `workflow` | Trigger GitHub Actions |

### 5. Setup GitHub Secrets

Repo → Settings → Secrets and variables → Actions:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Anda |
| `GIST_ID` | Gist ID watchlist |
| `GIST_ID_ALL_STOCKS` | Gist ID all_stocks |
| `GIST_TOKEN` | Token dengan scope gist |

### 6. Deploy ke Vercel

1. Login Vercel dengan GitHub
2. Import repositori `saham-monitor`
3. Tambahkan **Environment Variables**:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Anda |
| `GIST_ID` | Gist ID watchlist |
| `GIST_ID_ALL_STOCKS` | Gist ID all_stocks |
| `GIST_TOKEN` | Token gist |
| `GROQ_API_KEY` | Groq API Key |
| `GEMINI_API_KEY` | Gemini API Key (opsional) |
| `GITHUB_REPO` | `username/saham-monitor` |
| `GITHUB_PAT` | Token dengan scope workflow |

4. Klik **Deploy**
5. Catat URL Vercel Anda (misal `https://saham-monitor-xxx.vercel.app`)

### 7. Daftarkan Webhook Telegram

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<DOMAIN_VERCEL>/api/webhook"}'
```

Kalau berhasil: `{"ok":true,"result":true,"description":"Webhook was set"}`

### 8. Set Command di BotFather

Chat @BotFather → `/mybots` → pilih bot → **Edit Bot** → **Edit Commands** → paste:

```
start - Menu utama
help - Daftar perintah
list - Lihat watchlist
add - Tambah saham: /add TICKER REF
remove - Hapus saham: /remove TICKER
ref - Ubah harga acuan: /ref TICKER HARGA
zone - Ubah threshold: /zone TICKER ZONA DOWN UP
cek - Cek harga saham: /cek TICKER
cari - Cari saham: /cari NAMA
analisa - Analisis AI: /analisa TICKER
bandingkan - Bandingkan 2 saham: /bandingkan T1 T2
rekomendasi - Rekomendasi Top 5
```

### 9. Test

Kirim ke bot Telegram:

```
/help
```

Kalau muncul menu, berarti sudah berhasil.

## ⏰ Jadwal Otomatis

| Workflow | Jadwal | Fungsi |
|---|---|---|
| `suggest.yml` | 07:00 WIB (Sen-Jum) | Rekomendasi Top 5 saham |
| `alert.yml` | 16:00 WIB (Sen-Jum) | Alert threshold watchlist |

## 🎯 Cara Pakai

### Skenario 1: Cek Saham

```
User: /cek ANTM
Bot:  📊 ANTM — PT Antam Tbk
      💰 Rp 3,100
      📈 PE: 8.4 | PBV: 2.00
      ...
```

### Skenario 2: Analisis Lengkap

```
User: /analisa ANTM
Bot:  📊 ANALISA ANTM
      [data fundamental]
      🤖 HASIL ANALISIS
      [narasi analisis 5 paragraf]
```

### Skenario 3: Bangun Watchlist

```
User: /add BBCA 5925
Bot:  ✅ BBCA ditambahkan dengan ref Rp 5.925

User: /zone BBCA watch -5 +10
Bot:  ✅ BBCA watch = -5% / +10%
```

### Skenario 4: Terima Alert

```
[Otomatis jam 16:00]
Bot:  🔴 ZONA DARURAT
      URGENT — Bank Central Asia (BBCA)
      💰 Harga: Rp 5.500
      🎯 turun 7.2% dari Rp 5.925
```

## 🛠️ Troubleshooting

| Masalah | Solusi |
|---|---|
| Bot tidak merespons | Cek webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` |
| 403 Forbidden | Chat ID di Vercel berbeda dengan Chat ID Anda |
| 401 Unauthorized | GIST_TOKEN salah atau expired |
| Analisis gagal | Cek log Vercel, mungkin Groq/Gemini down |
| Alert tidak dikirim | Cek jadwal cron di `.github/workflows/alert.yml` |
| `/rekomendasi` gagal | Cek `GITHUB_PAT` punya scope `workflow` |

## 💰 Biaya

| Layanan | Biaya |
|---|---|
| GitHub (repo + Gist + Actions) | Gratis |
| Vercel (Hobby) | Gratis |
| Groq API | Gratis (14.400 req/hari) |
| Gemini API | Gratis (1.500 req/hari) |
| Yahoo Finance | Gratis |
| **Total** | **Rp 0/bulan** |

## ⚠️ Disclaimer

Bot ini adalah **alat bantu monitoring**, bukan pemberi rekomendasi investasi. Semua keputusan beli/jual adalah tanggung jawab pengguna. Selalu lakukan riset mandiri dan pertimbangkan profil risiko Anda.

## 📝 Lisensi

MIT License — bebas digunakan dan dimodifikasi.

## 🙏 Credits

- [yfinance](https://github.com/ranaroussi/yfinance) — data saham
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram API
- [Flask](https://flask.palletsprojects.com/) — web framework
- [Vercel](https://vercel.com) — hosting
- [Groq](https://groq.com) — AI inference
```

### Yang Diperbarui dari Versi Sebelumnya

| Item | Perubahan |
|---|---|
| Fitur **Riwayat** | Dihapus dari tabel Fitur |
| Command `/riwayat` | Dihapus dari tabel command |
| Gist `riwayat.json` | Dihapus dari langkah setup |
| Env `GIST_ID_RIWAYAT` | Dihapus dari Environment Variables Vercel |
| Diagram arsitektur | Dihapus `riwayat.json` dari diagram |
| **Troubleshooting** | Tambah baris `/rekomendasi` gagal |

### Cara Update di GitHub

1. Buka `README.md` di repositori
2. Klik ikon **pensil** (Edit)
3. Select all → Delete
4. Paste seluruh isi di atas
5. Commit

### Verifikasi Setelah Semua Update

Setelah kedua file di-update, cek:

| File | Status |
|---|---|
| `api/webhook.py` | Sudah bersih dari riwayat |
| `README.md` | Sudah konsisten dengan kode |

Test di Telegram:

1. `/help` — pastikan menu tidak menyebut `/riwayat`
2. `/riwayat ANTM` — pastikan balas "Perintah tidak dikenal"
3. `/analisa ANTM` — pastikan tetap berfungsi

Kalau ketiganya sesuai, berarti sudah selesai dan konsisten.

### Yang Bisa Dilakukan Setelah Ini

1. **Coba semua command** satu per satu untuk memastikan semuanya berjalan
2. **Bangun watchlist** dengan 3-5 saham yang Anda pahami
3. **Gunakan selama 1 bulan** tanpa menambah fitur
4. **Evaluasi** apa yang kurang, baru tambahkan

Kalau ada yang perlu diperbaiki saat test, kirimkan log-nya.
