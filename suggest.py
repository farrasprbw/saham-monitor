import os
import json
import time
import random
import requests
import yfinance as yf
from datetime import datetime

GIST_ID_ALL_STOCKS = os.environ.get("GIST_ID_ALL_STOCKS")
GIST_TOKEN = os.environ.get("GIST_TOKEN")

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
        else:
            print("✅ Telegram terkirim")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def load_all_stocks():
    """Baca daftar saham dari Gist. Return list of dict."""
    if not GIST_ID_ALL_STOCKS:
        raise Exception("GIST_ID_ALL_STOCKS tidak diatur")

    url = f"https://api.github.com/gists/{GIST_ID_ALL_STOCKS}"
    headers = {"Accept": "application/vnd.github+json"}
    if GIST_TOKEN:
        headers["Authorization"] = f"Bearer {GIST_TOKEN}"

    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal baca all_stocks.json: {r.status_code}")

    content = r.json()["files"]["all_stocks.json"]["content"]
    data = json.loads(content)

    stocks = []
    for item in data:
        if isinstance(item, dict):
            stocks.append(item)
        elif isinstance(item, str):
            stocks.append({"ticker": item, "name": item})
    return stocks

def quick_filter(stock: dict):
    """Filter cepat: 1 panggilan yfinance per saham. Return dict atau None."""
    ticker = stock["ticker"]
    yf_ticker = f"{ticker}.JK"

    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period="3mo")

        if hist.empty or len(hist) < 50:
            return None

        current = float(hist["Close"].iloc[-1])
        ma50 = float(hist["Close"].tail(50).mean())
        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())

        # Skor cepat
        score = 0

        # Harga di bawah MA50 = peluang beli
        if current < ma50:
            score += 20

        # Harga dekat 52w low
        if high_52w > low_52w:
            pos = (current - low_52w) / (high_52w - low_52w)
            if pos < 0.3:
                score += 20
            elif pos < 0.5:
                score += 10

        # Minimal skor 20 untuk lolos ke tahap 2
        if score < 20:
            return None

        return {
            "ticker": ticker,
            "name": stock["name"],
            "quick_score": score,
            "current": current,
        }
    except Exception as e:
        print(f"   ⚠️ Quick filter gagal untuk {ticker}: {e}")
        return None

def deep_analyze(stock: dict):
    """Analisis mendalam: PE, PBV, dividend, 52w range."""
    ticker = stock["ticker"]
    yf_ticker = f"{ticker}.JK"

    try:
        t = yf.Ticker(yf_ticker)
        info = t.info
        hist = t.history(period="1y")

        if hist.empty or len(hist) < 30:
            return None

        current = float(hist["Close"].iloc[-1])
        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())
        ma50 = float(hist["Close"].tail(50).mean())

        pe = info.get("trailingPE") or info.get("forwardPE")
        pbv = info.get("priceToBook")
        div_yield = info.get("dividendYield")
        div_pct = None
        if div_yield is not None:
            div_pct = div_yield * 100 if div_yield < 1 else div_yield

        # Zona beli
        buy_low = round(low_52w * 1.02, 0)
        buy_high = round(ma50, 0)
        upper = round(high_52w * 1.10, 0)
        lower = round(low_52w * 0.95, 0)

        # Skor
        score = 50
        if pe and pe > 0:
            if pe < 10: score += 20
            elif pe < 15: score += 10
            elif pe > 25: score -= 15
        if pbv and pbv > 0:
            if pbv < 1.5: score += 10
            elif pbv > 4: score -= 10
        if div_pct:
            if div_pct > 5: score += 15
            elif div_pct > 3: score += 8
        if high_52w > low_52w:
            pos = (current - low_52w) / (high_52w - low_52w)
            if pos < 0.3: score += 10
            elif pos > 0.8: score -= 10

        return {
            "ticker": ticker,
            "name": stock["name"],
            "current": current,
            "pe": pe,
            "pbv": pbv,
            "div_pct": div_pct,
            "buy_low": buy_low,
            "buy_high": buy_high,
            "upper": upper,
            "lower": lower,
            "score": max(0, min(100, score)),
        }
    except Exception as e:
        print(f"   ⚠️ Deep analyze gagal untuk {ticker}: {e}")
        return None

def main():
    print(f"📊 Mulai screening {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    stocks = load_all_stocks()
    print(f"📋 Total saham di database: {len(stocks)}")

    # Tahap 1: filter cepat
    print("\n🔍 Tahap 1: filter cepat...")
    candidates = []
    for i, stock in enumerate(stocks):
        print(f"   [{i+1}/{len(stocks)}] {stock['ticker']}...")
        result = quick_filter(stock)
        if result:
            candidates.append(result)
        time.sleep(0.3)  # hindari rate limit

    print(f"\n✅ Lolos filter cepat: {len(candidates)} saham")

    if not candidates:
        send_telegram("📊 Tidak ada saham yang lolos filter hari ini.")
        return

    # Ambil top 20 berdasarkan quick_score
    candidates.sort(key=lambda x: x["quick_score"], reverse=True)
    top_candidates = candidates[:20]
    print(f"🔍 Tahap 2: analisis mendalam {len(top_candidates)} kandidat...")

    # Tahap 2: analisis mendalam
    analyzed = []
    for i, c in enumerate(top_candidates):
        print(f"   [{i+1}/{len(top_candidates)}] {c['ticker']}...")
        result = deep_analyze(c)
        if result:
            analyzed.append(result)
        time.sleep(0.5)

    if not analyzed:
        send_telegram("📊 Tidak ada saham yang layak direkomendasikan hari ini.")
        return

    # Urutkan berdasarkan skor, ambil Top 5
    analyzed.sort(key=lambda x: x["score"], reverse=True)
    top5 = analyzed[:5]

    # Susun pesan
    tanggal = datetime.now().strftime("%d %b %Y")
    lines = [f"📈 *REKOMENDASI TOP 5* — {tanggal}\n"]

    for r in top5:
        if r["score"] >= 70:
            emoji = "🟢"
        elif r["score"] >= 55:
            emoji = "🟡"
        else:
            emoji = "🔴"

        pe_str = f"{r['pe']:.1f}" if r["pe"] else "N/A"
        pbv_str = f"{r['pbv']:.2f}" if r["pbv"] else "N/A"
        div_str = f"{r['div_pct']:.1f}%" if r["div_pct"] else "N/A"

        lines.append(
            f"{emoji} *{r['ticker']}* — {r['name']}\n"
            f"💰 Harga: Rp {r['current']:,.0f}\n"
            f"📊 PE: {pe_str} | PBV: {pbv_str} | Div: {div_str}\n"
            f"🟢 Zona beli: Rp {r['buy_low']:,.0f} – Rp {r['buy_high']:,.0f}\n"
            f"🔴 Batas bawah: Rp {r['lower']:,.0f}\n"
            f"🎯 Batas atas: Rp {r['upper']:,.0f}\n"
            f"⭐ Skor: {r['score']}/100\n"
        )

    lines.append(f"_Dari {len(stocks)} saham, {len(analyzed)} lolos analisis._")
    lines.append("_Bukan rekomendasi investasi._")

    send_telegram("\n".join(lines))
    print("✅ Rekomendasi terkirim")

if __name__ == "__main__":
    main()
