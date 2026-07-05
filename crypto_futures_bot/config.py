"""
config.py — Botun tüm ayarları tek yerde.

Sabit davranış ayarları buradaki `Config` dataclass'ında; gizli anahtarlar
(.env dosyasından) `Secrets` içinde tutulur. Anahtarlar ASLA koda yazılmaz.

KULLANIM:
    from config import CONFIG, SECRETS
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()  # aynı klasördeki .env dosyasını yükler
except ImportError:
    # python-dotenv yoksa ortam değişkenleri yine de okunur.
    pass


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    """Botun davranışını belirleyen ayarlar. Güvenli varsayılanlar (paper)."""

    # --- Borsa / çalışma modu ---
    exchange_name: str = "okx"
    # GÜVENLİK: Gerçek emir SADECE live_trading=True VE paper_trade=False iken gönderilir.
    paper_trade: bool = True
    live_trading: bool = False

    # --- Kaldıraç / margin ---
    leverage: int = 2                     # test aşaması için düşük (güvenlik önceliği)
    margin_mode: str = "isolated"         # cross KESİNLİKLE yasak

    # --- Risk yönetimi (KATI) ---
    risk_per_trade_percent: float = 2.0   # her işlemde margin = bakiyenin %2'si (sabit)
    max_open_positions: int = 1
    daily_max_loss_percent: float = 3.0   # gün içi zarar bu %'yi aşarsa gün kapanır
    max_consecutive_losses: int = 3       # üst üste bu kadar zarar → cooldown
    cooldown_after_losses_minutes: int = 120

    # --- Sinyal / tarama ---
    min_signal_score: float = 78.0        # işlem için minimum skor
    score_gap_min: float = 10.0           # long/short skor farkı bundan azsa işlem yok
    scan_interval_seconds: int = 30

    # Sembol filtreleri (boş allowed = tüm USDT-SWAP taranır)
    allowed_symbols: list[str] = field(default_factory=list)
    blocked_symbols: list[str] = field(default_factory=list)

    # --- Komisyon (OKX standart, config'de ayarlanabilir) ---
    maker_fee_percent: float = 0.02       # %0.02
    taker_fee_percent: float = 0.05       # %0.05

    # --- Kâr hedefi / trailing ---
    net_profit_target_percent_of_balance: float = 0.05  # net hedef = bakiyenin %0.05'i
    use_profit_trailing: bool = True
    # Trailing tepeden ne kadar geri gelince çıkılır (net kârın yüzdesi olarak).
    trailing_giveback_percent: float = 30.0

    # --- Likidite / spread filtreleri ---
    min_24h_volume_usdt: float = 5_000_000.0   # bunun altındaki coinler elenir
    max_spread_percent: float = 0.08           # spread bundan genişse işlem yok
    max_symbols_per_scan: int = 15             # her döngüde en likit N coin taranır (API tasarrufu)

    # --- Emir yürütme ---
    maker_limit_timeout_seconds: int = 8       # limit dolmazsa market'e düş
    trailing_exit_maker_timeout_seconds: int = 3
    max_slippage_percent: float = 0.10         # fiyat bu kadar kaçarsa işlem açma
    reentry_cooldown_minutes: int = 15         # aynı coine hızlı tekrar giriş engeli

    # --- Stop / risk-ödül ---
    # ATR bazlı stop, net kâr hedefinden büyük çıkarsa ne yapılsın?
    #   "skip"  → işlem açma (varsayılan, en güvenli)
    #   "clamp" → stop'u kâr hedefine eşitle (R/R = 1:1)
    stop_wider_than_target_action: str = "skip"
    atr_stop_multiplier: float = 1.5           # stop = giriş ± ATR * çarpan
    min_stop_distance_percent: float = 0.05    # çok dar stop → işlem yok
    max_stop_distance_percent: float = 3.0     # çok geniş stop → işlem yok

    # --- Yatay piyasa (trend) filtresi eşikleri ---
    adx_min: float = 20.0                 # işlem için ADX bunun üstünde olmalı
    adx_flat_threshold: float = 18.0      # bunun altı = yatay
    ema_proximity_percent: float = 0.15   # EMA21 ve EMA50 bu kadar yakınsa = yatay
    bb_squeeze_percent: float = 1.2       # BB genişliği bunun altındaysa = daralma

    # --- Telegram ---
    telegram_enabled: bool = False

    # --- Bakiye (paper mod başlangıç sermayesi) ---
    paper_starting_balance: float = 164.0

    # --- Zaman dilimleri (OKX bar kodları) ---
    tf_trend: str = "15m"   # ana trend yönü
    tf_entry: str = "5m"    # giriş sinyali
    tf_manage: str = "1m"   # pozisyon takibi / trailing / çıkış
    candle_limit: int = 200  # her TF için çekilecek mum sayısı

    # --- Dosya yolları ---
    db_path: str = "bot_state.db"
    log_path: str = "logs/bot.log"
    trades_csv_path: str = "logs/trades.csv"

    def gross_target_from_net(self, net_target: float, notional: float) -> float:
        """Net hedefe gidiş-dönüş komisyonu ekleyerek brüt hedefi bulur.

        notional: pozisyonun nominal büyüklüğü (fiyat * miktar).
        Gidiş-dönüş = açılış + kapanış komisyonu (taker varsayımı, en kötü senaryo).
        """
        roundtrip_fee = notional * (self.taker_fee_percent / 100.0) * 2
        return net_target + roundtrip_fee


@dataclass
class Secrets:
    """Gizli anahtarlar — sadece .env / ortam değişkenlerinden okunur."""

    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_api_passphrase: str = ""
    okx_demo: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            okx_api_key=os.getenv("OKX_API_KEY", ""),
            okx_api_secret=os.getenv("OKX_API_SECRET", ""),
            okx_api_passphrase=os.getenv("OKX_API_PASSPHRASE", ""),
            okx_demo=_get_bool("OKX_DEMO", False),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )

    def has_okx_keys(self) -> bool:
        return bool(self.okx_api_key and self.okx_api_secret and self.okx_api_passphrase)


# Global tekil örnekler
CONFIG = Config()
SECRETS = Secrets.from_env()
