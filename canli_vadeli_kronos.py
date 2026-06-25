import yfinance as yf
import numpy as np
import pandas as pd
import time
import os
import sys
from datetime import datetime
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from sklearn.preprocessing import StandardScaler

# ==========================================
#  KRONOS + RSI + PPO HİBRİT BTC BOTU
# ==========================================
# Kronos: 12 milyar candlestick ile eğitilmiş
# finansal tahmin modeli (AAAI 2026 kabul)
# ==========================================

MODEL_DOSYASI   = "rsi_hunter_bot"
BASLANGIC_SERMAYE = 10000.0
KALDIRAC        = 3.0
KOMISYON_ORANI  = 0.0005
RSI_AL          = 35
RSI_SAT         = 65
ZIRVEDEN_DONUS_LIMITI = 0.05

# Kronos ayarları
KRONOS_LOOKBACK  = 128   # Kaç mum geri bakılacak
KRONOS_PRED_LEN  = 3     # Kaç mum ilerisi tahmin edilecek (3x4h = 12 saat)
KRONOS_MODEL_ID  = "NeoQuasar/Kronos-mini"      # En hızlı, 2048 context
KRONOS_TOK_ID    = "NeoQuasar/Kronos-Tokenizer-base"

KRONOS_YUKLU    = False
kronos_predictor = None


# ------------------------------------------------------------------
# KRONOS BAŞLATMA
# ------------------------------------------------------------------

def kronos_kur():
    global KRONOS_YUKLU, kronos_predictor

    print("🔍 Kronos kontrol ediliyor...")

    # Repo yoksa klon al
    if not os.path.exists("Kronos"):
        print("📥 Kronos GitHub'dan klonlanıyor...")
        ret = os.system("git clone https://github.com/shiyu-coder/Kronos.git -q")
        if ret != 0:
            print("❌ Klonlama başarısız. Önce: bash kurulum.sh çalıştırın.")
            return False
        os.system("pip install -q -r Kronos/requirements.txt")

    # Kronos'u Python yoluna ekle
    kronos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kronos")
    if kronos_path not in sys.path:
        sys.path.insert(0, kronos_path)

    try:
        from model import Kronos, KronosTokenizer, KronosPredictor as KP

        print(f"🧠 Kronos modeli yükleniyor ({KRONOS_MODEL_ID})...")
        print("   İlk çalıştırmada HuggingFace'den indirilir (~2 dk).")
        tokenizer  = KronosTokenizer.from_pretrained(KRONOS_TOK_ID)
        model_obj  = Kronos.from_pretrained(KRONOS_MODEL_ID)
        kronos_predictor = KP(model_obj, tokenizer, max_context=KRONOS_LOOKBACK)

        KRONOS_YUKLU = True
        print("✅ Kronos hazır!\n")
        return True

    except Exception as e:
        print(f"⚠️  Kronos yüklenemedi: {e}")
        print("📋 Bot RSI+PPO modunda devam edecek.\n")
        return False


# ------------------------------------------------------------------
# KRONOS TAHMİNİ
# ------------------------------------------------------------------

def kronos_tahmin(df_4h):
    """
    df_4h: 4 saatlik OHLCV DataFrame (yfinance formatı - büyük harf kolonlar)
    Döndürür: (tahmin_fiyat, degisim_orani, yon_str)
    """
    if not KRONOS_YUKLU or kronos_predictor is None:
        return None, None, "Kronos yüklü değil"

    try:
        # Kronos lowercase kolon formatına çevir
        kdf = df_4h[["Open", "High", "Low", "Close", "Volume"]].copy()
        kdf.columns = ["open", "high", "low", "close", "volume"]
        kdf.index   = pd.to_datetime(kdf.index)

        # Son KRONOS_LOOKBACK mumu al
        lookback = min(KRONOS_LOOKBACK, len(kdf))
        x_df = kdf.iloc[-lookback:]
        x_ts = list(x_df.index)

        # Gelecek mumların timestamp'leri (4 saatlik aralıklar)
        son_ts = pd.Timestamp(x_ts[-1])
        y_ts   = [son_ts + pd.Timedelta(hours=4 * i) for i in range(1, KRONOS_PRED_LEN + 1)]

        pred_df = kronos_predictor.predict(
            df          = x_df,
            x_timestamp = x_ts,
            y_timestamp = y_ts,
            pred_len    = KRONOS_PRED_LEN,
            T           = 1.0,
            top_p       = 0.9,
            sample_count= 1,
        )

        mevcut_fiyat  = float(kdf["close"].iloc[-1])

        # Tahmin çıktısını oku
        if isinstance(pred_df, pd.DataFrame) and "close" in pred_df.columns:
            pred_yakin  = float(pred_df["close"].iloc[0])   # 4 saat sonra
            pred_uzak   = float(pred_df["close"].iloc[-1])  # 12 saat sonra
        else:
            arr = np.array(pred_df).flatten()
            pred_yakin  = float(arr[0])
            pred_uzak   = float(arr[-1])

        degisim       = (pred_uzak - mevcut_fiyat) / mevcut_fiyat
        yakin_degisim = (pred_yakin - mevcut_fiyat) / mevcut_fiyat

        yon = "YUKARI 📈" if degisim > 0 else "ASAGI 📉"
        return pred_uzak, degisim, yon, yakin_degisim

    except Exception as e:
        return None, None, f"Hata: {e}", None


# ------------------------------------------------------------------
# VERİ ÇEKME
# ------------------------------------------------------------------

def veri_getir():
    try:
        df = yf.download("BTC-USD", period="7d", interval="15m", progress=False)
        if df.empty:
            raise ValueError("Yahoo Finance boş veri döndürdü.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        ohlc = {"Open": "first", "High": "max", "Low": "min",
                "Close": "last", "Volume": "sum"}
        df_4h = df.resample("4h").apply(ohlc).dropna()

        if len(df_4h) < 15:
            raise ValueError("Yetersiz 4 saatlik veri.")

        df_4h["RSI"] = RSIIndicator(close=df_4h["Close"], window=14).rsi()
        df_4h["ATR"] = AverageTrueRange(
            high=df_4h["High"], low=df_4h["Low"],
            close=df_4h["Close"], window=14
        ).average_true_range()
        df_4h["Vol_Norm"] = df_4h["Volume"] / (df_4h["Volume"].rolling(20).max() + 1e-5)

        anlik_fiyat = float(df["Close"].iloc[-1])
        gun_acilis  = float(df["Open"].iloc[0])

        return df_4h.dropna(), anlik_fiyat, gun_acilis

    except Exception as e:
        print(f"\n❌ VERİ HATASI: {e}")
        return None, None, None


# ------------------------------------------------------------------
# PPO ORTAMI
# ------------------------------------------------------------------

class SanalOrtam:
    def __init__(self, df):
        self.scaler   = StandardScaler()
        feats = df[["Close", "RSI", "ATR", "Vol_Norm"]].values.astype(np.float32)
        self.scaler.fit(feats)

    def ozet(self, df):
        raw = df[["Close", "RSI", "ATR", "Vol_Norm"]].iloc[-1].values.reshape(1, -1)
        return self.scaler.transform(raw)[0]


# ------------------------------------------------------------------
# ANA DÖNGÜ
# ------------------------------------------------------------------

def ekran_temizle():
    os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    print("=" * 54)
    print("   KRONOS + RSI + PPO   HİBRİT BTC BOTU")
    print("=" * 54)

    kronos_kur()

    # PPO modeli (isteğe bağlı - yoksa Kronos+RSI yeterli)
    ppo_model = None
    if os.path.exists(f"{MODEL_DOSYASI}.zip"):
        try:
            from stable_baselines3 import PPO
            ppo_model = PPO.load(MODEL_DOSYASI)
            print("✅ PPO modeli yüklendi.")
        except Exception as e:
            print(f"⚠️  PPO yüklenemedi: {e}")
    else:
        print("⚠️  PPO model bulunamadı → Kronos+RSI modu aktif.")

    bakiye           = BASLANGIC_SERMAYE
    pozisyon         = False
    giris_fiyati     = 0.0
    tepe_fiyati      = 0.0
    en_yuksek_bakiye = BASLANGIC_SERMAYE

    print("\n🚀 Sistem başlatıldı, piyasa izleniyor...\n")
    time.sleep(1)

    while True:
        df, anlik_fiyat, gun_acilis = veri_getir()

        if df is None:
            print("⏳ 5 saniye sonra tekrar denenecek...")
            time.sleep(5)
            continue

        try:
            son_mum = df.iloc[-1]
            rsi     = float(son_mum["RSI"])

            # --- Kronos tahmini ---
            kronos_ret  = kronos_tahmin(df)
            if len(kronos_ret) == 4:
                k_fiyat, k_degisim, k_yon, k_yakin = kronos_ret
            else:
                k_fiyat = k_degisim = k_yakin = None
                k_yon = "Yok"

            k_pozitif = k_degisim is not None and k_degisim > 0.003
            k_negatif = k_degisim is not None and k_degisim < -0.003

            # --- PPO kararı ---
            action = 0
            if ppo_model is not None:
                env  = SanalOrtam(df)
                feat = env.ozet(df)
                action, _ = ppo_model.predict(feat, deterministic=True)

            # --- Hibrit RSI eşiği ---
            # Kronos yukarı görünce daha erken al, aşağı görünce daha geç al
            efektif_rsi_al = RSI_AL
            if k_pozitif:
                efektif_rsi_al = RSI_AL + 3   # 38 → daha geniş alım penceresi
            elif k_negatif:
                efektif_rsi_al = RSI_AL - 5   # 30 → Kronos düşüş diyorsa daha temkinli

            # --- Ekran ---
            ekran_temizle()
            simdi = datetime.now().strftime("%H:%M:%S")
            gunluk = (anlik_fiyat - gun_acilis) / gun_acilis
            yon_emoji = "🟢" if gunluk > 0 else "🔴"

            print(f"┌──────────────────────────────────────────────────────┐")
            print(f"│  ⏱️  {simdi}  │  BTC KRONOS HİBRİT BOT              │")
            print(f"└──────────────────────────────────────────────────────┘")
            print(f"  💲 Fiyat         : {anlik_fiyat:>12,.2f} $")
            print(f"  📊 Günlük Yön    : {yon_emoji}  %{gunluk * 100:+.2f}")
            print(f"  📈 RSI           : {rsi:.1f}  (AL eşiği: <{efektif_rsi_al})")
            print("  " + "─" * 50)

            # Kronos paneli
            if KRONOS_YUKLU and k_fiyat is not None:
                print(f"  🧠 KRONOS  (12 saat tahmini):")
                print(f"     Tahmin Fiyat  : {k_fiyat:>12,.2f} $")
                print(f"     Yön           : {k_yon}  (%{k_degisim * 100:+.2f})")
                print(f"     4 Saat Sonra  : %{k_yakin * 100:+.2f}")
            elif KRONOS_YUKLU:
                print(f"  🧠 KRONOS  : Tahmin hesaplanıyor...")
            else:
                print(f"  🧠 KRONOS  : Yüklü değil (RSI+PPO modu)")
            print("  " + "─" * 50)

            # Pozisyon paneli
            if pozisyon:
                if anlik_fiyat > tepe_fiyati:
                    tepe_fiyati = anlik_fiyat
                zirveden_dusus = (tepe_fiyati - anlik_fiyat) / tepe_fiyati
                roe             = ((anlik_fiyat - giris_fiyati) / giris_fiyati) * KALDIRAC
                unrealized      = bakiye * roe
                likidasyon      = giris_fiyati * (1 - 1 / KALDIRAC)

                print(f"  🚀 POZİSYON AÇIK  ({KALDIRAC:.0f}x LONG)")
                print(f"     Giriş         : {giris_fiyati:>12,.2f} $")
                print(f"     Zirve         : {tepe_fiyati:>12,.2f} $")
                print(f"     Zirveden Düşüş: %{zirveden_dusus * 100:.2f} (limit: %{ZIRVEDEN_DONUS_LIMITI*100:.0f})")
                print(f"     Likidasyon    : {likidasyon:>12,.2f} $")
                print("  " + "─" * 50)
                print(f"  ⚡ Anlık Kâr     : {unrealized:>+12,.2f} TL")
                print(f"  💼 Toplam Varlık : {bakiye + unrealized:>12,.2f} TL")
            else:
                rsi_fark = rsi - efektif_rsi_al
                durum    = "🔥 ALIM BÖLGESİ!" if rsi_fark < 0 else f"Hedefe {rsi_fark:.1f} puan kaldı"
                print(f"  ⚪ DURUM         : BEKLEMEDE")
                print(f"  📉 RSI Nerede   : {rsi:.1f}  →  {durum}")
                print("  " + "─" * 50)
                print(f"  💼 Bakiye        : {bakiye:>12,.2f} TL")
                print(f"  💪 Alım Gücü (3x): {bakiye * KALDIRAC:>12,.2f} TL")

            print("=" * 54)

            # ----------------------------------------------------------
            # AL / SAT MANTIĞI
            # ----------------------------------------------------------

            if not pozisyon:
                # Alım koşulları:
                # 1. RSI hibrit eşiğin altında
                # 2. (Kronos pozitif VEYA PPO "al" dedi VEYA hiçbir model yok)
                # 3. Kronos negatifse alım YAPMA (override)
                rsi_tamam  = rsi < efektif_rsi_al
                model_onay = kronos_yuklu_onay = k_pozitif or (action == 1) or (ppo_model is None and not KRONOS_YUKLU)
                kronos_veto = k_negatif  # Kronos düşüş diyorsa al'ı geç

                if rsi_tamam and model_onay and not kronos_veto:
                    bakiye -= bakiye * KALDIRAC * KOMISYON_ORANI
                    giris_fiyati = anlik_fiyat
                    tepe_fiyati  = anlik_fiyat
                    pozisyon     = True
                    sebep = []
                    if k_pozitif:   sebep.append("Kronos↑")
                    if action == 1: sebep.append("PPO:AL")
                    sebep_str = "+".join(sebep) if sebep else "RSI"
                    print(f"\n  🔔 ALIM YAPILDI! (RSI:{rsi:.1f} | {sebep_str})")
                    time.sleep(5)

            elif pozisyon:
                degisim_pct    = (anlik_fiyat - giris_fiyati) / giris_fiyati
                roe            = degisim_pct * KALDIRAC
                zirveden_dusus = (tepe_fiyati - anlik_fiyat) / tepe_fiyati

                sat   = False
                sebep = ""

                if rsi > RSI_SAT:
                    sat = True; sebep = f"RSI Doygunluğu (>{RSI_SAT})"
                if degisim_pct > 0.10:
                    sat = True; sebep = "Kâr Hedefi (%10)"
                if degisim_pct < -0.05:
                    sat = True; sebep = "Stop Loss (-%5)"
                if zirveden_dusus > ZIRVEDEN_DONUS_LIMITI and roe > 0.05:
                    sat = True; sebep = "Trailing Stop"
                if action == 2:
                    sat = True; sebep = "PPO: SAT"
                # Kronos düşüş tahmin ediyorsa VE kârımız varsa erken çık
                if k_negatif and roe > 0.02:
                    sat = True; sebep = f"Kronos↓ + Kâr Güvence (%{roe*100:.1f})"
                if roe <= -0.95:
                    sat = True; sebep = "LİKİDASYON"
                    bakiye = 0

                if sat and bakiye > 0:
                    bakiye += bakiye * roe
                    bakiye -= bakiye * KALDIRAC * KOMISYON_ORANI
                    pozisyon = False
                    if bakiye > en_yuksek_bakiye:
                        en_yuksek_bakiye = bakiye
                    print(f"\n  💰 SATILDI! ({sebep})")
                    print(f"  Yeni Bakiye: {bakiye:,.2f} TL")
                    time.sleep(5)

            print("\n  ⏳ Güncelleniyor... (Çıkmak: CTRL+C)", end="", flush=True)
            time.sleep(60)

        except Exception as e:
            print(f"\nHata: {e}")
            time.sleep(10)
