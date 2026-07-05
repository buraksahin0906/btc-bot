# PROGRESS — PC'ye devir notu

Bu dosya, projeyi **başka bir makinede (PC) kaldığı yerden devralmak** için
yazıldı. Bu ortam (Claude Code web) geçici bir buluttur; kalıcı olan tek şey
git branch'ine push edilen bu dosyalardır.

## Nasıl devralınır (PC'de)

```bash
git clone <repo>        # veya: git pull
cd btc-bot/crypto_futures_bot
git checkout claude/trading-bot-planning-rcv65j
pip install -r requirements.txt
cp .env.example .env    # OKX anahtarlarını gir
python main.py          # paper mod (varsayılan)
```

PC'de yeni bir Claude Code oturumu açarsan, **ilk iş bu dosyayı ve README'yi
okut** — tüm bağlam burada. (Sohbet hafızası taşınmaz; kod ve bu notlar taşınır.)

## Bu oturumda TAMAMLANANLAR (çalışıyor + test edildi)

- **Tam modüler mimari** (`crypto_futures_bot/` altında, spec'teki yapıya birebir).
- **OKX V5 client** (`exchange/okx_client.py`): public + imzalı private uçlar,
  retry + üstel bekleme. (OKX bu web ortamından ağ politikası nedeniyle erişilemedi;
  **PC'de gerçek OKX ile ilk kez test edilecek.**)
- **İndikatörler** saf pandas/numpy (`strategy/indicators.py`) — birim testli.
- **Skorlama + trend filtresi + sinyal motoru** — şeffaf ağırlıklar, 78 eşiği,
  fark<10, yatay piyasa eleme.
- **Risk yönetimi**: %2 margin / 2x / isolated, günlük %3 zarar, 3 ardışık zarar →
  120 dk cooldown, R/R ≥ 1:1 stop doğrulama, reentry cooldown.
- **Net-kâr hedefi + trailing (Sistem B)** + **melez stop** (`execution/position_manager.py`)
  — açılışta kilitlenen net hedef, tepe takibi, tek çıkış, hedefe ulaşınca stop'u
  girişe çekme. **Birim + smoke testli, çalışıyor.**
- **SQLite kalıcılık** (`persistence/state_store.py`): durum + işlem geçmişi +
  reentry + borsa senkron temizliği. Bot yeniden başlayınca devam eder.
- **Paper trader** (komisyon dahil PnL), **order_manager** (maker→market fallback,
  slippage/timeout), **market_scanner** (tek ticker çağrısıyla likidite/spread),
  **candle_fetcher** (cache + BTC bias).
- **Loglama**: `bot.log` (döner) + `trades.csv` + paper özet istatistik.
- **Çift katmanlı güvenlik** + `LIVE` terminal onayı — doğruluk tablosu test edildi.
- **Testler**: `tests/test_indicators.py`, `tests/test_trailing.py`,
  `tests/smoke_e2e.py` — **hepsi geçiyor**.

## İSKELET kalanlar (PC'de detaylandırılacak)

1. **Backtester** (`backtest/backtester.py`): çalışan ama minimal walk-forward.
   Eksik: OKX'ten tarihsel mum çekme, gerçekçi fill/slippage/funding, çoklu sembol,
   parametre taraması, grafik/rapor.
2. **Telegram** (`notifier/telegram_notifier.py`): sendMessage çalışıyor ama
   formatlama minimal. Eksik: zengin sinyal kartları, /status komutu, hata uyarıları.
3. **Canlı emir yolu**: `OKXClient` private uçları yazıldı ama **gerçek OKX hesabında
   test edilmedi** (bu ortamdan erişim yoktu). PC'de önce `OKX_DEMO=true` ile doğrula.

## PC'de İLK yapılacaklar (sırayla)

1. `.env`'e OKX anahtarlarını gir, `python main.py` ile **paper** koştur; OKX public
   verisiyle gerçek coinlerin tarandığını, sinyal/özet çıktısını gör.
2. `OKX_DEMO=true` + `paper_trade=False`, `live_trading=True` ile **demo** koştur;
   gerçek emir akışını (giriş/stop/çıkış) sahte parayla doğrula.
3. Backtester'ı tarihsel veriyle besleyip win rate/istatistik çıkar.
4. **Uzun paper/demo testi** (günlerce) → gerçek win rate görülmeden canlıya geçme.
5. Ancak sonuçlar tatminkârsa, küçük bakiyeyle gerçek canlıya geç.

## Bilinen notlar / dikkat

- **Küçük bakiye + min_size:** Bakiye çok düşükse (%2 margin × 2x notional) bazı
  coinlerde borsa min emir boyutunun altına düşülür → o coin atlanır. 164 USDT ile
  çoğu likit coin çalışır; sorun olursa `config.leverage` veya bakiye artır.
- **Trailing gap:** Ani fiyat sıçramasında net kâr, trailing seviyesinin altına
  gap'leyip net hedefin altında çıkış olabilir (limit emir olmadığı için doğal).
  Melez stop (borsada asılı) yine de zararı sınırlar. Spec'te kabul edilen ödünç.
- **Funding:** Şu an yaklaşık (`≈`) hesaplanıyor; kesin funding OKX'ten çekilebilir.
- **Tarama kapsamı:** Her döngü en likit `max_symbols_per_scan=15` coin taranır
  (API tasarrufu). Artırmak istersen `config.py`.
- **1m yönetim:** Şu an açık pozisyon her tarama döngüsünde (30 sn) bir yönetiliyor.
  Daha sık trailing için PC'de ayrı 1m alt-döngü eklenebilir.
