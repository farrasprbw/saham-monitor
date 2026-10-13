import asyncio
import os
import json
import requests
import yfinance as yf

# ========== 1. Konfigurasi tampilan tiap zona ==========
ZONE_STYLE = {
    "watch":  {"emoji": "🔵", "label": "ZONA PANTAU",   "prefix": "Informasi"},
    "action": {"emoji": "🟡", "label": "ZONA AKSI",     "prefix": "Perhatian"},
    "panic":  {"emoji": "🔴", "label": "ZONA DARURAT",  "prefix": "URGENT"},
}

# Prioritas zona — makin tinggi, makin urgent
ZONE_PRIORITY = {"panic": 3, "action": 2, "watch": 1}

# ========== 2. Fungsi Kirim Notifikasi Telegram ==========
def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Variabel lingkungan Telegram tidak diatur, lewati notifikasi")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Notifikasi Telegram berhasil dikirim")
        else:
            print(f"❌ Notifikasi Telegram gagal: {response.text}")
    except Exception as e:
        print(f"❌ Notifikasi Telegram error: {e}")

# ========== 3. Fungsi Cek Satu Rule ==========
def check_rule(rule: dict, current_price: float):
    direction = rule["direction"]
    threshold = rule["threshold"]

    if direction == "decrease" and current_price < threshold:
        return True, f"turun melewati Rp {threshold:,}"
    if direction == "increase" and current_price > threshold:
        return True, f"naik melewati Rp {threshold:,}"

    return False, ""

# ========== 4. Fungsi Ambil Harga dari Yahoo Finance ==========
def get_stock_price(ticker: str):
    """Ambil harga saham dari Yahoo Finance. Return (price, name) atau (None, None)."""
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

# ========== 5. Fungsi Utama Monitoring ==========
async def main():
    with open("watchlist.json", "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    print(f"📊 Mulai memantau {len(watchlist)} saham...")

    for item in watchlist:
        ticker = item["ticker"]
        rules = item.get("rules", [])

        print(f"\n🔍 Memeriksa {ticker}...")

        current_price, stock_name = get_stock_price(ticker)

        if current_price is None:
            print(f"   ⚠️ Gagal mengambil harga {ticker}, lewati")
            continue

        try:
            current_price = float(current_price)
        except (ValueError, TypeError):
            print(f"   ⚠️ Harga {ticker} bukan angka: {current_price}")
            continue

        print(f"   {stock_name} ({ticker}): Rp {current_price:,.0f}")

        # ========== Cek semua rule, kumpulkan yang terpicu ==========
        hit_rules = []
        for rule in rules:
            hit, condition_text = check_rule(rule, current_price)
            if hit:
                hit_rules.append((rule["zone"], condition_text))

        if not hit_rules:
            print(f"   ⏳ Tidak ada rule yang terpicu")
            continue

        # ========== Hanya kirim SATU notifikasi — zona paling urgent ==========
        hit_rules.sort(key=lambda x: ZONE_PRIORITY.get(x[0], 0), reverse=True)

        zone, condition_text = hit_rules[0]  # Ambil yang paling urgent
        style = ZONE_STYLE.get(zone, ZONE_STYLE["watch"])

        # Info tambahan: berapa zona yang terlewati
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
        print(f"   ✅ Notifikasi [{zone}] dikirim (total {len(hit_rules)} zona terpicu)")

    print("\n✅ Selesai memeriksa semua saham.")

if __name__ == "__main__":
    asyncio.run(main())
