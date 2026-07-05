"""
base_exchange.py — Soyut borsa arayüzü.

İleride MEXC/Binance/Bitget eklemek için: bu ABC'yi implement eden yeni bir
sınıf yaz (ör. `BinanceClient`). Botun geri kalanı sadece bu arayüzü tanır,
borsaya özgü detayları bilmez.

Tüm metotlar borsa-bağımsız, normalize edilmiş sözlükler/değerler döndürür.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExchange(ABC):
    """Bir vadeli işlem borsası için minimum arayüz."""

    # ---------------- Public (anahtar gerektirmez) ----------------

    @abstractmethod
    def get_swap_symbols(self) -> list[dict]:
        """Tüm USDT perpetual swap sembollerini döndürür.

        Her eleman en az: {"symbol", "ct_val", "min_size", "tick_size"} içerir.
        """

    @abstractmethod
    def get_ticker(self, symbol: str) -> dict:
        """Anlık ticker: {"last", "bid", "ask", "vol_ccy_24h"} (spread hesabı için)."""

    @abstractmethod
    def get_all_tickers(self) -> list[dict]:
        """Tüm SWAP ticker'ları tek çağrıda. Her biri:
        {"symbol", "last", "bid", "ask", "vol_ccy_24h"}. Likidite taraması için.
        """

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[list]:
        """OHLCV mumları. Her mum: [ts, open, high, low, close, volume] (eskiden yeniye).

        timeframe örnekleri: "1m", "5m", "15m".
        """

    # ---------------- Private (imzalı, anahtar gerekir) ----------------

    @abstractmethod
    def get_balance(self, ccy: str = "USDT") -> float:
        """Kullanılabilir bakiye (USDT)."""

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Açık pozisyonlar. Her biri: {"symbol", "side", "size", "entry_price",
        "leverage", "margin", "liq_price"}.
        """

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int, margin_mode: str) -> dict:
        """Sembol için kaldıraç ve margin modunu ayarlar (isolated zorunlu)."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,           # "buy" | "sell"
        size: float,
        order_type: str = "limit",   # "limit" | "market"
        price: float | None = None,
        reduce_only: bool = False,
        pos_side: str | None = None,  # "long" | "short" (hedge modu için)
    ) -> dict:
        """Emir gönderir. Döndürür: {"order_id", "status", ...}."""

    @abstractmethod
    def place_stop_loss(
        self,
        symbol: str,
        side: str,           # pozisyonu kapatacak yön
        size: float,
        trigger_price: float,
        pos_side: str | None = None,
    ) -> dict:
        """Borsada asılı reduce-only stop-market emri. Bot çökse bile çalışır.

        Döndürür: {"algo_id", "status", ...}.
        """

    @abstractmethod
    def amend_stop_loss(self, symbol: str, algo_id: str, new_trigger_price: float) -> dict:
        """Asılı stop'un tetik fiyatını günceller (ör. girişe çekme)."""

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> dict:
        """Bekleyen (dolmamış) emri iptal eder."""

    @abstractmethod
    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        """Asılı algo (stop) emrini iptal eder."""

    @abstractmethod
    def get_order(self, symbol: str, order_id: str) -> dict:
        """Emir durumunu sorgular: {"status", "filled_size", "avg_price"}."""
