import asyncio
import os
import json
import requests
import yfinance as yf

ZONE_STYLE = {
    "watch":  {"emoji": "🔵", "label": "ZONA PANTAU",   "prefix": "Informasi"},
    "action": {"emoji": "🟡", "label": "ZONA AKSI",     "prefix": "Perhatian"},
    "panic":  {"emoji": "🔴", "label": "ZONA DARURAT",  "prefix": "URGENT"},
}

ZONE_PRIORITY = {"panic": 3, "action": 2, "watch": 1}

def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ Telegram tidak diatur")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
        if r.status_code != 200:
            print(f"❌ Telegram gagal: {r.text}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def load_watchlist_from_gist():
    gist_id = os.environ.get("GIST_ID")
    gist_token = os.environ.get("GIST_TOKEN")

    if not gist_id:
        print("⚠️ GIST_ID tidak diatur")
        return []

    url = f"https://api.github.com/gists/{gist_id}"
    headers = {"Accept": "application/vnd.github+json"}
    if gist_token:
        headers["Authorization"] = f"Bearer {gist_token}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"❌ Gagal baca Gist: {r.status_code}")
            return []
        data = r.json()
        files = data.get("files", {})
        if "watchlist.json" not in files:
            print("⚠️ File watchlist.json tidak ditemukan di Gist")
            return []
        content = files["watchlist.json"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"❌ Error baca Gist: {e}")
        return []

def check_rule(rule: dict, current_price: float, reference_price: float):
    direction = rule["direction"]
    pct = rule["pct"]
    threshold = reference_price * (1 + pct / 100)

    if direction == "decrease" and current_price < threshold:
        return True, f"turun {abs(pct)}% dari Rp {reference_price:,.0f} (level Rp {threshold:,.0f})"
    if direction == "increase" and current_price > threshold:
        return True, f"naik {pct}% dari Rp {reference_price:,.0f} (level Rp {threshold:,.0f})"
    return False, ""

def get_stock_price(ticker: str):
    yf_ticker = f"{ticker}.JK"
    try:
        stock = yf.Ticker(yf_ticker)
        info = stock.info
        price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("previousClose")
        )
        name = info.get("longName") or info.get("shortName") or ticker
        if price is None:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return price, name
    except Exception as e:
        print(f"   ⚠️ Error yfinance untuk {ticker}: {e}")
        return None, None

def build_rules(item: dict):
    rules = []
    mapping = [
        ("watch", "decrease", item.get("watch_down", 0)),
        ("watch", "increase", item.get("watch_up", 0)),
        ("action", "decrease", item.get("action_down", 0)),
        ("action", "increase", item.get("action_up", 0)),
        ("panic", "decrease", item.get("panic_down", 0)),
        ("panic", "increase", item.get("panic_up", 0)),
    ]
    for zone, direction, pct in mapping:
        if pct != 0:
            rules.append({"zone": zone, "direction": direction, "pct": float(pct)})
    return rules

async def main():
    watchlist = load_watchlist_from_gist()

    if not watchlist:
        print("⚠️ Watchlist kosong atau gagal dibaca, berhenti.")
        return

    print(f"📊 Mulai memantau {len(watchlist)} saham...")

    for item in watchlist:
        ticker = item["ticker"]
        reference_price = float(item["reference_price"])
        rules = build_rules(item)

        print(f"\n🔍 Memeriksa {ticker} (ref: Rp {reference_price:,.0f})...")

        current_price, stock_name = get_stock_price(ticker)

        if current_price is None:
            print(f"   ⚠️ Gagal mengambil harga {ticker}, lewati")
            continue

        try:
            current_price = float(current_price)
        except (ValueError, TypeError):
            continue

        print(f"   {stock_name} ({ticker}): Rp {current_price:,.0f}")

        hit_rules = []
        for rule in rules:
            hit, condition_text = check_rule(rule, current_price, reference_price)
            if hit:
                hit_rules.append((rule["zone"], condition_text))

        if not hit_rules:
            print(f"   ⏳ Tidak ada rule yang terpicu")
            continue

        hit_rules.sort(key=lambda x: ZONE_PRIORITY.get(x[0], 0), reverse=True)
        zone, condition_text = hit_rules[0]
        style = ZONE_STYLE.get(zone, ZONE_STYLE["watch"])

        zones_passed = [z for z, _ in hit_rules]
        extra_info = ""
        if len(hit_rules) > 1:
            extra_info = f"\n📊 Melewati {len(hit_rules)} zona: {', '.join(zones_passed)}"

        message = (
            f"{style['emoji']} *{style['label']}*\n"
            f"{style['prefix']} — {stock_name} ({ticker})\n\n"
            f"💰 Harga saat ini: Rp {current_price:,.0f}\n"
            f"🎯 Kondisi: {condition_text}"
            f"{extra_info}\n\n"
            f"⏰ Segera cek aplikasi sekuritas Anda."
        )
        send_telegram(message)
        print(f"   ✅ Notifikasi [{zone}] dikirim")

    print("\n✅ Selesai.")

if __name__ == "__main__":
    asyncio.run(main())
