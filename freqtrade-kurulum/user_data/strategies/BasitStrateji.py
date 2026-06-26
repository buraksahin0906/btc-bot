# ================================================================
# BasitStrateji.py — Freqtrade için RSI + EMA Stratejisi
# ================================================================
#
# Bu strateji şu indikatörleri kullanır:
#   RSI  (14 periyot) — Aşırı satım/alım bölgesi
#   EMA9 / EMA21     — Kısa ve uzun hareketli ortalama kesişimi
#   MACD             — Momentum göstergesi
#
# Giriş (AL) koşulu:
#   RSI < 35  VE  EMA9, EMA21'i yukarı kesiyor
#
# Çıkış (SAT) koşulu:
#   RSI > 65  VEYA  EMA9, EMA21'i aşağı kesiyor
#
# Stop-loss: %3  |  Take-profit (ROI): %5
# ================================================================

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class BasitStrateji(IStrategy):
    """
    Basit RSI + EMA Crossover Stratejisi.
    Dry-run (paper trading) modunda güvenle test edilebilir.
    """

    # Freqtrade arayüz sürümü (değiştirmeyin)
    INTERFACE_VERSION = 3

    # İşlem zaman dilimi
    timeframe = "5m"

    # Stop-loss: giriş fiyatından %3 düşerse zararı kes
    stoploss = -0.03

    # ROI (Kâr Hedefi) Tablosu
    # "dakika": "minimum_kazanç_oranı"
    # 0. dakikada %5 kâr varsa çık
    # 60. dakikada %3 kâr varsa çık
    # 120. dakikada %2 kâr varsa çık
    # 240. dakikada %1 kâr varsa çık
    minimal_roi = {
        "0":   0.05,
        "60":  0.03,
        "120": 0.02,
        "240": 0.01
    }

    # Kayan stop-loss (trailing stop): kapalı
    trailing_stop = False

    # Bot başlarken kaç mum geçmişe ihtiyaç var
    # (indikatörlerin doğru hesaplanabilmesi için)
    startup_candle_count: int = 30

    # ─── 1. İNDİKATÖRLERİ HESAPLA ────────────────────────────────
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Her coin için teknik indikatörleri hesaplar.
        dataframe: Fiyat verisi (açılış, kapanış, yüksek, düşük, hacim)
        metadata:  {"pair": "BTC/USDT"} gibi coin bilgisi
        """

        # RSI — 14 periyot
        # 0-100 arasında değer alır.
        # < 35 → aşırı satılmış (AL fırsatı)
        # > 65 → aşırı alınmış (SAT fırsatı)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # EMA 9 — Kısa periyot hareketli ortalama (hızlı)
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)

        # EMA 21 — Uzun periyot hareketli ortalama (yavaş)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)

        # MACD — 12/26/9
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"]       = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"]   = macd["macdhist"]

        return dataframe

    # ─── 2. GİRİŞ SİNYALİ (LONG — AL) ──────────────────────────
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Alış sinyalini belirler.
        'enter_long' = 1 olan muma ulaşıldığında bot alım yapar.
        """

        dataframe.loc[
            (
                # RSI aşırı satım bölgesinde
                (dataframe["rsi"] < 35) &

                # EMA9, EMA21'i YUKARI kesti (yükseliş başlıyor)
                (dataframe["ema9"] > dataframe["ema21"]) &
                (dataframe["ema9"].shift(1) <= dataframe["ema21"].shift(1)) &

                # Hacim sıfır değil (gerçek işlem var)
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    # ─── 3. ÇIKIŞ SİNYALİ (SAT) ─────────────────────────────────
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Satış sinyalini belirler.
        Not: Stop-loss ve ROI de otomatik çıkış sağlar.
        """

        dataframe.loc[
            (
                # RSI aşırı alım bölgesine girdi
                (dataframe["rsi"] > 65) |

                # EMA9, EMA21'i AŞAĞI kesti (düşüş başlıyor)
                (
                    (dataframe["ema9"] < dataframe["ema21"]) &
                    (dataframe["ema9"].shift(1) >= dataframe["ema21"].shift(1))
                )
            ),
            "exit_long",
        ] = 1

        return dataframe
