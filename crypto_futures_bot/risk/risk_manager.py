"""
risk_manager.py — Gün içi risk kapıları (KATI).

Sorumluluklar:
  - Günlük maksimum zarar (bakiyenin %3'ü) aşılırsa gün kapanır.
  - Üst üste 3 zararlı işlem → 120 dk cooldown.
  - Stop ZORUNLU + risk/ödül >= 1:1 kontrolü.
  - Aynı coine hızlı tekrar giriş (reentry) cooldown'u.

Durum (ardışık zarar, günlük PnL, cooldown bitişi) StateStore'da (SQLite)
saklanır; bu sınıf o durumu okuyup karar üretir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from config import CONFIG


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


class RiskManager:
    def __init__(self, state_store):
        self.state = state_store

    # ---------------- Gün içi kapılar ----------------

    def can_open_new_trade(self, balance: float, day_start_balance: float) -> RiskDecision:
        """Yeni işlem açmaya izin var mı? (pozisyon sayısı hariç — o main'de kontrol edilir)"""
        st = self.state.get_runtime_state()

        # 1) Cooldown aktif mi?
        now = time.time()
        if st["cooldown_until"] and now < st["cooldown_until"]:
            kalan = int((st["cooldown_until"] - now) / 60)
            return RiskDecision(False, f"Cooldown aktif (~{kalan} dk kaldı)")

        # 2) Günlük zarar limiti
        daily_pnl = st["daily_pnl"]
        max_loss = day_start_balance * (CONFIG.daily_max_loss_percent / 100.0)
        if daily_pnl <= -abs(max_loss):
            return RiskDecision(
                False,
                f"Günlük zarar limiti aşıldı (PnL {daily_pnl:.4f} <= -{max_loss:.4f}) → gün kapandı"
            )

        return RiskDecision(True, "OK")

    def check_reentry(self, symbol: str) -> RiskDecision:
        """Aynı coine çok hızlı tekrar giriş engeli."""
        last_ts = self.state.get_last_entry_time(symbol)
        if last_ts:
            elapsed_min = (time.time() - last_ts) / 60
            if elapsed_min < CONFIG.reentry_cooldown_minutes:
                return RiskDecision(
                    False,
                    f"{symbol} reentry cooldown ({elapsed_min:.0f}/{CONFIG.reentry_cooldown_minutes} dk)"
                )
        return RiskDecision(True, "OK")

    # ---------------- Stop / risk-ödül ----------------

    def validate_stop(
        self,
        entry: float,
        stop: float,
        direction: str,
        net_target: float,
        notional: float,
    ) -> RiskDecision:
        """Stop mesafesini ve risk/ödül oranını doğrular.

        Kural: stop mesafesinin getirdiği zarar, net kâr hedefinden büyük olamaz
        (R/R >= 1:1). Ayrıca stop çok dar/geniş olamaz.
        """
        if stop <= 0 or entry <= 0:
            return RiskDecision(False, "Geçersiz stop/giriş")

        stop_dist_pct = abs(entry - stop) / entry * 100
        if stop_dist_pct < CONFIG.min_stop_distance_percent:
            return RiskDecision(False, f"Stop çok dar ({stop_dist_pct:.3f}%)")
        if stop_dist_pct > CONFIG.max_stop_distance_percent:
            return RiskDecision(False, f"Stop çok geniş ({stop_dist_pct:.3f}%)")

        # Yön tutarlılığı
        if direction == "long" and stop >= entry:
            return RiskDecision(False, "LONG stop girişin üstünde olamaz")
        if direction == "short" and stop <= entry:
            return RiskDecision(False, "SHORT stop girişin altında olamaz")

        # Risk (stop tetiklenince kaybedilecek yaklaşık USDT) <= net hedef
        stop_loss_usdt = notional * (stop_dist_pct / 100.0)
        if stop_loss_usdt > net_target + 1e-9:
            return RiskDecision(
                False,
                f"R/R < 1:1 (risk {stop_loss_usdt:.4f} > hedef {net_target:.4f})"
            )

        return RiskDecision(True, "OK")

    # ---------------- İşlem sonucu güncelleme ----------------

    def register_trade_result(self, net_pnl: float) -> None:
        """Kapanan işlemin sonucunu işleyip cooldown/zarar sayacını günceller."""
        st = self.state.get_runtime_state()
        daily_pnl = st["daily_pnl"] + net_pnl

        if net_pnl < 0:
            consecutive = st["consecutive_losses"] + 1
        else:
            consecutive = 0

        cooldown_until = st["cooldown_until"]
        if consecutive >= CONFIG.max_consecutive_losses:
            cooldown_until = time.time() + CONFIG.cooldown_after_losses_minutes * 60
            consecutive = 0  # cooldown sonrası temiz sayfa

        self.state.update_runtime_state(
            daily_pnl=daily_pnl,
            consecutive_losses=consecutive,
            cooldown_until=cooldown_until,
        )
