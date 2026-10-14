import os
import json
import io
import asyncio
import time
import random
import urllib.parse
import requests
from flask import Flask, request, jsonify
from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
)

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GIST_ID = os.environ.get("GIST_ID")
GIST_ID_ALL_STOCKS = os.environ.get("GIST_ID_ALL_STOCKS")
GIST_TOKEN = os.environ.get("GIST_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
GITHUB_PAT = os.environ.get("GITHUB_PAT")

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

# ========== Format tampilan ==========
def format_menu_utama():
    return (
        "🤖 *SAHAM MONITOR*\n"
        "_Bot pemantau saham IDX_\n\n"
        "Selamat datang! Saya membantu Anda:\n\n"
        "📋 *KELOLA WATCHLIST*\n"
        "• /list — lihat daftar pantau\n"
        "• /add BBCA 5500 — tambah saham\n"
        "• /remove BBRI — hapus saham\n"
        "• /ref BBCA 5800 — ubah harga acuan\n"
        "• /zone BBCA watch -5 +10 — ubah threshold\n\n"
        "🔍 *CARI & CEK SAHAM*\n"
        "• /cari Bank Mandiri — cari saham\n"
        "• /cek ANTM — cek harga & zona beli\n"
        "• /bandingkan ANTM MDKA — bandingkan 2 saham\n\n"
        "📊 *ANALISIS & REKOMENDASI*\n"
        "• /analisa ANTM — analisis lengkap\n"
        "• /rekomendasi — minta rekomendasi Top 5\n\n"
        "_Bukan rekomendasi investasi._"
    )

def format_sapaan():
    return (
        "👋 *Halo!*\n\n"
        "Saya bot pemantau saham IDX.\n"
        "Kirim perintah dengan awalan `/`.\n\n"
        "Ketik /help untuk lihat menu lengkap.\n"
        "Atau coba: `/cek ANTM`"
    )

def format_watchlist(watchlist):
    if not watchlist:
        return (
            "📋 *WATCHLIST KOSONG*\n\n"
            "Belum ada saham yang dipantau.\n\n"
            "Tambahkan dengan:\n"
            "• /add BBCA 5500\n"
            "• /add BBRI 3000"
        )

    lines = [f"📋 *WATCHLIST ANDA* ({len(watchlist)} saham)\n"]
    for i, item in enumerate(watchlist, 1):
        ticker = item['ticker']
        ref = item['reference_price']
        wd = item.get('watch_down', 0)
        wu = item.get('watch_up', 0)
        ad = item.get('action_down', 0)
        au = item.get('action_up', 0)
        pd = item.get('panic_down', 0)
        pu = item.get('panic_up', 0)

        lines.append(
            f"\n*{i}. {ticker}* — ref Rp {ref:,.0f}\n"
            f"🔵 watch {wd}% / +{wu}%\n"
            f"🟡 action {ad}% / +{au}%\n"
            f"🔴 panic {pd}% / +{pu}%"
        )

    return "\n".join(lines)

# ========== Chart Generator (QuickChart) ==========
def generate_chart_url(ticker: str, period: str = "3mo") -> str:
    import yfinance as yf

    yf_ticker = f"{ticker}.JK"
    t = yf.Ticker(yf_ticker)
    hist = t.history(period=period)

    if hist.empty or len(hist) < 5:
        raise Exception("Data historis tidak cukup")

    labels = [d.strftime("%d/%m") for d in hist.index]
    prices = [round(float(p), 0) for p in hist["Close"]]

    naik = prices[-1] > prices[0]
    color = "rgb(34, 197, 94)" if naik else "rgb(239, 68, 68)"
    bg_color = "rgba(34, 197, 94, 0.1)" if naik else "rgba(239, 68, 68, 0.1)"

    period_label = {"3mo": "3 Bulan", "6mo": "6 Bulan", "1y": "1 Tahun"}.get(period, period)

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": ticker,
                "data": prices,
                "borderColor": color,
                "backgroundColor": bg_color,
                "fill": True,
                "tension": 0.3,
                "pointRadius": 0,
                "borderWidth": 2
            }]
        },
        "options": {
            "title": {
                "display": True,
                "text": f"{ticker} - {period_label}",
                "fontSize": 16
            },
            "scales": {
                "y": {"beginAtZero": False}
            },
            "plugins": {
                "legend": {"display": False}
            }
        }
    }

    config_str = json.dumps(chart_config)
    encoded = urllib.parse.quote(config_str)
    return f"https://quickchart.io/chart?c={encoded}&w=600&h=300&bkg=white"

def get_chart_info(ticker: str, period: str = "3mo"):
    import yfinance as yf

    yf_ticker = f"{ticker}.JK"
    t = yf.Ticker(yf_ticker)
    hist = t.history(period=period)

    if hist.empty:
        return None

    current = float(hist["Close"].iloc[-1])
    high = float(hist["High"].max())
    low = float(hist["Low"].min())
    change = ((current - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])) * 100

    return {
        "current": current,
        "high": high,
        "low": low,
        "change": change
    }

# ========== Inline keyboard ==========
def keyboard_cek(ticker: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Analisa", callback_data=f"analisa:{ticker}"),
            InlineKeyboardButton("📈 Chart", callback_data=f"chart:{ticker}:3mo"),
        ],
        [
            InlineKeyboardButton("➕ Watchlist", callback_data=f"add:{ticker}"),
        ],
    ])

def keyboard_analisa(ticker: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Chart", callback_data=f"chart:{ticker}:3mo"),
            InlineKeyboardButton("➕ Watchlist", callback_data=f"add:{ticker}"),
        ],
    ])

# ========== Cek saham (return text + keyboard) ==========
def cek_saham_data(query: str):
    import yfinance as yf

    stocks = load_all_stocks()
    matches = search_in_database(stocks, query)

    if not matches:
        return (
            f"❌ *Tidak Ditemukan*\n\n"
            f"Kata kunci: `{query}`\n\n"
            f"Coba `/cari {query}` untuk lihat saran.",
            None
        )

    blocks = []
    first_ticker = None
    for s in matches:
        ticker = s["ticker"]
        name = s["name"]
        yf_ticker = f"{ticker}.JK"

        if first_ticker is None:
            first_ticker = ticker

        try:
            t = yf.Ticker(yf_ticker)
            info = t.info
            hist = t.history(period="1y")

            if hist.empty:
                blocks.append(f"⚠️ *{ticker}* — data tidak tersedia.")
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

            blocks.append(
                f"📊 *{ticker}*\n"
                f"_{name}_\n\n"
                f"💰 Harga: *Rp {current:,.0f}*\n"
                f"📈 PE: {pe_str}  |  PBV: {pbv_str}\n"
                f"💵 Dividend: {div_str}\n\n"
                f"🟢 Zona beli: Rp {buy_low:,.0f} – {buy_high:,.0f}\n"
                f"🔴 Batas bawah: Rp {lower:,.0f}\n"
                f"🎯 Batas atas: Rp {upper:,.0f}\n\n"
                f"📉 52w: Rp {low_52w:,.0f} – {high_52w:,.0f}"
            )
        except Exception as e:
            print(f"⚠️ cek_saham error {ticker}: {e}")
            blocks.append(f"⚠️ *{ticker}* — data tidak dapat dimuat.")

    keyboard = keyboard_cek(first_ticker) if first_ticker else None
    return "\n\n".join(blocks), keyboard

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

# ========== Trigger workflow ==========
def trigger_suggest_workflow():
    if not GITHUB_REPO or not GITHUB_PAT:
        raise Exception("GITHUB_REPO atau GITHUB_PAT tidak diatur")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/suggest.yml/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
    }
    payload = {"ref": "main"}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    if r.status_code != 204:
        raise Exception(f"Gagal trigger workflow: {r.status_code}")

# ========== Bandingkan ==========
def bandingkan_saham(ticker1: str, ticker2: str) -> str:
    import yfinance as yf

    def ambil(ticker):
        yf_ticker = f"{ticker}.JK"
        try:
            t = yf.Ticker(yf_ticker)
            info = t.info
            hist = t.history(period="1y")
            if hist.empty or len(hist) < 50:
                return None
            current = float(hist["Close"].iloc[-1])
            high_52w = float(hist["High"].max())
            low_52w = float(hist["Low"].min())
            ma50 = float(hist["Close"].tail(50).mean())

            delta = hist["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = float(rsi.iloc[-1]) if not rsi.empty else None

            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "current": current,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "ma50": ma50,
                "rsi": rsi_val,
                "pe": info.get("trailingPE") or info.get("forwardPE"),
                "pbv": info.get("priceToBook"),
                "div": info.get("dividendYield"),
            }
        except Exception as e:
            print(f"⚠️ bandingkan error {ticker}: {e}")
            return None

    a = ambil(ticker1)
    b = ambil(ticker2)

    if not a or not b:
        return "⚠️ Data untuk salah satu saham tidak dapat dimuat."

    def fmt_div(d):
        if not d:
            return "N/A"
        return f"{d*100:.2f}%" if d < 1 else f"{d:.2f}%"

    def fmt(v, fmt_str=".1f"):
        if v is None:
            return "N/A"
        return f"{v:{fmt_str}}"

    return (
        f"⚖️ *PERBANDINGAN SAHAM*\n\n"
        f"📊 *{a['ticker']}*\n"
        f"_{a['name']}_\n"
        f"💰 Rp {a['current']:,.0f}\n"
        f"📈 PE {fmt(a['pe'])} | PBV {fmt(a['pbv'], '.2f')}\n"
        f"💵 Div {fmt_div(a['div'])}\n"
        f"📉 RSI {fmt(a['rsi'])}\n"
        f"📏 MA50 Rp {a['ma50']:,.0f}\n\n"
        f"📊 *{b['ticker']}*\n"
        f"_{b['name']}_\n"
        f"💰 Rp {b['current']:,.0f}\n"
        f"📈 PE {fmt(b['pe'])} | PBV {fmt(b['pbv'], '.2f')}\n"
        f"💵 Div {fmt_div(b['div'])}\n"
        f"📉 RSI {fmt(b['rsi'])}\n"
        f"📏 MA50 Rp {b['ma50']:,.0f}\n\n"
        f"_Bukan rekomendasi investasi._"
    )

# ========== Handler command ==========
def handle_command(text: str):
    parts = text.split()
    cmd = parts[0].lower()

    if cmd in ("/start", "/help"):
        return format_menu_utama(), None

    if cmd == "/list":
        return format_watchlist(read_watchlist()), None

    if cmd == "/add":
        if len(parts) != 3:
            return ("➕ *TAMBAH SAHAM*\n\n"
                    "Format: `/add TICKER REF`\n\n"
                    "Contoh:\n"
                    "`/add BBCA 5500`\n"
                    "`/add ANTM 3100`"), None
        ticker = parts[1].upper()
        try:
            ref = float(parts[2])
        except ValueError:
            return "❌ REF harus angka. Contoh: `/add BBCA 5500`", None

        watchlist = read_watchlist()
        if find_item(watchlist, ticker):
            return (f"⚠️ *{ticker}* sudah ada di watchlist.\n\n"
                    f"Pakai `/ref {ticker} HARGA` untuk ubah harga acuan."), None
        watchlist.append({
            "ticker": ticker,
            "reference_price": ref,
            "watch_down": -5, "watch_up": 10,
            "action_down": -10, "action_up": 20,
            "panic_down": -15, "panic_up": 30
        })
        write_watchlist(watchlist)
        return (
            f"✅ *{ticker}* ditambahkan!\n\n"
            f"💰 Ref harga: Rp {ref:,.0f}\n"
            f"🔵 Watch: -5% / +10%\n"
            f"🟡 Action: -10% / +20%\n"
            f"🔴 Panic: -15% / +30%\n\n"
            f"_Ubah threshold dengan:_\n"
            f"`/zone {ticker} watch -5 +10`"
        ), None

    if cmd == "/remove":
        if len(parts) != 2:
            return "Format: `/remove TICKER`\nContoh: `/remove BBRI`", None
        ticker = parts[1].upper()
        watchlist = read_watchlist()
        new_wl = [x for x in watchlist if x["ticker"].upper() != ticker]
        if len(new_wl) == len(watchlist):
            return f"⚠️ *{ticker}* tidak ditemukan di watchlist.", None
        write_watchlist(new_wl)
        return f"✅ *{ticker}* dihapus dari watchlist.", None

    if cmd == "/ref":
        if len(parts) != 3:
            return "Format: `/ref TICKER HARGA`\nContoh: `/ref BBCA 5800`", None
        ticker = parts[1].upper()
        try:
            ref = float(parts[2])
        except ValueError:
            return "❌ HARGA harus angka.", None
        watchlist = read_watchlist()
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ *{ticker}* belum ada. Tambah dulu: `/add {ticker} {parts[2]}`", None
        item["reference_price"] = ref
        write_watchlist(watchlist)
        return f"✅ *{ticker}* ref = Rp {ref:,.0f}", None

    if cmd == "/zone":
        if len(parts) != 5:
            return ("🎯 *UBAH THRESHOLD*\n\n"
                    "Format: `/zone TICKER ZONA DOWN UP`\n\n"
                    "Zona: watch / action / panic\n\n"
                    "Contoh:\n"
                    "`/zone BBCA watch -5 +10`\n"
                    "`/zone BBCA panic -15 +30`"), None
        ticker = parts[1].upper()
        zone = parts[2].lower()
        if zone not in ("watch", "action", "panic"):
            return "⚠️ Zona harus: watch, action, atau panic.", None
        try:
            down = float(parts[3])
            up = float(parts[4])
        except ValueError:
            return "❌ DOWN dan UP harus angka. Contoh: -5 +10", None
        watchlist = read_watchlist()
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ *{ticker}* tidak ada di watchlist.", None
        item[f"{zone}_down"] = down
        item[f"{zone}_up"] = up
        write_watchlist(watchlist)

        emoji_zone = {"watch": "🔵", "action": "🟡", "panic": "🔴"}[zone]
        return (
            f"✅ *{ticker}* — {emoji_zone} {zone}\n\n"
            f"⬇️ Turun: {down}%\n"
            f"⬆️ Naik: +{up}%"
        ), None

    if cmd == "/cek":
        if len(parts) < 2:
            return "Format: `/cek TICKER`\nContoh: `/cek ANTM`", None
        query = " ".join(parts[1:])
        text, keyboard = cek_saham_data(query)
        return text, keyboard

    if cmd == "/cari":
        if len(parts) < 2:
            return "Format: `/cari NAMA`\nContoh: `/cari Bank Mandiri`", None
        query = " ".join(parts[1:])
        stocks = load_all_stocks()
        matches = search_in_database(stocks, query)
        if not matches:
            return f"❌ Tidak ada saham dengan nama *{query}*.", None
        lines = [f"🔎 *HASIL PENCARIAN: {query}*\n"]
        for s in matches:
            lines.append(f"• `{s['ticker']}` — {s['name']}")
        lines.append("")
        lines.append("Pakai `/cek TICKER` untuk lihat harga.")
        return "\n".join(lines), None

    if cmd == "/analisa":
        if len(parts) < 2:
            return "Format: `/analisa TICKER`\nContoh: `/analisa ANTM`", None
        ticker = parts[1].upper()

        stocks = load_all_stocks()
        match = None
        for s in stocks:
            if s["ticker"].upper() == ticker:
                match = s
                break

        if not match:
            return f"❌ *{ticker}* tidak ada di database. Cek dengan `/cari NAMA`.", None

        try:
            data = ambil_data_untuk_analisis(ticker)
        except Exception as e:
            print(f"⚠️ ambil_data error: {e}")
            return f"⚠️ Data untuk *{ticker}* tidak dapat dimuat saat ini.", None

        if not data:
            return f"⚠️ Data untuk *{ticker}* tidak cukup untuk dianalisis.", None

        try:
            analisis = analisa_dengan_ai(data)
        except Exception as e:
            print(f"⚠️ analisa error: {e}")
            return ("⚠️ Layanan analisis sedang tidak dapat diakses.\n\n"
                    f"Coba lagi nanti, atau pakai `/cek {ticker}` untuk data mentah."), None

        rsi_str = f"{data['rsi']:.1f}" if data.get("rsi") else "N/A"
        pe_str = f"{data['pe']:.1f}" if data.get('pe') else "N/A"
        pbv_str = f"{data['pbv']:.2f}" if data.get('pbv') else "N/A"

        text = (
            f"📊 *ANALISA {ticker}*\n"
            f"_{data['name']}_\n\n"
            f"💰 Harga: *Rp {data['current_price']:,.0f}*\n"
            f"📈 PE: {pe_str}  |  PBV: {pbv_str}\n"
            f"📉 RSI: {rsi_str}\n\n"
            f"━━━ 🤖 *HASIL ANALISIS* ━━━\n\n"
            f"{analisis}\n\n"
            f"_Bukan rekomendasi investasi._"
        )
        return text, keyboard_analisa(ticker)

    if cmd == "/bandingkan":
        if len(parts) != 3:
            return ("⚖️ *BANDINGKAN SAHAM*\n\n"
                    "Format: `/bandingkan T1 T2`\n\n"
                    "Contoh:\n"
                    "`/bandingkan ANTM MDKA`"), None
        return bandingkan_saham(parts[1].upper(), parts[2].upper()), None

    if cmd == "/rekomendasi":
        try:
            trigger_suggest_workflow()
        except Exception as e:
            print(f"⚠️ trigger workflow error: {e}")
            return ("⚠️ Layanan rekomendasi sedang tidak dapat diakses.\n\n"
                    "Coba lagi beberapa menit lagi."), None
        return (
            "📊 *REKOMENDASI SEDANG DISIAPKAN*\n\n"
            "Screening 100+ saham membutuhkan 3-5 menit.\n\n"
            "Hasil akan dikirim ke chat ini secara otomatis.\n"
            "Mohon tunggu ya. ☕"
        ), None

    return (f"❓ Perintah `{cmd}` tidak dikenal.\n\n"
            f"Kirim `/help` untuk lihat menu."), None

# ========== Handler callback query ==========
def handle_callback(callback):
    data = callback.data or ""
    parts = data.split(":")
    action = parts[0] if parts else ""

    chat_id = callback.message.chat_id
    bot = Bot(BOT_TOKEN)

    def answer(text=""):
        try:
            asyncio.run(bot.answer_callback_query(callback.id, text=text))
        except:
            pass

    def reply_text(text, keyboard=None):
        try:
            asyncio.run(bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            ))
        except Exception as e:
            print(f"⚠️ reply_text error: {e}")

    try:
        # ========== ANALISA ==========
        if action == "analisa" and len(parts) == 2:
            ticker = parts[1].upper()
            answer("Menyiapkan analisis...")

            # Loading
            try:
                loading_msg = asyncio.run(bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ Menganalisis *{ticker}*...\n_Mohon tunggu 5-15 detik._",
                    parse_mode="Markdown"
                ))
                loading_id = loading_msg.message_id
            except:
                loading_id = None

            # Ambil data
            try:
                data_analisis = ambil_data_untuk_analisis(ticker)
            except Exception as e:
                print(f"⚠️ ambil_data error: {e}")
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"⚠️ Data *{ticker}* tidak dapat dimuat."
                        ))
                    except:
                        pass
                return

            if not data_analisis:
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"⚠️ Data *{ticker}* tidak cukup."
                        ))
                    except:
                        pass
                return

            # Generate analisis AI
            try:
                analisis = analisa_dengan_ai(data_analisis)
            except Exception as e:
                print(f"⚠️ analisa error: {e}")
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text="⚠️ Layanan analisis sedang tidak dapat diakses."
                        ))
                    except:
                        pass
                return

            # Hapus loading
            if loading_id:
                try:
                    asyncio.run(bot.delete_message(chat_id=chat_id, message_id=loading_id))
                except:
                    pass

            # Kirim hasil — kalau timeout, jangan kirim error
            rsi_str = f"{data_analisis['rsi']:.1f}" if data_analisis.get("rsi") else "N/A"
            pe_str = f"{data_analisis['pe']:.1f}" if data_analisis.get('pe') else "N/A"
            pbv_str = f"{data_analisis['pbv']:.2f}" if data_analisis.get('pbv') else "N/A"

            text = (
                f"📊 *ANALISA {ticker}*\n"
                f"_{data_analisis['name']}_\n\n"
                f"💰 Harga: *Rp {data_analisis['current_price']:,.0f}*\n"
                f"📈 PE: {pe_str}  |  PBV: {pbv_str}\n"
                f"📉 RSI: {rsi_str}\n\n"
                f"━━━ 🤖 *HASIL ANALISIS* ━━━\n\n"
                f"{analisis}\n\n"
                f"_Bukan rekomendasi investasi._"
            )

            try:
                asyncio.run(bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard_analisa(ticker)
                ))
                print(f"✅ Analisa {ticker} terkirim")
            except Exception as e:
                print(f"⚠️ send analisa error: {e}")
            return

        # ========== CHART ==========
        if action == "chart" and len(parts) == 3:
            ticker = parts[1].upper()
            period = parts[2]
            answer("⏳ Menyiapkan chart...")

            period_label = {"3mo": "3 Bulan", "6mo": "6 Bulan", "1y": "1 Tahun"}.get(period, period)

            # Loading
            try:
                loading_msg = asyncio.run(bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ Menyiapkan chart *{ticker}* ({period_label})...",
                    parse_mode="Markdown"
                ))
                loading_id = loading_msg.message_id
            except:
                loading_id = None

            # Generate chart URL + info
            try:
                chart_url = generate_chart_url(ticker, period)
                info = get_chart_info(ticker, period)
            except Exception as e:
                print(f"⚠️ chart error: {e}")
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"⚠️ Chart *{ticker}* tidak dapat dibuat saat ini."
                        ))
                    except:
                        pass
                return

            if not info:
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"⚠️ Data historis *{ticker}* tidak tersedia."
                        ))
                    except:
                        pass
                return

            arah = "naik" if info["change"] > 0 else "turun"
            caption = (
                f"📈 *{ticker}* — {period_label} Terakhir\n\n"
                f"💰 Sekarang: Rp {info['current']:,.0f}\n"
                f"📊 Perubahan: {info['change']:+.2f}% ({arah})\n"
                f"🔺 Tertinggi: Rp {info['high']:,.0f}\n"
                f"🔻 Terendah: Rp {info['low']:,.0f}"
            )

            # Download dari QuickChart
            download_ok = False
            photo_bytes = None
            try:
                r = requests.get(chart_url, timeout=6)
                if r.status_code == 200:
                    photo_bytes = io.BytesIO(r.content)
                    download_ok = True
                    print("✅ Chart didownload")
                else:
                    print(f"⚠️ QuickChart status: {r.status_code}")
            except Exception as e:
                print(f"⚠️ download chart error: {e}")

            if not download_ok:
                # Benar-benar gagal download — edit loading jadi link
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"{caption}\n\n📊 [Buka Chart]({chart_url})",
                            parse_mode="Markdown"
                        ))
                        print("✅ Fallback link dikirim")
                    except Exception as e:
                        print(f"⚠️ fallback edit error: {e}")
                return

            # Download OK — kirim foto. Kalau timeout, jangan kirim error
            try:
                asyncio.run(bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_bytes,
                    caption=caption,
                    parse_mode="Markdown"
                ))
                print(f"✅ Chart {ticker} terkirim")

                # Hapus loading
                if loading_id:
                    try:
                        asyncio.run(bot.delete_message(chat_id=chat_id, message_id=loading_id))
                    except:
                        pass
            except Exception as e:
                print(f"⚠️ send_photo error: {e}")
                # Coba fallback edit jadi link
                if loading_id:
                    try:
                        asyncio.run(bot.edit_message_text(
                            chat_id=chat_id, message_id=loading_id,
                            text=f"{caption}\n\n📊 [Buka Chart]({chart_url})",
                            parse_mode="Markdown"
                        ))
                    except:
                        pass
            return

        # ========== ADD WATCHLIST ==========
        if action == "add" and len(parts) == 2:
            ticker = parts[1].upper()
            answer("Menambahkan...")

            # STEP 1: Ambil harga + tulis ke Gist
            # Kalau berhasil, JANGAN kirim pesan gagal meski step 2 timeout
            ref = None
            try:
                import yfinance as yf
                t = yf.Ticker(f"{ticker}.JK")
                hist = t.history(period="1d")
                if hist.empty:
                    reply_text(f"⚠️ Harga *{ticker}* tidak tersedia.")
                    return
                ref = float(hist["Close"].iloc[-1])

                watchlist = read_watchlist()
                if find_item(watchlist, ticker):
                    reply_text(f"⚠️ *{ticker}* sudah ada di watchlist.")
                    return

                watchlist.append({
                    "ticker": ticker,
                    "reference_price": round(ref, 0),
                    "watch_down": -5, "watch_up": 10,
                    "action_down": -10, "action_up": 20,
                    "panic_down": -15, "panic_up": 30
                })
                write_watchlist(watchlist)
                print(f"✅ {ticker} tertulis ke Gist, ref Rp {ref:,.0f}")
            except Exception as e:
                print(f"⚠️ add error: {e}")
                # Gagal di step ini = benar-benar gagal, kirim error
                reply_text(f"⚠️ Gagal menambahkan *{ticker}*.")
                return

            # STEP 2: Kirim konfirmasi — kalau timeout, jangan kirim error
            try:
                asyncio.run(bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ *{ticker}* ditambahkan!\n\n"
                        f"💰 Ref: Rp {ref:,.0f} (harga saat ini)\n"
                        f"🔵 Watch: -5% / +10%\n"
                        f"🟡 Action: -10% / +20%\n"
                        f"🔴 Panic: -15% / +30%\n\n"
                        f"_Ubah threshold:_\n"
                        f"`/zone {ticker} watch -5 +10`"
                    ),
                    parse_mode="Markdown"
                ))
                print(f"✅ Konfirmasi {ticker} terkirim")
            except Exception as e:
                print(f"⚠️ send konfirmasi error: {e}")
                # Jangan kirim pesan error — Gist sudah tertulis
            return

        answer("Aksi tidak dikenal.")

    except Exception as e:
        print(f"❌ callback handler error: {e}")

# ========== Webhook ==========
@app.route("/api/webhook", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), Bot(BOT_TOKEN))

    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return jsonify({"ok": False}), 403

    if update.callback_query:
        handle_callback(update.callback_query)
        return jsonify({"ok": True}), 200

    msg = update.message
    if not msg or not msg.text:
        return jsonify({"ok": True}), 200

    text = msg.text.strip()
    bot = Bot(BOT_TOKEN)

    def reply(t, keyboard=None):
        try:
            asyncio.run(bot.send_message(
                chat_id=msg.chat_id,
                text=t,
                parse_mode="Markdown",
                reply_markup=keyboard
            ))
        except Exception as e:
            print(f"⚠️ reply error: {e}")

    try:
        if not text.startswith("/"):
            reply(format_sapaan())
            return jsonify({"ok": True}), 200

        balasan, keyboard = handle_command(text)
        reply(balasan, keyboard)

    except Exception as e:
        print(f"❌ handler error: {e}")
        try:
            reply("❌ Terjadi kesalahan. Silakan coba lagi.")
        except:
            pass

    return jsonify({"ok": True}), 200
