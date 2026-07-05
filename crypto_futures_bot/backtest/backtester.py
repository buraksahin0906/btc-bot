"""
backtester.py — Tarihsel mum üzerinde strateji simülasyonu (İSKELET).

Bu sürümde ÇALIŞAN ama minimal bir backtester var: geçmiş mumlar üzerinde
skorlama + net-kâr trailing mantığını yürütür ve özet metrik üretir. PC'de
detaylandırılacak (funding, gerçekçi fill/slippage, çoklu sembol, parametre
taraması, grafik).

KULLANIM:
    python -m backtest.backtester BTC-USDT-SWAP
"""

from __future__ import annotations

import sys

import pandas as pd

from config import CONFIG
from strategy.indicators import candles_to_df, compute_all
from strategy.signal_engine import evaluate_symbol


def run_backtest(candles_15m: list, candles_5m: list, symbol: str = "TEST") -> dict:
    """Basit walk-forward: 5m mumları ilerletir, her adımda sinyal + trailing simüle eder.

    NOT (iskelet): 15m/5m hizalama kaba (son mumlar); fill fiyatı = kapanış;
    tek pozisyon; funding hariç. Amaç mantığı uçtan uca doğrulamak.
    """
    df15_full = compute_all(candles_to_df(candles_15m))
    df5_full = compute_all(candles_to_df(candles_5m))

    balance = CONFIG.paper_starting_balance
    trades: list[dict] = []
    pos: dict | None = None
    warmup = 210  # EMA200 için yeterli mum

    for i in range(warmup, len(df5_full)):
        df5 = df5_full.iloc[: i + 1]
        # 15m'i 5m zamanına kaba hizala (son kapanmış 15m mumu)
        t = df5.iloc[-1]["ts"]
        df15 = df15_full[df15_full["ts"] <= t]
        if len(df15) < warmup:
            continue

        price = float(df5.iloc[-1]["close"])

        if pos is None:
            signal, _ = evaluate_symbol(symbol, df15, df5, btc_bias=0.0, spread_pct=0.0)
            if signal:
                net_target = balance * (CONFIG.net_profit_target_percent_of_balance / 100.0)
                atr = signal.atr or price * 0.005
                stop = (price - atr * CONFIG.atr_stop_multiplier) if signal.direction == "long" \
                    else (price + atr * CONFIG.atr_stop_multiplier)
                pos = {"direction": signal.direction, "entry": price, "stop": stop,
                       "net_target": net_target, "peak": 0.0, "trailing": False}
        else:
            # basit net kâr (komisyon yaklaşık), notional = margin*kaldıraç
            margin = balance * (CONFIG.risk_per_trade_percent / 100.0)
            notional = margin * CONFIG.leverage
            move = (price - pos["entry"]) / pos["entry"]
            if pos["direction"] == "short":
                move = -move
            gross = notional * move
            fees = notional * (CONFIG.taker_fee_percent / 100.0) * 2
            net = gross - fees

            exit_reason = None
            stop_hit = (pos["direction"] == "long" and price <= pos["stop"]) or \
                       (pos["direction"] == "short" and price >= pos["stop"])
            if stop_hit:
                exit_reason = "stop"
            else:
                if not pos["trailing"] and net >= pos["net_target"]:
                    pos["trailing"] = True
                    pos["peak"] = net
                if pos["trailing"]:
                    pos["peak"] = max(pos["peak"], net)
                    giveback = pos["peak"] * (CONFIG.trailing_giveback_percent / 100.0)
                    level = max(pos["net_target"], pos["peak"] - giveback)
                    if net <= level:
                        exit_reason = "trailing"

            if exit_reason:
                balance += net
                trades.append({"net_pnl": net, "reason": exit_reason})
                pos = None

    return _summarize(trades, balance)


def _summarize(trades: list[dict], balance: float) -> dict:
    if not trades:
        return {"trades": 0, "final_balance": balance, "note": "işlem yok"}
    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    return {
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": len(wins) / len(trades) * 100,
        "total_net": sum(pnls),
        "final_balance": balance,
    }


if __name__ == "__main__":
    print("Backtester iskelet — canlı veriyle demo için main.py kullanın.")
    print("PC'de: OKX'ten tarihsel mum çekip run_backtest(candles_15m, candles_5m) çağırın.")
    if len(sys.argv) > 1:
        print(f"Sembol argümanı alındı: {sys.argv[1]} (veri kaynağı PC'de eklenecek)")
