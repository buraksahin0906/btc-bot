"""
position_sizer.py — Pozisyon boyutu hesabı.

KATI kural: margin = toplam bakiyenin %2'si. Skor 95 bile olsa boyut ARTMAZ.
isolated, 2x. Bot hiçbir şartta bakiyenin %2'sinden fazla margin kullanmaz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from config import CONFIG


@dataclass
class PositionSize:
    margin_usdt: float       # kullanılacak teminat (bakiye %2)
    notional_usdt: float     # nominal büyüklük (margin * kaldıraç)
    contracts: float         # borsa emrindeki miktar (sz)
    coin_amount: float       # yaklaşık coin miktarı (contracts * ct_val)


def compute_position_size(
    balance: float,
    price: float,
    ct_val: float,
    lot_size: float,
    min_size: float,
) -> PositionSize | None:
    """Bakiye %2 margin, 2x kaldıraçla kontrat adedini hesaplar.

    ct_val: 1 kontratın kaç coin ettiği (OKX instrument ctVal).
    lot_size: emir adım büyüklüğü. min_size: minimum emir.
    Miktar min_size altına düşerse None (işlem açılamaz).
    """
    if balance <= 0 or price <= 0 or ct_val <= 0:
        return None

    margin = balance * (CONFIG.risk_per_trade_percent / 100.0)
    notional = margin * CONFIG.leverage
    raw_contracts = notional / (price * ct_val)

    # lot_size'a aşağı yuvarla
    if lot_size > 0:
        contracts = math.floor(raw_contracts / lot_size) * lot_size
    else:
        contracts = raw_contracts

    if contracts < min_size or contracts <= 0:
        return None

    actual_notional = contracts * price * ct_val
    actual_margin = actual_notional / CONFIG.leverage

    # Güvenlik: gerçek margin, bakiye %2'sini ASLA aşmasın.
    max_margin = balance * (CONFIG.risk_per_trade_percent / 100.0) + 1e-9
    if actual_margin > max_margin:
        return None

    return PositionSize(
        margin_usdt=actual_margin,
        notional_usdt=actual_notional,
        contracts=contracts,
        coin_amount=contracts * ct_val,
    )


def liquidation_price(entry: float, direction: str, leverage: int) -> float:
    """isolated pozisyon için kabaca likidasyon fiyatı (bilgi/log amaçlı).

    Basitleştirilmiş: bakım marjini ve komisyon hariç. 2x için ~%50 hareket.
    """
    move = 1.0 / leverage
    if direction == "long":
        return entry * (1 - move)
    return entry * (1 + move)
