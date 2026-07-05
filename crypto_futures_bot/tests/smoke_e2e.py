"""
smoke_e2e.py — Ağ-bağımsız uçtan uca boru hattı doğrulaması (mock borsa).

OKX bu ortamdan erişilemediği için (ağ politikası), tüm modüllerin doğru
bağlandığını sahte bir borsayla kanıtlar:
  - scan_cycle() istisnasız dönüyor mu? (scanner→fetcher→indikatör→skor→sinyal)
  - try_open_trade() bir sinyali işleme çevirip SQLite'a yazıyor mu?
  - PositionManager fiyat yolunu sürüp pozisyonu kapatıyor, CSV'ye yazıyor mu?

Çalıştırma (crypto_futures_bot/ içinden):  python tests/smoke_e2e.py
"""

import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as config_mod  # noqa: E402
from config import CONFIG  # noqa: E402
from data.candle_fetcher import CandleFetcher  # noqa: E402
from data.market_scanner import MarketScanner  # noqa: E402
from execution.order_manager import OrderManager  # noqa: E402
from execution.position_manager import PositionManager  # noqa: E402
from notifier.telegram_notifier import TelegramNotifier  # noqa: E402
from paper.paper_trader import PaperTrader  # noqa: E402
from persistence.state_store import StateStore  # noqa: E402
from risk.risk_manager import RiskManager  # noqa: E402
from strategy.signal_engine import Signal  # noqa: E402
from logs.trade_logger import TradeLogger, setup_logger  # noqa: E402
import main as bot_main  # noqa: E402


SYMBOLS = ["FAKEUP-USDT-SWAP", "FAKEDN-USDT-SWAP", "BTC-USDT-SWAP"]


def _gen_candles(n, start, slope, noise, seed):
    """Deterministik OHLCV üretir: [ts,o,h,l,c,v] (eskiden yeniye)."""
    rng = np.random.default_rng(seed)
    closes = start + slope * np.arange(n) + rng.normal(0, noise, n)
    closes = np.abs(closes) + 1.0
    out = []
    base_ts = int(time.time() * 1000) - n * 60000
    for i in range(n):
        c = float(closes[i])
        o = float(closes[i - 1]) if i > 0 else c
        hi = max(o, c) + abs(rng.normal(0, noise * 0.3))
        lo = min(o, c) - abs(rng.normal(0, noise * 0.3))
        vol = float(abs(rng.normal(5000, 500)) + (2000 if i > n - 5 else 0))
        out.append([base_ts + i * 60000, o, hi, lo, c, vol])
    return out


class MockExchange:
    """BaseExchange'i taklit eden sahte borsa (deterministik sentetik veri)."""

    def __init__(self):
        # Yükselen, düşen, yatay-BTC serileri
        self._candles = {
            "FAKEUP-USDT-SWAP": _gen_candles(260, 100, 0.15, 0.6, 1),
            "FAKEDN-USDT-SWAP": _gen_candles(260, 300, -0.15, 0.6, 2),
            "BTC-USDT-SWAP": _gen_candles(260, 60000, 2.0, 30, 3),
        }

    def get_swap_symbols(self):
        # Gerçekçi ct_val (OKX'te çoğu USDT-SWAP için 0.01 mertebesinde) →
        # küçük bakiyeyle bile min_size üstünde kontrat çıkar.
        return [{"symbol": s, "ct_val": 0.01, "min_size": 1.0,
                 "tick_size": 0.001, "lot_size": 1.0} for s in SYMBOLS]

    def get_all_tickers(self):
        out = []
        for s in SYMBOLS:
            last = self._candles[s][-1][4]
            out.append({"symbol": s, "last": last,
                        "bid": last * 0.9999, "ask": last * 1.0001,
                        "vol_ccy_24h": 1_000_000})  # yüksek likidite
        return out

    def get_ticker(self, symbol):
        last = self._candles[symbol][-1][4]
        return {"last": last, "bid": last * 0.9999, "ask": last * 1.0001,
                "vol_ccy_24h": 1_000_000}

    def get_candles(self, symbol, timeframe, limit=200):
        return self._candles[symbol][-limit:]


def build_ctx(tmpdir):
    log = setup_logger("smoke")
    exch = MockExchange()
    paper = PaperTrader(starting_balance=1000.0)
    CONFIG.db_path = os.path.join(tmpdir, "smoke.db")
    CONFIG.trades_csv_path = os.path.join(tmpdir, "trades.csv")
    state = StateStore(CONFIG.db_path)
    trade_logger = TradeLogger(CONFIG.trades_csv_path)
    notifier = TelegramNotifier(log)
    scanner = MarketScanner(exch, log)
    fetcher = CandleFetcher(exch, log, cache_ttl_seconds=0)
    risk = RiskManager(state)
    orders = OrderManager(exch, paper, is_live=False, logger=log)
    pm = PositionManager(exch, orders, paper, state, risk, trade_logger,
                         notifier, is_live=False, logger=log)
    scanner.load_instruments()
    ctx = {"exchange": exch, "state": state, "paper": paper, "notifier": notifier,
           "scanner": scanner, "fetcher": fetcher, "risk": risk, "orders": orders,
           "position_manager": pm, "live": False, "log": log, "balance": 0.0}
    return ctx, exch, state, paper


def test_scan_cycle_runs():
    """scan_cycle birkaç kez istisnasız dönmeli (tüm boru hattı bağlı)."""
    with tempfile.TemporaryDirectory() as d:
        ctx, exch, state, paper = build_ctx(d)
        for _ in range(3):
            bot_main.scan_cycle(ctx)  # istisna atmamalı
        # Bir sinyal açıldıysa SQLite'ta pozisyon olur; açılmadıysa da sorun yok.
        pos = state.get_open_position()
        print(f"  ✓ scan_cycle 3x istisnasız çalıştı "
              f"(açık pozisyon: {'var → ' + pos['symbol'] if pos else 'yok'})")


def test_forced_trade_lifecycle():
    """Sinyali zorla → giriş → SQLite kaydı → fiyat yükselt → trailing çıkış → CSV."""
    with tempfile.TemporaryDirectory() as d:
        ctx, exch, state, paper = build_ctx(d)
        ctx["balance"] = paper.get_balance()

        # Yükselen sembol için elle bir LONG sinyali kur
        price = exch.get_ticker("FAKEUP-USDT-SWAP")["last"]
        signal = Signal(
            symbol="FAKEUP-USDT-SWAP", direction="long",
            long_score=85.0, short_score=30.0,
            entry_price=price, atr=price * 0.004, details={},
        )
        opened = bot_main.try_open_trade(signal, ctx)
        assert opened, "işlem açılmalıydı"
        pos = state.get_open_position()
        assert pos and pos["symbol"] == "FAKEUP-USDT-SWAP", "SQLite'a pozisyon yazılmadı"
        assert pos["net_target"] > 0, "net hedef kilitlenmedi"
        print(f"  ✓ giriş: entry {pos['entry_price']:.3f}, stop {pos['stop_price']:.3f}, "
              f"net hedef {pos['net_target']:.4f}, {pos['contracts']} kontrat")

        # Fiyatı yukarı sürükle → hedef aşılır, trailing başlar, sonra geri gel → çıkış
        entry = pos["entry_price"]
        closed = False
        for mult in [1.002, 1.005, 1.01, 1.02, 1.03, 1.01]:
            exch._candles["FAKEUP-USDT-SWAP"][-1][4] = entry * mult
            res = ctx["position_manager"].manage(state.get_open_position())
            if res is None:
                closed = True
                break
        assert closed, "fiyat oynamasına rağmen pozisyon kapanmadı"
        assert state.get_open_position() is None, "kapanışta SQLite temizlenmedi"

        stats = state.get_trade_stats()
        assert stats["trades"] == 1
        assert os.path.exists(CONFIG.trades_csv_path), "trades.csv oluşmadı"
        with open(CONFIG.trades_csv_path) as f:
            lines = f.read().strip().splitlines()
        assert len(lines) >= 2, "trades.csv'ye işlem satırı yazılmadı"
        print(f"  ✓ yaşam döngüsü: net {stats['total_net']:+.4f} USDT, "
              f"CSV satırı yazıldı ({len(lines) - 1} işlem)")


def test_safety_gate_no_live_order():
    """paper modda is_live=False → OrderManager gerçek borsaya emir göndermez."""
    with tempfile.TemporaryDirectory() as d:
        ctx, exch, state, paper = build_ctx(d)
        # MockExchange'e place_order yok → çağrılırsa AttributeError olurdu.
        # Paper yolu kullanıldığı için hata olmamalı.
        fill = ctx["orders"].open_entry("FAKEUP-USDT-SWAP", "long", 5.0,
                                        exch.get_ticker("FAKEUP-USDT-SWAP")["last"], 1.0)
        assert fill is not None and fill["order_id"] == "paper", \
            "paper modda emir paper yoluna gitmedi"
        print("  ✓ güvenlik: paper modda gerçek emir gönderilmedi (order_id='paper')")


if __name__ == "__main__":
    test_scan_cycle_runs()
    test_forced_trade_lifecycle()
    test_safety_gate_no_live_order()
    print("\nUçtan uca smoke testleri geçti.")
