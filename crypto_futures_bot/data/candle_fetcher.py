"""
candle_fetcher.py — Mum verisi çekme + indikatör hesaplama.

15m/5m/1m mumlarını çeker, DataFrame'e çevirir, tüm indikatörleri ekler.
Kısa süreli cache ile aynı döngüde tekrar isteği azaltır.
"""

from __future__ import annotations

import time

import pandas as pd

from config import CONFIG
from strategy.indicators import candles_to_df, compute_all


class CandleFetcher:
    def __init__(self, exchange, logger, cache_ttl_seconds: int = 20):
        self.exchange = exchange
        self.log = logger
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}

    def get_indicator_df(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """Belirtilen sembol/TF için indikatörlü DataFrame döndürür (cache'li)."""
        key = (symbol, timeframe)
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        try:
            candles = self.exchange.get_candles(symbol, timeframe, CONFIG.candle_limit)
        except Exception as exc:  # noqa: BLE001
            self.log.warning(f"{symbol} {timeframe} mum çekilemedi: {exc}")
            return None

        if not candles or len(candles) < 60:
            return None

        df = candles_to_df(candles)
        df = compute_all(df)
        self._cache[key] = (now, df)
        return df

    def get_all_timeframes(self, symbol: str) -> dict[str, pd.DataFrame] | None:
        """15m/5m/1m üçlüsünü döndürür. Herhangi biri eksikse None."""
        out = {}
        for tf in (CONFIG.tf_trend, CONFIG.tf_entry, CONFIG.tf_manage):
            df = self.get_indicator_df(symbol, tf)
            if df is None:
                return None
            out[tf] = df
        return out

    def get_btc_bias(self) -> float:
        """BTC kısa vadeli momentum: 15m close'un EMA50'ye göre yüzdesi.

        >0 BTC güçlü/yükseliş, <0 zayıf/düşüş. Sinyal filtresinde kullanılır.
        """
        df = self.get_indicator_df("BTC-USDT-SWAP", CONFIG.tf_trend)
        if df is None:
            return 0.0
        last = df.iloc[-1]
        if not last["ema50"]:
            return 0.0
        return (last["close"] - last["ema50"]) / last["ema50"] * 100
