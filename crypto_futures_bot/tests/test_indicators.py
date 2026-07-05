"""
test_indicators.py — İndikatörlerin makul aralıklarda çalıştığını doğrular.

Çalıştırma (crypto_futures_bot/ içinden):
    python -m pytest tests/ -q      (pytest varsa)
    python tests/test_indicators.py (pytest yoksa doğrudan)
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.indicators import compute_all, ema, rsi, atr  # noqa: E402


def _make_df(n=300, trend=0.0, seed=42):
    rng = np.random.default_rng(seed)
    price = 100 + np.cumsum(rng.normal(trend, 1.0, n))
    price = np.abs(price) + 10
    high = price + np.abs(rng.normal(0, 0.5, n))
    low = price - np.abs(rng.normal(0, 0.5, n))
    vol = np.abs(rng.normal(1000, 100, n))
    return pd.DataFrame({
        "ts": np.arange(n) * 60000,
        "open": price, "high": high, "low": low, "close": price, "volume": vol,
    })


def test_ema_follows_price():
    df = _make_df(trend=0.5)
    e = ema(df["close"], 20)
    assert len(e) == len(df)
    # EMA son değeri fiyat aralığında olmalı
    assert df["close"].min() <= e.iloc[-1] <= df["close"].max()


def test_rsi_bounds():
    df = _make_df()
    r = rsi(df["close"], 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_rsi_uptrend_high():
    # Sürekli artan seri → RSI yüksek olmalı
    up = pd.Series(np.linspace(100, 200, 100))
    r = rsi(up, 14)
    assert r.iloc[-1] > 70


def test_atr_positive():
    df = _make_df()
    a = atr(df["high"], df["low"], df["close"], 14).dropna()
    assert (a > 0).all()


def test_compute_all_columns():
    df = _make_df()
    out = compute_all(df)
    for col in ["ema9", "ema21", "ema50", "ema200", "rsi", "macd", "adx",
                "bb_upper", "bb_lower", "atr", "vwap", "vol_sma20"]:
        assert col in out.columns, f"eksik kolon: {col}"
    # ADX 0-100 aralığında
    adx_vals = out["adx"].dropna()
    assert (adx_vals >= 0).all() and (adx_vals <= 100).all()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} indikatör testi geçti.")
