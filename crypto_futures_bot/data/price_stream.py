"""
price_stream.py — OKX public WebSocket ile anlık fiyat akışı + REST fallback.

Küçük-hedef scalping'de çıkış/trailing'in hassas olması için fiyatı 30 sn'de bir
REST ile değil, değiştikçe WebSocket'ten alırız.

İki sınıf:
  - PriceStream: arka planda WS thread'i, `tickers` kanalına abone olur, en güncel
    fiyatı thread-safe tutar. Bağlantı koparsa otomatik yeniden bağlanır.
  - PriceFeed: PositionManager'a enjekte edilir. Akış fiyatı tazeyse onu, bayatsa
    veya WS kapalıysa REST ticker'ı döndürür. Böylece WS olmasa bile bot çalışır.

WS erişilemezse (ör. ağ/politika) her şey sessizce REST'e düşer — bot çökmez.
"""

from __future__ import annotations

import json
import threading
import time

try:
    import websocket  # websocket-client
    _WS_AVAILABLE = True
except ImportError:  # kütüphane yoksa saf REST modunda çalış
    _WS_AVAILABLE = False

from config import CONFIG


class PriceStream:
    """OKX public WebSocket 'tickers' akışı (arka plan thread)."""

    def __init__(self, url: str, logger):
        self.url = url
        self.log = logger
        self._prices: dict[str, tuple[float, float]] = {}  # symbol -> (price, ts)
        self._subscribed: set[str] = set()
        self._lock = threading.Lock()
        self._ws: "websocket.WebSocketApp | None" = None
        self._thread: threading.Thread | None = None
        self._keepalive: threading.Thread | None = None
        self._running = False

    # ---------------- Yaşam döngüsü ----------------

    def start(self) -> None:
        if not _WS_AVAILABLE:
            self.log.warning("websocket-client yok → fiyat akışı devre dışı, REST kullanılacak")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._keepalive = threading.Thread(target=self._keepalive_loop, daemon=True)
        self._keepalive.start()
        self.log.info("WebSocket fiyat akışı başlatıldı")

    def stop(self) -> None:
        self._running = False
        try:
            if self._ws:
                self._ws.close()
        except Exception:  # noqa: BLE001
            pass

    def is_active(self) -> bool:
        return self._running and _WS_AVAILABLE

    # ---------------- Abonelik ----------------

    def subscribe(self, symbol: str) -> None:
        """Bir sembolün ticker akışına abone olur (zaten aboneyse no-op)."""
        with self._lock:
            if symbol in self._subscribed:
                return
            self._subscribed.add(symbol)
        self._send_sub(symbol, subscribe=True)

    def unsubscribe(self, symbol: str) -> None:
        with self._lock:
            if symbol not in self._subscribed:
                return
            self._subscribed.discard(symbol)
        self._send_sub(symbol, subscribe=False)

    def _send_sub(self, symbol: str, subscribe: bool) -> None:
        if not self._ws:
            return
        op = "subscribe" if subscribe else "unsubscribe"
        try:
            self._ws.send(json.dumps({
                "op": op,
                "args": [{"channel": "tickers", "instId": symbol}],
            }))
        except Exception as exc:  # noqa: BLE001
            self.log.debug(f"WS {op} gönderilemedi ({symbol}): {exc}")

    # ---------------- Fiyat okuma ----------------

    def get_price(self, symbol: str) -> tuple[float, float] | None:
        """(fiyat, yaş_saniye) döndürür; hiç veri yoksa None."""
        with self._lock:
            entry = self._prices.get(symbol)
        if not entry:
            return None
        price, ts = entry
        return price, time.time() - ts

    # ---------------- WS callback'leri ----------------

    def _on_open(self, ws) -> None:
        # Yeniden bağlanınca mevcut tüm abonelikleri tazele
        with self._lock:
            symbols = list(self._subscribed)
        for sym in symbols:
            self._send_sub(sym, subscribe=True)
        self.log.info(f"WS bağlandı, {len(symbols)} sembol yeniden abone edildi")

    def _on_message(self, ws, message: str) -> None:
        if message == "pong":
            return
        try:
            msg = json.loads(message)
        except (ValueError, TypeError):
            return
        if msg.get("event") == "error":
            self.log.warning(f"WS hata mesajı: {msg}")
            return
        data = msg.get("data")
        arg = msg.get("arg", {})
        if not data or arg.get("channel") != "tickers":
            return
        now = time.time()
        with self._lock:
            for d in data:
                inst = d.get("instId")
                last = d.get("last")
                if inst and last:
                    self._prices[inst] = (float(last), now)

    def _on_error(self, ws, error) -> None:
        self.log.debug(f"WS hata: {error}")

    def _on_close(self, ws, *args) -> None:
        self.log.debug("WS kapandı")

    # ---------------- Thread döngüleri ----------------

    def _run_loop(self) -> None:
        """WS'i çalıştırır; koparsa otomatik yeniden bağlanır."""
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:  # noqa: BLE001
                self.log.debug(f"WS run_forever hatası: {exc}")
            if self._running:
                time.sleep(2)  # yeniden bağlanmadan önce kısa bekleme

    def _keepalive_loop(self) -> None:
        """OKX text 'ping' keepalive (idle bağlantı düşmesini önler)."""
        while self._running:
            time.sleep(15)
            try:
                if self._ws:
                    self._ws.send("ping")
            except Exception:  # noqa: BLE001
                pass


class PriceFeed:
    """PositionManager'ın kullandığı fiyat kaynağı: akış → bayatsa REST fallback."""

    def __init__(self, exchange, stream: PriceStream | None, logger,
                 staleness_seconds: float | None = None):
        self.exchange = exchange
        self.stream = stream
        self.log = logger
        self.staleness = staleness_seconds if staleness_seconds is not None \
            else CONFIG.price_staleness_seconds

    def ensure_subscribed(self, symbol: str) -> None:
        if self.stream and self.stream.is_active():
            self.stream.subscribe(symbol)

    def get_price(self, symbol: str) -> float:
        """En güncel fiyat. Akış tazeyse ondan, değilse REST ticker'dan.

        REST de başarısız olursa istisna yükselir (çağıran yakalar).
        """
        if self.stream and self.stream.is_active():
            entry = self.stream.get_price(symbol)
            if entry is not None:
                price, age = entry
                if age <= self.staleness:
                    return price
        # Fallback: REST ticker
        return self.exchange.get_ticker(symbol)["last"]

    def source_of(self, symbol: str) -> str:
        """Teşhis: fiyatın şu an akıştan mı REST'ten mi geldiği."""
        if self.stream and self.stream.is_active():
            entry = self.stream.get_price(symbol)
            if entry is not None and entry[1] <= self.staleness:
                return "ws"
        return "rest"
