# ================================================================
# BOT.PY - Kripto Trading Simülasyon Botu - Ana Motor
# ================================================================
#
# Bu dosya botun tüm işlemlerini yapar:
#   1. Binance'den gerçek fiyat ve mum verisi çeker (API anahtarı gerekmez)
#   2. Üç teknik analiz stratejisi hesaplar (RSI, EMA, MACD)
#   3. 3 stratejiyi oylatır, kararı çoğunlukla alır (2/3 oy)
#   4. LONG (yükseliş) veya SHORT (düşüş) pozisyon açar
#   5. Stop-loss ve take-profit ile riski yönetir
#   6. Sanal cüzdanı günceller (gerçek para kullanılmaz)
#   7. Her şeyi terminale ve log dosyasına yazar
#   8. Web paneli için veri hazırlar
#
# LONG ne demek? Fiyatın yükseleceğini düşündüğümüzde açarız.
# SHORT ne demek? Fiyatın düşeceğini düşündüğümüzde açarız.
# ================================================================

import requests        # İnternet istekleri için
import pandas as pd    # Veri işleme için
import numpy as np     # Matematik işlemleri için
import threading       # Paralel çalışma (bot + web paneli aynı anda)
import time            # Bekleme için
from datetime import datetime
import ayarlar         # Kendi ayarlar dosyamız

# ================================================================
# PAYLAŞILAN DURUM - Dashboard ile Bot Arasındaki Köprü
# ================================================================
# Bu sözlük hem bot thread'i hem de Flask web sunucusu tarafından
# okunur/güncellenir. "durum_kilidi" aynı anda çakışmayı önler.

durum_kilidi = threading.Lock()

paylasilan_durum = {
    "bakiye": ayarlar.BASLANGIC_BAKIYE,
    "baslangic_bakiye": ayarlar.BASLANGIC_BAKIYE,
    "kar_zarar": 0.0,
    "kar_zarar_yuzde": 0.0,
    "acik_pozisyonlar": {},      # Şu an açık olan işlemler
    "son_islemler": [],          # Kapanmış işlemlerin listesi
    "coin_sinyaller": {},        # Her coinin son sinyal durumu
    "guncel_fiyatlar": {},       # Her coinin anlık fiyatı
    "bakiye_gecmisi": [ayarlar.BASLANGIC_BAKIYE],  # Grafik için
    "zaman_gecmisi": [datetime.now().strftime("%H:%M")],
    "son_guncelleme": "-",
    "bot_durumu": "Başlıyor...",
    "dongü_no": 0
}


# ================================================================
# SANAL CÜZDAN SINIFI
# ================================================================
# Gerçek para kullanmadan işlemleri simüle eder.
# Bakiye, pozisyonlar ve işlem geçmişi burada tutulur.

class SanalCuzdan:
    """Simülasyon için sanal para cüzdanı. Gerçek para kullanılmaz."""

    def __init__(self):
        self.bakiye = ayarlar.BASLANGIC_BAKIYE  # Mevcut USDT bakiyesi
        self.acik = {}       # Açık pozisyonlar: {coin: {yon, giris_fiyati, ...}}
        self.gecmis = []     # Kapanmış işlemler listesi (en yeni başta)
        self.bekleme = {}    # Kapatma sonrası bekleme: {coin: kalan_döngü}

    def pozisyon_ac(self, coin, yon, piyasa_fiyati):
        """
        Yeni bir pozisyon açar.
        yon: "LONG" veya "SHORT"
        Slippage ve komisyon gerçekçilik için uygulanır.
        """
        # Kullanılacak USDT miktarını hesapla (%20 gibi)
        kullanilacak_usdt = self.bakiye * ayarlar.POZISYON_ORANI

        if kullanilacak_usdt < 1.0:
            return False, "Yetersiz bakiye (minimum 1 USDT gerekli)"

        # Slippage uygula: alışta biraz pahalıya, satışta biraz ucuza
        if yon == "LONG":
            # Long alışında fiyat biraz yukarı kayar (kötü taraf)
            efektif_fiyat = piyasa_fiyati * (1 + ayarlar.SLIPPAGE)
        else:  # SHORT
            # Short girişinde fiyat biraz aşağı kayar (kötü taraf)
            efektif_fiyat = piyasa_fiyati * (1 - ayarlar.SLIPPAGE)

        # Komisyon düş
        komisyon_tutari = kullanilacak_usdt * ayarlar.KOMISYON
        net_usdt = kullanilacak_usdt - komisyon_tutari

        # Net USDT ile kaç coin alabiliriz?
        coin_adedi = net_usdt / efektif_fiyat

        # Bakiyeden düş
        self.bakiye -= kullanilacak_usdt

        # Pozisyonu kaydet
        self.acik[coin] = {
            "yon": yon,
            "giris_fiyati": round(efektif_fiyat, 8),
            "coin_adedi": coin_adedi,
            "usdt_miktari": round(kullanilacak_usdt, 4),
            "acilis_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return True, efektif_fiyat

    def pozisyon_kapat(self, coin, piyasa_fiyati, neden=""):
        """
        Mevcut bir pozisyonu kapatır.
        Kâr/zarar hesaplanır ve bakiyeye eklenir.
        """
        if coin not in self.acik:
            return None

        p = self.acik[coin]
        yon = p["yon"]

        # Kapanışta da slippage uygulanır (ters yönde)
        if yon == "LONG":
            # Long kapatırken (satış) fiyat biraz aşağı kayar
            efektif_fiyat = piyasa_fiyati * (1 - ayarlar.SLIPPAGE)
        else:  # SHORT
            # Short kapatırken (alış) fiyat biraz yukarı kayar
            efektif_fiyat = piyasa_fiyati * (1 + ayarlar.SLIPPAGE)

        # Kâr/zarar hesapla
        if yon == "LONG":
            # Long: fiyat yükselince kâr ederiz
            brut_kar = (efektif_fiyat - p["giris_fiyati"]) * p["coin_adedi"]
        else:  # SHORT
            # Short: fiyat düşünce kâr ederiz
            brut_kar = (p["giris_fiyati"] - efektif_fiyat) * p["coin_adedi"]

        # Çıkış komisyonu
        cikis_komisyonu = p["usdt_miktari"] * ayarlar.KOMISYON
        net_kar = brut_kar - cikis_komisyonu

        # Bakiyeye geri ekle (ana para + kâr/zarar)
        self.bakiye += p["usdt_miktari"] + net_kar

        # İşlem kaydı oluştur
        islem = {
            "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "coin": coin,
            "yon": yon,
            "giris": round(p["giris_fiyati"], 6),
            "cikis": round(efektif_fiyat, 6),
            "usdt": round(p["usdt_miktari"], 2),
            "kar_zarar": round(net_kar, 4),
            "kar_zarar_yuzde": round((net_kar / p["usdt_miktari"]) * 100, 2),
            "neden": neden
        }

        # Geçmişe ekle (en yeni başa)
        self.gecmis.insert(0, islem)

        # Pozisyonu kaldır
        del self.acik[coin]

        # Bekleme süresini başlat (aynı coinde hemen tekrar girmeyi önler)
        self.bekleme[coin] = ayarlar.KAPATMA_BEKLEME

        return islem

    def anlik_kar_zarar(self, coin, guncel_fiyat):
        """Açık bir pozisyonun şu anki kâr/zararını hesaplar (USDT)"""
        if coin not in self.acik:
            return 0.0
        p = self.acik[coin]
        if p["yon"] == "LONG":
            return round((guncel_fiyat - p["giris_fiyati"]) * p["coin_adedi"], 4)
        else:  # SHORT
            return round((p["giris_fiyati"] - guncel_fiyat) * p["coin_adedi"], 4)

    def bekleme_guncelle(self):
        """Her döngü başında bekleme sayaçlarını bir azalt"""
        bitecekler = []
        for coin in self.bekleme:
            self.bekleme[coin] -= 1
            if self.bekleme[coin] <= 0:
                bitecekler.append(coin)
        for coin in bitecekler:
            del self.bekleme[coin]


# ================================================================
# VERİ ÇEKME FONKSİYONLARI
# ================================================================

def fiyat_cek(sembol):
    """
    Binance'den anlık fiyat çeker.
    Hiç API anahtarı gerekmez - herkese açık endpoint.
    """
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        yanit = requests.get(url, params={"symbol": sembol}, timeout=10)
        yanit.raise_for_status()
        return float(yanit.json()["price"])
    except requests.exceptions.Timeout:
        log_yaz(f"[UYARI] {sembol} fiyat isteği zaman aşımına uğradı")
        return None
    except Exception as hata:
        log_yaz(f"[HATA] {sembol} fiyat çekilemedi: {hata}")
        return None


def mum_verisi_cek(sembol):
    """
    Binance'den mum (kline/candlestick) verisi çeker.
    Her mum: açılış, kapanış, en yüksek, en düşük fiyatı içerir.
    """
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": sembol,
            "interval": ayarlar.MUM_ARALIGI,
            "limit": ayarlar.MUM_LIMIT
        }
        yanit = requests.get(url, params=params, timeout=15)
        yanit.raise_for_status()

        veriler = yanit.json()
        # Binance 12 sütun döndürür, biz önemlilerini kullanırız
        df = pd.DataFrame(veriler, columns=[
            "acilis_z", "acilis", "yuksek", "dusuk", "kapanis",
            "hacim", "kapanis_z", "kote_hacim", "islem_sayisi",
            "alici_hacim", "alici_kote", "yoksay"
        ])

        # Sayısal sütunları float'a çevir
        for sutun in ["acilis", "yuksek", "dusuk", "kapanis", "hacim"]:
            df[sutun] = df[sutun].astype(float)

        return df

    except requests.exceptions.Timeout:
        log_yaz(f"[UYARI] {sembol} mum verisi isteği zaman aşımına uğradı")
        return None
    except Exception as hata:
        log_yaz(f"[HATA] {sembol} mum verisi çekilemedi: {hata}")
        return None


# ================================================================
# TEKNİK ANALİZ STRATEJİLERİ
# ================================================================

def rsi_hesapla(kapanis_serisi, periyot=14):
    """
    RSI (Relative Strength Index) hesaplar.
    0-100 arasında değer alır.
    Düşük RSI = aşırı satılmış (toparlanabilir) → AL fırsatı
    Yüksek RSI = aşırı alınmış (düşebilir) → SAT fırsatı
    """
    degisim = kapanis_serisi.diff()
    kazanc = degisim.where(degisim > 0, 0.0)
    kayip = -degisim.where(degisim < 0, 0.0)

    # Üstel ağırlıklı ortalama (son değerlere daha fazla ağırlık)
    ort_kazanc = kazanc.ewm(com=periyot - 1, min_periods=periyot).mean()
    ort_kayip = kayip.ewm(com=periyot - 1, min_periods=periyot).mean()

    rs = ort_kazanc / ort_kayip
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def ema_hesapla(kapanis_serisi, periyot):
    """
    EMA (Exponential Moving Average) - Üstel Hareketli Ortalama.
    Normal ortalamadan farklı olarak son fiyatlara daha fazla ağırlık verir.
    """
    return kapanis_serisi.ewm(span=periyot, adjust=False).mean()


def strateji_rsi(df):
    """
    RSI Stratejisi:
    - RSI < 35 (aşırı satılmış bölge) → AL oyu
    - RSI > 65 (aşırı alınmış bölge) → SAT oyu
    - Arada → BEKLE oyu
    Döndürür: (sinyal, açıklama_metni)
    """
    rsi = rsi_hesapla(df["kapanis"], ayarlar.RSI_PERIYOT)
    son_rsi = round(float(rsi.iloc[-1]), 2)

    if son_rsi < ayarlar.RSI_SATIM_SINIRI:
        return "AL", f"RSI={son_rsi} ({ayarlar.RSI_SATIM_SINIRI} altında → aşırı satılmış)"
    elif son_rsi > ayarlar.RSI_ALIM_SINIRI:
        return "SAT", f"RSI={son_rsi} ({ayarlar.RSI_ALIM_SINIRI} üstünde → aşırı alınmış)"
    else:
        return "BEKLE", f"RSI={son_rsi} (nötr bölgede)"


def strateji_ema(df):
    """
    EMA Crossover (Kesişim) Stratejisi:
    - Kısa EMA (9), Uzun EMA'yı (21) YUKARI keserse → AL oyu (yükseliş trendi başlıyor)
    - Kısa EMA (9), Uzun EMA'yı (21) AŞAĞI keserse → SAT oyu (düşüş trendi başlıyor)
    - Kesişim yoksa → BEKLE oyu
    """
    ema_kisa = ema_hesapla(df["kapanis"], ayarlar.EMA_KISA)
    ema_uzun = ema_hesapla(df["kapanis"], ayarlar.EMA_UZUN)

    # Bir önceki ve şimdiki değerleri karşılaştır
    onceki_k = float(ema_kisa.iloc[-2])
    onceki_u = float(ema_uzun.iloc[-2])
    simdi_k = float(ema_kisa.iloc[-1])
    simdi_u = float(ema_uzun.iloc[-1])

    # Kesişim tespiti
    if onceki_k <= onceki_u and simdi_k > simdi_u:
        # Kısa EMA uzunu yukarı kesti → boğa sinyali
        return "AL", f"EMA{ayarlar.EMA_KISA}({simdi_k:.2f}) EMA{ayarlar.EMA_UZUN}({simdi_u:.2f})'ı yukarı kesti ↑"
    elif onceki_k >= onceki_u and simdi_k < simdi_u:
        # Kısa EMA uzunu aşağı kesti → ayı sinyali
        return "SAT", f"EMA{ayarlar.EMA_KISA}({simdi_k:.2f}) EMA{ayarlar.EMA_UZUN}({simdi_u:.2f})'ı aşağı kesti ↓"
    else:
        # Kesişim yok, trend yönünü bilgi olarak göster
        trend = "↑ yükseliş" if simdi_k > simdi_u else "↓ düşüş"
        return "BEKLE", f"EMA{ayarlar.EMA_KISA}({simdi_k:.2f}) vs EMA{ayarlar.EMA_UZUN}({simdi_u:.2f}) - kesişim yok, trend: {trend}"


def strateji_macd(df):
    """
    MACD (Moving Average Convergence Divergence) Stratejisi:
    - MACD çizgisi sinyal çizgisini YUKARI keserse → AL oyu
    - MACD çizgisi sinyal çizgisini AŞAĞI keserse → SAT oyu
    - Kesişim yoksa → BEKLE oyu
    """
    # MACD = Hızlı EMA - Yavaş EMA
    ema_hizli = ema_hesapla(df["kapanis"], ayarlar.MACD_HIZLI)
    ema_yavas = ema_hesapla(df["kapanis"], ayarlar.MACD_YAVAS)
    macd = ema_hizli - ema_yavas

    # Sinyal çizgisi = MACD'nin kendi EMA'sı
    sinyal = macd.ewm(span=ayarlar.MACD_SINYAL, adjust=False).mean()

    # Önceki ve şimdiki değerleri karşılaştır
    m1, s1 = float(macd.iloc[-2]), float(sinyal.iloc[-2])
    m0, s0 = float(macd.iloc[-1]), float(sinyal.iloc[-1])

    if m1 <= s1 and m0 > s0:
        return "AL", f"MACD({m0:.4f}) sinyal({s0:.4f})'i yukarı kesti ↑"
    elif m1 >= s1 and m0 < s0:
        return "SAT", f"MACD({m0:.4f}) sinyal({s0:.4f})'i aşağı kesti ↓"
    else:
        durum = "üstte" if m0 > s0 else "altta"
        return "BEKLE", f"MACD({m0:.4f}) sinyal({s0:.4f}) {durum} - kesişim yok"


def oylama_yap(rsi_s, ema_s, macd_s):
    """
    3 stratejinin verdiği oyları sayar ve nihai karar verir.
    2 veya 3 AL oyu → LONG aç
    2 veya 3 SAT oyu → SHORT aç
    Aksi hâlde → BEKLE
    """
    al_oyu = sum(1 for s in [rsi_s, ema_s, macd_s] if s == "AL")
    sat_oyu = sum(1 for s in [rsi_s, ema_s, macd_s] if s == "SAT")

    if al_oyu >= 2:
        return "LONG", al_oyu
    elif sat_oyu >= 2:
        return "SHORT", sat_oyu
    else:
        return "BEKLE", 0


# ================================================================
# LOG YAZMA
# ================================================================

def log_yaz(mesaj):
    """Mesajı hem terminale yazdırır hem de log dosyasına kaydeder"""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    try:
        with open(ayarlar.LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except Exception as h:
        print(f"  [UYARI] Log dosyası yazılamadı: {h}")


# ================================================================
# PAYLAŞILAN DURUMU GÜNCELLE (Web Paneli İçin)
# ================================================================

def durumu_guncelle(cuzdan, fiyatlar, sinyaller, dongü_no):
    """Dashboard'a gösterilecek verileri paylaşılan sözlükte günceller"""
    global paylasilan_durum

    toplam_kz = round(cuzdan.bakiye - ayarlar.BASLANGIC_BAKIYE, 4)
    yuzde_kz = round((toplam_kz / ayarlar.BASLANGIC_BAKIYE) * 100, 2)

    # Açık pozisyonlara anlık fiyat ve K/Z bilgisi ekle
    acik_ozet = {}
    for coin, poz in cuzdan.acik.items():
        fiyat = fiyatlar.get(coin, poz["giris_fiyati"])
        acik_ozet[coin] = {
            "yon": poz["yon"],
            "giris_fiyati": round(poz["giris_fiyati"], 6),
            "coin_adedi": round(poz["coin_adedi"], 6),
            "usdt_miktari": round(poz["usdt_miktari"], 2),
            "acilis_zamani": poz["acilis_zamani"],
            "guncel_fiyat": round(fiyat, 6),
            "anlik_kar_zarar": cuzdan.anlik_kar_zarar(coin, fiyat)
        }

    # Bakiye geçmişine yeni nokta ekle
    yeni_bakiye_g = list(paylasilan_durum["bakiye_gecmisi"])
    yeni_zaman_g = list(paylasilan_durum["zaman_gecmisi"])
    yeni_bakiye_g.append(round(cuzdan.bakiye, 2))
    yeni_zaman_g.append(datetime.now().strftime("%H:%M"))

    # Grafikte en fazla 60 nokta göster
    if len(yeni_bakiye_g) > 60:
        yeni_bakiye_g = yeni_bakiye_g[-60:]
        yeni_zaman_g = yeni_zaman_g[-60:]

    with durum_kilidi:
        paylasilan_durum.update({
            "bakiye": round(cuzdan.bakiye, 2),
            "kar_zarar": toplam_kz,
            "kar_zarar_yuzde": yuzde_kz,
            "acik_pozisyonlar": acik_ozet,
            "son_islemler": cuzdan.gecmis[:25],
            "coin_sinyaller": sinyaller,
            "guncel_fiyatlar": {k: round(v, 6) for k, v in fiyatlar.items()},
            "bakiye_gecmisi": yeni_bakiye_g,
            "zaman_gecmisi": yeni_zaman_g,
            "son_guncelleme": datetime.now().strftime("%H:%M:%S"),
            "bot_durumu": "Çalışıyor ✓",
            "dongü_no": dongü_no
        })


# ================================================================
# ANA BOT DÖNGÜSÜ
# ================================================================

def bot_baslat():
    """
    Botun ana döngüsü. Bu fonksiyon arka plan thread'inde çalışır.

    Her döngüde şunları yapar:
    1. Tüm coinler için Binance'den veri çeker
    2. RSI, EMA, MACD stratejilerini hesaplar
    3. Oylama ile LONG / SHORT / BEKLE kararı verir
    4. Açık pozisyonların stop-loss / take-profit kontrolünü yapar
    5. Yeni pozisyon açılıp açılmayacağını değerlendirir
    6. Dashboard'u günceller ve log kaydeder
    7. Bir sonraki döngüye kadar bekler
    """
    log_yaz("=" * 65)
    log_yaz("  KRİPTO TRADİNG SİMÜLASYON BOTU BAŞLIYOR")
    log_yaz("  !! GERÇEK PARA KULLANILMIYOR - SADECE SİMÜLASYON !!")
    log_yaz("=" * 65)
    log_yaz(f"  Başlangıç bakiyesi : {ayarlar.BASLANGIC_BAKIYE} USDT (sanal)")
    log_yaz(f"  Takip edilen coinler: {', '.join(ayarlar.COINLER)}")
    log_yaz(f"  Döngü süresi        : {ayarlar.DONGÜ_SURESI} saniye ({ayarlar.DONGÜ_SURESI//60} dakika)")
    log_yaz(f"  Mum aralığı         : {ayarlar.MUM_ARALIGI}")
    log_yaz(f"  Long stop/take      : %{ayarlar.LONG_STOP_LOSS*100:.0f} / %{ayarlar.LONG_TAKE_PROFIT*100:.0f}")
    log_yaz(f"  Short stop/take     : %{ayarlar.SHORT_STOP_LOSS*100:.0f} / %{ayarlar.SHORT_TAKE_PROFIT*100:.0f}")
    log_yaz("=" * 65)

    cuzdan = SanalCuzdan()
    dongü_no = 0

    while True:
        dongü_no += 1

        try:
            # ─── Döngü Başlığı ───────────────────────────────────────────
            log_yaz(f"\n{'═' * 65}")
            log_yaz(f"  DÖNGÜ #{dongü_no}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            log_yaz(f"  Bakiye: {cuzdan.bakiye:.2f} USDT  |  "
                    f"K/Z: {cuzdan.bakiye - ayarlar.BASLANGIC_BAKIYE:+.2f} USDT  |  "
                    f"Açık pos.: {len(cuzdan.acik)} / {ayarlar.MAX_POZISYON}")
            log_yaz(f"{'═' * 65}")

            # Her döngü başında bekleme sayaçlarını bir azalt
            cuzdan.bekleme_guncelle()

            fiyatlar = {}   # Bu döngüde çekilen fiyatlar
            sinyaller = {}  # Dashboard için sinyal özeti

            # ─── Her Coin İçin Döngü ─────────────────────────────────────
            for coin in ayarlar.COINLER:

                log_yaz(f"\n  ┌── {coin} ──────────────────────────────────────────")

                # 1) Güncel fiyatı çek
                fiyat = fiyat_cek(coin)
                if fiyat is None:
                    log_yaz(f"  │  [ATLA] Fiyat alınamadı, bu döngüde geçildi")
                    log_yaz(f"  └───────────────────────────────────────────────────")
                    continue

                fiyatlar[coin] = fiyat
                log_yaz(f"  │  Güncel fiyat: {fiyat:,.4f} USDT")

                # 2) Mum verilerini çek
                df = mum_verisi_cek(coin)
                if df is None or len(df) < 30:
                    log_yaz(f"  │  [ATLA] Yeterli mum verisi alınamadı (en az 30 gerekli)")
                    log_yaz(f"  └───────────────────────────────────────────────────")
                    continue

                # 3) Üç stratejiyi hesapla
                rsi_s, rsi_a = strateji_rsi(df)
                ema_s, ema_a = strateji_ema(df)
                macd_s, macd_a = strateji_macd(df)

                # 4) Oyları terminale yazdır
                sembol_map = {"AL": "🟢 AL  ", "SAT": "🔴 SAT ", "BEKLE": "🟡 BEKLE"}
                log_yaz(f"  │  RSI       → {sembol_map.get(rsi_s, rsi_s):8s} | {rsi_a}")
                log_yaz(f"  │  EMA Cross → {sembol_map.get(ema_s, ema_s):8s} | {ema_a}")
                log_yaz(f"  │  MACD      → {sembol_map.get(macd_s, macd_s):8s} | {macd_a}")

                # 5) Oylama yap - nihai karar
                karar, oy_sayisi = oylama_yap(rsi_s, ema_s, macd_s)
                if karar == "LONG":
                    log_yaz(f"  │  ★ OYLAMA SONUCU: LONG ({oy_sayisi}/3 AL oyu) → Yükseliş beklentisi")
                elif karar == "SHORT":
                    log_yaz(f"  │  ★ OYLAMA SONUCU: SHORT ({oy_sayisi}/3 SAT oyu) → Düşüş beklentisi")
                else:
                    log_yaz(f"  │  ★ OYLAMA SONUCU: BEKLE → Yeterli çoğunluk yok")

                # Sinyalleri kaydet (dashboard için)
                sinyaller[coin] = {
                    "fiyat": round(fiyat, 6),
                    "rsi": rsi_s,
                    "rsi_aciklama": rsi_a,
                    "ema": ema_s,
                    "ema_aciklama": ema_a,
                    "macd": macd_s,
                    "macd_aciklama": macd_a,
                    "karar": karar
                }

                # ─── AÇIK POZİSYON KONTROL: Stop-Loss / Take-Profit ──────
                if coin in cuzdan.acik:
                    poz = cuzdan.acik[coin]
                    yon = poz["yon"]
                    giris = poz["giris_fiyati"]

                    # Giriş fiyatından yüzdesel değişim
                    degisim = (fiyat - giris) / giris

                    kapat = False
                    neden = ""

                    if yon == "LONG":
                        # Long pozisyonda: fiyat çok düştü → stop-loss
                        if degisim <= -ayarlar.LONG_STOP_LOSS:
                            kapat = True
                            neden = f"LONG STOP-LOSS ({degisim*100:+.2f}%)"
                        # Long pozisyonda: fiyat yeterince yükseldi → take-profit
                        elif degisim >= ayarlar.LONG_TAKE_PROFIT:
                            kapat = True
                            neden = f"LONG TAKE-PROFIT ({degisim*100:+.2f}%)"
                        # Long varken SHORT sinyali geldi → ters sinyal
                        elif karar == "SHORT":
                            kapat = True
                            neden = f"Ters sinyal (LONG iken SHORT sinyali, değişim: {degisim*100:+.2f}%)"

                    elif yon == "SHORT":
                        # Short pozisyonda: fiyat çok yükseldi → stop-loss
                        if degisim >= ayarlar.SHORT_STOP_LOSS:
                            kapat = True
                            neden = f"SHORT STOP-LOSS ({degisim*100:+.2f}%)"
                        # Short pozisyonda: fiyat yeterince düştü → take-profit
                        elif degisim <= -ayarlar.SHORT_TAKE_PROFIT:
                            kapat = True
                            neden = f"SHORT TAKE-PROFIT ({degisim*100:+.2f}%)"
                        # Short varken LONG sinyali geldi → ters sinyal
                        elif karar == "LONG":
                            kapat = True
                            neden = f"Ters sinyal (SHORT iken LONG sinyali, değişim: {degisim*100:+.2f}%)"

                    if kapat:
                        islem = cuzdan.pozisyon_kapat(coin, fiyat, neden)
                        if islem:
                            isaretci = "✅" if islem["kar_zarar"] >= 0 else "❌"
                            log_yaz(f"  │  {isaretci} POZİSYON KAPANDI: {coin} {yon}")
                            log_yaz(f"  │     Giriş: {islem['giris']:.6f} → Çıkış: {islem['cikis']:.6f}")
                            log_yaz(f"  │     K/Z: {islem['kar_zarar']:+.4f} USDT ({islem['kar_zarar_yuzde']:+.2f}%)")
                            log_yaz(f"  │     Neden: {neden}")
                            log_yaz(f"  │     Yeni bakiye: {cuzdan.bakiye:.2f} USDT")
                    else:
                        # Pozisyon açık, sadece anlık durumu göster
                        anlik_kz = cuzdan.anlik_kar_zarar(coin, fiyat)
                        isaretci = "📈" if anlik_kz >= 0 else "📉"
                        log_yaz(f"  │  {isaretci} AÇIK {yon}: giriş={giris:.6f} güncel={fiyat:.6f} "
                                f"K/Z={anlik_kz:+.4f} USDT ({degisim*100:+.2f}%)")

                # ─── YENİ POZİSYON AÇMA KARARI ───────────────────────────
                if coin not in cuzdan.acik:
                    # Açık pozisyon yok - yeni pozisyon açılabilir mi?

                    if coin in cuzdan.bekleme:
                        # Kapama sonrası bekleme süresi devam ediyor
                        log_yaz(f"  │  ⏳ Bekleme: {cuzdan.bekleme[coin]} döngü daha beklenecek "
                                f"(kapama sonrası koruma)")

                    elif len(cuzdan.acik) >= ayarlar.MAX_POZISYON:
                        # Maksimum pozisyon sayısına ulaşıldı
                        log_yaz(f"  │  🔒 Max pozisyon ({ayarlar.MAX_POZISYON}) dolu, yeni pozisyon açılamaz")

                    elif karar == "LONG":
                        # LONG pozisyon aç
                        basari, sonuc = cuzdan.pozisyon_ac(coin, "LONG", fiyat)
                        if basari:
                            log_yaz(f"  │  🟢 LONG POZİSYON AÇILDI: {coin}")
                            log_yaz(f"  │     Giriş fiyatı: {sonuc:.6f} USDT (slippage dahil)")
                            log_yaz(f"  │     Kullanılan: {cuzdan.acik[coin]['usdt_miktari']:.2f} USDT")
                            log_yaz(f"  │     Stop-loss: {sonuc*(1-ayarlar.LONG_STOP_LOSS):.6f} | "
                                    f"Take-profit: {sonuc*(1+ayarlar.LONG_TAKE_PROFIT):.6f}")
                        else:
                            log_yaz(f"  │  [HATA] LONG açılamadı: {sonuc}")

                    elif karar == "SHORT":
                        # SHORT pozisyon aç
                        basari, sonuc = cuzdan.pozisyon_ac(coin, "SHORT", fiyat)
                        if basari:
                            log_yaz(f"  │  🔴 SHORT POZİSYON AÇILDI: {coin}")
                            log_yaz(f"  │     Giriş fiyatı: {sonuc:.6f} USDT (slippage dahil)")
                            log_yaz(f"  │     Kullanılan: {cuzdan.acik[coin]['usdt_miktari']:.2f} USDT")
                            log_yaz(f"  │     Stop-loss: {sonuc*(1+ayarlar.SHORT_STOP_LOSS):.6f} | "
                                    f"Take-profit: {sonuc*(1-ayarlar.SHORT_TAKE_PROFIT):.6f}")
                        else:
                            log_yaz(f"  │  [HATA] SHORT açılamadı: {sonuc}")

                    else:
                        log_yaz(f"  │  ⬜ BEKLE: sinyal belirsiz, yeni pozisyon açılmıyor")

                log_yaz(f"  └───────────────────────────────────────────────────")

            # ─── Dashboard Güncelle ───────────────────────────────────────
            durumu_guncelle(cuzdan, fiyatlar, sinyaller, dongü_no)

            # ─── Döngü Sonu Özeti ─────────────────────────────────────────
            toplam_kz = cuzdan.bakiye - ayarlar.BASLANGIC_BAKIYE
            log_yaz(f"\n  ╔═══ DÖNGÜ #{dongü_no} ÖZET ═══════════════════════════════════╗")
            log_yaz(f"  ║  Bakiye   : {cuzdan.bakiye:>10.2f} USDT")
            log_yaz(f"  ║  K/Z      : {toplam_kz:>+10.2f} USDT ({(toplam_kz/ayarlar.BASLANGIC_BAKIYE)*100:+.2f}%)")
            log_yaz(f"  ║  Açık pos : {len(cuzdan.acik)} / {ayarlar.MAX_POZISYON}")
            log_yaz(f"  ║  İşlem    : {len(cuzdan.gecmis)} toplam")
            if cuzdan.acik:
                for c, p in cuzdan.acik.items():
                    f_an = fiyatlar.get(c, p["giris_fiyati"])
                    kz = cuzdan.anlik_kar_zarar(c, f_an)
                    log_yaz(f"  ║  {c} {p['yon']:5s}: anlık K/Z = {kz:+.4f} USDT")
            log_yaz(f"  ╚═══════════════════════════════════════════════════════╝")

        except KeyboardInterrupt:
            log_yaz("\n\n[BİTİŞ] Kullanıcı botu durdurdu (Ctrl+C).")
            break

        except Exception as hata:
            # Beklenmeyen hata olursa botu durdurmayız, loglayıp devam ederiz
            import traceback
            log_yaz(f"\n[HATA] Döngü #{dongü_no} sırasında hata: {hata}")
            log_yaz(traceback.format_exc())
            log_yaz("5 saniye sonra devam ediliyor...")

            with durum_kilidi:
                paylasilan_durum["bot_durumu"] = f"Hata (otomatik toparlanıyor...)"

            time.sleep(5)
            continue

        # Bir sonraki döngüye kadar bekle
        log_yaz(f"\n  ⏱  Sonraki analiz {ayarlar.DONGÜ_SURESI} saniye sonra "
                f"({ayarlar.DONGÜ_SURESI // 60} dakika {ayarlar.DONGÜ_SURESI % 60} saniye)...")
        time.sleep(ayarlar.DONGÜ_SURESI)
