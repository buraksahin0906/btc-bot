# Crypto Futures Trading Bot (OKX V5)

OKX USDT perpetual futures üzerinde çalışan, **disiplinli risk yönetimi** odaklı,
modüler bir Python trading botu. Her coin için ayrı LONG/SHORT puanı hesaplar,
yalnızca **net yön varsa ve puan ≥ 78** ise işlem açar. Yatay piyasada işlem
açmaz — varsayılan davranış **beklemektir**.

## ⚠️ Risk uyarısı (önce oku)

- **Bu bot kâr garantisi VERMEZ.** Amaç riski disiplinle yönetmek (minimum zarar),
  kârı trailing ile akıllıca bırakmak (maksimum kâr) ve komisyonu minimize etmektir.
  Bunlar birer *yaklaşım*, sonuç garantisi değildir.
- Kaldıraçlı vadeli işlemler **yüksek risklidir**; sermayenin tamamını
  kaybettirebilir.
- **Gerçek kazanma oranı ancak uzun paper trade testiyle görülür.** Backtest ve
  paper sonuçları gelecek performansı garanti etmez.
- **Backtest ve paper trade tamamlanmadan, gerçek win rate görülmeden canlı işlem
  açma.**

## Güvenlik modeli (çift katman)

| paper_trade | live_trading | Sonuç |
|-------------|--------------|-------|
| `True`  | `False` | Simülasyon (varsayılan) |
| `True`  | `True`  | Simülasyon (çift kilit) |
| `False` | `False` | Simülasyon |
| `False` | `True`  | **GERÇEK EMİR** |

Gerçek emir **SADECE** `live_trading=True` **VE** `paper_trade=False` iken gönderilir.
Ayrıca canlı moda geçişte terminalde büyük harf **`LIVE`** onayı istenir.

## Kurulum

```bash
cd crypto_futures_bot
pip install -r requirements.txt

# Anahtarları ayarla
cp .env.example .env
# .env dosyasını aç, OKX_API_KEY / SECRET / PASSPHRASE gir.
# Demo (testnet) için OKX_DEMO=true yap.
```

`.env` dosyası `.gitignore`'dadır; anahtarların **asla** commit edilmez.

## Çalıştırma

### Paper trade (varsayılan, güvenli)

```bash
python main.py
```

Anahtar olmadan da OKX'in **halka açık** market verisiyle çalışır: coinleri tarar,
sinyal üretir, simüle işlem açar/kapatır, sonuçları `logs/trades.csv` ve SQLite'a yazar.

### Backtest (iskelet — PC'de detaylandırılacak)

```bash
python -m backtest.backtester BTC-USDT-SWAP
```

### Canlı moda geçiş (dikkatli)

`config.py` içinde:

```python
paper_trade = False
live_trading = True
```

Sonra `python main.py` → terminalde `LIVE` yazarak onayla. **Önce demo (`OKX_DEMO=true`)
ile test etmen şiddetle önerilir.**

## Mimari

```
main.py              → döngü orkestrasyonu (her 30 sn tarama)
config.py            → tüm ayarlar + .env
exchange/            → BaseExchange (soyut) + OKXClient (V5 REST)
data/                → market_scanner (likidite/spread), candle_fetcher (15m/5m/1m),
                       price_stream (WebSocket anlık fiyat + REST fallback)
strategy/            → indicators (saf pandas/numpy), scoring, trend_filter, signal_engine
risk/                → risk_manager (günlük zarar, cooldown, R/R), position_sizer (%2, 2x)
execution/           → order_manager (maker→market), position_manager (net hedef + trailing)
persistence/         → state_store (SQLite: durum + geçmiş + borsa senkron)
paper/               → paper_trader (simüle fill/PnL, komisyon dahil)
backtest/            → backtester (iskelet)
notifier/            → telegram_notifier (iskelet)
logs/                → trade_logger (bot.log + trades.csv)
tests/               → indikatör, trailing/stop, uçtan uca smoke testleri
```

Yeni borsa eklemek için: `exchange/base_exchange.py`'deki `BaseExchange`'i implement
eden yeni bir sınıf yaz (ör. `BinanceClient`), `main.build_exchange()`'i güncelle.

## Strateji özeti

- **Zaman dilimleri:** 15m ana trend, 5m giriş sinyali, 1m takip/trailing/çıkış.
- **İndikatörler:** EMA 9/21/50/200, RSI 14, MACD, ADX 14, Bollinger, VWAP, ATR 14,
  Volume SMA 20 — tümü saf pandas/numpy (harici TA kütüphanesi yok).
- **Puanlama:** Her coin için `long_score` / `short_score` (0–100). Ağırlıklar
  `strategy/scoring.py`'de şeffaf.
- **Karar:** Kazanan skor ≥ 78, diğeri < 78 ve aradaki fark ≥ 10 olmalı. Aksi halde
  ve yatay piyasada işlem yok.
- **Risk:** isolated, 2x, margin = bakiye %2 (sabit), max 1 pozisyon, günlük zarar
  %3'te gün kapanır, 3 ardışık zarar → 120 dk cooldown, stop zorunlu (R/R ≥ 1:1).
- **Kâr/çıkış (Sistem B):** Net hedef = bakiye %0.05 (komisyon dahil, açılışta
  kilitlenir). Hedefe ulaşınca trailing başlar; tepeden geri gelince **tam** çıkış.
- **Melez stop:** Borsada asılı reduce-only stop-market (bot çökse bile korur) +
  bot tarafında trailing. Hedef kilitlenince stop bir kez girişe çekilir (risksiz).
- **Hız (scalping):** Açık pozisyonda fiyat **WebSocket** ile anlık akar; trailing/stop
  ~1 sn'de bir kontrol edilir (30 sn tarama yerine). WS düşerse otomatik REST fallback.

## Testler

```bash
python tests/test_indicators.py    # indikatör doğrulaması
python tests/test_trailing.py      # net hedef + trailing + stop yaşam döngüsü
python tests/test_price_stream.py  # WebSocket akış + REST fallback
python tests/smoke_e2e.py          # mock borsayla uçtan uca boru hattı
```

## Config'de öne çıkan ayarlar (`config.py`)

`leverage=2`, `risk_per_trade_percent=2`, `daily_max_loss_percent=3`,
`max_consecutive_losses=3`, `cooldown_after_losses_minutes=120`,
`min_signal_score=78`, `scan_interval_seconds=30`,
`net_profit_target_percent_of_balance=0.05`, `maker_fee_percent=0.02`,
`taker_fee_percent=0.05`, `paper_starting_balance=164`.
