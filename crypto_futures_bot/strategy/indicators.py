"""
indicators.py — Tüm teknik indikatörler SAF pandas/numpy ile.

ta / ta-lib gibi harici kütüphaneye bağımlılık YOK. Her fonksiyon bir pandas
Series/DataFrame alır, aynı indeksli sonuç döndürür.

Sağlanan indikatörler:
  EMA (9/21/50/200), RSI 14 (Wilder), MACD, ADX 14 (Wilder), Bollinger Bands,
  VWAP, ATR 14, Volume SMA 20.

`compute_all(df)` bir OHLCV DataFrame'i alıp tüm indikatör kolonlarını ekler.
Beklenen kolonlar: open, high, low, close, volume.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Üssel hareketli ortalama (pandas ewm, span=period)."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI — Wilder yumuşatması (EMA alpha=1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing = ewm alpha=1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # avg_loss=0 iken RSI=100
    out = out.where(avg_loss != 0, 100.0)
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD çizgisi, sinyal çizgisi ve histogram döndürür."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range — Wilder yumuşatması."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
        ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX, +DI, -DI — Wilder yöntemi.

    ADX düşükse (ör. <20) trend zayıf/yatay demektir.
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    tr = true_range(high, low, close)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx_ = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx_, plus_di, minus_di


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0
                    ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger üst/orta/alt bant."""
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def bollinger_width_percent(close: pd.Series, period: int = 20, num_std: float = 2.0
                            ) -> pd.Series:
    """Bant genişliği (üst-alt) / orta * 100. Daralma tespiti için."""
    upper, mid, lower = bollinger_bands(close, period, num_std)
    return (upper - lower) / mid.replace(0.0, np.nan) * 100


def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP — kümülatif (typical price * volume) / kümülatif volume.

    Intraday niyetli; verilen pencere içindeki mumların kümülatifi alınır.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum().replace(0.0, np.nan)
    return (typical * df["volume"]).cumsum() / cum_vol


def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    return sma(volume, period)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV DataFrame'ine tüm indikatör kolonlarını ekleyip döndürür.

    Beklenen kolonlar: open, high, low, close, volume (küçük harf).
    """
    out = df.copy()
    close, high, low, vol = out["close"], out["high"], out["low"], out["volume"]

    out["ema9"] = ema(close, 9)
    out["ema21"] = ema(close, 21)
    out["ema50"] = ema(close, 50)
    out["ema200"] = ema(close, 200)

    out["rsi"] = rsi(close, 14)

    macd_line, signal_line, hist = macd(close)
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist

    adx_, plus_di, minus_di = adx(high, low, close, 14)
    out["adx"] = adx_
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di

    upper, mid, lower = bollinger_bands(close, 20, 2.0)
    out["bb_upper"] = upper
    out["bb_mid"] = mid
    out["bb_lower"] = lower
    out["bb_width_pct"] = (upper - lower) / mid.replace(0.0, np.nan) * 100

    out["atr"] = atr(high, low, close, 14)
    out["vwap"] = vwap(out)
    out["vol_sma20"] = volume_sma(vol, 20)

    return out


def candles_to_df(candles: list[list]) -> pd.DataFrame:
    """[[ts,o,h,l,c,v], ...] listesini OHLCV DataFrame'e çevirir (eskiden yeniye)."""
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms")
    return df
