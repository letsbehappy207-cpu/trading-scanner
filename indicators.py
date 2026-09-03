"""
Indikator teknikal sederhana untuk screener saham LQ45.
Semua dihitung dari data OHLCV Yahoo Finance (gratis, delay ~15 menit).

CATATAN JUJUR: ini BUKAN replikasi bandarmology/Dean Earwicker Score asli
(itu butuh data broker summary tick-level yang tidak tersedia gratis).
Skor di sini murni price-action + volume dari data publik: volume spike,
posisi RSI, breakout dari range konsolidasi (proxy kasar utk "akumulasi").
Anggap ini SATU alat bantu screening, bukan sinyal pasti.
"""

import pandas as pd
import numpy as np


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def analyze(df: pd.DataFrame) -> dict | None:
    """df: OHLCV harian, index tanggal ascending, kolom Open/High/Low/Close/Volume.
    Return None kalau data kurang (baru IPO / kosong)."""
    if df is None or len(df) < 55:
        return None

    close = df["Close"]
    vol = df["Volume"]

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    rsi = compute_rsi(close)

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    chg_pct = (last_close - prev_close) / prev_close * 100

    # VPA: rasio volume hari ini vs rata-rata volume 20 hari sebelumnya (exclude hari ini)
    vol_avg20 = vol.iloc[-21:-1].mean()
    vpa_ratio = float(vol.iloc[-1] / vol_avg20) if vol_avg20 > 0 else 0.0

    # Range konsolidasi 20 hari terakhir (proxy "sideways base" sebelum breakout)
    range_20 = close.iloc[-21:-1]
    base_high = float(range_20.max())
    base_low = float(range_20.min())
    base_width_pct = (base_high - base_low) / base_low * 100 if base_low > 0 else 999

    breakout = last_close > base_high and prev_close <= base_high
    tight_base = base_width_pct <= 15  # base rapat = kandidat akumulasi

    support = float(close.iloc[-60:].min())
    resistance_target = last_close * 1.08  # target TP tengah dari 6-10%

    turnover_rp = float((close.iloc[-1] * vol.iloc[-1]))

    # Skor confluence sederhana (0-3): tight base + volume spike + breakout
    score = int(tight_base) + int(vpa_ratio >= 2) + int(breakout)

    if score >= 3:
        signal = "STRONG BUY (Breakout + Vol)"
    elif score == 2:
        signal = "BUY ON WEAKNESS"
    elif rsi.iloc[-1] > 70:
        signal = "TAKE PROFIT SEBAGIAN (Overbought)"
    else:
        signal = "WATCHLIST"

    return {
        "close": last_close,
        "chg_pct": chg_pct,
        "vpa_ratio": vpa_ratio,
        "rsi": float(rsi.iloc[-1]),
        "ma20": float(ma20.iloc[-1]),
        "ma50": float(ma50.iloc[-1]),
        "support": support,
        "target": resistance_target,
        "turnover_rp": turnover_rp,
        "tight_base": tight_base,
        "breakout": breakout,
        "score": score,
        "signal": signal,
    }
