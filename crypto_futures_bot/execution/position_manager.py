"""
position_manager.py — Net-kâr hedefi + trailing + melez stop yönetimi.

Bu modül bu sürümün en önemli farkı. Klasik kademeli TP1/TP2 YOK; tek net
hedef + trailing (Sistem B) var.

Akış (her 1m tick):
  1. Önce güncel fiyat okunur (yarış önleme), sonra karar verilir.
  2. Net kâr (komisyon + yaklaşık funding düşülmüş) hesaplanır.
  3. Fiyat stop'a değdiyse → tam çıkış (zarar).
  4. Net kâr, kilitli net hedefe ulaşınca:
       - trailing başlar,
       - borsadaki asılı stop BİR KEZ girişe çekilir (risksiz hale getirir).
  5. Trailing aktifken tepe net kâr izlenir; net kâr tepeden geri gelip trailing
     seviyesine (>=) değince pozisyonun TAMAMI kapanır. Trailing tabanı net
     hedefin altına asla inmez.

Kilitlenen net hedef ve tüm durum SQLite'a yazılır → bot yeniden başlarsa devam eder.
"""

from __future__ import annotations

import time

from config import CONFIG


class PositionManager:
    def __init__(self, exchange, order_manager, paper_trader, state_store,
                 risk_manager, trade_logger, notifier, is_live: bool, logger,
                 price_feed=None):
        self.exchange = exchange
        self.orders = order_manager
        self.paper = paper_trader
        self.state = state_store
        self.risk = risk_manager
        self.trade_log = trade_logger
        self.notifier = notifier
        self.is_live = is_live
        self.log = logger
        # price_feed: WS-öncelikli fiyat kaynağı. None ise doğrudan REST ticker.
        self.price_feed = price_feed

    def _read_price(self, symbol: str) -> float:
        """En güncel fiyat: price_feed (WS→REST) varsa ondan, yoksa REST ticker."""
        if self.price_feed is not None:
            return self.price_feed.get_price(symbol)
        return self.exchange.get_ticker(symbol)["last"]

    # ------------------------------------------------------------------
    # Net kâr hesabı (komisyon + yaklaşık funding dahil)
    # ------------------------------------------------------------------

    def _unrealized_net(self, pos: dict, price: float) -> float:
        contracts = pos["contracts"]
        ct_val = pos["ct_val"]
        entry = pos["entry_price"]

        entry_notional = entry * contracts * ct_val
        exit_notional = price * contracts * ct_val

        if pos["direction"] == "long":
            gross = exit_notional - entry_notional
        else:
            gross = entry_notional - exit_notional

        entry_fee = entry_notional * (
            (CONFIG.maker_fee_percent if pos.get("entry_maker") else CONFIG.taker_fee_percent) / 100.0
        )
        # Çıkışı en kötü senaryo (taker) varsay → net muhafazakâr
        exit_fee = exit_notional * (CONFIG.taker_fee_percent / 100.0)

        # Yaklaşık funding (pozisyon açık kaldıkça): kesin değil, "≈".
        funding_est = self._approx_funding(pos, entry_notional)

        return gross - entry_fee - exit_fee - funding_est

    @staticmethod
    def _approx_funding(pos: dict, notional: float) -> float:
        """Kaba funding tahmini: 8 saatte bir ~%0.01 varsayımı (işaret: yaklaşık).

        Kesin funding OKX'ten çekilmeli; burada muhafazakâr küçük bir kesinti.
        """
        held_hours = max(0.0, (time.time() - pos.get("opened_ts", time.time())) / 3600)
        periods = held_hours / 8.0
        return notional * 0.0001 * periods

    # ------------------------------------------------------------------
    # Ana yönetim
    # ------------------------------------------------------------------

    def manage(self, pos: dict) -> dict | None:
        """Açık pozisyonu bir tick yönetir. Kapandıysa None, açıksa güncel pos döner."""
        symbol = pos["symbol"]
        direction = pos["direction"]

        # 1) Önce güncel fiyat (WS akışı → bayatsa REST). Yarış önleme: karardan önce.
        try:
            price = self._read_price(symbol)
        except Exception as exc:  # noqa: BLE001
            self.log.warning(f"{symbol} fiyat okunamadı, tick atlanıyor: {exc}")
            return pos

        # 2) Stop kontrolü (paper'da bot yönetir; live'da borsa da yönetir ama
        #    bot da tespit edip kaydı kapatır — senkron main'de teyit edilir)
        stop = pos["stop_price"]
        stop_hit = (direction == "long" and price <= stop) or \
                   (direction == "short" and price >= stop)
        if stop_hit:
            return self._exit(pos, stop, "stop-loss")

        # 3) Net kâr
        net = self._unrealized_net(pos, price)
        net_target = pos["net_target"]

        # 4) Hedefe ulaşıldı mı? (>= ile "geçti mi" mantığı)
        if not pos.get("trailing_active") and net >= net_target:
            pos["trailing_active"] = True
            pos["peak_net"] = net
            # Stop'u bir kez girişe çek (risksiz). Sürekli güncelleme yok.
            if not pos.get("stop_moved_to_entry"):
                moved = self.orders.amend_stop(symbol, pos.get("algo_id", ""), pos["entry_price"])
                if moved:
                    pos["stop_price"] = pos["entry_price"]
                    pos["stop_moved_to_entry"] = True
                    self.log.info(f"{symbol} kâr hedefi kilitlendi, stop girişe çekildi (risksiz)")
            self.state.save_open_position(pos)

        # 5) Trailing aktifse tepe izle + çıkış kontrolü
        if pos.get("trailing_active"):
            if net > pos["peak_net"]:
                pos["peak_net"] = net
                self.state.save_open_position(pos)

            giveback = pos["peak_net"] * (CONFIG.trailing_giveback_percent / 100.0)
            trailing_level = max(net_target, pos["peak_net"] - giveback)

            if net <= trailing_level:
                return self._exit(pos, price, "trailing")

        # Açık kalmaya devam
        self.state.save_open_position(pos)
        return pos

    # ------------------------------------------------------------------
    # Çıkış
    # ------------------------------------------------------------------

    def _exit(self, pos: dict, ref_price: float, reason: str) -> None:
        symbol = pos["symbol"]
        direction = pos["direction"]
        contracts = pos["contracts"]
        ct_val = pos["ct_val"]

        # Borsadaki asılı stop'u iptal et (çıkışı biz yapıyoruz) — live
        if self.is_live and pos.get("algo_id") and pos["algo_id"] != "paper":
            try:
                self.exchange.cancel_algo_order(symbol, pos["algo_id"])
            except Exception:  # noqa: BLE001
                pass

        result = self.orders.close_position(symbol, direction, contracts, ref_price)
        if result is None:
            self.log.error(f"{symbol} ÇIKIŞ BAŞARISIZ — bir sonraki tick'te tekrar denenecek")
            return pos  # pozisyonu koru, tekrar denenecek

        exit_price = result["exit_price"]
        exit_maker = result["exit_maker"]

        pnl = self.paper.realize_pnl(
            direction, pos["entry_price"], exit_price, contracts, ct_val,
            entry_maker=pos.get("entry_maker", True), exit_maker=exit_maker,
        )

        trade = {
            "ts": time.time(),
            "symbol": symbol,
            "direction": direction,
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "contracts": contracts,
            "gross_pnl": pnl["gross_pnl"],
            "fees": pnl["fees"],
            "net_pnl": pnl["net_pnl"],
            "exit_reason": reason,
            "net_target": pos["net_target"],
            "peak_net": pos.get("peak_net", 0.0),
        }
        self.state.record_trade(trade)
        self.trade_log.log_trade(trade)
        self.risk.register_trade_result(pnl["net_pnl"])
        self.state.clear_open_position()

        emoji = "✅" if pnl["net_pnl"] >= 0 else "🔻"
        msg = (f"{emoji} KAPANDI {symbol} {direction.upper()} ({reason}) | "
               f"Net PnL: {pnl['net_pnl']:+.4f} USDT | Bakiye: {self.paper.get_balance():.2f}")
        self.log.info(msg)
        self.notifier.send(msg)
        return None
