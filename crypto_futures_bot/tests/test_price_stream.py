"""
test_price_stream.py — WS mesaj ayrıştırma + PriceFeed fallback mantığı.

Gerçek ağ olmadan: PriceStream callback'lerini elle sürerek fiyat cache'ini,
PriceFeed'in akış→REST fallback davranışını doğrular.

Çalıştırma (crypto_futures_bot/ içinden):  python tests/test_price_stream.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.price_stream import PriceFeed, PriceStream  # noqa: E402
from logs.trade_logger import setup_logger  # noqa: E402


class FakeExchange:
    def __init__(self, price=50.0):
        self.price = price
        self.calls = 0
    def get_ticker(self, symbol):
        self.calls += 1
        return {"last": self.price, "bid": self.price, "ask": self.price,
                "vol_ccy_24h": 0}


def test_ws_message_updates_price():
    log = setup_logger("test")
    s = PriceStream("wss://dummy", log)
    # OKX tickers kanalı mesaj formatı
    msg = json.dumps({
        "arg": {"channel": "tickers", "instId": "BTC-USDT-SWAP"},
        "data": [{"instId": "BTC-USDT-SWAP", "last": "64000.5", "ts": "1"}],
    })
    s._on_message(None, msg)
    entry = s.get_price("BTC-USDT-SWAP")
    assert entry is not None, "fiyat cache'e yazılmadı"
    price, age = entry
    assert price == 64000.5, f"yanlış fiyat: {price}"
    assert age < 1.0, "yaş makul değil"
    print(f"  ✓ WS mesajı parse edildi: 64000.5 (yaş {age:.3f}s)")


def test_ws_ignores_pong_and_errors():
    log = setup_logger("test")
    s = PriceStream("wss://dummy", log)
    s._on_message(None, "pong")  # ping/pong → yok sayılmalı
    s._on_message(None, json.dumps({"event": "error", "msg": "x"}))  # hata → yok sayılmalı
    s._on_message(None, "bozuk-json")  # çökmemer
    assert s.get_price("BTC-USDT-SWAP") is None
    print("  ✓ pong / error / bozuk mesaj güvenli şekilde yok sayıldı")


def test_pricefeed_uses_fresh_stream():
    log = setup_logger("test")
    exch = FakeExchange(price=50.0)
    s = PriceStream("wss://dummy", log)
    s._running = True  # is_active() True olsun (gerçek WS gerekmez)
    import data.price_stream as ps
    ps._WS_AVAILABLE = True
    s._on_message(None, json.dumps({
        "arg": {"channel": "tickers", "instId": "X-USDT-SWAP"},
        "data": [{"instId": "X-USDT-SWAP", "last": "99.9"}],
    }))
    feed = PriceFeed(exch, s, log, staleness_seconds=3.0)
    price = feed.get_price("X-USDT-SWAP")
    assert price == 99.9, "taze akış fiyatı kullanılmadı"
    assert exch.calls == 0, "taze akış varken REST çağrıldı"
    assert feed.source_of("X-USDT-SWAP") == "ws"
    print("  ✓ taze akış fiyatı kullanıldı, REST'e gidilmedi")


def test_pricefeed_falls_back_to_rest_when_stale():
    log = setup_logger("test")
    exch = FakeExchange(price=50.0)
    s = PriceStream("wss://dummy", log)
    s._running = True
    import data.price_stream as ps
    ps._WS_AVAILABLE = True
    # Bayat fiyat: ts'i geçmişe koy
    s._prices["X-USDT-SWAP"] = (99.9, time.time() - 10)
    feed = PriceFeed(exch, s, log, staleness_seconds=3.0)
    price = feed.get_price("X-USDT-SWAP")
    assert price == 50.0, "bayat akışta REST'e düşülmedi"
    assert exch.calls == 1, "REST fallback çağrılmadı"
    assert feed.source_of("X-USDT-SWAP") == "rest"
    print("  ✓ bayat akışta REST fallback çalıştı")


def test_pricefeed_no_stream_uses_rest():
    log = setup_logger("test")
    exch = FakeExchange(price=77.0)
    feed = PriceFeed(exch, None, log)  # WS yok
    price = feed.get_price("X-USDT-SWAP")
    assert price == 77.0 and exch.calls == 1
    assert feed.source_of("X-USDT-SWAP") == "rest"
    print("  ✓ WS olmadan doğrudan REST kullanıldı")


def test_position_manager_reads_from_feed():
    """PositionManager._read_price, enjekte edilen akış fiyatını kullanmalı."""
    from execution.position_manager import PositionManager
    log = setup_logger("test")
    exch = FakeExchange(price=50.0)  # REST 50 der
    s = PriceStream("wss://dummy", log)
    s._running = True
    import data.price_stream as ps
    ps._WS_AVAILABLE = True
    s._on_message(None, json.dumps({
        "arg": {"channel": "tickers", "instId": "X-USDT-SWAP"},
        "data": [{"instId": "X-USDT-SWAP", "last": "88.8"}],
    }))
    feed = PriceFeed(exch, s, log)
    pm = PositionManager(exch, None, None, None, None, None, None,
                         is_live=False, logger=log, price_feed=feed)
    assert pm._read_price("X-USDT-SWAP") == 88.8, "PositionManager akış fiyatını okumadı"
    assert exch.calls == 0, "akış varken REST'e gidildi"
    print("  ✓ PositionManager fiyatı WS akışından okudu (REST'e gitmedi)")


if __name__ == "__main__":
    test_ws_message_updates_price()
    test_ws_ignores_pong_and_errors()
    test_pricefeed_uses_fresh_stream()
    test_pricefeed_falls_back_to_rest_when_stale()
    test_pricefeed_no_stream_uses_rest()
    test_position_manager_reads_from_feed()
    print("\nFiyat akışı / PriceFeed testleri geçti.")
