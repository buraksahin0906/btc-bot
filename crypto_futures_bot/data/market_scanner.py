"""
market_scanner.py — Taranacak coin listesini hazırlar ve filtreler.

  - Tüm USDT-SWAP sembollerini çeker.
  - allowed/blocked listelerine göre süzer.
  - Likiditesi düşük coinleri eler (24h hacim eşiği).
  - Spread'i yüksek coinleri eler.

Not: Her sembol için ticker çekmek maliyetlidir; likidite ön-elemesi ticker'daki
volCcy24h ile yapılır. Spread kontrolü seçilen adaylar için yapılır.
"""

from __future__ import annotations

from config import CONFIG


class MarketScanner:
    def __init__(self, exchange, logger):
        self.exchange = exchange
        self.log = logger
        self._instruments: dict[str, dict] = {}

    def load_instruments(self) -> None:
        """Sembol metadata'sını (ct_val, min_size...) bir kez yükler/tazeler."""
        try:
            symbols = self.exchange.get_swap_symbols()
            self._instruments = {s["symbol"]: s for s in symbols}
            self.log.info(f"{len(self._instruments)} USDT-SWAP sembol yüklendi")
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"Sembol listesi çekilemedi: {exc}")

    def get_instrument(self, symbol: str) -> dict | None:
        return self._instruments.get(symbol)

    def candidate_symbols(self) -> list[str]:
        """allow/block filtresinden geçen tüm sembol adları (likidite hariç)."""
        if not self._instruments:
            self.load_instruments()
        symbols = list(self._instruments.keys())
        if CONFIG.allowed_symbols:
            allow = set(CONFIG.allowed_symbols)
            symbols = [s for s in symbols if s in allow]
        block = set(CONFIG.blocked_symbols)
        return [s for s in symbols if s not in block]

    def scan_candidates(self) -> list[dict]:
        """Tek ticker çağrısıyla likidite+spread filtreleyip en likit N coini döndürür.

        Döndürür: [{"symbol", "spread_pct", "last"}], hacme göre azalan, en fazla
        CONFIG.max_symbols_per_scan eleman. API tasarrufu için tek istek kullanır.
        """
        if not self._instruments:
            self.load_instruments()

        allowed = set(self.candidate_symbols())
        try:
            tickers = self.exchange.get_all_tickers()
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"Toplu ticker çekilemedi: {exc}")
            return []

        scored = []
        for t in tickers:
            sym = t["symbol"]
            if sym not in allowed:
                continue
            vol_usdt = t["vol_ccy_24h"] * t["last"]
            if vol_usdt < CONFIG.min_24h_volume_usdt:
                continue
            mid = (t["bid"] + t["ask"]) / 2
            spread_pct = (t["ask"] - t["bid"]) / mid * 100 if mid > 0 else 999
            if spread_pct > CONFIG.max_spread_percent:
                continue
            scored.append({"symbol": sym, "spread_pct": spread_pct,
                           "last": t["last"], "vol_usdt": vol_usdt})

        scored.sort(key=lambda x: x["vol_usdt"], reverse=True)
        return scored[: CONFIG.max_symbols_per_scan]

    def passes_liquidity_and_spread(self, symbol: str) -> tuple[bool, float, str]:
        """Bir sembol likidite + spread filtresinden geçiyor mu?

        Döndürür: (geçti_mi, spread_pct, sebep).
        """
        try:
            t = self.exchange.get_ticker(symbol)
        except Exception as exc:  # noqa: BLE001
            return False, 0.0, f"ticker hatası: {exc}"

        # Likidite (24h işlem hacmi USDT cinsinden)
        vol_usdt = t["vol_ccy_24h"] * t["last"]
        if vol_usdt < CONFIG.min_24h_volume_usdt:
            return False, 0.0, f"düşük likidite ({vol_usdt:,.0f} USDT)"

        # Spread
        mid = (t["bid"] + t["ask"]) / 2
        spread_pct = (t["ask"] - t["bid"]) / mid * 100 if mid > 0 else 999
        if spread_pct > CONFIG.max_spread_percent:
            return False, spread_pct, f"spread yüksek ({spread_pct:.3f}%)"

        return True, spread_pct, "OK"
