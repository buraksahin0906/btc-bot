"""
order_manager.py — Emir yürütme (paper/live yönlendirme tek merkez).

GÜVENLİK: Gerçek emir SADECE is_live=True iken (live_trading=True VE
paper_trade=False) borsaya gider. Aksi halde her şey PaperTrader'a yönlenir.

Sorumluluklar:
  - Giriş: önce maker limit dener, timeout'ta market'e düşer.
  - Slippage kontrolü: fiyat çok hızlı kaçıyorsa işlem açma.
  - Stop: borsada asılı reduce-only stop-market (live) / bellekte (paper).
  - Çıkış: önce maker (kısa timeout), dolmazsa market (garantili çıkış).
"""

from __future__ import annotations

import time

from config import CONFIG


class OrderManager:
    def __init__(self, exchange, paper_trader, is_live: bool, logger):
        self.exchange = exchange
        self.paper = paper_trader
        self.is_live = is_live
        self.log = logger

    # ------------------------------------------------------------------
    # Giriş
    # ------------------------------------------------------------------

    def open_entry(
        self,
        symbol: str,
        direction: str,
        contracts: float,
        ref_price: float,
        ct_val: float,
    ) -> dict | None:
        """Pozisyon girişi. Döndürür: {entry_price, contracts, entry_maker} veya None.

        side: long→buy, short→sell.
        """
        side = "buy" if direction == "long" else "sell"
        pos_side = direction

        # Maker limit fiyatı: fiyatın hafif gerisine koy (dolması için piyasa gelmeli)
        limit_price = self._maker_limit_price(ref_price, side)

        if not self.is_live:
            return self._paper_entry(symbol, side, contracts, ref_price, limit_price)

        # ---- LIVE ----
        try:
            order = self.exchange.place_order(
                symbol, side, contracts, order_type="limit",
                price=limit_price, reduce_only=False, pos_side=pos_side,
            )
            order_id = order["order_id"]
            filled = self._await_fill(symbol, order_id, CONFIG.maker_limit_timeout_seconds)
            if filled and filled["status"] == "filled":
                return {"entry_price": filled["avg_price"], "contracts": filled["filled_size"],
                        "entry_maker": True, "order_id": order_id}
            # Timeout → iptal et, market'e düş
            self.exchange.cancel_order(symbol, order_id)

            # Slippage kontrolü: güncel fiyat referanstan çok kaçtıysa vazgeç
            cur = self.exchange.get_ticker(symbol)["last"]
            if abs(cur - ref_price) / ref_price * 100 > CONFIG.max_slippage_percent:
                self.log.warning(f"{symbol} slippage yüksek, giriş iptal (ref {ref_price} → {cur})")
                return None

            mkt = self.exchange.place_order(
                symbol, side, contracts, order_type="market",
                reduce_only=False, pos_side=pos_side,
            )
            filled = self._await_fill(symbol, mkt["order_id"], 5)
            if filled and filled["filled_size"] > 0:
                return {"entry_price": filled["avg_price"], "contracts": filled["filled_size"],
                        "entry_maker": False, "order_id": mkt["order_id"]}
            return None
        except Exception as exc:  # noqa: BLE001 — borsa hatasında çökme yok
            self.log.error(f"{symbol} giriş emri hatası: {exc}")
            return None

    def _paper_entry(self, symbol, side, contracts, ref_price, limit_price) -> dict:
        # Paper: maker limit'i dener; anlık fiyat limit'i "geçmiş" say → dolar kabul et
        fill = self.paper.fill_limit(limit_price, ref_price, side)
        if fill is not None:
            return {"entry_price": fill, "contracts": contracts,
                    "entry_maker": True, "order_id": "paper"}
        fill = self.paper.fill_market(ref_price, side)
        return {"entry_price": fill, "contracts": contracts,
                "entry_maker": False, "order_id": "paper"}

    # ------------------------------------------------------------------
    # Stop (borsada asılı, reduce-only)
    # ------------------------------------------------------------------

    def place_stop(self, symbol: str, direction: str, contracts: float,
                   trigger_price: float) -> str | None:
        """Reduce-only stop-market. Live'da borsaya asılır; paper'da bellekte tutulur.

        Döndürür: algo_id (live) / "paper".
        """
        close_side = "sell" if direction == "long" else "buy"
        if not self.is_live:
            return "paper"
        try:
            r = self.exchange.place_stop_loss(
                symbol, close_side, contracts, trigger_price, pos_side=direction
            )
            return r.get("algo_id", "")
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"{symbol} stop emri hatası: {exc}")
            return None

    def amend_stop(self, symbol: str, algo_id: str, new_trigger: float) -> bool:
        if not self.is_live or not algo_id or algo_id == "paper":
            return True
        try:
            self.exchange.amend_stop_loss(symbol, algo_id, new_trigger)
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"{symbol} stop güncelleme hatası: {exc}")
            return False

    # ------------------------------------------------------------------
    # Çıkış
    # ------------------------------------------------------------------

    def close_position(self, symbol: str, direction: str, contracts: float,
                       ref_price: float) -> dict | None:
        """Pozisyonu tamamen kapat. Önce maker (kısa timeout), dolmazsa market.

        Döndürür: {exit_price, exit_maker}.
        """
        close_side = "sell" if direction == "long" else "buy"

        if not self.is_live:
            # Paper: maker'ı kısa dene, olmazsa market (garantili çıkış tercih edilir)
            limit_price = self._maker_limit_price(ref_price, close_side)
            fill = self.paper.fill_limit(limit_price, ref_price, close_side)
            if fill is not None:
                return {"exit_price": fill, "exit_maker": True}
            fill = self.paper.fill_market(ref_price, close_side)
            return {"exit_price": fill, "exit_maker": False}

        # ---- LIVE ----
        try:
            limit_price = self._maker_limit_price(ref_price, close_side)
            order = self.exchange.place_order(
                symbol, close_side, contracts, order_type="limit",
                price=limit_price, reduce_only=True, pos_side=direction,
            )
            filled = self._await_fill(symbol, order["order_id"],
                                      CONFIG.trailing_exit_maker_timeout_seconds)
            if filled and filled["status"] == "filled":
                return {"exit_price": filled["avg_price"], "exit_maker": True}
            self.exchange.cancel_order(symbol, order["order_id"])
            # Garantili çıkış: market
            mkt = self.exchange.place_order(
                symbol, close_side, contracts, order_type="market",
                reduce_only=True, pos_side=direction,
            )
            filled = self._await_fill(symbol, mkt["order_id"], 5)
            price = filled["avg_price"] if filled and filled["avg_price"] else ref_price
            return {"exit_price": price, "exit_maker": False}
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"{symbol} çıkış emri hatası: {exc}")
            return None

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    @staticmethod
    def _maker_limit_price(ref_price: float, side: str) -> float:
        """Maker olma ihtimali için fiyatı hafif geri çeker (1 bps)."""
        offset = ref_price * 0.0001
        return ref_price - offset if side == "buy" else ref_price + offset

    def _await_fill(self, symbol: str, order_id: str, timeout_s: int) -> dict | None:
        """Emir dolana veya timeout'a kadar bekler (live)."""
        deadline = time.time() + timeout_s
        last = None
        while time.time() < deadline:
            try:
                last = self.exchange.get_order(symbol, order_id)
                if last["status"] in ("filled", "canceled"):
                    return last
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        return last
