import os
import json
import requests
import yfinance as yf
from datetime import datetime

# ========== Konfigurasi ==========
GIST_ID = os.environ.get("GIST_ID")
GIST_TOKEN = os.environ.get("GIST_TOKEN")

# Kriteria screening untuk investor jangka panjang
KRITERIA = {
    "pe_max": 20,           # PE maksimal 20
    "pbv_max": 4,           # PBV maksimal 4
    "div_min": 1.5,         # Dividend yield minimal 1.5%
    "market_cap_min": 5e12, # Market cap minimal Rp 5 triliun
}

# ========== Fungsi baca/tulis Gist ==========
def read_gist_file(filename: str):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Accept": "application/vnd.github+json"}
    if GIST_TOKEN:
        headers["Authorization"] = f"Bearer {GIST_TOKEN}"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal baca Gist: {r.status_code}")
    files = r.json()["files"]
    if filename not in files:
        raise Exception(f"File {filename} tidak ditemukan di Gist")
    return json.loads(files[filename]["content"])

def write_gist_file(filename: str, data):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GIST_TOKEN}",
    }
    payload = {
        "files": {
            filename: {
                "content": json.dumps(data, indent=2, ensure_ascii=False)
            }
        }
    }
    r = requests.patch(url, headers=headers, json=payload, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Gagal tulis Gist: {r.status_code} {r.text}")

# ========== Analisis saham ==========
def analisis_saham(ticker: str):
    """Ambil data fundamental + hitung skor. Return dict atau None."""
    try:
        stock = yf.Ticker(f"{ticker}.JK")
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
        market_cap = info.get("marketCap") or 0
        name = info.get("shortName") or ticker

        div_pct = None
        if div_yield is not None:
            div_pct = div_yield * 100 if div_yield < 1 else div_yield

        # Filter kriteria
        if market_cap and market_cap < KRITERIA["market_cap_min"]:
            return None
        if pe and (pe <= 0 or pe > KRITERIA["pe_max"]):
            return None
        if pbv and pbv > KRITERIA["pbv_max"]:
            return None
        if div_pct is not None and div_pct < KRITERIA["div_min"]:
            return None

        # Hitung skor
        score = 50
        if pe and pe > 0:
            if pe < 10: score += 20
            elif pe < 15: score += 10
        if pbv and pbv > 0:
            if pbv < 1.5: score += 10
            elif pbv < 2.5: score += 5
        if div_pct:
            if div_pct > 5: score += 15
            elif div_pct > 3: score += 8
        if current and low_52w and high_52w > low_52w:
            pos = (current - low_52w) / (high_52w - low_52w)
            if pos < 0.3: score += 10
            elif pos > 0.8: score -= 10

        score = max(0, min(100, score))

        # Zona beli
        buy_low = round(low_52w * 1.02, 0)
        buy_high = round(ma50, 0)
        upper = round(high_52w * 1.10, 0)
        lower = round(low_52w * 0.95, 0)

        return {
            "ticker": ticker, "name": name, "current": current,
            "pe": pe, "pbv": pbv, "div_pct": div_pct,
            "market_cap": market_cap,
            "buy_low": buy_low, "buy_high": buy_high,
            "upper": upper, "lower": lower,
            "score": score,
        }
    except Exception as e:
        print(f"⚠️ {ticker}: {e}")
        return None

def main():
    print(f"📊 Mulai screening {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    kandidat = read_gist_file("all_stocks.json")
    print(f"📋 Total kandidat: {len(kandidat)} saham")

    hasil = []
    for i, ticker in enumerate(kandidat, 1):
        print(f"[{i}/{len(kandidat)}] {ticker}...", end=" ")
        r = analisis_saham(ticker)
        if r:
            hasil.append(r)
            print(f"✅ skor {r['score']}")
        else:
            print("❌ tidak lolos filter")

    hasil.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "last_updated": datetime.now().isoformat(),
        "total_analyzed": len(kandidat),
        "total_passed": len(hasil),
        "results": hasil,
    }
    write_gist_file("screening_results.json", output)
    print(f"\n✅ Selesai. {len(hasil)} saham lolos filter.")
    print(f"📤 Hasil disimpan ke Gist: screening_results.json")

if __name__ == "__main__":
    main()
