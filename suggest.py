import os
import requests
import yfinance as yf
from datetime import datetime

# ========== Kandidat saham yang dipantau ==========
CANDIDATES = [
    "BBCA",  # Bank Central Asia
    "BBRI",  # Bank Rakyat Indonesia
    "BMRI",  # Bank Mandiri
    "TLKM",  # Telkom Indonesia
    "ASII",  # Astra International
    "UNVR",  # Unilever Indonesia
    "ICBP",  # Indofood CBP
    "INDF",  # Indofood Sukses Makmur
]

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

def analyze_stock(ticker: str):
    """Ambil data fundamental + teknikal sederhana."""
    yf_ticker = f"{ticker}.JK"
    try:
        stock = yf.Ticker(yf_ticker)
        info = stock.info
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 30:
            return None

        current = float(hist["Close"].iloc[-1])
        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())
        ma50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else current

        pe = info.get("trailingPE") or info.get("forwardPE")
        pbv = info.get("priceToBook")
        div_yield = info.get("dividendYield")
        name = info.get("shortName") or ticker

        buy_low = round(low_52w * 1.02, 0)
        buy_high = round(ma50, 0)
        upper = round(high_52w * 1.10, 0)
        lower = round(low_52w * 0.95, 0)

        div_pct = None
        if div_yield is not None:
            div_pct = div_yield * 100 if div_yield < 1 else div_yield

        return {
            "ticker": ticker,
            "name": name,
            "current": current,
            "pe": pe,
            "pbv": pbv,
            "div_pct": div_pct,
            "buy_low": buy_low,
            "buy_high": buy_high,
            "upper": upper,
            "lower": lower,
            "high_52w": high_52w,
            "low_52w": low_52w,
        }
    except Exception as e:
        print(f"⚠️ Error analisis {ticker}: {e}")
        return None

def score_stock(r: dict) -> int:
    """Skor sederhana 0-100 berdasarkan valuasi."""
    score = 50

    if r["pe"] and r["pe"] > 0:
        if r["pe"] < 10:
            score += 20
        elif r["pe"] < 15:
            score += 10
        elif r["pe"] > 25:
            score -= 15

    if r["pbv"] and r["pbv"] > 0:
        if r["pbv"] < 1.5:
            score += 10
        elif r["pbv"] > 4:
            score -= 10

    if r["div_pct"]:
        if r["div_pct"] > 5:
            score += 15
        elif r["div_pct"] > 3:
            score += 8

    if r["current"] and r["low_52w"]:
        pos = (r["current"] - r["low_52w"]) / (r["high_52w"] - r["low_52w"])
        if pos < 0.3:
            score += 10
        elif pos > 0.8:
            score -= 10

    return max(0, min(100, score))

def main():
    print("📊 Mulai scan rekomendasi jangka panjang...")
    results = []

    for ticker in CANDIDATES:
        print(f"🔍 Analisis {ticker}...")
        r = analyze_stock(ticker)
        if r:
            r["score"] = score_stock(r)
            results.append(r)
            print(f"   {r['name']}: Rp {r['current']:,.0f} (skor: {r['score']})")

    if not results:
        print("⚠️ Tidak ada hasil analisis")
        return

    results.sort(key=lambda x: x["score"], reverse=True)

    tanggal = datetime.now().strftime("%d %b %Y")
    lines = [f"📈 *REKOMENDASI JANGKA PANJANG* — {tanggal}\n"]

    for r in results:
        if r["score"] >= 70:
            emoji = "🟢"
            label = "Menarik"
        elif r["score"] >= 55:
            emoji = "🟡"
            label = "Netral"
        else:
            emoji = "🔴"
            label = "Hati-hati"

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
            f"⭐ Skor: {r['score']}/100 ({label})\n"
        )

    lines.append("_Bukan rekomendasi investasi. Selalu cek fundamental dan laporan keuangan._")
    message = "\n".join(lines)

    send_telegram(message)
    print("✅ Rekomendasi terkirim")

if __name__ == "__main__":
    main()
