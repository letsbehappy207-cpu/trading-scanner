"""
Screener LQ45 -> Telegram, sumber data Yahoo Finance (gratis, delay ~15 menit).

Cara pakai:
  export TELEGRAM_BOT_TOKEN="xxxx:yyyy"      # dari @BotFather
  export TELEGRAM_CHAT_ID="123456789"        # chat id tujuan (grup/pribadi)
  python3 main.py morning     # broadcast sinyal screening pagi
  python3 main.py closing     # rekap penutupan sore

Tanpa TELEGRAM_BOT_TOKEN/CHAT_ID di-set, script hanya print ke terminal
(mode dry-run) -- tidak akan gagal, aman untuk uji coba dulu.
"""

import os
import sys
import datetime
import time

import yfinance as yf
import pandas as pd

from tickers_lq45 import LQ45
from indicators import analyze

WIB = datetime.timezone(datetime.timedelta(hours=7))


def fetch_batch(tickers: list[str]) -> dict[str, pd.DataFrame]:
    yf_tickers = [f"{t}.JK" for t in tickers]
    data = yf.download(
        yf_tickers, period="4mo", interval="1d",
        group_by="ticker", auto_adjust=True, threads=True, progress=False,
    )
    out = {}
    for t, yft in zip(tickers, yf_tickers):
        try:
            df = data[yft].dropna(how="all")
            if not df.empty:
                out[t] = df
        except Exception:
            continue
    return out


def build_morning_message(results: list[tuple[str, dict]]) -> str:
    now = datetime.datetime.now(WIB)
    lines = [
        "🏆 *TOP BUY CANDIDATES (LQ45 SCREENER)* 🏆",
        f"⏰ {now.strftime('%d/%m/%Y %H:%M')} WIB | Sumber: Yahoo Finance (delay ~15 menit)",
        "🎯 Filter: Base rapat + Volume spike + Breakout",
        "",
    ]
    strong = [r for r in results if r[1]["signal"].startswith("STRONG BUY")]
    strong = sorted(strong, key=lambda r: r[1]["vpa_ratio"], reverse=True)[:10]

    if not strong:
        lines.append("Tidak ada kandidat STRONG BUY hari ini. Pasar sepi volume/breakout.")
    else:
        for i, (code, r) in enumerate(strong, 1):
            lines.append(
                f"{i}. *{code}* | Rp {r['close']:,.0f} ({r['chg_pct']:+.2f}%)\n"
                f"   ↳ 📊 Vol: {r['vpa_ratio']:.2f}x rata-rata 20D | RSI: {r['rsi']:.1f}\n"
                f"   ↳ 🎯 Support Rp {r['support']:,.0f} | Target TP Rp {r['target']:,.0f} (+8%)\n"
                f"   ↳ 🚦 {r['signal']}"
            )
    lines.append("")
    lines.append("⚠️ Ini alat bantu screening dari data publik, bukan rekomendasi pasti. DYOR.")
    return "\n".join(lines)


def build_closing_message(results: list[tuple[str, dict]]) -> str:
    now = datetime.datetime.now(WIB)
    gainers = sorted(results, key=lambda r: r[1]["chg_pct"], reverse=True)[:5]
    losers = sorted(results, key=lambda r: r[1]["chg_pct"])[:5]

    lines = [
        "📉📈 *REKAP PENUTUPAN LQ45*",
        f"⏰ {now.strftime('%d/%m/%Y %H:%M')} WIB",
        "",
        "🟢 *Top Gainers:*",
    ]
    for code, r in gainers:
        lines.append(f"  {code}: Rp {r['close']:,.0f} ({r['chg_pct']:+.2f}%)")
    lines.append("")
    lines.append("🔴 *Top Losers:*")
    for code, r in losers:
        lines.append(f"  {code}: Rp {r['close']:,.0f} ({r['chg_pct']:+.2f}%)")
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
    print(f"Mengambil data {len(LQ45)} saham LQ45 dari Yahoo Finance...")
    raw = fetch_batch(LQ45)
    results = []
    for code, df in raw.items():
        r = analyze(df)
        if r:
            results.append((code, r))
    print(f"Berhasil analisis {len(results)}/{len(LQ45)} saham.")

    if mode == "closing":
        msg = build_closing_message(results)
    else:
        msg = build_morning_message(results)

    send_telegram(msg)


if __name__ == "__main__":
    main()
