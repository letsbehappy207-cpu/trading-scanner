"""
Deteksi saham yang KEMUNGKINAN sedang diakumulasi lama / dibeli cicil --
pola Wyckoff accumulation sederhana: harga sideways/rapat dalam beberapa
bulan terakhir, TAPI volume & OBV (On Balance Volume) naik terus-menerus
di periode yang sama. Itu tanda klasik ada pihak yang mengumpulkan
posisi pelan-pelan sebelum markup, dilihat dari price-action publik.

INI BUKAN bandarmology asli (broker summary berbayar) -- ini proxy dari
data harga/volume publik Yahoo Finance. Saham "sedang diakumulasi" versi
sini = base sideways + volume/OBV naik + likuid (bukan saham tidur).

CATATAN JUJUR SOAL TARGET 30-100% / 4-5 HARI:
Itu target yang SANGAT agresif -- bahkan lebih tinggi dari rata-rata ARA
(auto reject atas) IDX 2 hari beruntun untuk saham > Rp50. Tidak ada
screener, termasuk bandarmology berbayar sekalipun, yang bisa menjamin itu
konsisten. Tool ini cuma mempersempit kandidat yang SECARA POLA punya
potensi gerak cepat (base rapat + volume mengumpul) -- bukan jaminan hasil.
Posisi sizing & risk management tetap tanggung jawab Anda.

Cara pakai:
  export TELEGRAM_BOT_TOKEN="xxxx:yyyy"
  export TELEGRAM_CHAT_ID="123456789"
  python3 accumulation_screener.py
"""

import os
import sys
import datetime

import yfinance as yf
import pandas as pd
import numpy as np

from tickers_all_idx import ALL_IDX

WIB = datetime.timezone(datetime.timedelta(hours=7))
BATCH_SIZE = 150
MAX_ORDER_RP = 1_000_000_000         # order terbesar yang mau dieksekusi sekali transaksi
MIN_AVG_TURNOVER_RP = MAX_ORDER_RP * 15  # turnover harian min 15x order terbesar,
                                          # supaya Rp500jt-1M sekali beli/jual nggak
                                          # bikin harga "kabur" (slippage kecil)
LOOKBACK_DAYS = 90                   # ~4 bulan, periode cek akumulasi
BASE_WIDTH_MAX_PCT = 25              # range harga max 25% selama periode = "sideways"


def obv_series(close: pd.Series, vol: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * vol).cumsum()


def analyze_accumulation(df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < LOOKBACK_DAYS:
        return None

    df = df.iloc[-LOOKBACK_DAYS:]
    close = df["Close"]
    vol = df["Volume"]

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    chg_pct = (last_close - prev_close) / prev_close * 100

    avg_turnover_20d = float((close * vol).iloc[-20:].mean())
    if avg_turnover_20d < MIN_AVG_TURNOVER_RP:
        return None  # saham tidur -- skip

    base_high, base_low = float(close.max()), float(close.min())
    base_width_pct = (base_high - base_low) / base_low * 100 if base_low > 0 else 999
    if base_width_pct > BASE_WIDTH_MAX_PCT:
        return None  # bukan sideways, sudah bergerak jauh -- bukan "sedang" diakumulasi

    # sudah breakout dari base? kalau iya, skip (sudah telat, bukan "akan bergerak")
    near_high = last_close >= base_high * 0.97
    if near_high and chg_pct > 5:
        return None

    half = len(vol) // 2
    vol_first_half = float(vol.iloc[:half].mean())
    vol_second_half = float(vol.iloc[half:].mean())
    vol_trend_ratio = vol_second_half / vol_first_half if vol_first_half > 0 else 0

    obv = obv_series(close, vol)
    obv_slope = float(np.polyfit(range(len(obv)), obv.values, 1)[0])
    obv_rising = obv_slope > 0

    # skor akumulasi: makin tinggi makin kuat sinyal "sedang dikumpulin"
    score = 0.0
    score += max(0, vol_trend_ratio - 1) * 2       # volume periode kedua lebih ramai
    score += 1.0 if obv_rising else -1.0            # net buying pressure
    score += max(0, (BASE_WIDTH_MAX_PCT - base_width_pct) / BASE_WIDTH_MAX_PCT)  # makin rapat makin bagus

    if vol_trend_ratio < 1.15 or not obv_rising:
        return None  # nggak ada tanda akumulasi yang jelas

    return {
        "close": last_close,
        "chg_pct": chg_pct,
        "base_width_pct": base_width_pct,
        "vol_trend_ratio": vol_trend_ratio,
        "obv_rising": obv_rising,
        "avg_turnover_20d": avg_turnover_20d,
        "score": score,
        "base_low": base_low,
        "base_high": base_high,
    }


def fetch_and_screen(tickers: list[str]) -> list[tuple[str, dict]]:
    results = []
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i:i + BATCH_SIZE]
        yf_chunk = [f"{t}.JK" for t in chunk]
        try:
            data = yf.download(
                yf_chunk, period="6mo", interval="1d",
                group_by="ticker", auto_adjust=True, threads=True, progress=False,
            )
        except Exception as e:
            print(f"Gagal fetch batch {i}: {e}")
            continue
        for t, yft in zip(chunk, yf_chunk):
            try:
                df = data[yft].dropna(how="all")
                r = analyze_accumulation(df)
                if r:
                    results.append((t, r))
            except Exception:
                continue
    return results


def build_message(ranked: list[tuple[str, dict]]) -> str:
    now = datetime.datetime.now(WIB)
    lines = [
        "🎯 *KANDIDAT SEDANG DIAKUMULASI (base rapat + volume/OBV naik)* 🎯",
        f"⏰ {now.strftime('%d/%m/%Y %H:%M')} WIB | Sumber: Yahoo Finance",
        f"Filter: base {LOOKBACK_DAYS}hr terakhir rapat ≤{BASE_WIDTH_MAX_PCT}%, volume periode "
        f"2 lebih ramai dari periode 1, OBV naik, turnover ≥ Rp{MIN_AVG_TURNOVER_RP/1e9:.0f}M/hari "
        f"(aman utk order sampai Rp{MAX_ORDER_RP/1e6:.0f}jt sekali beli/jual tanpa bikin harga kabur)",
        "",
    ]
    if not ranked:
        lines.append("Tidak ada kandidat yang lolos semua filter saat ini.")
    else:
        for i, (code, r) in enumerate(ranked[:10], 1):
            lines.append(
                f"{i}. *{code}* | Rp {r['close']:,.0f} ({r['chg_pct']:+.2f}%)\n"
                f"   ↳ 📦 Base rapat: {r['base_width_pct']:.1f}% (Rp{r['base_low']:,.0f}-{r['base_high']:,.0f})\n"
                f"   ↳ 📊 Volume periode 2 vs 1: {r['vol_trend_ratio']:.2f}x | OBV: {'naik ✅' if r['obv_rising'] else 'turun'}\n"
                f"   ↳ 💧 Turnover 20D: Rp {r['avg_turnover_20d']/1e9:,.2f} M/hari"
            )
    lines.append("")
    lines.append(
        "⚠️ Target 30-100% dalam 4-5 hari itu SANGAT agresif -- tidak ada screener yang bisa "
        "menjamin itu, termasuk bandarmology berbayar. Ini cuma mempersempit kandidat yang "
        "SECARA POLA berpotensi gerak cepat (base rapat + volume terkumpul). Tetap pakai CL "
        "dan position sizing yang wajar. DYOR."
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
    print(f"Cek pola akumulasi di {len(ALL_IDX)} saham IDX...")
    raw = fetch_and_screen(ALL_IDX)
    print(f"Lolos semua filter: {len(raw)} saham")
    ranked = sorted(raw, key=lambda kv: kv[1]["score"], reverse=True)
    msg = build_message(ranked)
    send_telegram(msg)


if __name__ == "__main__":
    main()
