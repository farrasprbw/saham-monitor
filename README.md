### `README.md` 

```markdown
# 📈 Saham Monitor

Bot Telegram untuk memantau saham IDX. Dilengkapi analisis otomatis, alert threshold, dan rekomendasi harian — semua berjalan otomatis di cloud, tanpa biaya bulanan.

## 🎯 Apa Itu Saham Monitor

Saham Monitor adalah bot Telegram yang membantu investor jangka panjang memantau saham Indonesia (IDX). Bot ini menggabungkan:

- **Data real-time** dari Yahoo Finance
- **Penyimpanan fleksibel** via GitHub Gist
- **Analisis AI** dengan Groq dan Gemini sebagai fallback
- **Penjadwalan otomatis** via GitHub Actions

Semua berjalan di infrastruktur gratis (Vercel + GitHub), sehingga biaya operasional **Rp 0 per bulan**.

## ✨ Fitur Utama

### 🔍 Cek Saham
Cek harga terkini, PE ratio, PBV, dividend yield, dan zona beli dari 100+ saham IDX. Cukup kirim `/cek TICKER`.

### 📊 Analisis AI
Analisis mendalam yang menggabungkan data fundamental dan teknikal, dinarasikan oleh AI dalam Bahasa Indonesia. Hasilnya berupa 5 paragraf ringkas: posisi harga, valuasi, sinyal teknikal, risiko, dan kesimpulan.

### ⚖️ Bandingkan Saham
Bandingkan 2 saham side-by-side. Berguna saat ingin memilih antara dua saham di sektor yang sama (misalnya ANTM vs MDKA).

### 📋 Watchlist Pribadi
Kelola daftar saham yang ingin Anda pantau. Setiap saham punya harga acuan dan tiga zona threshold (watch, action, panic) yang bisa dikustomisasi.

### 🔔 Alert Otomatis
Bot memeriksa watchlist Anda 2x sehari (07:00 dan 16:00 WIB). Jika harga saham menyentuh threshold, Anda akan menerima notifikasi di Telegram.

### 📈 Rekomendasi Harian
Setiap pagi (07:00 WIB, Senin-Jumat), bot melakukan screening otomatis terhadap 100+ saham IDX dan mengirimkan Top 5 saham terbaik berdasarkan skor fundamental + teknikal.

## 🏗️ Cara Kerja

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
         │ 1. Kirim command (/cek, /analisa, dll.)
         ▼
┌─────────────────────┐         ┌──────────────────┐
│  Vercel (webhook)   │◄───────►│   GitHub Gist    │
│   api/webhook.py    │         │  - watchlist.json│
│                     │         │  - all_stocks    │
└─────────┬───────────┘         └──────────────────┘
          │
          │ 2. Ambil data harga + kirim ke AI
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

### Alur Interaksi (User → Bot)

1. User kirim command ke bot Telegram
2. Telegram teruskan ke Vercel via webhook
3. Vercel jalankan `api/webhook.py`
4. Bot ambil data dari Yahoo Finance / Gist
5. Kalau perlu, kirim ke Groq/Gemini untuk analisis
6. Bot kirim balasan ke Telegram

### Alur Otomatis (Tanpa Interaksi)

1. GitHub Actions trigger pada jadwal cron
2. Jalankan `suggest.py` (rekomendasi) atau `main.py` (alert)
3. Baca data dari Gist + Yahoo Finance
4. Kirim hasil ke Telegram

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

### 📋 Kelola Watchlist

| Command | Contoh | Deskripsi |
|---|---|---|
| `/list` | `/list` | Lihat daftar pantau |
| `/add` | `/add BBCA 5500` | Tambah saham dengan harga acuan |
| `/remove` | `/remove BBRI` | Hapus saham dari watchlist |
| `/ref` | `/ref BBCA 5800` | Ubah harga acuan |
| `/zone` | `/zone BBCA watch -5 +10` | Ubah threshold zona |

### 🔍 Cari & Cek

| Command | Contoh | Deskripsi |
|---|---|---|
| `/cari` | `/cari Bank Mandiri` | Cari saham berdasarkan nama |
| `/cek` | `/cek ANTM` | Cek harga & zona beli |
| `/bandingkan` | `/bandingkan ANTM MDKA` | Bandingkan 2 saham |

### 📊 Analisis

| Command | Contoh | Deskripsi |
|---|---|---|
| `/analisa` | `/analisa ANTM` | Analisis lengkap dengan AI |
| `/rekomendasi` | `/rekomendasi` | Minta rekomendasi Top 5 sekarang |

## 🎯 Cara Pakai

### Skenario 1: Cek Saham

Ingin tahu harga dan valuasi suatu saham?

```
User: /cek ANTM

Bot:  📊 ANTM
      PT Antam (Persero) Tbk
      
      💰 Harga: Rp 3,100
      📈 PE: 8.4  |  PBV: 2.00
      💵 Dividend: 6.8%
      
      🟢 Zona beli: Rp 2,330 – 3,150
      🔴 Batas bawah: Rp 2,170
      🎯 Batas atas: Rp 5,090
      
      📉 52w: Rp 2,283 – 4,631
```

### Skenario 2: Analisis Mendalam

Ingin analisis lengkap dengan konteks?

```
User: /analisa ANTM

Bot:  📊 ANALISA ANTM
      PT Antam (Persero) Tbk
      
      💰 Harga: Rp 3,100
      📈 PE: 8.4  |  PBV: 2.00
      📉 RSI: 39.2
      
      ━━━ 🤖 HASIL ANALISIS ━━━
      
      Harga saham ANTM saat ini berada di level Rp 3.100...
      [5 paragraf analisis]
      
      Bukan rekomendasi investasi.
```

### Skenario 3: Bangun Watchlist

Ingin memantau saham tertentu?

```
User: /add BBCA 5925

Bot:  ✅ BBCA ditambahkan!
      
      💰 Ref harga: Rp 5,925
      🔵 Watch: -5% / +10%
      🟡 Action: -10% / +20%
      🔴 Panic: -15% / +30%
```

Kemudian sesuaikan threshold:

```
User: /zone BBCA watch -3 +8

Bot:  ✅ BBCA — 🔵 watch
      
      ⬇️ Turun: -3%
      ⬆️ Naik: +8%
```

### Skenario 4: Terima Alert Otomatis

Jam 16:00 WIB setiap hari kerja, bot cek watchlist Anda. Kalau harga menyentuh threshold:

```
Bot:  🔴 ZONA DARURAT
      URGENT — Bank Central Asia (BBCA)
      
      💰 Harga saat ini: Rp 5.500
      🎯 turun 7.2% dari Rp 5.925
      
      Segera cek aplikasi sekuritas Anda.
```

### Skenario 5: Rekomendasi Harian

Jam 07:00 WIB setiap hari kerja, Anda otomatis menerima:

```
Bot:  📈 REKOMENDASI TOP 5 — 14 Okt 2026
      
      🟢 BMRI — Bank Mandiri
      💰 Harga: Rp 3,990
      📊 PE: 7.5 | PBV: 1.5 | Div: 8.1%
      🟢 Zona beli: Rp 3,750 – 4,100
      ...
```

### Skenario 6: Minta Rekomendasi Sekarang

Kalau tidak mau menunggu besok pagi:

```
User: /rekomendasi

Bot:  📊 REKOMENDASI SEDANG DISIAPKAN
      
      Screening 100+ saham membutuhkan 3-5 menit.
      Hasil akan dikirim ke chat ini secara otomatis.
```

## 🚀 Setup

### Prasyarat

- Akun GitHub
- Akun Vercel (gratis)
- Akun Telegram
- Groq API Key (gratis) — https://console.groq.com
- Gemini API Key (opsional, untuk fallback) — https://aistudio.google.com

### Langkah Setup

**1. Buat Bot Telegram**

- Chat **@BotFather**, kirim `/newbot`
- Simpan Token
- Dapatkan Chat ID via **@userinfobot**

**2. Buat GitHub Gist**

Dua Gist (secret):

- `watchlist.json` — isi awal `[]`
- `all_stocks.json` — daftar saham dalam format:
  ```json
  [
    {"ticker": "BBCA", "name": "Bank Central Asia"},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia"}
  ]
  ```

Catat Gist ID masing-masing.

**3. Buat Personal Access Token**

Buat dua token di https://github.com/settings/tokens:

| Token | Scope | Untuk |
|---|---|---|
| `GIST_TOKEN` | `gist` | Baca/tulis Gist |
| `GITHUB_PAT` | `workflow` | Trigger GitHub Actions |

**4. Setup GitHub Secrets**

Repo → Settings → Secrets and variables → Actions:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Anda |
| `GIST_ID` | Gist ID watchlist |
| `GIST_ID_ALL_STOCKS` | Gist ID all_stocks |
| `GIST_TOKEN` | Token dengan scope gist |

**5. Deploy ke Vercel**

Import repositori, tambahkan Environment Variables:

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

**6. Daftarkan Webhook Telegram**

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<DOMAIN_VERCEL>/api/webhook"}'
```

**7. Set Command di BotFather**

Chat @BotFather → `/mybots` → pilih bot → **Edit Bot** → **Edit Commands**:

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

**8. Test**

Kirim `/help` ke bot Anda.

## ⏰ Jadwal Otomatis

| Workflow | Jadwal | Fungsi |
|---|---|---|
| `suggest.yml` | 07:00 WIB (Sen-Jum) | Rekomendasi Top 5 saham |
| `alert.yml` | 16:00 WIB (Sen-Jum) | Alert threshold watchlist |

## 🛠️ Troubleshooting

| Masalah | Solusi |
|---|---|
| Bot tidak merespons | Cek webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` |
| 403 Forbidden | Chat ID di Vercel berbeda dengan Chat ID Anda |
| 401 Unauthorized | `GIST_TOKEN` salah atau expired |
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

### Cara Update

1. Buka `README.md` di repositori GitHub
2. Klik ikon **pensil** (Edit)
3. Select all → Delete
4. Paste seluruh isi di atas
5. Commit

### Struktur Baru README

| Bagian | Fokus |
|---|---|
| **Apa Itu Saham Monitor** | Overview singkat aplikasi |
| **Fitur Utama** | 6 fitur dengan deskripsi |
| **Cara Kerja** | Arsitektur + alur interaksi |
| **Struktur Repositori** | File tree |
| **Perintah Bot** | 10 command dikelompokkan |
| **Cara Pakai** | 6 skenario penggunaan |
| **Setup** | 8 langkah dari nol |
| **Jadwal Otomatis** | Kapan bot berjalan sendiri |
| **Troubleshooting** | Masalah umum |
| **Biaya** | Semua gratis |
| **Disclaimer** | Peringatan hukum |
| **Credits** | Terima kasih ke layanan |

**Tidak ada** bagian "update terakhir" atau changelog. README sekarang berfungsi sebagai **dokumentasi lengkap** untuk siapa pun yang ingin memahami atau menggunakan bot ini.
