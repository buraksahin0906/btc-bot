"""
signal_engine.py — Skor + filtre → nihai işlem kararı.

Karar kuralları (spec):
  - long_score >= 78 ve short_score < 78 → LONG
  - short_score >= 78 ve long_score < 78 → SHORT
  - ikisi de < 78 → işlem yok
  - ikisi de >= 78 → işlem yok
  - |long - short| < score_gap_min → işlem yok
  - yatay piyasa → işlem yok
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import CONFIG
from strategy.scoring import compute_scores
from strategy.trend_filter import is_flat_market


@dataclass
class Signal:
    symbol: str
    direction: str          # "long" | "short"
    long_score: float
    short_score: float
    entry_price: float      # referans (son kapanış)
    atr: float              # 5m ATR (stop hesabı için)
    details: dict

    @property
    def score(self) -> float:
        return self.long_score if self.direction == "long" else self.short_score


def evaluate_symbol(
    symbol: str,
    df15: pd.DataFrame,
    df5: pd.DataFrame,
    btc_bias: float,
    spread_pct: float,
) -> tuple[Signal | None, str]:
    """Bir sembol için sinyal üretir. (Signal | None, sebep) döndürür.

    Signal None ise sebep açıklaması döner (loglama/şeffaflık için).
    """
    # 1) Yatay piyasa filtresi (skordan önce ucuz eleme)
    flat, reason = is_flat_market(df15, df5)
    if flat:
        return None, f"Yatay piyasa: {reason}"

    # 2) Skorları hesapla
    long_score, short_score, details = compute_scores(
        df15, df5, btc_bias, spread_pct, CONFIG.max_spread_percent
    )

    thr = CONFIG.min_signal_score
    gap = CONFIG.score_gap_min

    # 3) Karar kuralları
    if long_score >= thr and short_score >= thr:
        return None, f"İki skor da eşik üstü (L={long_score} S={short_score}) → belirsiz"
    if long_score < thr and short_score < thr:
        return None, f"İki skor da eşik altı (L={long_score} S={short_score})"
    if abs(long_score - short_score) < gap:
        return None, f"Skorlar çok yakın (fark {abs(long_score - short_score)} < {gap})"

    direction = "long" if long_score >= thr else "short"

    last5 = df5.iloc[-1]
    signal = Signal(
        symbol=symbol,
        direction=direction,
        long_score=long_score,
        short_score=short_score,
        entry_price=float(last5["close"]),
        atr=float(last5["atr"]) if not pd.isna(last5["atr"]) else 0.0,
        details=details,
    )
    return signal, "OK"


def pick_best_signal(signals: list[Signal]) -> Signal | None:
    """Birden çok geçerli sinyal arasından en yüksek kaliteliyi seçer.

    Kalite = kazanan yönün skoru; eşitlikte iki skor farkı büyük olan (daha net).
    """
    if not signals:
        return None
    return max(signals, key=lambda s: (s.score, abs(s.long_score - s.short_score)))
