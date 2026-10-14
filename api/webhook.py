import os
import json
import requests
from flask import Flask, request, jsonify
from telegram import Update, Bot

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GIST_ID = os.environ.get("GIST_ID")
GIST_TOKEN = os.environ.get("GIST_TOKEN")

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

# ========== Cari item berdasarkan ticker ==========
def find_item(watchlist, ticker):
    for item in watchlist:
        if item["ticker"].upper() == ticker.upper():
            return item
    return None

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
        bot.send_message(chat_id=msg.chat_id, text=t, parse_mode="Markdown")

    try:
        # /start atau /help
        if text.startswith("/start") or text.startswith("/help"):
            reply(
                "🤖 *Bot Saham Monitor*\n\n"
                "/list — lihat watchlist\n"
                "/add TICKER REF — tambah saham\n"
                "/remove TICKER — hapus saham\n"
                "/set TICKER ref PRICE — ubah ref\n"
                "/set TICKER watch -5 +10\n"
                "/set TICKER action -10 +20\n"
                "/set TICKER panic -15 +30"
            )
            return jsonify({"ok": True}), 200

        # /list
        if text.startswith("/list"):
            watchlist = read_gist()
            if not watchlist:
                reply("📋 Watchlist kosong.")
                return jsonify({"ok": True}), 200
            lines = ["📋 *Watchlist:*\n"]
            for item in watchlist:
                lines.append(
                    f"*{item['ticker']}* ref Rp {item['reference_price']:,.0f}\n"
                    f"  watch {item.get('watch_down',0)}% / +{item.get('watch_up',0)}%\n"
                    f"  action {item.get('action_down',0)}% / +{item.get('action_up',0)}%\n"
                    f"  panic {item.get('panic_down',0)}% / +{item.get('panic_up',0)}%\n"
                )
            reply("\n".join(lines))
            return jsonify({"ok": True}), 200

        # /add TICKER REF
        if text.startswith("/add"):
            parts = text.split()
            if len(parts) != 3:
                reply("Format: `/add TICKER REF`\nContoh: `/add BBCA 5925`")
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
                "ticker": ticker,
                "reference_price": ref,
                "watch_down": -5, "watch_up": 10,
                "action_down": -10, "action_up": 20,
                "panic_down": -15, "panic_up": 30
            })
            write_gist(watchlist)
            reply(f"✅ {ticker} ditambahkan dengan ref Rp {ref:,.0f}")
            return jsonify({"ok": True}), 200

        # /remove TICKER
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

        # /set TICKER FIELD VALUE [VALUE2]
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

    except Exception as e:
        reply(f"❌ Error: {e}")

    return jsonify({"ok": True}), 200
