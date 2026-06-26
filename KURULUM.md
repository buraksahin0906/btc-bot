# Kripto Trading Simülasyon Botu — Kurulum ve Kullanım Rehberi

> **Önemli:** Bu bot gerçek para kullanmaz. Binance'den sadece fiyat verisi okur,
> tüm alım-satımlar bilgisayarınızda sanal olarak simüle edilir.

---

## İçindekiler

1. [Gereksinimler](#1-gereksinimler)
2. [Python Kurulumu (Windows)](#2-python-kurulumu-windows)
3. [Botu Kurun](#3-botu-kurun)
4. [Botu Çalıştırın](#4-botu-çalıştırın)
5. [Web Panelini Açın](#5-web-panelini-açın)
6. [Terminal Çıktısını Okuyun](#6-terminal-çıktısını-okuyun)
7. [Web Panelini Okuyun](#7-web-panelini-okuyun)
8. [Ayarları Değiştirin](#8-ayarları-değiştirin)
9. [LONG ve SHORT Ne Demek?](#9-long-ve-short-ne-demek)
10. [Sık Hatalar ve Çözümleri](#10-sık-hatalar-ve-çözümleri)

---

## 1. Gereksinimler

- Windows 10 veya 11 (Mac/Linux da çalışır, adımlar benzerdir)
- İnternet bağlantısı (Binance'e erişim için)
- Python 3.9 veya üstü (ücretsiz, aşağıda kurulumu anlatılıyor)

---

## 2. Python Kurulumu (Windows)

**Zaten Python yüklüyse bu adımı atlayın.**

### Adım 1 — Python'u İndirin

1. Tarayıcınızda şu adresi açın: `https://www.python.org/downloads/`
2. Büyük sarı "Download Python 3.x.x" butonuna tıklayın
3. İndirilen `.exe` dosyasını çalıştırın

### Adım 2 — Python'u Yükleyin

> ⚠️ **MUTLAKA yapmanız gereken:** Kurulum ekranında en altta
> **"Add Python to PATH"** kutucuğunu işaretleyin!

- "Add Python to PATH" ✅ işaretli
- "Install Now" butonuna tıklayın
- Kurulum bitince "Close" deyin

### Adım 3 — Python'un Kurulduğunu Doğrulayın

1. `Windows + R` tuşlarına basın, `cmd` yazın, Enter'a basın
2. Açılan siyah ekranda şunu yazıp Enter'a basın:

```
python --version
```

Ekranda `Python 3.x.x` yazıyorsa kurulum başarılı.

---

## 3. Botu Kurun

### Adım 1 — Bot Klasörünü Hazırlayın

Zip dosyasını istediğiniz bir yere çıkarın.
Örnek: `C:\Kullanicim\Masaustu\btc-bot\`

Klasör içinde şu dosyalar olmalı:
```
btc-bot/
├── main.py           ← Botu başlatan dosya
├── ayarlar.py        ← Tüm ayarlar burada
├── bot.py            ← Bot motoru
├── dashboard.py      ← Web paneli
├── templates/
│   └── index.html    ← Panel arayüzü
├── requirements.txt  ← Gerekli kütüphaneler listesi
└── KURULUM.md        ← Bu dosya
```

### Adım 2 — Komut Satırını Açın

1. Windows'ta bot klasörünü açın
2. Adres çubuğuna tıklayın (üst kısımdaki yol yazıyor)
3. `cmd` yazıp Enter'a basın

Veya:
1. `Windows + R` → `cmd` → Enter
2. Klasörünüze gidin:
```
cd C:\Kullanicim\Masaustu\btc-bot
```

### Adım 3 — Kütüphaneleri Yükleyin

Komut satırında şunu yazıp Enter'a basın:

```
pip install -r requirements.txt
```

Birkaç dakika sürebilir. İndirme ve kurulum mesajları gelecek.
En sonda `Successfully installed...` yazıyorsa tamamdır.

> **Hata alırsanız:** `pip` yerine `pip3` deneyin:
> `pip3 install -r requirements.txt`

---

## 4. Botu Çalıştırın

Komut satırında şunu yazın:

```
python main.py
```

Ekranda şu çıktıyı görmelisiniz:

```
============================================================
   ₿  KRİPTO TRADİNG SİMÜLASYON BOTU  ₿
============================================================

  ⚠️  UYARI: Bu bir SİMÜLASYONDUR!
  Gerçek para kullanılmaz. Gerçek işlem açılmaz.
  Binance'den sadece VERİ OKUNUR.

  Başlangıç sanal bakiyesi : 10,000.00 USDT
  Takip edilen coinler     : BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
  Döngü süresi             : 300 sn (5 dk)
...
```

Bot çalışmaya başladıktan sonra terminali **kapatmayın**.
Durdurmak için: `Ctrl + C`

> **Not:** Botu durdurunca log dosyası (`islem_gecmisi.txt`) silinmez,
> bir sonraki çalıştırmada kaldığı yerden devam eder.

---

## 5. Web Panelini Açın

Bot çalışırken tarayıcınızda şu adresi açın:

```
http://localhost:5000
```

Panel otomatik olarak **her 5 saniyede** güncellenir.

> **Panel açılmıyorsa:**
> - Botun hâlâ çalıştığından emin olun (terminali kapatmayın)
> - Tarayıcı adres çubuğuna tam olarak `http://localhost:5000` yazın
> - Farklı tarayıcı deneyin (Chrome, Firefox, Edge)

---

## 6. Terminal Çıktısını Okuyun

Bot her döngüde terminale bilgi yazar. İşte örnek çıktı:

```
═══════════════════════════════════════════════════════════════════
  DÖNGÜ #1  |  2025-01-15 14:30:00
  Bakiye: 10000.00 USDT  |  K/Z: +0.00 USDT  |  Açık pos.: 0 / 2
═══════════════════════════════════════════════════════════════════

  ┌── BTCUSDT ──────────────────────────────────────────
  │  Güncel fiyat: 97,345.2000 USDT
  │  RSI       → 🟡 BEKLE  | RSI=52.4 (nötr bölgede)
  │  EMA Cross → 🟢 AL     | EMA9(97100.00) EMA21(96800.00)'ı yukarı kesti ↑
  │  MACD      → 🟡 BEKLE  | MACD(45.2300) sinyal(38.1200) üstte - kesişim yok
  │  ★ OYLAMA SONUCU: BEKLE → Yeterli çoğunluk yok
  │  ⬜ BEKLE: sinyal belirsiz, yeni pozisyon açılmıyor
  └───────────────────────────────────────────────────

  ┌── ETHUSDT ──────────────────────────────────────────
  │  Güncel fiyat: 3,421.8500 USDT
  │  RSI       → 🟢 AL     | RSI=31.2 (35 altında → aşırı satılmış)
  │  EMA Cross → 🟢 AL     | EMA9(3400.00) EMA21(3390.00)'ı yukarı kesti ↑
  │  MACD      → 🟡 BEKLE  | MACD(5.4200) sinyal(6.1100) altta - kesişim yok
  │  ★ OYLAMA SONUCU: LONG (2/3 AL oyu) → Yükseliş beklentisi
  │  🟢 LONG POZİSYON AÇILDI: ETHUSDT
  │     Giriş fiyatı: 3,423.5600 USDT (slippage dahil)
  │     Kullanılan: 2000.00 USDT
  │     Stop-loss: 3,320.85 | Take-profit: 3,594.74
  └───────────────────────────────────────────────────
```

### Sembollerin Anlamı

| Sembol | Anlamı |
|--------|--------|
| 🟢 AL  | Bu strateji "fiyat yükselir" diyor (AL oyu) |
| 🔴 SAT | Bu strateji "fiyat düşer" diyor (SAT oyu) |
| 🟡 BEKLE | Bu strateji kararsız |
| ★ OYLAMA | 3 stratejinin oylarının toplamı ve nihai karar |
| ⬜ BEKLE | Yeterli çoğunluk yok, işlem yapılmıyor |
| 🟢 LONG AÇILDI | Fiyat yükselir beklentisiyle pozisyon açıldı |
| 🔴 SHORT AÇILDI | Fiyat düşer beklentisiyle pozisyon açıldı |
| ✅ POZİSYON KAPANDI | Kârlı kapanış |
| ❌ POZİSYON KAPANDI | Zararlı kapanış |
| ⏳ Bekleme | Kapama sonrası aynı coinde bekleme süresi |
| 🔒 Max pozisyon dolu | Maksimum açık işlem sayısına ulaşıldı |

---

## 7. Web Panelini Okuyun

### Üst Kısım — İstatistik Kutuları

| Kutu | Ne Gösterir |
|------|-------------|
| **Sanal Bakiye** | Şu anki sanal USDT miktarı |
| **Toplam Kâr/Zarar** | Başlangıçtan beri kazanılan/kaybedilen miktar |
| **Açık Pozisyon** | Şu an kaç farklı coinde pozisyon açık |
| **Toplam İşlem** | Şimdiye kadar kaç işlem tamamlandı |

Kâr = **yeşil renk** ▲  
Zarar = **kırmızı renk** ▼

### Açık Pozisyonlar Tablosu

Şu an açık olan işlemleri gösterir:

- **Coin:** Hangi kripto (BTC, ETH...)
- **Yön:** LONG (yükseliş) veya SHORT (düşüş) pozisyonu
- **Giriş Fiyatı:** Pozisyon açıldığındaki fiyat
- **Güncel Fiyat:** Şu anki fiyat
- **Değişim:** Girişten bu yana yüzdesel değişim
- **Kullanılan:** Bu işlem için ayrılan sanal USDT miktarı
- **Anlık K/Z:** Şu an kapatsaydık ne kazanır/kaybederdik

### Coin Sinyal Durumları

Her coinin son analiz sonuçlarını gösterir:

- **RSI:** Aşırı satılmış/alınmış sinyali
- **EMA Cross:** Kısa/uzun hareketli ortalama kesişimi
- **MACD:** Momentum sinyali
- **Üst sağ köşe:** 3 stratejinin oylamasıyla ulaşılan nihai karar

### Bakiye Değişimi Grafiği

Başlangıçtan bu yana bakiyenin nasıl değiştiğini gösterir.
- Yükselen çizgi → kâr
- Düşen çizgi → zarar

### Son İşlemler

Tamamlanmış işlemlerin listesi (en yeni üstte):
- **Giriş → Çıkış:** Pozisyon açılış ve kapanış fiyatları
- **K/Z:** Bu işlemde kazanılan veya kaybedilen miktar
- **Neden:** Neden kapandı (stop-loss, take-profit, ters sinyal...)

---

## 8. Ayarları Değiştirin

`ayarlar.py` dosyasını Not Defteri ile açarak değiştirebilirsiniz.
Değiştirdikten sonra botu yeniden başlatmanız gerekir (Ctrl+C → python main.py).

### Önemli Ayarlar

```python
# Takip edilecek coinler
COINLER = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
# Başka coin eklemek için Binance'deki sembolü kullanın:
# "XRPUSDT", "ADAUSDT", "DOGEUSDT" gibi

# Başlangıç bakiyesi
BASLANGIC_BAKIYE = 10000.0
# Örnek: 50000.0 yaparsanız 50,000 sanal USDT ile başlarsınız

# Döngü süresi (saniye)
DONGÜ_SURESI = 300
# 60 = 1 dakika (çok sık, test için)
# 300 = 5 dakika (varsayılan)
# 900 = 15 dakika (daha az sinyale daha güveniriz)

# Her işlemde bakiyenin yüzde kaçı kullanılsın
POZISYON_ORANI = 0.20
# 0.10 = %10 (daha muhafazakâr)
# 0.30 = %30 (daha agresif, riskli)

# Aynı anda maksimum açık pozisyon sayısı
MAX_POZISYON = 2

# Risk yönetimi — Long için
LONG_STOP_LOSS = 0.03    # 0.03 = %3 zarar → kapat
LONG_TAKE_PROFIT = 0.05  # 0.05 = %5 kâr → kapat

# Risk yönetimi — Short için
SHORT_STOP_LOSS = 0.03   # %3 yükselirse → kapat (zarar)
SHORT_TAKE_PROFIT = 0.05 # %5 düşerse → kapat (kâr)

# Kapama sonrası bekleme döngüsü
KAPATMA_BEKLEME = 2
# 2 döngü × 5 dakika = 10 dakika bekleme (varsayılan)
```

### RSI Eşiklerini Değiştirmek

```python
RSI_SATIM_SINIRI = 35   # Bu değeri düşürürseniz daha az AL sinyali
RSI_ALIM_SINIRI = 65    # Bu değeri yükseltirseniz daha az SAT sinyali
```

---

## 9. LONG ve SHORT Ne Demek?

### LONG (Uzun Pozisyon) — "Fiyat Yükselir" Beklentisi

Düşük fiyattan alıp yüksek fiyattan satmak.

**Örnek:**
- BTC 95,000'den LONG girildi
- BTC 99,750'e yükseldi (%5 artış)
- Take-profit tetiklendi → Pozisyon kapandı, **kâr** elde edildi

**Zarar senaryosu:**
- BTC 95,000'den LONG girildi
- BTC 92,150'e düştü (%3 düşüş)
- Stop-loss tetiklendi → Pozisyon kapandı, **zarar** kesildi

### SHORT (Kısa Pozisyon) — "Fiyat Düşer" Beklentisi

Yüksek fiyattan "ödünç satıp" düşük fiyattan geri almak.
(Bu simülasyonda matematiksel hesap olarak çalışır)

**Örnek:**
- ETH 3,500'den SHORT girildi
- ETH 3,325'e düştü (%5 düşüş)
- Take-profit tetiklendi → Pozisyon kapandı, **kâr** elde edildi

**Zarar senaryosu:**
- ETH 3,500'den SHORT girildi
- ETH 3,605'e yükseldi (%3 artış)
- Stop-loss tetiklendi → Pozisyon kapandı, **zarar** kesildi

> **Short'ta dikkat:** Fiyat teorik olarak sonsuz yükselebilir,
> bu yüzden short pozisyonlar genellikle daha riskli kabul edilir.
> Bot bu riski stop-loss ile kontrol altında tutar.

---

## 10. Sık Hatalar ve Çözümleri

### ❌ "python: command not found" veya "'python' is not recognized"

**Neden:** Python PATH'e eklenmemiş.

**Çözüm:**
1. Python'u kaldırıp yeniden yükleyin
2. Kurulum sırasında **"Add Python to PATH"** kutucuğunu işaretleyin
3. Veya `python3` komutu deneyin: `python3 main.py`

---

### ❌ "No module named 'flask'" veya "ModuleNotFoundError"

**Neden:** Kütüphaneler yüklenmemiş.

**Çözüm:**
```
pip install -r requirements.txt
```

Hâlâ çalışmıyorsa:
```
pip3 install flask requests pandas numpy
```

---

### ❌ "Address already in use" (Port meşgul)

**Neden:** Port 5000 başka bir program tarafından kullanılıyor.

**Çözüm 1:** Önceki bot oturumunu tamamen kapatın (Ctrl+C), yeniden deneyin.

**Çözüm 2:** `ayarlar.py` dosyasında port numarasını değiştirin:
```python
PANEL_PORT = 5001  # veya 5002, 8080, 8888 gibi
```
Sonra `http://localhost:5001` adresini kullanın.

---

### ❌ Panel açılıyor ama "Veriler yükleniyor..." kalıyor

**Neden:** Bot henüz başlamış ve ilk döngüsünü tamamlamamış.

**Çözüm:** 1-2 dakika bekleyin. Bot ilk veriyi çekince panel dolacak.

---

### ❌ "ConnectionError" veya "Timeout" hataları terminalde

**Neden:** İnternet bağlantısı veya Binance erişim sorunu.

**Çözüm:**
- İnternet bağlantınızı kontrol edin
- Tarayıcıda `https://api.binance.com/api/v3/ping` açmayı deneyin
- VPN kullanıyorsanız kapatıp tekrar deneyin
- Bot otomatik olarak tekrar deneyecektir (hata durumunda 5 saniye bekler)

---

### ❌ "KeyboardInterrupt" mesajı

Bu bir hata değil! `Ctrl+C` tuşlarına bastığınızda botu durdurduğunuzda görünür.
Normal bir bilgi mesajıdır.

---

### ❌ Panel "Bağlantı kesildi" gösteriyor

**Neden:** Bot durdu veya çöktü.

**Çözüm:**
1. Terminali kontrol edin — hata mesajı var mı?
2. `python main.py` komutuyla yeniden başlatın

---

### İşlemler neden az oluyor?

Bot kasıtlı olarak sık işlem yapmaz. Bunun nedenleri:

1. **2/3 oy kuralı:** Üç stratejiden en az ikisinin aynı yönde oy vermesi gerekir
2. **RSI eşikleri (35/65):** Piyasa çoğunlukla bu eşiklerin dışına çıkmaz
3. **Kapama bekleme süresi:** Aynı coinde pozisyon kapandıktan sonra 2 döngü beklenir
4. **Maksimum pozisyon:** Aynı anda en fazla 2 pozisyon açılır

Bu sizi korumak içindir — gerçek borsalarda sık alım-satım, komisyon birikimi nedeniyle zararlıdır.

Daha fazla sinyal üretmek isterseniz `ayarlar.py`'de:
```python
RSI_SATIM_SINIRI = 40   # 35'ten 40'a yükselt
RSI_ALIM_SINIRI = 60    # 65'ten 60'a düşür
```

---

## Özet: İlk Çalıştırma Kontrol Listesi

- [ ] Python 3.9+ kurulu
- [ ] `pip install -r requirements.txt` çalıştırıldı
- [ ] Komut satırı bot klasöründe açık
- [ ] `python main.py` yazıldı ve bot çalışıyor
- [ ] Tarayıcıda `http://localhost:5000` açıldı
- [ ] Terminalde coin analizleri görünüyor

Hepsi tamam? Bot çalışıyor demektir. İyi simülasyonlar! 🚀
