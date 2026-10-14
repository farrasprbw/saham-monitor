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
    """Return list of {ticker, name}."""
    data = read_gist_file(GIST_ID_ALL_STOCKS, "all_stocks.json")
    stocks = []
    for item in data:
        if isinstance(item, dict):
            stocks.append(item)
        elif isinstance(item, str):
            stocks.append({"ticker": item, "name": item})
    return stocks

# ========== Cari saham ==========
def find_item(watchlist, ticker):
    for item in watchlist:
        if item["ticker"].upper() == ticker.upper():
            return item
    return None

def search_in_database(stocks: list, query: str):
    """Cari saham berdasarkan ticker atau nama. Return list of match."""
    q = query.upper().strip()
    matches = []

    for s in stocks:
        ticker = s["ticker"].upper()
        name = s["name"].upper()

        if q == ticker:
            return [s]  # exact ticker match
        if q in ticker:
            matches.append(s)
        elif q in name:
            matches.append(s)

    return matches[:5]  # maksimal 5 hasil

# ========== Format watchlist ==========
def format_watchlist(watchlist):
    if not watchlist:
        return "📋 Watchlist kosong."
    lines = ["📋 *Watchlist:*\n"]
    for item in watchlist:
        lines.append(
            f"*{item['ticker']}* ref Rp {item['reference_price']:,.0f}\n"
            f"  watch {item.get('watch_down',0)}% / +{item.get('watch_up',0)}%\n"
            f"  action {item.get('action_down',0)}% / +{item.get('action_up',0)}%\n"
            f"  panic {item.get('panic_down',0)}% / +{item.get('panic_up',0)}%\n"
        )
    return "\n".join(lines)

# ========== Gemini: tentukan aksi ==========
def tanya_gemini(pesan_user: str, watchlist: list) -> dict:
    prompt = f"""Kamu adalah asisten bot saham. Pengguna mengirim pesan dalam bahasa Indonesia.

Pesan pengguna: "{pesan_user}"

Watchlist saat ini: {json.dumps(watchlist, ensure_ascii=False)}

Tugasmu: tentukan aksi yang dimaksud pengguna. Balas HANYA dengan JSON valid, tanpa teks lain, tanpa markdown.

Format JSON yang diperbolehkan:
- {{"action": "list"}} — lihat watchlist
- {{"action": "add", "ticker": "XXXX", "ref": 5500}} — tambah saham
- {{"action": "remove", "ticker": "XXXX"}} — hapus saham
- {{"action": "set_ref", "ticker": "XXXX", "ref": 5500}} — ubah harga acuan
- {{"action": "set_zone", "ticker": "XXXX", "zone": "watch", "down": -5, "up": 10}} — ubah threshold zona
- {{"action": "cek", "query": "kata kunci"}} — cari saham di database, cek harga, zona beli
- {{"action": "tidak_jelas", "pesan": "penjelasan"}} — kalau tidak yakin

Aturan:
- ticker selalu 4 huruf kapital
- Kalau pengguna minta cek saham (contoh: "cek ANTM", "bagaimana dengan Bank Mandiri"), pakai action "cek" dengan query berisi ticker atau nama
- Kalau pengguna minta tambah saham tanpa harga, pakai "tidak_jelas" dan minta harga
"""

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(2):
            try:
                r = requests.post(url, json=payload, timeout=20)
                if r.status_code == 200:
                    teks = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(teks)
                if r.status_code == 404:
                    last_error = f"{model} tidak tersedia"
                    break
                if r.status_code in (429, 500, 503):
                    last_error = f"{model} error {r.status_code}"
                    if attempt < 1:
                        time.sleep(1 + random.uniform(0, 1))
                        continue
                    break
                raise Exception(f"Gemini error: {r.status_code} {r.text[:200]}")
            except requests.exceptions.Timeout:
                last_error = f"{model} timeout"
                if attempt < 1:
                    time.sleep(1)
                    continue
                break
    raise Exception(f"Gemini gagal: {last_error}")

# ========== Cek saham untuk action "cek" ==========
def cek_saham(query: str) -> str:
    """Cari saham, ambil harga, hitung zona beli."""
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
                lines.append(f"⚠️ *{ticker}* — data harga tidak tersedia.")
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
            lines.append(f"⚠️ *{ticker}* — error: {e}")

    return "\n".join(lines)

# ========== Eksekusi aksi ==========
def eksekusi_aksi(aksi: dict, watchlist: list) -> str:
    action = aksi.get("action")

    if action == "list":
        return format_watchlist(watchlist)

    if action == "add":
        ticker = aksi["ticker"].upper()
        ref = float(aksi["ref"])
        if find_item(watchlist, ticker):
            return f"⚠️ {ticker} sudah ada di watchlist."
        watchlist.append({
            "ticker": ticker,
            "reference_price": ref,
            "watch_down": -5, "watch_up": 10,
            "action_down": -10, "action_up": 20,
            "panic_down": -15, "panic_up": 30
        })
        write_watchlist(watchlist)
        return f"✅ {ticker} ditambahkan dengan ref Rp {ref:,.0f}"

    if action == "remove":
        ticker = aksi["ticker"].upper()
        new_wl = [x for x in watchlist if x["ticker"].upper() != ticker]
        if len(new_wl) == len(watchlist):
            return f"⚠️ {ticker} tidak ditemukan di watchlist."
        write_watchlist(new_wl)
        return f"✅ {ticker} dihapus."

    if action == "set_ref":
        ticker = aksi["ticker"].upper()
        ref = float(aksi["ref"])
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ {ticker} tidak ditemukan."
        item["reference_price"] = ref
        write_watchlist(watchlist)
        return f"✅ {ticker} ref = Rp {ref:,.0f}"

    if action == "set_zone":
        ticker = aksi["ticker"].upper()
        zone = aksi["zone"].lower()
        if zone not in ("watch", "action", "panic"):
            return "⚠️ Zona harus watch, action, atau panic."
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ {ticker} tidak ditemukan."
        item[f"{zone}_down"] = float(aksi["down"])
        item[f"{zone}_up"] = float(aksi["up"])
        write_watchlist(watchlist)
        return f"✅ {ticker} {zone} = {aksi['down']}% / +{aksi['up']}%"

    if action == "cek":
        return cek_saham(aksi["query"])

    if action == "tidak_jelas":
        return f"🤔 {aksi.get('pesan', 'Saya tidak paham. Coba jelaskan lebih spesifik.')}"

    return "⚠️ Aksi tidak dikenal."

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
        if text.startswith("/start") or text.startswith("/help"):
            reply(
                "🤖 *Bot Saham Monitor*\n\n"
                "*Cara pakai (kirim pesan bebas):*\n"
                "• \"lihat watchlist saya\"\n"
                "• \"tambahkan BBCA di 5500\"\n"
                "• \"ubah harga acuan BBCA jadi 5800\"\n"
                "• \"hapus BBRI\"\n"
                "• \"cek ANTM\"\n"
                "• \"bagaimana dengan Bank Mandiri?\""
            )
            return jsonify({"ok": True}), 200

        # Command-based
        if text.startswith("/list"):
            reply(format_watchlist(read_watchlist()))
            return jsonify({"ok": True}), 200

        if text.startswith("/cek"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply("Format: `/cek TICKER` atau `/cek Nama Saham`")
                return jsonify({"ok": True}), 200
            reply(cek_saham(parts[1]))
            return jsonify({"ok": True}), 200

        # Natural language
        watchlist = read_watchlist()
        aksi = tanya_gemini(text, watchlist)
        balasan = eksekusi_aksi(aksi, watchlist)
        reply(balasan)

    except Exception as e:
        reply(f"❌ Error: {e}")

    return jsonify({"ok": True}), 200
