"""
test_trailing.py — Net-kâr hedefi kilitleme + trailing çıkışını doğrular.

Sentetik fiyat serisiyle PositionManager mantığını (gerçek borsa olmadan)
sürer: fiyat hedefe iter → trailing başlar → tepeden geri gelince tam çıkış.

Çalıştırma (crypto_futures_bot/ içinden):
    python tests/test_trailing.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG  # noqa: E402
from execution.order_manager import OrderManager  # noqa: E402
from execution.position_manager import PositionManager  # noqa: E402
from paper.paper_trader import PaperTrader  # noqa: E402
from persistence.state_store import StateStore  # noqa: E402
from risk.risk_manager import RiskManager  # noqa: E402
from logs.trade_logger import setup_logger  # noqa: E402


class FakeExchange:
    """Sadece get_ticker döndüren sahte borsa; fiyatı testte biz sürüyoruz."""
    def __init__(self):
        self.price = 100.0
    def get_ticker(self, symbol):
        return {"last": self.price, "bid": self.price, "ask": self.price,
                "vol_ccy_24h": 0}


class NoopNotifier:
    def send(self, text):
        pass


class NoopTradeLog:
    def log_trade(self, trade):
        pass


def build_manager(tmpdb):
    log = setup_logger("test")
    exch = FakeExchange()
    paper = PaperTrader(starting_balance=1000.0)
    state = StateStore(tmpdb)
    risk = RiskManager(state)
    orders = OrderManager(exch, paper, is_live=False, logger=log)
    pm = PositionManager(exch, orders, paper, state, risk, NoopTradeLog(),
                         NoopNotifier(), is_live=False, logger=log)
    return exch, state, pm, paper


def test_trailing_exit_takes_profit():
    with tempfile.TemporaryDirectory() as d:
        exch, state, pm, paper = build_manager(os.path.join(d, "t.db"))

        # LONG pozisyon: giriş 100, net hedef küçük (kolay ulaşsın)
        contracts, ct_val = 10.0, 1.0
        net_target = 5.0
        pos = {
            "symbol": "TEST-USDT-SWAP", "direction": "long", "entry_price": 100.0,
            "contracts": contracts, "ct_val": ct_val, "entry_maker": True,
            "stop_price": 95.0, "algo_id": "paper", "net_target": net_target,
            "peak_net": 0.0, "trailing_active": False, "stop_moved_to_entry": False,
            "opened_ts": __import__("time").time(),
        }
        state.save_open_position(pos)

        # Fiyat kademeli yukarı → hedef aşılır, trailing başlar
        for p in [100.5, 101.0, 102.0, 103.0]:
            exch.price = p
            pos = pm.manage(state.get_open_position())
            assert pos is not None, f"fiyat {p}'de erken kapandı"

        cur = state.get_open_position()
        assert cur["trailing_active"], "hedef aşıldı ama trailing başlamadı"
        assert cur["stop_moved_to_entry"], "stop girişe çekilmedi"
        assert cur["stop_price"] == 100.0, "stop giriş fiyatına eşit değil"
        peak = cur["peak_net"]

        # Fiyat tepeden geri gelsin → trailing çıkışı tetiklensin
        exch.price = 101.2
        result = pm.manage(state.get_open_position())

        assert result is None, "trailing seviyesine değdi ama pozisyon kapanmadı"
        assert state.get_open_position() is None, "SQLite pozisyonu temizlenmedi"
        stats = state.get_trade_stats()
        assert stats["trades"] == 1
        assert stats["total_net"] > 0, "trailing çıkışı kârla kapanmalıydı"
        print(f"  ✓ trailing çıkış: net {stats['total_net']:+.4f} USDT (tepe {peak:.4f})")


def test_stop_loss_exit():
    with tempfile.TemporaryDirectory() as d:
        exch, state, pm, paper = build_manager(os.path.join(d, "t.db"))
        pos = {
            "symbol": "TEST-USDT-SWAP", "direction": "long", "entry_price": 100.0,
            "contracts": 10.0, "ct_val": 1.0, "entry_maker": True,
            "stop_price": 98.0, "algo_id": "paper", "net_target": 5.0,
            "peak_net": 0.0, "trailing_active": False, "stop_moved_to_entry": False,
            "opened_ts": __import__("time").time(),
        }
        state.save_open_position(pos)
        exch.price = 97.5  # stop altına düş
        result = pm.manage(state.get_open_position())
        assert result is None, "stop tetiklenmeli"
        stats = state.get_trade_stats()
        assert stats["trades"] == 1
        assert stats["total_net"] < 0, "stop çıkışı zararla kapanmalı"
        print(f"  ✓ stop-loss çıkış: net {stats['total_net']:+.4f} USDT")


if __name__ == "__main__":
    test_trailing_exit_takes_profit()
    test_stop_loss_exit()
    print("\nTrailing/stop testleri geçti.")
