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
GIST_TOKEN = os.environ.get("GIST_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ========== Fungsi baca/tulis Gist ==========
def read_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Accept": "application/vnd.github+json"}
    if GIST_TOKEN:
        headers["Authorization"] = f"Bearer {GIST_TOKEN}"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal baca Gist: {r.status_code}")
    content = r.json()["files"]["watchlist.json"]["content"]
    return json.loads(content)

def write_gist(watchlist):
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
        raise Exception(f"Gagal tulis Gist: {r.status_code} {r.text}")

def find_item(watchlist, ticker):
    for item in watchlist:
        if item["ticker"].upper() == ticker.upper():
            return item
    return None

# ========== Format watchlist jadi teks ==========
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

# ========== Tanya Gemini (dengan retry) ==========
def tanya_gemini(pesan_user: str, watchlist: list, max_retries: int = 3) -> dict:
    prompt = f"""Kamu adalah asisten bot saham. Pengguna mengirim pesan dalam bahasa Indonesia (bisa formal, santai, atau campur Inggris).

Pesan pengguna: "{pesan_user}"

Watchlist saat ini: {json.dumps(watchlist, ensure_ascii=False)}

Tugasmu: tentukan aksi yang dimaksud pengguna. Balas HANYA dengan JSON valid, tanpa teks lain, tanpa markdown, tanpa penjelasan.

Format JSON yang diperbolehkan:
- {{"action": "list"}} — pengguna ingin lihat watchlist
- {{"action": "add", "ticker": "XXXX", "ref": 5500}} — tambah saham (ref = harga acuan, angka)
- {{"action": "remove", "ticker": "XXXX"}} — hapus saham
- {{"action": "set_ref", "ticker": "XXXX", "ref": 5500}} — ubah harga acuan
- {{"action": "set_zone", "ticker": "XXXX", "zone": "watch", "down": -5, "up": 10}} — ubah threshold zona (zone: watch/action/panic)
- {{"action": "tidak_jelas", "pesan": "penjelasan singkat"}} — kalau tidak yakin

Aturan:
- ticker selalu 4 huruf kapital (BBCA, BBRI, dst)
- ref, down, up selalu angka (bisa negatif untuk down)
- Kalau pengguna minta tambah saham tapi tidak sebut harga, pakai action "tidak_jelas" dan minta harga
- Kalau pengguna minta ubah threshold tapi tidak sebut zona, tanya zona mana
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, timeout=20)

            # Sukses
            if r.status_code == 200:
                teks = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(teks)

            # Error sementara (503, 429, 500) — coba lagi
            if r.status_code in (429, 500, 503):
                last_error = f"Gemini error {r.status_code}"
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⚠️ Gemini {r.status_code}, retry dalam {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                raise Exception(f"Gemini error {r.status_code}: {r.text[:200]}")

            # Error permanen (401, 404) — langsung lempar
            raise Exception(f"Gemini error: {r.status_code} {r.text[:200]}")

        except requests.exceptions.Timeout:
            last_error = "Timeout"
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Gemini timeout, retry dalam {delay:.1f}s...")
                time.sleep(delay)
                continue
            raise Exception("Gemini timeout setelah beberapa kali percobaan.")

    raise Exception(f"Gemini gagal setelah {max_retries} percobaan: {last_error}")

# ========== Eksekusi aksi dari Gemini ==========
def eksekusi_aksi(aksi: dict, watchlist: list) -> str:
    """Return pesan balasan."""
    action = aksi.get("action")

    if action == "list":
        return format_watchlist(watchlist)

    if action == "add":
        ticker = aksi["ticker"].upper()
        ref = float(aksi["ref"])
        if find_item(watchlist, ticker):
            return f"⚠️ {ticker} sudah ada di watchlist. Pakai 'ubah harga acuan {ticker} jadi X' kalau mau update."
        watchlist.append({
            "ticker": ticker,
            "reference_price": ref,
            "watch_down": -5, "watch_up": 10,
            "action_down": -10, "action_up": 20,
            "panic_down": -15, "panic_up": 30
        })
        write_gist(watchlist)
        return f"✅ {ticker} ditambahkan dengan ref Rp {ref:,.0f}"

    if action == "remove":
        ticker = aksi["ticker"].upper()
        new_watchlist = [x for x in watchlist if x["ticker"].upper() != ticker]
        if len(new_watchlist) == len(watchlist):
            return f"⚠️ {ticker} tidak ditemukan di watchlist."
        write_gist(new_watchlist)
        return f"✅ {ticker} dihapus dari watchlist."

    if action == "set_ref":
        ticker = aksi["ticker"].upper()
        ref = float(aksi["ref"])
        item = find_item(watchlist, ticker)
        if not item:
            return f"⚠️ {ticker} tidak ditemukan. Tambahkan dulu dengan 'tambahkan {ticker} di X'."
        item["reference_price"] = ref
        write_gist(watchlist)
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
        write_gist(watchlist)
        return f"✅ {ticker} {zone} = {aksi['down']}% / +{aksi['up']}%"

    if action == "tidak_jelas":
        return f"🤔 {aksi.get('pesan', 'Saya tidak paham maksudnya. Coba jelaskan lebih spesifik.')}"

    return "⚠️ Aksi tidak dikenal."

# ========== Webhook handler ==========
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
        # ========== Command-based (kalau diawali /) ==========
        if text.startswith("/"):
            if text.startswith("/start") or text.startswith("/help"):
                reply(
                    "🤖 *Bot Saham Monitor*\n\n"
                    "*Cara pakai:*\n"
                    "Kirim pesan bebas, contoh:\n"
                    "• \"tambahkan BBCA di 5500\"\n"
                    "• \"lihat watchlist saya\"\n"
                    "• \"ubah harga acuan BBCA jadi 5800\"\n"
                    "• \"hapus BBRI\"\n\n"
                    "*Atau pakai command:*\n"
                    "/list — lihat watchlist\n"
                    "/add TICKER REF\n"
                    "/remove TICKER\n"
                    "/set TICKER ref PRICE\n"
                    "/set TICKER watch -5 +10"
                )
                return jsonify({"ok": True}), 200

            if text.startswith("/list"):
                reply(format_watchlist(read_gist()))
                return jsonify({"ok": True}), 200

            if text.startswith("/add"):
                parts = text.split()
                if len(parts) != 3:
                    reply("Format: `/add TICKER REF`\nContoh: `/add BBCA 5500`")
                    return jsonify({"ok": True}), 200
                ticker = parts[1].upper()
                try:
                    ref = float(parts[2])
                except ValueError:
                    reply("❌ REF harus angka.")
                    return jsonify({"ok": True}), 200
                watchlist = read_gist()
                if find_item(watchlist, ticker):
                    reply(f"⚠️ {ticker} sudah ada.")
                    return jsonify({"ok": True}), 200
                watchlist.append({
                    "ticker": ticker, "reference_price": ref,
                    "watch_down": -5, "watch_up": 10,
                    "action_down": -10, "action_up": 20,
                    "panic_down": -15, "panic_up": 30
                })
                write_gist(watchlist)
                reply(f"✅ {ticker} ditambahkan dengan ref Rp {ref:,.0f}")
                return jsonify({"ok": True}), 200

            if text.startswith("/remove"):
                parts = text.split()
                if len(parts) != 2:
                    reply("Format: `/remove TICKER`")
                    return jsonify({"ok": True}), 200
                ticker = parts[1].upper()
                watchlist = read_gist()
                new_watchlist = [x for x in watchlist if x["ticker"].upper() != ticker]
                if len(new_watchlist) == len(watchlist):
                    reply(f"⚠️ {ticker} tidak ditemukan.")
                    return jsonify({"ok": True}), 200
                write_gist(new_watchlist)
                reply(f"✅ {ticker} dihapus.")
                return jsonify({"ok": True}), 200

            if text.startswith("/set"):
                parts = text.split()
                if len(parts) < 4:
                    reply("Format:\n`/set TICKER ref PRICE`\n`/set TICKER watch -5 +10`")
                    return jsonify({"ok": True}), 200
                ticker = parts[1].upper()
                field = parts[2].lower()
                values = parts[3:]
                watchlist = read_gist()
                item = find_item(watchlist, ticker)
                if not item:
                    reply(f"⚠️ {ticker} tidak ditemukan.")
                    return jsonify({"ok": True}), 200
                if field == "ref":
                    item["reference_price"] = float(values[0])
                    reply(f"✅ {ticker} ref = Rp {float(values[0]):,.0f}")
                elif field in ("watch", "action", "panic"):
                    if len(values) != 2:
                        reply(f"Format: `/set {ticker} {field} -5 +10`")
                        return jsonify({"ok": True}), 200
                    item[f"{field}_down"] = float(values[0])
                    item[f"{field}_up"] = float(values[1])
                    reply(f"✅ {ticker} {field} = {values[0]}% / +{values[1]}%")
                else:
                    reply(f"⚠️ Field '{field}' tidak dikenal.")
                    return jsonify({"ok": True}), 200
                write_gist(watchlist)
                return jsonify({"ok": True}), 200

            reply("Perintah tidak dikenal. Kirim /start untuk bantuan.")
            return jsonify({"ok": True}), 200

        # ========== Natural language (bukan command) ==========
        watchlist = read_gist()
        aksi = tanya_gemini(text, watchlist)
        balasan = eksekusi_aksi(aksi, watchlist)
        reply(balasan)

    except Exception as e:
        reply(f"❌ Error: {e}")

    return jsonify({"ok": True}), 200
