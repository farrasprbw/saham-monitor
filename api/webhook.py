import os
import json
import asyncio
import time
import random
import requests
from flask import Flask, request, jsonify
from telegram import Update, Bot

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GIST_ID = os.environ.get("GIST_ID")
GIST_ID_ALL_STOCKS = os.environ.get("GIST_ID_ALL_STOCKS")
GIST_TOKEN = os.environ.get("GIST_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ========== Baca Gist ==========
def read_gist_file(gist_id: str, filename: str):
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {"Accept": "application/vnd.github+json"}
    if GIST_TOKEN:
        headers["Authorization"] = f"Bearer {GIST_TOKEN}"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal baca Gist {gist_id}: {r.status_code}")
    files = r.json().get("files", {})
    if filename not in files:
        raise Exception(f"File {filename} tidak ditemukan di Gist")
    return json.loads(files[filename]["content"])

def read_watchlist():
    return read_gist_file(GIST_ID, "watchlist.json")

def write_watchlist(watchlist):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GIST_TOKEN}",
    }
    payload = {
        "files": {
            "watchlist.json": {
                "content": json.dumps(watchlist, indent=2)
            }
        }
    }
    r = requests.patch(url, headers=headers, json=payload, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal tulis Gist: {r.status_code}")

def load_all_stocks():
    data = read_gist_file(GIST_ID_ALL_STOCKS, "all_stocks.json")
    stocks = []
    for item in data:
        if isinstance(item, dict):
            stocks.append(item)
        elif isinstance(item, str):
            stocks.append({"ticker": item, "name": item})
    return stocks

# ========== Helper ==========
def find_item(watchlist, ticker):
    for item in watchlist:
        if item["ticker"].upper() == ticker.upper():
            return item
    return None

def search_in_database(stocks: list, query: str):
    q = query.upper().strip()
    matches = []
    for s in stocks:
        ticker = s["ticker"].upper()
        name = s["name"].upper()
        if q == ticker:
            return [s]
        if q in ticker or q in name:
            matches.append(s)
    return matches[:5]

def format_watchlist(watchlist):
    if not watchlist:
        return "📋 Watchlist kosong. Tambahkan dengan `/add BBCA 5500`"
    lines = ["📋 *Watchlist:*\n"]
    for item in watchlist:
        lines.append(
            f"*{item['ticker']}* ref Rp {item['reference_price']:,.0f}\n"
            f"  watch {item.get('watch_down',0)}% / +{item.get('watch_up',0)}%\n"
            f"  action {item.get('action_down',0)}% / +{item.get('action_up',0)}%\n"
            f"  panic {item.get('panic_down',0)}% / +{item.get('panic_up',0)}%\n"
        )
    return "\n".join(lines)

def cek_saham(query: str) -> str:
    import yfinance as yf

    stocks = load_all_stocks()
    matches = search_in_database(stocks, query)

    if not matches:
        return f"❌ Tidak ada saham dengan kata kunci '{query}' di database."

    lines = []
    for s in matches:
        ticker = s["ticker"]
        name = s["name"]
        yf_ticker = f"{ticker}.JK"

        try:
            t = yf.Ticker(yf_ticker)
            info = t.info
            hist = t.history(period="1y")

            if hist.empty:
                lines.append(f"⚠️ *{ticker}* — data tidak tersedia.")
                continue

            current = float(hist["Close"].iloc[-1])
            high_52w = float(hist["High"].max())
            low_52w = float(hist["Low"].min())
            ma50 = float(hist["Close"].tail(50).mean())

            pe = info.get("trailingPE") or info.get("forwardPE")
            pbv = info.get("priceToBook")
            div = info.get("dividendYield")
            div_pct = (div * 100 if div and div < 1 else div) if div else None

            buy_low = round(low_52w * 1.02, 0)
            buy_high = round(ma50, 0)
            upper = round(high_52w * 1.10, 0)
            lower = round(low_52w * 0.95, 0)

            pe_str = f"{pe:.1f}" if pe else "N/A"
            pbv_str = f"{pbv:.2f}" if pbv else "N/A"
            div_str = f"{div_pct:.1f}%" if div_pct else "N/A"

            lines.append(
                f"📊 *{ticker}* — {name}\n"
                f"💰 Harga: Rp {current:,.0f}\n"
                f"📈 PE: {pe_str} | PBV: {pbv_str} | Div: {div_str}\n"
                f"🟢 Zona beli: Rp {buy_low:,.0f} – Rp {buy_high:,.0f}\n"
                f"🔴 Batas bawah: Rp {lower:,.0f}\n"
                f"🎯 Batas atas: Rp {upper:,.0f}\n"
            )
        except Exception as e:
            print(f"⚠️ cek_saham error {ticker}: {e}")
            lines.append(f"⚠️ *{ticker}* — data tidak dapat dimuat.")

    return "\n".join(lines)

# ========== Ambil data untuk analisa ==========
def ambil_data_untuk_analisis(ticker: str):
    import yfinance as yf

    yf_ticker = f"{ticker}.JK"
    t = yf.Ticker(yf_ticker)
    info = t.info
    hist = t.history(period="1y")

    if hist.empty or len(hist) < 50:
        return None

    current = float(hist["Close"].iloc[-1])
    high_52w = float(hist["High"].max())
    low_52w = float(hist["Low"].min())
    ma50 = float(hist["Close"].tail(50).mean())
    ma200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else None

    # RSI 14 hari
    delta = hist["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = float(rsi.iloc[-1]) if not rsi.empty else None

    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "current_price": current,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "ma50": ma50,
        "ma200": ma200,
        "rsi": rsi_val,
        "pe": info.get("trailingPE") or info.get("forwardPE"),
        "pbv": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "sector": info.get("sector"),
    }

def susun_prompt_analisis(data: dict) -> str:
    div = data.get("dividend_yield")
    div_str = f"{div*100:.2f}%" if div and div < 1 else (f"{div:.2f}%" if div else "N/A")
    ma200_str = f"Rp {data['ma200']:,.0f}" if data.get("ma200") else "N/A"
    rsi_str = f"{data['rsi']:.1f}" if data.get("rsi") else "N/A"

    return f"""Kamu adalah analis saham untuk investor jangka panjang di Indonesia.

Data saham {data['ticker']} ({data['name']}):
- Harga saat ini: Rp {data['current_price']:,.0f}
- 52-week high: Rp {data['high_52w']:,.0f}
- 52-week low: Rp {data['low_52w']:,.0f}
- MA50: Rp {data['ma50']:,.0f}
- MA200: {ma200_str}
- RSI(14): {rsi_str}
- PE Ratio: {data.get('pe') or 'N/A'}
- PBV: {data.get('pbv') or 'N/A'}
- Dividend Yield: {div_str}
- Sektor: {data.get('sector') or 'N/A'}

Berikan analisis dalam Bahasa Indonesia, maksimal 5 paragraf pendek:
1. Posisi harga saat ini (murah/mahal/netral) berdasarkan 52w range dan MA
2. Penilaian valuasi (PE, PBV, dividend)
3. Sinyal teknikal (RSI, tren MA50 vs MA200)
4. Risiko utama yang perlu diperhatikan
5. Kesimpulan singkat

Jangan gunakan markdown bold. Jangan beri rekomendasi beli/jual secara eksplisit. Cukup analisis objektif."""

def call_groq(prompt: str, api_key: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1000,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=25)
    if r.status_code != 200:
        raise Exception(f"Groq {r.status_code}")
    return r.json()["choices"][0]["message"]["content"].strip()

def call_gemini(prompt: str, api_key: str) -> str:
    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 1000},
    }

    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if r.status_code == 404:
                last_error = f"{model} tidak tersedia"
                continue
            if r.status_code in (429, 500, 503):
                last_error = f"{model} {r.status_code}"
                continue
            raise Exception(f"Gemini {r.status_code}")
        except requests.exceptions.Timeout:
            last_error = f"{model} timeout"
            continue
    raise Exception(f"Gemini gagal: {last_error}")

def analisa_dengan_ai(data: dict) -> str:
    prompt = susun_prompt_analisis(data)

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            print("🤖 Mencoba Groq...")
            result = call_groq(prompt, groq_key)
            print("✅ Groq berhasil")
            return result
        except Exception as e:
            print(f"⚠️ Groq gagal: {e}")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            print("🤖 Mencoba Gemini...")
            result = call_gemini(prompt, gemini_key)
            print("✅ Gemini berhasil")
            return result
        except Exception as e:
            print(f"⚠️ Gemini gagal: {e}")

    raise Exception("Layanan analisis sedang tidak dapat diakses.")

# ========== Handler command ==========
def handle_command(text: str) -> str:
    parts = text.split()
    cmd = parts[0].lower()

    if cmd in ("/start", "/help"):
        return (
            "🤖 *Bot Saham Monitor*\n\n"
            "*Perintah yang tersedia:*\n\n"
            "📋 `/list` — lihat watchlist\n"
            "➕ `/add TICKER REF` — tambah saham\n"
            "   Contoh: `/add BBCA 5500`\n"
            "❌ `/remove TICKER` — hapus saham\n"
            "💰 `/ref TICKER HARGA` — ubah harga acuan\n"
            "   Contoh: `/ref BBCA 5800`\n"
            "🎯 `/zone TICKER ZONA DOWN UP` — ubah threshold\n"
            "   Contoh: `/zone BBCA watch -5 +10`\n"
            "   Zona: watch / action / panic\n"
            "🔍 `/cek TICKER` — cek harga & zona beli\n"
            "   Contoh: `/cek ANTM`\n"
            "🔎 `/cari NAMA` — cari saham berdasarkan nama\n"
            "   Contoh: `/cari Bank Mandiri`\n"
            "📊 `/analisa TICKER` — analisis lengkap\n"
            "   Contoh: `/analisa ANTM`"
        )

    if cmd == "/list":
        return format_watchlist(read_watchlist())

    if cmd == "/add":
        if len(parts) != 3:
            return "Format: `/add TICKER REF`\nContoh: `/add BBCA 5500`"
        ticker = parts[1].upper()
        try:
            ref = float(parts[2])
        except ValueError:
            return "❌ REF harus angka. Contoh: `/add BBCA 5500`"

        watchlist = read_watchlist()
        if find_item(watchlist, ticker):
            return f"⚠️ {ticker} sudah ada. Pakai `/ref {ticker} HARGA` untuk ubah."
        watchlist.append({
            "ticker": ticker,
            "reference_price": ref,
            "watch_down": -5, "watch_up": 10,
            "action_down": -10, "action_up": 20,
            "panic_down": -15, "panic_up": 30
        })
        write_watchlist(watchlist)
        return f"✅ {ticker} ditambahkan dengan ref Rp {ref:,.0f}"

    if cmd == "/remove":
        if len(parts) != 2:
            return "Format: `/remove TICKER`\nContoh: `/remove BBRI`"
        ticker = parts[1].upper()
        watchlist = read_watchlist()
        new_wl = [x for x in watchlist if x["ticker"].upper() != ticker]
        if len(new_wl) == len(watchlist):
            return f"⚠️ {ticker} tidak ditemukan di watchlist."
        write_watchlist(new_wl)
        return f"✅ {ticker} dihapus dari watchlist."

    if cmd == "/ref":
        if len(parts) != 3:
            return "Format: `/ref TICKER HARGA`\nContoh: `/ref BBCA 5800`"
        ticker = parts[1].upper()
        try:
            ref = float(parts[2])
        except ValueError:
            return "❌ HARGA harus angka."
        watchlist = read_watchlist()
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ {ticker} tidak ada. Tambah dulu dengan `/add {ticker} {parts[2]}`"
        item["reference_price"] = ref
        write_watchlist(watchlist)
        return f"✅ {ticker} ref = Rp {ref:,.0f}"

    if cmd == "/zone":
        if len(parts) != 5:
            return ("Format: `/zone TICKER ZONA DOWN UP`\n"
                    "Contoh: `/zone BBCA watch -5 +10`\n"
                    "Zona: watch / action / panic")
        ticker = parts[1].upper()
        zone = parts[2].lower()
        if zone not in ("watch", "action", "panic"):
            return "⚠️ Zona harus watch, action, atau panic."
        try:
            down = float(parts[3])
            up = float(parts[4])
        except ValueError:
            return "❌ DOWN dan UP harus angka. Contoh: -5 +10"
        watchlist = read_watchlist()
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ {ticker} tidak ada di watchlist."
        item[f"{zone}_down"] = down
        item[f"{zone}_up"] = up
        write_watchlist(watchlist)
        return f"✅ {ticker} {zone} = {down}% / +{up}%"

    if cmd == "/cek":
        if len(parts) < 2:
            return "Format: `/cek TICKER`\nContoh: `/cek ANTM`"
        query = " ".join(parts[1:])
        return cek_saham(query)

    if cmd == "/cari":
        if len(parts) < 2:
            return "Format: `/cari NAMA`\nContoh: `/cari Bank Mandiri`"
        query = " ".join(parts[1:])
        stocks = load_all_stocks()
        matches = search_in_database(stocks, query)
        if not matches:
            return f"❌ Tidak ada saham dengan nama '{query}'."
        lines = ["🔎 *Hasil pencarian:*\n"]
        for s in matches:
            lines.append(f"• `{s['ticker']}` — {s['name']}")
        lines.append("\nPakai `/cek TICKER` untuk lihat harga.")
        return "\n".join(lines)

    if cmd == "/analisa":
        if len(parts) < 2:
            return "Format: `/analisa TICKER`\nContoh: `/analisa ANTM`"
        ticker = parts[1].upper()

        stocks = load_all_stocks()
        match = None
        for s in stocks:
            if s["ticker"].upper() == ticker:
                match = s
                break

        if not match:
            return f"❌ {ticker} tidak ada di database. Cek dengan `/cari NAMA`."

        try:
            data = ambil_data_untuk_analisis(ticker)
        except Exception as e:
            print(f"⚠️ ambil_data error: {e}")
            return f"⚠️ Data untuk {ticker} tidak dapat dimuat saat ini."

        if not data:
            return f"⚠️ Data untuk {ticker} tidak cukup untuk dianalisis."

        try:
            analisis = analisa_dengan_ai(data)
        except Exception as e:
            print(f"⚠️ analisa error: {e}")
            return ("⚠️ Layanan analisis sedang tidak dapat diakses.\n\n"
                    f"Sebagai gantinya, coba `/cek {ticker}` untuk data mentah.")

        rsi_str = f"{data['rsi']:.1f}" if data.get("rsi") else "N/A"

        return (
            f"📊 *ANALISA {ticker}* — {data['name']}\n\n"
            f"💰 Harga: Rp {data['current_price']:,.0f}\n"
            f"📈 PE: {data.get('pe') or 'N/A'} | PBV: {data.get('pbv') or 'N/A'}\n"
            f"📉 RSI: {rsi_str}\n\n"
            f"🤖 *Analisis:*\n\n{analisis}\n\n"
            f"_Bukan rekomendasi investasi._"
        )

    return f"❓ Perintah `{cmd}` tidak dikenal. Kirim `/help` untuk daftar perintah."

# ========== Webhook ==========
@app.route("/api/webhook", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), Bot(BOT_TOKEN))

    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return jsonify({"ok": False}), 403

    msg = update.message
    if not msg or not msg.text:
        return jsonify({"ok": True}), 200

    text = msg.text.strip()
    bot = Bot(BOT_TOKEN)

    def reply(t):
        asyncio.run(bot.send_message(chat_id=msg.chat_id, text=t, parse_mode="Markdown"))

    try:
        if not text.startswith("/"):
            reply(
                "ℹ️ Kirim perintah dengan awalan `/`.\n\n"
                "Contoh:\n"
                "• `/list` — lihat watchlist\n"
                "• `/add BBCA 5500` — tambah saham\n"
                "• `/cek ANTM` — cek harga saham\n"
                "• `/analisa ANTM` — analisis saham\n\n"
                "Kirim `/help` untuk daftar lengkap."
            )
            return jsonify({"ok": True}), 200

        balasan = handle_command(text)
        reply(balasan)

    except Exception as e:
        print(f"❌ handler error: {e}")
        reply("❌ Terjadi kesalahan. Silakan coba lagi.")

    return jsonify({"ok": True}), 200
