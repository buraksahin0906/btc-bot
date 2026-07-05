"""
scoring.py — Her coin için ayrı long_score / short_score (0–100).

Her koşulun puana katkısı `LONG_WEIGHTS` / `SHORT_WEIGHTS` sözlüklerinde
ŞEFFAF ve yorumlu olarak tanımlıdır; ağırlıklar toplamı 100'dür. Bir koşul
sağlanırsa ağırlığı puana eklenir.

Karar (78 eşiği, fark<10, tek net yön) signal_engine'de verilir; burada sadece
skorlar üretilir.
"""

from __future__ import annotations

import pandas as pd

# ------------------------------------------------------------------
# Ağırlıklar (toplam = 100). Değiştirmek istediğinde tek yer burası.
# ------------------------------------------------------------------
LONG_WEIGHTS = {
    "price_above_ema50_15m": 15,   # 15m fiyat EMA50 üstünde
    "ema21_gt_ema50": 12,          # EMA21 > EMA50
    "ema50_gt_ema200": 8,          # EMA50 > EMA200 (ekstra trend teyidi)
    "rsi_in_range": 12,            # RSI 45–65 (sağlıklı yükseliş bölgesi)
    "adx_strong": 10,             # ADX > 20 (trend gücü)
    "entry_near_ema21_vwap_5m": 12,  # 5m fiyat EMA21/VWAP yakınından tepki
    "volume_above_avg": 8,        # hacim SMA20 üstünde
    "macd_up": 8,                 # MACD yukarı
    "not_overextended": 7,        # fiyat aşırı şişmemiş (BB üst bandını aşmamış)
    "btc_not_dumping": 5,         # BTC sert düşmüyor
    "spread_low": 3,              # spread düşük
}

SHORT_WEIGHTS = {
    "price_below_ema50_15m": 15,   # 15m fiyat EMA50 altında
    "ema21_lt_ema50": 12,          # EMA21 < EMA50
    "ema50_lt_ema200": 8,          # EMA50 < EMA200 (ekstra)
    "rsi_in_range": 12,            # RSI 35–55
    "adx_strong": 10,             # ADX > 20
    "entry_reject_ema21_vwap_5m": 12,  # 5m fiyat EMA21/VWAP bölgesinden aşağı reddediliyor
    "sell_volume_strong": 8,      # satış hacmi güçlü
    "macd_down": 8,               # MACD aşağı
    "not_overextended": 7,        # fiyat aşırı düşmemiş (BB alt bandını kırmamış)
    "btc_weak": 5,                # BTC zayıf/düşüşte
    "spread_low": 3,              # spread düşük
}

assert sum(LONG_WEIGHTS.values()) == 100
assert sum(SHORT_WEIGHTS.values()) == 100

ADX_MIN = 20.0


def _near(a: float, b: float, tol_pct: float) -> bool:
    """a ve b birbirine yüzde tol_pct içinde yakın mı."""
    if not b:
        return False
    return abs(a - b) / abs(b) * 100 <= tol_pct


def compute_scores(
    df15: pd.DataFrame,
    df5: pd.DataFrame,
    btc_bias: float,
    spread_pct: float,
    max_spread_pct: float,
) -> tuple[float, float, dict]:
    """LONG ve SHORT skorlarını (0–100) ve hangi koşulların sağlandığını döndürür.

    df15/df5: compute_all() geçmiş indikatör DataFrame'leri.
    btc_bias:  BTC kısa vadeli momentum. >0 = BTC güçlü/yükseliş, <0 = zayıf/düşüş
               (ör. BTC 15m close'un EMA50'ye göre yüzdesi).
    spread_pct: (ask-bid)/mid * 100.
    """
    l = df15.iloc[-1]   # 15m son mum (ana trend)
    e = df5.iloc[-1]    # 5m son mum (giriş)

    long_hits: dict[str, bool] = {}
    short_hits: dict[str, bool] = {}

    # ---------------- LONG koşulları ----------------
    long_hits["price_above_ema50_15m"] = l["close"] > l["ema50"]
    long_hits["ema21_gt_ema50"] = l["ema21"] > l["ema50"]
    long_hits["ema50_gt_ema200"] = l["ema50"] > l["ema200"]
    long_hits["rsi_in_range"] = 45 <= l["rsi"] <= 65
    long_hits["adx_strong"] = l["adx"] > ADX_MIN
    # 5m fiyat EMA21 veya VWAP yakınından yukarı tepki
    long_hits["entry_near_ema21_vwap_5m"] = (
        (_near(e["close"], e["ema21"], 0.25) or _near(e["close"], e["vwap"], 0.25))
        and e["close"] >= e["open"]
    )
    long_hits["volume_above_avg"] = e["volume"] > e["vol_sma20"]
    long_hits["macd_up"] = e["macd"] > e["macd_signal"]
    long_hits["not_overextended"] = l["close"] < l["bb_upper"]
    long_hits["btc_not_dumping"] = btc_bias > -0.3   # BTC sert düşmüyor
    long_hits["spread_low"] = spread_pct <= max_spread_pct

    # ---------------- SHORT koşulları ----------------
    short_hits["price_below_ema50_15m"] = l["close"] < l["ema50"]
    short_hits["ema21_lt_ema50"] = l["ema21"] < l["ema50"]
    short_hits["ema50_lt_ema200"] = l["ema50"] < l["ema200"]
    short_hits["rsi_in_range"] = 35 <= l["rsi"] <= 55
    short_hits["adx_strong"] = l["adx"] > ADX_MIN
    # 5m fiyat EMA21/VWAP bölgesinden aşağı reddediliyor
    short_hits["entry_reject_ema21_vwap_5m"] = (
        (_near(e["close"], e["ema21"], 0.25) or _near(e["close"], e["vwap"], 0.25))
        and e["close"] <= e["open"]
    )
    short_hits["sell_volume_strong"] = e["volume"] > e["vol_sma20"]
    short_hits["macd_down"] = e["macd"] < e["macd_signal"]
    short_hits["not_overextended"] = l["close"] > l["bb_lower"]
    short_hits["btc_weak"] = btc_bias < 0.3   # BTC zayıf/düşüşte
    short_hits["spread_low"] = spread_pct <= max_spread_pct

    long_score = sum(w for k, w in LONG_WEIGHTS.items() if long_hits.get(k))
    short_score = sum(w for k, w in SHORT_WEIGHTS.items() if short_hits.get(k))

    details = {
        "long_hits": long_hits,
        "short_hits": short_hits,
        "long_score": float(long_score),
        "short_score": float(short_score),
    }
    return float(long_score), float(short_score), details
