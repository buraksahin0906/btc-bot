"""
paper_trader.py — Simülasyon motoru (paper mod).

Gerçek emir göndermeden fill ve PnL'i simüle eder. Komisyon her zaman dahildir.
paper_trade=True (varsayılan) iken order_manager tüm emirleri buraya yönlendirir.

Bakiye burada tutulur; gerçek borsa bakiyesi kullanılmaz. Böylece anahtar
olmadan da (OKX public veriyle) uçtan uca test yapılabilir.
"""

from __future__ import annotations

from config import CONFIG


class PaperTrader:
    def __init__(self, starting_balance: float | None = None):
        self.balance = (
            starting_balance if starting_balance is not None
            else CONFIG.paper_starting_balance
        )

    # ---------------- Fill simülasyonu ----------------

    def fill_market(self, ref_price: float, side: str) -> float:
        """Market emri fill fiyatı. Küçük slippage eklenir (alışta yukarı, satışta aşağı)."""
        slip = ref_price * (CONFIG.max_slippage_percent / 100.0) * 0.3  # kısmi slippage
        if side == "buy":
            return ref_price + slip
        return ref_price - slip

    def fill_limit(self, limit_price: float, current_price: float, side: str) -> float | None:
        """Limit emir dolar mı? Basit model: fiyat limit'i geçtiyse dolar.

        Maker limit: buy için fiyat <= limit ise, sell için fiyat >= limit ise dolar.
        Dolmuyorsa None (order_manager market'e düşer).
        """
        if side == "buy" and current_price <= limit_price:
            return limit_price
        if side == "sell" and current_price >= limit_price:
            return limit_price
        return None

    # ---------------- Komisyon / PnL ----------------

    @staticmethod
    def fee(notional: float, maker: bool) -> float:
        rate = (CONFIG.maker_fee_percent if maker else CONFIG.taker_fee_percent) / 100.0
        return notional * rate

    def realize_pnl(
        self,
        direction: str,
        entry: float,
        exit_price: float,
        contracts: float,
        ct_val: float,
        entry_maker: bool,
        exit_maker: bool,
    ) -> dict:
        """Kapanan işlemin brüt/net PnL'ini hesaplar ve bakiyeyi günceller.

        Döndürür: {"gross_pnl", "fees", "net_pnl"}.
        """
        entry_notional = entry * contracts * ct_val
        exit_notional = exit_price * contracts * ct_val

        if direction == "long":
            gross = exit_notional - entry_notional
        else:  # short
            gross = entry_notional - exit_notional

        fees = self.fee(entry_notional, entry_maker) + self.fee(exit_notional, exit_maker)
        net = gross - fees

        self.balance += net
        return {"gross_pnl": gross, "fees": fees, "net_pnl": net}

    def get_balance(self, ccy: str = "USDT") -> float:
        return self.balance
