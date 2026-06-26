# Freqtrade — Windows Kurulum ve Kullanım Rehberi

> **Güvenlik Notu:** Bu rehberde her şey **DRY-RUN (paper trading)** modunda yapılır.
> Gerçek para **asla** riske girmez. Binance'den sadece fiyat verisi okunur.
> Tüm işlemler 1.000 sanal USDT ile simüle edilir.

---

## İçindekiler

1. [Docker Desktop Kurulumu](#1-docker-desktop-kurulumu)
2. [Freqtrade Klasörünü Hazırlayın](#2-freqtrade-klasörünü-hazırlayın)
3. [Yapılandırma Dosyasını Anlayın](#3-yapılandırma-dosyasını-anlayın)
4. [İlk İmajı İndirin](#4-i̇lk-i̇majı-i̇ndirin)
5. [Backtest — Geçmiş Veri Testi](#5-backtest--geçmiş-veri-testi)
6. [Botu Canlı Başlatın (Dry-Run)](#6-botu-canlı-başlatın-dry-run)
7. [FreqUI Web Arayüzü](#7-frequi-web-arayüzü)
8. [Bot Yönetimi](#8-bot-yönetimi)
9. [Strateji Değiştirme](#9-strateji-değiştirme)
10. [Sık Hatalar ve Çözümleri](#10-sık-hatalar-ve-çözümleri)

---

## 1. Docker Desktop Kurulumu

### Docker Kurulu mu? Kontrol Edin

`Windows + R` tuşlarına basın → `cmd` yazın → Enter.

Açılan siyah ekranda şunu yazın ve Enter'a basın:

```
docker --version
```

**Eğer şuna benzer bir çıktı görüyorsanız** → Docker kurulu, **Adım 2'ye geçin:**
```
Docker version 26.1.4, build 5650f9b
```

**Eğer `docker is not recognized` hatası görüyorsanız** → Docker kurulu değil, aşağıdaki adımları izleyin.

---

### Docker Desktop Kurulum Adımları

#### Adım A — İndirin

Tarayıcınızda şu adresi açın:

```
https://docs.docker.com/desktop/install/windows-install/
```

"Docker Desktop for Windows" yazan mavi butona tıklayın. İndirme başlayacak (`Docker Desktop Installer.exe`, yaklaşık 500 MB).

#### Adım B — Sistem Gereksinimleri

Docker çalışmak için **WSL2** (Windows Subsystem for Linux) gerektirir.

Windows 10 sürüm 2004 veya üstü / Windows 11 → Destekleniyor.

Windows sürümünüzü öğrenmek için: `Windows + R` → `winver` → Enter.

#### Adım C — WSL2 Yükleyin (gerekiyorsa)

PowerShell'i **Yönetici olarak** açın (Başlat'a sağ tık → "Windows PowerShell (Yönetici)"):

```powershell
wsl --install
```

Kurulum bittikten sonra bilgisayarı **yeniden başlatın**.

#### Adım D — Docker Desktop'ı Yükleyin

1. İndirilen `Docker Desktop Installer.exe` dosyasına çift tıklayın
2. "Use WSL 2 instead of Hyper-V" seçili olsun ✅
3. "OK" → kurulum başlar (birkaç dakika)
4. Kurulum bitince "Close and restart" deyin

#### Adım E — Docker Desktop'ı Başlatın

Masaüstünde Docker simgesine çift tıklayın.  
İlk açılışta "Accept" → "Start" deyin.  
Altta "Docker Desktop is running" yazısını görünce hazır.

#### Adım F — Docker'ın Çalıştığını Doğrulayın

Komut satırını açın ve yazın:

```
docker --version
docker compose version
```

Her ikisi de versiyon numarası gösteriyorsa → **Docker başarıyla kuruldu!**

---

## 2. Freqtrade Klasörünü Hazırlayın

### Adım A — Klasörü Yerleştirin

Bu zip dosyasından çıkan `freqtrade-kurulum` klasörünü istediğiniz bir yere taşıyın.

Öneri: `C:\freqtrade\` veya `Masaüstü\freqtrade\`

İçinde şunlar olmalı:
```
freqtrade-kurulum/
├── docker-compose.yml         ← Docker ayarları
└── user_data/
    ├── config.json            ← Bot yapılandırması (DRY-RUN AÇIK)
    ├── strategies/
    │   └── BasitStrateji.py   ← Hazır strateji
    └── logs/                  ← Log dosyaları buraya yazılır
```

### Adım B — Klasörde Komut Satırı Açın

**Yöntem 1 (En kolay):**
1. Klasörü Dosya Gezgini'nde açın
2. Adres çubuğuna tıklayın (üstte klasör yolu yazıyor)
3. `cmd` yazıp Enter'a basın → Doğru klasörde komut satırı açılır

**Yöntem 2:**
1. `Windows + R` → `cmd` → Enter
2. Şunu yazın (kendi yolunuzu kullanın):
   ```
   cd C:\freqtrade\freqtrade-kurulum
   ```

**Doğru klasörde olduğunuzu kontrol edin:**
```
dir
```
Çıktıda `docker-compose.yml` ve `user_data` görünmeli.

---

## 3. Yapılandırma Dosyasını Anlayın

`user_data/config.json` dosyası Not Defteri veya VS Code ile açılabilir.

### Kritik Ayarlar (değiştirmeyin!)

```json
"dry_run": true
```
> ⚠️ **Bu satır EN KRİTİK ayardır.** `true` → gerçek para kullanılmaz.
> Asla `false` yapmayın!

```json
"dry_run_wallet": 1000
```
> Sanal cüzdanınızın başlangıç miktarı: 1000 sanal USDT.

### Değiştirebileceğiniz Ayarlar

```json
"max_open_trades": 3
```
> Aynı anda en fazla kaç açık işlem olsun? (Varsayılan: 3)

```json
"stake_amount": 100
```
> Her işlemde kaç USDT kullanılsın? (Varsayılan: 100)

```json
"pair_whitelist": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
```
> Hangi coinler takip edilsin? Yeni coin eklemek için listeye yazın:
> `"XRP/USDT"` gibi (Binance'de var mı diye kontrol edin)

### Web Arayüzü Giriş Bilgileri

```json
"username": "freqtrader",
"password": "Freqtrade2024!"
```
> Tarayıcıda `localhost:8080` açıldığında bu bilgilerle giriş yaparsınız.
> Dilediğiniz gibi değiştirebilirsiniz.

---

## 4. İlk İmajı İndirin

Freqtrade'in Docker imajını indirin (tek seferlik, ~500 MB):

```
docker compose pull
```

**Beklenen çıktı:**
```
Pulling freqtrade ... done
```

İndirme birkaç dakika sürebilir. "done" yazısını görünce tamamdır.

---

## 5. Backtest — Geçmiş Veri Testi

Botu canlıya almadan önce geçmiş verilerle test etmek önemlidir.

### Adım A — Geçmiş Veri İndir

Önce Binance'den son 60 günlük 5 dakikalık veri çekin:

```
docker compose run --rm freqtrade download-data --config user_data/config.json --exchange binance --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT --days 60 --timeframe 5m
```

**Beklenen çıktı (yaklaşık):**
```
INFO - Downloading pair BTC/USDT, interval 5m, from ...
INFO - Downloading pair ETH/USDT, interval 5m, from ...
...
INFO - Done! 4 pairs downloaded.
```

Veriler `user_data/data/binance/` klasörüne kaydedilir.

**Bu komutu anlamak:**
| Parça | Açıklama |
|-------|----------|
| `download-data` | Veri indirme modunu başlat |
| `--pairs BTC/USDT ...` | Hangi coinlerin verisi indirilsin |
| `--days 60` | Kaç günlük veri indirilsin |
| `--timeframe 5m` | 5 dakikalık mum verisi |

### Adım B — Backtest Çalıştır

```
docker compose run --rm freqtrade backtesting --config user_data/config.json --strategy BasitStrateji --timerange 20241101-20250101
```

**Beklenen çıktı (özet kısmı):**
```
=============== SUMMARY METRICS ==================
| Metric                | Value               |
|-----------------------|---------------------|
| Backtesting from      | 2024-11-01 00:00:00 |
| Backtesting to        | 2025-01-01 00:00:00 |
| Max open trades       | 3                   |
| Total/Daily Avg Trades| 47 / 0.77           |
| Win rate              | 61.7%               |
| Total profit %        | 8.53%               |
| Avg. stake amount     | 100 USDT            |
| Tot. profit USDT      | 85.30 USDT          |
| Max Drawdown          | -12.50%             |
==================================================
```

### Backtest Sonuçlarını Okuma

| Metrik | Ne Anlama Gelir |
|--------|----------------|
| **Win rate** | İşlemlerin yüzde kaçı kârlı kapandı |
| **Total profit %** | Test döneminde toplam kâr/zarar yüzdesi |
| **Tot. profit USDT** | Kazanılan sanal para miktarı |
| **Max Drawdown** | En kötü düşüş (bakiyenin en fazla ne kadar eridi) |
| **Total Trades** | Kaç işlem açıldı |
| **Avg Duration** | Ortalama işlem süresi |

> **İyi bir strateji için genel kriterler:**
> - Win rate %50'nin üstünde
> - Max Drawdown -%20'den az
> - Risk/Ödül oranı mantıklı

### Tarih Aralığını Değiştirmek

```
--timerange 20240601-20241201
```
`YYYYMMDD-YYYYMMDD` formatında yazılır.

---

## 6. Botu Canlı Başlatın (Dry-Run)

### Botu Başlatın

```
docker compose up -d
```

**Beklenen çıktı:**
```
[+] Running 1/1
 ✔ Container freqtrade  Started
```

`-d` = arka planda çalışır (terminali kapatabilirsiniz).

### Bot Çalışıyor Mu? Kontrol Edin

```
docker compose ps
```

**Beklenen çıktı:**
```
NAME         IMAGE                           STATUS         PORTS
freqtrade    freqtradeorg/freqtrade:stable   Up 2 minutes   127.0.0.1:8080->8080/tcp
```

`STATUS` sütununda `Up` yazıyorsa bot çalışıyor demektir.

---

## 7. FreqUI Web Arayüzü

### Arayüzü Açın

Bot çalışırken tarayıcınızda şu adresi açın:

```
http://localhost:8080
```

**Giriş bilgileri:**
- Kullanıcı adı: `freqtrader`
- Şifre: `Freqtrade2024!`

### FreqUI'yi Okuma Kılavuzu

**Dashboard sekmesi:**
- **Cüzdan bakiyesi:** Sanal USDT miktarı (başlangıçta 1000)
- **Toplam kâr/zarar:** Başlangıçtan beri kazanılan/kaybedilen
- **Açık işlemler:** Şu an aktif pozisyonlar

**Trades (İşlemler) sekmesi:**
- Tüm açık ve kapanmış işlemlerin listesi
- Her işlem için: coin, giriş fiyatı, kâr/zarar, süre

**Pairlist sekmesi:**
- Takip edilen coinler ve anlık durumları

**Logs sekmesi:**
- Bot'un gerçek zamanlı log çıktısı
- Hata veya uyarıları buradan görürsünüz

**Grafik:**
- Sağ üstten coin seçin → alım/satım noktalarını grafikte görün

> **Önemli:** Ekranda "DRY" veya "DRY-RUN" ibaresi görünmeli.
> Bu, gerçek para kullanılmadığını teyit eder.

---

## 8. Bot Yönetimi

### Botu Durdur

```
docker compose down
```

**Beklenen çıktı:**
```
[+] Running 1/1
 ✔ Container freqtrade  Removed
```

### Botu Yeniden Başlat

```
docker compose up -d
```

### Logları Canlı İzle

```
docker compose logs -f freqtrade
```

`-f` = canlı takip (real-time follow). Çıkmak için `Ctrl + C`.

Son 50 satır log için:
```
docker compose logs --tail=50 freqtrade
```

Log dosyası ayrıca `user_data/logs/freqtrade.log` içinde de tutulur.
Not Defteri ile açabilirsiniz.

### Bot Durumu Kontrol

```
docker compose ps
```

`Up` → Çalışıyor  
`Exited` → Durmuş (hata olabilir, log'a bakın)

### Docker'ı Tamamen Temizle (Sıfırdan Başlama)

```
docker compose down
docker compose pull
docker compose up -d
```

---

## 9. Strateji Değiştirme

### Mevcut Strateji Hakkında

`user_data/strategies/BasitStrateji.py` — RSI + EMA crossover stratejisi.

### Farklı Strateji Kullanmak

#### Adım A — Strateji Dosyasını Ekle

Yeni `.py` strateji dosyasını `user_data/strategies/` klasörüne kopyalayın.

#### Adım B — docker-compose.yml Güncelle

`docker-compose.yml` dosyasını Not Defteri ile açın, son satırı değiştirin:

```yaml
# Eski:
--strategy BasitStrateji
# Yeni:
--strategy YeniStratejiAdi
```

#### Adım C — Botu Yeniden Başlat

```
docker compose down
docker compose up -d
```

### Stratejiyi Düzenlemek

`user_data/strategies/BasitStrateji.py` dosyasını Not Defteri veya
Notepad++ ile açıp düzenleyebilirsiniz.

Değiştirip kaydettikten sonra botu yeniden başlatın:
```
docker compose down && docker compose up -d
```

### RSI Eşiklerini Ayarlama

`BasitStrateji.py` içinde şu satırları bulun:

```python
(dataframe["rsi"] < 35)   ← AL sinyali eşiği (düşürürseniz daha az sinyal)
(dataframe["rsi"] > 65)   ← SAT sinyali eşiği (yükseltirseniz daha az sinyal)
```

### minimal_roi (Kâr Hedefi) Ayarlama

```python
minimal_roi = {
    "0":   0.05,   # 0. dakikada %5 kâr → çık
    "60":  0.03,   # 60. dakikada %3 kâr → çık
    "120": 0.02,   # 120. dakikada %2 kâr → çık
    "240": 0.01    # 240. dakikada %1 kâr → çık
}
```

### Stop-Loss Ayarlama

```python
stoploss = -0.03   # -0.03 = %3 zarar → işlemi kapat
```

`-0.05` yaparsanız %5 zararı kabul edersiniz (daha toleranslı ama riskli).

---

## 10. Sık Hatalar ve Çözümleri

---

### ❌ `docker: command not found`

**Neden:** Docker kurulu değil veya PATH'e eklenmemiş.

**Çözüm:**
1. Docker Desktop'ı indirin ve kurun (Adım 1'e bakın)
2. Docker Desktop'ın çalıştığından emin olun (system tray'de docker simgesi)
3. Komut satırını kapatıp yeniden açın

---

### ❌ `Error response from daemon: driver failed programming external connectivity`

**Neden:** Port 8080 başka bir program tarafından kullanılıyor.

**Çözüm:**
`docker-compose.yml` dosyasını açın, şu satırı bulun:
```yaml
ports:
  - "127.0.0.1:8080:8080"
```
Şöyle değiştirin (8081 veya 9080 gibi):
```yaml
ports:
  - "127.0.0.1:8081:8080"
```
Sonra `http://localhost:8081` adresini kullanın.

---

### ❌ `Exchange binance is not available`

**Neden:** İnternet bağlantısı yok veya Binance'e erişilemiyor.

**Çözüm:**
- İnternet bağlantınızı kontrol edin
- VPN kullanıyorsanız kapatıp deneyin
- `docker compose logs freqtrade` ile tam hatayı görün

---

### ❌ `Strategy 'BasitStrateji' not found`

**Neden:** Strateji dosyası doğru klasörde değil.

**Çözüm:**
- `user_data/strategies/BasitStrateji.py` dosyasının var olduğundan emin olun
- Dosya adı büyük/küçük harf dahil tam eşleşmeli
- `docker-compose.yml` içindeki `--strategy BasitStrateji` ile eşleşmeli

---

### ❌ FreqUI açılmıyor (`localhost:8080`)

**Neden:** Bot henüz başlatılmamış veya port kapalı.

**Adım 1:** Bot çalışıyor mu?
```
docker compose ps
```
`Up` yazıyorsa çalışıyor.

**Adım 2:** Birkaç dakika bekleyin (bot ilk başlarken veri yüklüyor).

**Adım 3:** Farklı tarayıcı deneyin (Chrome, Firefox, Edge).

**Adım 4:** `http://127.0.0.1:8080` adresini deneyin (localhost yerine).

---

### ❌ `No data found for BTC/USDT`

**Neden:** Backtest için veri indirilmemiş.

**Çözüm:**
Önce veri indirme komutunu çalıştırın:
```
docker compose run --rm freqtrade download-data --config user_data/config.json --exchange binance --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT --days 60 --timeframe 5m
```

---

### ❌ `WSL2 is not installed` veya WSL2 hatası

**Çözüm:**
PowerShell'i Yönetici olarak açın ve çalıştırın:
```powershell
wsl --install
wsl --update
```
Bilgisayarı yeniden başlatın.

---

### ❌ `Insufficient balance` (Yetersiz bakiye)

**Neden:** `stake_amount` değeri `dry_run_wallet`'tan büyük.

**Çözüm:**
`config.json` içinde:
```json
"dry_run_wallet": 1000,   ← Sanal bakiye
"stake_amount": 100,      ← Her işlem başına kullanılacak miktar
"max_open_trades": 3      ← 3 × 100 = 300, 1000'den küçük ✓
```

`max_open_trades × stake_amount` değerinin `dry_run_wallet`'tan küçük olmasına dikkat edin.

---

### ❌ İşlemler neden çok az açılıyor?

**Neden:** Strateji kasıtlı olarak seçici davranıyor.

**Açıklama:**
- RSI'nin 35'in altına düşmesi ve EMA kesişimi **aynı anda** gerekiyor
- Piyasa her zaman bu koşulları sağlamıyor

**Daha fazla sinyal için:**
`BasitStrateji.py` içinde RSI eşiğini yükseltin:
```python
(dataframe["rsi"] < 40)   # 35'ten 40'a (daha çok sinyal üretir)
```
Dosyayı kaydedin ve botu yeniden başlatın.

---

## Hızlı Komut Referansı

| Komut | Ne Yapar |
|-------|----------|
| `docker compose pull` | Freqtrade imajını indir/güncelle |
| `docker compose up -d` | Botu arka planda başlat |
| `docker compose down` | Botu durdur |
| `docker compose ps` | Bot durumunu göster |
| `docker compose logs -f freqtrade` | Canlı log izle |
| `docker compose logs --tail=50 freqtrade` | Son 50 satır log |
| `docker compose restart freqtrade` | Botu yeniden başlat |

**Backtest komutları:**
```
# Veri indir:
docker compose run --rm freqtrade download-data --config user_data/config.json --exchange binance --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT --days 60 --timeframe 5m

# Backtest yap:
docker compose run --rm freqtrade backtesting --config user_data/config.json --strategy BasitStrateji --timerange 20241101-20250101
```

---

## Kontrol Listesi — İlk Kurulum

- [ ] Docker Desktop kuruldu ve çalışıyor
- [ ] `docker --version` komutu çalışıyor
- [ ] `freqtrade-kurulum` klasörü hazır
- [ ] Komut satırı bu klasörde açık
- [ ] `docker compose pull` tamamlandı
- [ ] `docker compose run --rm freqtrade download-data ...` çalıştırıldı
- [ ] Backtest tamamlandı ve sonuçlar okundu
- [ ] `docker compose up -d` ile bot başlatıldı
- [ ] `http://localhost:8080` tarayıcıda açıldı
- [ ] FreqUI'de "DRY" ibaresi görünüyor ✅

---

*Son güncelleme: Haziran 2025 | Freqtrade stable sürümü için*
