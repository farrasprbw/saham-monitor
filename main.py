import asyncio
import os
import json
import requests
from fastmcp import Client

# ========== 1. Konfigurasi tampilan tiap zona ==========
ZONE_STYLE = {
    "watch":  {"emoji": "🔵", "label": "ZONA PANTAU",   "prefix": "Informasi"},
    "action": {"emoji": "🟡", "label": "ZONA AKSI",     "prefix": "Perhatian"},
    "panic":  {"emoji": "🔴", "label": "ZONA DARURAT",  "prefix": "URGENT"},
}

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

# ========== 4. Fungsi Utama Monitoring ==========
async def main():
    with open("watchlist.json", "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    print(f"📊 Mulai memantau {len(watchlist)} saham...")

    # Konfigurasi server MCP — dibungkus dalam "mcpServers"
    server_params = {
        "mcpServers": {
            "idx": {
                "command": "npx",
                "args": ["-y", "idx-mcp-server@latest"]
            }
        }
    }

    async with Client(server_params) as client:
        # ========== DEBUG: Lihat tool apa saja yang tersedia ==========
        print("🔧 Tool yang tersedia:")
        try:
            tools = await client.list_tools()
            for tool in tools:
                print(f"   - {tool.name}")
        except Exception as e:
            print(f"   ⚠️ Gagal list tools: {e}")

        # ========== Loop saham ==========
        for item in watchlist:
            ticker = item["ticker"]
            rules = item.get("rules", [])

            print(f"\n🔍 Memeriksa {ticker}...")

            # Panggil tool get_stock_info (tanpa prefix)
            try:
                result = await client.call_tool("get_stock_info", {"ticker": ticker})
            except Exception as e:
                print(f"⚠️ Error memanggil tool untuk {ticker}: {e}")
                continue

            # Parsing respons
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
                            # Kalau bukan JSON, mungkin teks biasa
                            print(f"   📄 Respons: {content.text[:200]}")
                            pass

            if not data:
                print(f"⚠️ Tidak ada data untuk {ticker}, lewati")
                continue

            # Coba beberapa kemungkinan struktur respons
            stock = None
            if isinstance(data, dict):
                if data.get("success") and "data" in data:
                    stock = data["data"]
                elif "price" in data:
                    stock = data
                elif "data" in data:
                    stock = data["data"]

            if not stock:
                print(f"⚠️ Struktur data tidak dikenal untuk {ticker}: {str(data)[:200]}")
                continue

            current_price = stock.get("price") or stock.get("last") or stock.get("close")
            stock_name = stock.get("name") or stock.get("company_name") or ticker

            if current_price is None:
                print(f"⚠️ Harga {ticker} tidak tersedia, lewati")
                continue

            # Konversi ke float kalau string
            try:
                current_price = float(current_price)
            except (ValueError, TypeError):
                print(f"⚠️ Harga {ticker} bukan angka: {current_price}")
                continue

            print(f"   {stock_name} ({ticker}): Rp {current_price:,.0f}")

            # Cek semua rule untuk saham ini
            hit_rules = []
            for rule in rules:
                hit, condition_text = check_rule(rule, current_price)
                if hit:
                    hit_rules.append((rule["zone"], condition_text))

            if not hit_rules:
                print(f"   ⏳ Tidak ada rule yang terpicu")
                continue

            # Kirim notifikasi untuk setiap rule yang terpicu
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
