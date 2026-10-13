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
        "command": "npx",
        "args": ["-y", "idx-mcp-server@latest"]
    }
    
    async with Client(server_params) as client:
        for item in watchlist:
            ticker = item["ticker"]
            rules = item.get("rules", [])
            
            print(f"\n🔍 Memeriksa {ticker}...")
            
            result = await client.call_tool("get_stock_info", {"ticker": ticker})
            
            data = None
            if hasattr(result, 'structured_content'):
                data = result.structured_content
            elif hasattr(result, 'data'):
                data = result.data
            elif hasattr(result, 'content'):
                for content in result.content:
                    if hasattr(content, 'text'):
                        try:
                            data = json.loads(content.text)
                            break
                        except:
                            pass
            
            if not data or not data.get("success"):
                print(f"⚠️ Gagal mengambil data {ticker}, lewati")
                continue
            
            stock = data.get("data", {})
            current_price = stock.get("price")
            stock_name = stock.get("name", ticker)
            
            if current_price is None:
                print(f"⚠️ Harga {ticker} tidak tersedia, lewati")
                continue
            
            print(f"   {stock_name} ({ticker}): Rp {current_price:,}")
            
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
                    f"💰 Harga saat ini: Rp {current_price:,}\n"
                    f"🎯 Kondisi: {condition_text}\n\n"
                    f"⏰ Segera cek aplikasi sekuritas Anda."
                )
                send_telegram(message)
                print(f"   ✅ Rule [{zone}] terpicu, notifikasi dikirim")
    
    print("\n✅ Selesai memeriksa semua saham.")

if __name__ == "__main__":
    asyncio.run(main())
