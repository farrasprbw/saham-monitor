import asyncio
import os
import json
import requests
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ========== 1. Konfigurasi tampilan tiap zona ==========
ZONE_STYLE = {
    "watch":  {"emoji": "🔵", "label": "ZONA PANTAU",   "prefix": "Informasi"},
    "action": {"emoji": "🟡", "label": "ZONA AKSI",     "prefix": "Perhatian"},
    "panic":  {"emoji": "🔴", "label": "ZONA DARURAT",  "prefix": "URGENT"},
}

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

# ========== 3. Baca watchlist dari Google Sheets ==========
def load_watchlist_from_sheets():
    """Baca watchlist dari Google Sheets. Return list of dict."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")

    if not creds_json or not spreadsheet_id:
        print("⚠️ GOOGLE_CREDENTIALS atau SPREADSHEET_ID tidak diatur")
        return []

    try:
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(spreadsheet_id).worksheet("watchlist")
        rows = sheet.get_all_records()

        watchlist = []
        for row in rows:
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                continue

            try:
                ref_price = float(row.get("reference_price", 0))
            except (ValueError, TypeError):
                print(f"⚠️ reference_price invalid untuk {ticker}, lewati")
                continue

            def get_pct(key):
                try:
                    return float(row.get(key, 0))
                except (ValueError, TypeError):
                    return 0

            rules = [
                {"zone": "watch",  "direction": "decrease", "pct": get_pct("watch_down")},
                {"zone": "watch",  "direction": "increase", "pct": get_pct("watch_up")},
                {"zone": "action", "direction": "decrease", "pct": get_pct("action_down")},
                {"zone": "action", "direction": "increase", "pct": get_pct("action_up")},
                {"zone": "panic",  "direction": "decrease", "pct": get_pct("panic_down")},
                {"zone": "panic",  "direction": "increase", "pct": get_pct("panic_up")},
            ]
            # Buang rule yang pct-nya 0 (tidak diaktifkan)
            rules = [r for r in rules if r["pct"] != 0]

            watchlist.append({
                "ticker": ticker,
                "reference_price": ref_price,
                "rules": rules
            })

        return watchlist

    except Exception as e:
        print(f"❌ Error baca Google Sheets: {e}")
        return []

# ========== 4. Fungsi Cek Satu Rule (pakai persentase) ==========
def check_rule(rule: dict, current_price: float, reference_price: float):
    direction = rule["direction"]
    pct = rule["pct"]
    threshold = reference_price * (1 + pct / 100)

    if direction == "decrease" and current_price < threshold:
        return True, f"turun {abs(pct)}% dari Rp {reference_price:,.0f} (level Rp {threshold:,.0f})"
    if direction == "increase" and current_price > threshold:
        return True, f"naik {pct}% dari Rp {reference_price:,.0f} (level Rp {threshold:,.0f})"

    return False, ""

# ========== 5. Fungsi Ambil Harga dari Yahoo Finance ==========
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

# ========== 6. Fungsi Utama Monitoring ==========
async def main():
    watchlist = load_watchlist_from_sheets()

    if not watchlist:
        print("⚠️ Watchlist kosong atau gagal dibaca, berhenti.")
        return

    print(f"📊 Mulai memantau {len(watchlist)} saham...")

    for item in watchlist:
        ticker = item["ticker"]
        reference_price = item["reference_price"]
        rules = item["rules"]

        print(f"\n🔍 Memeriksa {ticker} (ref: Rp {reference_price:,.0f})...")

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

        # Cek semua rule
        hit_rules = []
        for rule in rules:
            hit, condition_text = check_rule(rule, current_price, reference_price)
            if hit:
                hit_rules.append((rule["zone"], condition_text))

        if not hit_rules:
            print(f"   ⏳ Tidak ada rule yang terpicu")
            continue

        # Hanya kirim satu notifikasi — zona paling urgent
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
        print(f"   ✅ Notifikasi [{zone}] dikirim (total {len(hit_rules)} zona terpicu)")

    print("\n✅ Selesai memeriksa semua saham.")

if __name__ == "__main__":
    asyncio.run(main())
