# ================================================================
# AYARLAR.PY - Botun Tüm Ayarları
# ================================================================
# Bu dosyayı düzenleyerek botu özelleştirebilirsiniz.
# Değiştirdikten sonra botu yeniden başlatmanız gerekir.
# ================================================================

# ---------------------------------------------------------------
# TAKİP EDİLECEK COİNLER
# Binance'deki sembol isimlerini kullanın (USDT çifti)
# ---------------------------------------------------------------
COINLER = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

# ---------------------------------------------------------------
# BAŞLANGIÇ BAKİYESİ
# Sanal cüzdanın başlangıç USDT miktarı (gerçek para değil!)
# ---------------------------------------------------------------
BASLANGIC_BAKIYE = 10000.0

# ---------------------------------------------------------------
# DÖNGÜ SÜRESİ
# Kaç saniyede bir yeni analiz yapılsın?
# 300 = 5 dakika (önerilen, Binance'e çok fazla istek atmamak için)
# ---------------------------------------------------------------
DONGÜ_SURESI = 300

# ---------------------------------------------------------------
# POZİSYON BOYUTU
# Her işlemde mevcut bakiyenin yüzde kaçı kullanılsın?
# 0.20 = %20 anlamına gelir
# ---------------------------------------------------------------
POZISYON_ORANI = 0.20

# ---------------------------------------------------------------
# MAKSIMUM AÇIK POZİSYON
# Aynı anda kaç farklı coin pozisyonu açık olabilir?
# ---------------------------------------------------------------
MAX_POZISYON = 2

# ---------------------------------------------------------------
# KAPATMA SONRASI BEKLEME
# Bir pozisyon kapandıktan sonra aynı coinde kaç döngü beklensin?
# (Aynı coinde hemen geri girip testereye yakalanmayı önler)
# ---------------------------------------------------------------
KAPATMA_BEKLEME = 2

# ---------------------------------------------------------------
# LONG POZİSYON RİSK YÖNETİMİ
# LONG = "Fiyat yükselir" diye pozisyon açmak
# ---------------------------------------------------------------
# Giriş fiyatından bu kadar DÜŞERSE pozisyonu kapat (zarar durdur)
LONG_STOP_LOSS = 0.03    # 0.03 = %3

# Giriş fiyatından bu kadar YÜKSELIRSE pozisyonu kapat (kâr al)
LONG_TAKE_PROFIT = 0.05  # 0.05 = %5

# ---------------------------------------------------------------
# SHORT POZİSYON RİSK YÖNETİMİ
# SHORT = "Fiyat düşer" diye pozisyon açmak
# ---------------------------------------------------------------
# Giriş fiyatından bu kadar YÜKSELIRSE pozisyonu kapat (zarar durdur)
SHORT_STOP_LOSS = 0.03   # 0.03 = %3

# Giriş fiyatından bu kadar DÜŞERSE pozisyonu kapat (kâr al)
SHORT_TAKE_PROFIT = 0.05  # 0.05 = %5

# ---------------------------------------------------------------
# İŞLEM MALİYETLERİ (Gerçekçilik için)
# ---------------------------------------------------------------
# Her alım/satımdan alınan komisyon (Binance standart ücreti)
KOMISYON = 0.001   # 0.001 = %0.1

# Piyasa emrinde oluşan fiyat kayması (büyük emirlerde olur)
SLIPPAGE = 0.0005  # 0.0005 = %0.05

# ---------------------------------------------------------------
# STRATEJİ PARAMETRELERİ
# ---------------------------------------------------------------

# RSI (Relative Strength Index) ayarları
RSI_PERIYOT = 14
RSI_SATIM_SINIRI = 35   # Bu değerin ALTINDAYSA = AL sinyali (aşırı satılmış)
RSI_ALIM_SINIRI = 65    # Bu değerin ÜSTÜNDEYSE = SAT sinyali (aşırı alınmış)

# EMA (Üstel Hareketli Ortalama) ayarları
EMA_KISA = 9    # Kısa periyot EMA (hızlı tepki verir)
EMA_UZUN = 21   # Uzun periyot EMA (yavaş ama güvenilir)

# MACD ayarları
MACD_HIZLI = 12    # Hızlı EMA periyodu
MACD_YAVAS = 26    # Yavaş EMA periyodu
MACD_SINYAL = 9    # Sinyal çizgisi periyodu

# ---------------------------------------------------------------
# MUM VERİSİ AYARLARI
# ---------------------------------------------------------------
MUM_ARALIGI = "5m"   # Mum büyüklüğü: "1m", "5m", "15m", "1h" gibi
MUM_LIMIT = 100       # Kaç adet mum çekilsin (en az 30 olsun)

# ---------------------------------------------------------------
# WEB PANEL AYARLARI
# ---------------------------------------------------------------
PANEL_PORT = 5000
PANEL_HOST = "0.0.0.0"   # Tüm ağ arayüzlerinden erişilebilsin

# ---------------------------------------------------------------
# LOG DOSYASI
# ---------------------------------------------------------------
LOG_DOSYASI = "islem_gecmisi.txt"
