"""
Top 10 saham: harga Rp 50-200, likuid/ramai (turnover tinggi), dan kas
perusahaan kuat (net cash positif / cash ratio bagus).

Sumber data: Yahoo Finance (gratis, delay ~15 menit untuk harga; data
fundamental -- kas, utang -- diambil dari laporan terakhir yang di-index
Yahoo, BUKAN real-time, dan untuk saham kecil/menengah IDX seringkali TIDAK
LENGKAP di Yahoo -- saham yang datanya kosong otomatis di-skip, bukan error.
Anggap kas score ini sebagai filter awal, bukan analisis fundamental penuh.

Cara pakai:
  export TELEGRAM_BOT_TOKEN="xxxx:yyyy"
  export TELEGRAM_CHAT_ID="123456789"
  python3 cash_screener.py morning     # jam 05:00 WIB, sebelum market buka
  python3 cash_screener.py closing     # jam 19:00 WIB, setelah market tutup
"""

import os
import sys
import datetime

import yfinance as yf
import pandas as pd

from tickers_all_idx import ALL_IDX

WIB = datetime.timezone(datetime.timedelta(hours=7))
PRICE_MIN, PRICE_MAX = 50, 200
BATCH_SIZE = 150
LIQUIDITY_SHORTLIST = 60   # ambil N teratas by turnover dulu, baru cek data kas (lebih cepat)


def fetch_price_liquidity(tickers: list[str]) -> dict[str, dict]:
    """Ambil harga + rata-rata turnover 20 hari untuk semua ticker, per batch."""
    out = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i:i + BATCH_SIZE]
        yf_chunk = [f"{t}.JK" for t in chunk]
        try:
            data = yf.download(
                yf_chunk, period="2mo", interval="1d",
                group_by="ticker", auto_adjust=True, threads=True, progress=False,
            )
        except Exception as e:
            print(f"Gagal fetch batch {i}: {e}")
            continue
        for t, yft in zip(chunk, yf_chunk):
            try:
                df = data[yft].dropna(how="all")
                if len(df) < 15:
                    continue
                close = df["Close"]
                vol = df["Volume"]
                last_close = float(close.iloc[-1])
                prev_close = float(close.iloc[-2])
                chg_pct = (last_close - prev_close) / prev_close * 100
                avg_turnover = float((close * vol).iloc[-20:].mean())
                if PRICE_MIN <= last_close <= PRICE_MAX:
                    out[t] = {
                        "close": last_close,
                        "chg_pct": chg_pct,
                        "avg_turnover": avg_turnover,
                    }
            except Exception:
                continue
    return out


def fetch_cash_strength(ticker: str) -> dict | None:
    """Skor kekuatan kas dari data fundamental Yahoo Finance (best-effort)."""
    try:
        info = yf.Ticker(f"{ticker}.JK").get_info()
    except Exception:
        return None

    total_cash = info.get("totalCash")
    total_debt = info.get("totalDebt")
    market_cap = info.get("marketCap")

    if total_cash is None or market_cap in (None, 0):
        return None  # data tidak lengkap di Yahoo, skip -- bukan berarti kasnya jelek

    net_cash = total_cash - (total_debt or 0)
    cash_ratio = total_cash / market_cap  # kas dibanding kapitalisasi pasar

    return {
        "total_cash": total_cash,
        "total_debt": total_debt or 0,
        "net_cash": net_cash,
        "cash_ratio": cash_ratio,
        "net_cash_positive": net_cash > 0,
    }


def build_message(mode: str, ranked: list[tuple[str, dict, dict]]) -> str:
    now = datetime.datetime.now(WIB)
    title = "PAGI (pre-market)" if mode == "morning" else "PENUTUPAN"
    lines = [
        f"💰 *TOP 10 SAHAM KAS KUAT & RAMAI ({title})* 💰",
        f"⏰ {now.strftime('%d/%m/%Y %H:%M')} WIB | Sumber: Yahoo Finance",
        f"🎯 Filter: harga Rp{PRICE_MIN}-{PRICE_MAX}, turnover tinggi, net cash positif",
        "",
    ]
    if not ranked:
        lines.append(
            "Tidak ada kandidat yang lolos semua filter hari ini (harga/likuiditas/data "
            "kas lengkap di Yahoo). Coba lagi sesi berikutnya."
        )
    else:
        for i, (code, liq, cash) in enumerate(ranked, 1):
            lines.append(
                f"{i}. *{code}* | Rp {liq['close']:,.0f} ({liq['chg_pct']:+.2f}%)\n"
                f"   ↳ 💵 Net cash: Rp {cash['net_cash']/1e9:,.1f} M | Cash ratio: {cash['cash_ratio']*100:.1f}% dari market cap\n"
                f"   ↳ 📊 Turnover rata-rata 20D: Rp {liq['avg_turnover']/1e9:,.1f} M/hari"
            )
    lines.append("")
    lines.append(
        "⚠️ Data kas dari laporan keuangan terakhir yang ter-index Yahoo (bukan real-time), "
        "dan tidak semua saham kecil/menengah punya data lengkap. Alat bantu screening, "
        "bukan rekomendasi/analisis fundamental penuh. DYOR."
    )
    return "\n".join(lines)


def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[DRY-RUN -- TELEGRAM_BOT_TOKEN/CHAT_ID belum di-set]\n")
        print(text)
        return
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id, "text": text, "parse_mode": "Markdown",
    }, timeout=15)
    if resp.status_code != 200:
        print(f"Gagal kirim Telegram: {resp.status_code} {resp.text}")
    else:
        print("Terkirim ke Telegram.")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"

    print(f"Tahap 1: cek harga+likuiditas {len(ALL_IDX)} saham IDX...")
    price_liq = fetch_price_liquidity(ALL_IDX)
    print(f"Lolos filter harga Rp{PRICE_MIN}-{PRICE_MAX}: {len(price_liq)} saham")

    shortlist = sorted(price_liq.items(), key=lambda kv: kv[1]["avg_turnover"], reverse=True)
    shortlist = shortlist[:LIQUIDITY_SHORTLIST]
    print(f"Tahap 2: cek data kas untuk {len(shortlist)} saham paling ramai...")

    candidates = []
    for code, liq in shortlist:
        cash = fetch_cash_strength(code)
        if cash and cash["net_cash_positive"]:
            candidates.append((code, liq, cash))

    print(f"Lolos filter kas (net cash positif, data lengkap): {len(candidates)} saham")

    ranked = sorted(candidates, key=lambda c: c[2]["cash_ratio"], reverse=True)[:10]

    msg = build_message(mode, ranked)
    send_telegram(msg)


if __name__ == "__main__":
    main()
