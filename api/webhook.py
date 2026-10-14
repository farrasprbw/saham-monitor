import os
import json
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update, Bot

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GIST_ID = os.environ.get("GIST_ID")
GIST_ID_ALL_STOCKS = os.environ.get("GIST_ID_ALL_STOCKS")
GIST_TOKEN = os.environ.get("GIST_TOKEN")

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
            lines.append(f"⚠️ *{ticker}* — error: {e}")

    return "\n".join(lines)

# ========== Handler command ==========
def handle_command(text: str) -> str:
    parts = text.split()
    cmd = parts[0].lower()

    # /start atau /help
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
            "   Contoh: `/cari Bank Mandiri`"
        )

    # /list
    if cmd == "/list":
        return format_watchlist(read_watchlist())

    # /add TICKER REF
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

    # /remove TICKER
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

    # /ref TICKER HARGA
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

    # /zone TICKER ZONA DOWN UP
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

    # /cek TICKER atau /cek NAMA
    if cmd == "/cek":
        if len(parts) < 2:
            return "Format: `/cek TICKER`\nContoh: `/cek ANTM`"
        query = " ".join(parts[1:])
        return cek_saham(query)

    # /cari NAMA
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
            # Kalau user kirim pesan tanpa "/", arahkan ke /help
            reply(
                "ℹ️ Kirim perintah dengan awalan `/`.\n\n"
                "Contoh:\n"
                "• `/list` — lihat watchlist\n"
                "• `/add BBCA 5500` — tambah saham\n"
                "• `/cek ANTM` — cek harga saham\n\n"
                "Kirim `/help` untuk daftar lengkap."
            )
            return jsonify({"ok": True}), 200

        balasan = handle_command(text)
        reply(balasan)

    except Exception as e:
        reply(f"❌ Error: {e}")

    return jsonify({"ok": True}), 200
