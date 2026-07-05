"""
trend_filter.py — Yatay piyasa filtresi.

Bot yatay piyasada KESİNLİKLE işlem açmaz; varsayılan davranış beklemektir.
`is_flat_market()` şu koşullardan biri sağlanırsa (True, sebep) döndürür:

  - ADX 18 altında (trend yok)
  - EMA21 ve EMA50 çok yakın (sıkışma)
  - Bollinger bandı daralmış
  - Hacim son 20 mum ortalamasının altında
  - 15m'de net trend yok (fiyat EMA50'ye çok yakın)
  - Fiyat EMA'lar içinde sıkışmış

Skorlarla ilgili "ikisi de 78 üstünde / skorlar çok yakın" kontrolleri
signal_engine içinde yapılır (skorlar orada hesaplandığı için).
"""

from __future__ import annotations

import pandas as pd

from config import CONFIG


def is_flat_market(df15: pd.DataFrame, df5: pd.DataFrame | None = None
                   ) -> tuple[bool, str]:
    """15m (ve opsiyonel 5m) indikatör DataFrame'ine bakarak yatay mı karar verir.

    df15: compute_all() geçmiş, en az 50 mumluk 15m verisi.
    Döndürür: (yatay_mı, sebep). Yatay değilse (False, "").
    """
    last = df15.iloc[-1]

    # 1) ADX düşük → trend zayıf
    if pd.isna(last["adx"]) or last["adx"] < CONFIG.adx_flat_threshold:
        return True, f"ADX düşük ({last['adx']:.1f} < {CONFIG.adx_flat_threshold})"

    # 2) EMA21 ve EMA50 çok yakın → sıkışma
    if last["ema50"] and abs(last["ema21"] - last["ema50"]) / last["ema50"] * 100 < \
            CONFIG.ema_proximity_percent:
        return True, "EMA21 ve EMA50 çok yakın (sıkışma)"

    # 3) Bollinger daralmış
    if not pd.isna(last["bb_width_pct"]) and last["bb_width_pct"] < CONFIG.bb_squeeze_percent:
        return True, f"Bollinger daralmış (genişlik {last['bb_width_pct']:.2f}%)"

    # 4) Hacim son 20 mum ortalamasının altında
    if not pd.isna(last["vol_sma20"]) and last["volume"] < last["vol_sma20"]:
        return True, "Hacim 20-mum ortalamasının altında"

    # 5) 15m'de net trend yok → fiyat EMA50'ye çok yakın (yön belirsiz)
    if last["ema50"] and abs(last["close"] - last["ema50"]) / last["ema50"] * 100 < \
            CONFIG.ema_proximity_percent:
        return True, "Fiyat EMA50'ye yapışık (net yön yok)"

    # 6) Fiyat EMA9-EMA21-EMA50 sarmalı içinde sıkışmış (hepsi birbirine çok yakın)
    emas = [last["ema9"], last["ema21"], last["ema50"]]
    if all(e and e > 0 for e in emas):
        spread_pct = (max(emas) - min(emas)) / min(emas) * 100
        if spread_pct < CONFIG.ema_proximity_percent:
            return True, "Fiyat EMA sarmalı içinde sıkışmış"

    return False, ""
