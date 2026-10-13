import asyncio
import os
import json
import requests
from fastmcp import Client

ZONE_STYLE = {
    "watch":  {"emoji": "🔵", "label": "ZONA PANTAU",   "prefix": "Informasi"},
    "action": {"emoji": "🟡", "label": "ZONA AKSI",     "prefix": "Perhatian"},
    "panic":  {"emoji": "🔴", "label": "ZONA DARURAT",  "prefix": "URGENT"},
}

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

def check_rule(rule: dict, current_price: float):
    direction = rule["direction"]
    threshold = rule["threshold"]

    if direction == "decrease" and current_price < threshold:
        return True, f"turun melewati Rp {threshold:,}"
    if direction == "increase" and current_price > threshold:
        return True, f"naik melewati Rp {threshold:,}"

    return False, ""

async def main():
    with open("watchlist.json", "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    print(f"📊 Mulai memantau {len(watchlist)} saham...")

    server_params = {
        "mcpServers": {
            "idx": {
                "command": "npx",
                "args": ["-y", "idx-mcp-server@latest"]
            }
        }
    }

    async with Client(server_params) as client:
        print("🔧 Tool yang tersedia:")
        try:
            tools = await client.list_tools()
            for tool in tools:
                print(f"   - {tool.name}")
        except Exception as e:
            print(f"   ⚠️ Gagal list tools: {e}")

        # Debug: test get_stock_analysis untuk BBCA
        print("\n🧪 TEST: get_stock_analysis untuk BBCA")
        try:
            test_result = await client.call_tool("get_stock_analysis", {"ticker": "BBCA"})
            print(f"Hasil: {str(test_result)[:1500]}")
        except Exception as e:
            print(f"⚠️ Test error: {e}")

        print("\n🧪 TEST: get_historical_data untuk BBCA")
        try:
            hist_result = await client.call_tool("get_historical_data", {"ticker": "BBCA"})
            print(f"Hasil: {str(hist_result)[:1500]}")
        except Exception as e:
            print(f"⚠️ Test error: {e}")

        # ========== Loop saham ==========
        for item in watchlist:
            ticker = item["ticker"]
            rules = item.get("rules", [])

            print(f"\n🔍 Memeriksa {ticker}...")

            try:
                result = await client.call_tool("get_stock_analysis", {"ticker": ticker})
            except Exception as e:
                print(f"⚠️ Error memanggil tool untuk {ticker}: {e}")
                continue

            # Parsing
            data = None
            if hasattr(result, 'structured_content') and result.structured_content:
                data = result.structured_content
            elif hasattr(result, 'data') and result.data:
                data = result.data
            elif hasattr(result, 'content'):
                for content in result.content:
                    if hasattr(content, 'text'):
                        try:
                            data = json.loads(content.text)
                            break
                        except:
                            print(f"   📄 Respons mentah: {content.text[:300]}")
                            pass

            if not data:
                print(f"⚠️ Tidak ada data untuk {ticker}, lewati")
                continue

            if isinstance(data, dict) and data.get("success") is False:
                print(f"⚠️ Server menolak {ticker}: {data.get('error', 'unknown')}")
                continue

            print(f"   📦 Struktur data: {str(data)[:500]}")

            # Cari harga
            stock = data.get("data") if isinstance(data, dict) else None
            if not stock:
                print(f"⚠️ Tidak ada field 'data' untuk {ticker}")
                continue

            # Coba berbagai kemungkinan field harga
            current_price = None
            for key in ["price", "last", "close", "currentPrice", "lastPrice"]:
                if isinstance(stock, dict) and stock.get(key):
                    current_price = stock[key]
                    break

            # Kalau tidak ada, coba dari prices array
            if current_price is None and isinstance(stock, dict):
                prices = stock.get("prices") or stock.get("historical") or stock.get("data")
                if isinstance(prices, list) and len(prices) > 0:
                    last = prices[-1]
                    if isinstance(last, dict):
                        current_price = last.get("close") or last.get("price")

            stock_name = ticker
            if isinstance(stock, dict):
                stock_name = stock.get("name") or stock.get("company_name") or stock.get("ticker") or ticker

            if current_price is None:
                print(f"⚠️ Harga {ticker} tidak tersedia, lewati")
                continue

            try:
                current_price = float(current_price)
            except (ValueError, TypeError):
                print(f"⚠️ Harga {ticker} bukan angka: {current_price}")
                continue

            print(f"   {stock_name} ({ticker}): Rp {current_price:,.0f}")

            # Cek rules
            hit_rules = []
            for rule in rules:
                hit, condition_text = check_rule(rule, current_price)
                if hit:
                    hit_rules.append((rule["zone"], condition_text))

            if not hit_rules:
                print(f"   ⏳ Tidak ada rule yang terpicu")
                continue

            for zone, condition_text in hit_rules:
                style = ZONE_STYLE.get(zone, ZONE_STYLE["watch"])
                message = (
                    f"{style['emoji']} *{style['label']}*\n"
                    f"{style['prefix']} — {stock_name} ({ticker})\n\n"
                    f"💰 Harga saat ini: Rp {current_price:,.0f}\n"
                    f"🎯 Kondisi: {condition_text}\n\n"
                    f"⏰ Segera cek aplikasi sekuritas Anda."
                )
                send_telegram(message)
                print(f"   ✅ Rule [{zone}] terpicu, notifikasi dikirim")

    print("\n✅ Selesai memeriksa semua saham.")

if __name__ == "__main__":
    asyncio.run(main())
