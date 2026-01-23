import yfinance as yf
import numpy as np
import pandas as pd
import time
import os
from datetime import datetime
from stable_baselines3 import PPO
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from sklearn.preprocessing import StandardScaler

# ==========================================
# 🔧 TAMİR MODU: PRO VADELİ İŞLEMLER
# ==========================================

MODEL_DOSYASI = "rsi_hunter_bot"
BASLANGIC_SERMAYE = 10000.0
KALDIRAC = 3.0
KOMISYON_ORANI = 0.0005

RSI_AL = 30
RSI_SAT = 65
ZIRVEDEN_DONUS_LIMITI = 0.05


def ekran_temizle():
    os.system('cls' if os.name == 'nt' else 'clear')


def veri_getir_anlik():
    try:
        # HATA AYIKLAMA İÇİN DETAYLI İNDİRME
        # period='1d' yaptık ki daha hızlı olsun
        df = yf.download("BTC-USD", period="1d", interval="5m", progress=False)

        # Eğer veri boş gelirse hata fırlat
        if df.empty:
            raise ValueError("Yahoo Finance boş veri döndürdü (İnternet veya IP sorunu olabilir).")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 4 Saatlik Mum Yapısı
        ohlc = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        df_resampled = df.resample('4h').apply(ohlc).dropna()

        # Göstergeleri Hesapla
        close = df_resampled['Close']
        df_resampled['RSI'] = RSIIndicator(close=close, window=14).rsi()
        df_resampled['ATR'] = AverageTrueRange(high=df_resampled['High'], low=df_resampled['Low'], close=close,
                                               window=14).average_true_range()
        df_resampled['Vol_Norm'] = df_resampled['Volume'] / (df_resampled['Volume'].rolling(20).max() + 1e-5)

        # Canlı Veriler
        anlik_fiyat = df['Close'].iloc[-1]
        gun_acilis = df['Open'].iloc[0]

        return df_resampled.dropna(), anlik_fiyat, gun_acilis

    except Exception as e:
        # İŞTE BURASI HATAYI GÖSTERECEK
        print(f"\n❌ VERİ HATASI OLUŞTU: {e}")
        return None, None, None


class SanalOrtam:
    def __init__(self, df):
        self.scaler = StandardScaler()
        self.features = df[['Close', 'RSI', 'ATR', 'Vol_Norm']].values.astype(np.float32)
        self.scaler.fit(self.features)


if __name__ == "__main__":
    if not os.path.exists(f"{MODEL_DOSYASI}.zip"):
        print("❌ Model dosyası yok!");
        exit()

    print(f"🧠 Robot ve İz Süren Stop Yükleniyor...")
    model = PPO.load(MODEL_DOSYASI)

    bakiye = BASLANGIC_SERMAYE
    pozisyon = False
    giris_fiyati = 0
    tepe_fiyati = 0
    en_yuksek_bakiye = BASLANGIC_SERMAYE

    print("\n🚀 SİSTEM BAŞLADI... Veri bekleniyor...")
    time.sleep(1)

    while True:
        df, anlik_canli_fiyat, gun_acilis = veri_getir_anlik()

        if df is None:
            # Hata mesajını zaten yukarıda yazdırdık, 5 sn bekle tekrar dene
            print("⏳ 5 saniye sonra tekrar denenecek...")
            time.sleep(5)
            continue

        try:
            env_sim = SanalOrtam(df)
            son_mum = df.iloc[-1]
            rsi = son_mum['RSI']

            # Robot Kararı
            raw_feat = df[['Close', 'RSI', 'ATR', 'Vol_Norm']].iloc[-1].values.reshape(1, -1)
            scaled_feat = env_sim.scaler.transform(raw_feat)
            action, _ = model.predict(scaled_feat[0], deterministic=True)

            ekran_temizle()

            # --- EKRAN GÖSTERİMİ ---
            simdi = datetime.now().strftime("%H:%M:%S")
            gunluk_degisim = (anlik_canli_fiyat - gun_acilis) / gun_acilis
            renk_degisim = "🟢" if gunluk_degisim > 0 else "🔴"

            rsi_fark = rsi - RSI_AL
            rsi_mesaji = "ALIM BÖLGESİNDEYİZ! 🔥" if rsi_fark < 0 else f"Hedefe {rsi_fark:.1f} puan var"

            print(f"┌──────────────────────────────────────────────────┐")
            print(f"│  ⏱️ {simdi} | BTC CANLI ANALİZ (3x PRO)       │")
            print(f"└──────────────────────────────────────────────────┘")
            print(f"💲 Fiyat       : {anlik_canli_fiyat:,.2f} $")
            print(f"📊 Günlük Yön  : {renk_degisim} %{gunluk_degisim * 100:.2f}")
            print(f"📈 RSI Durumu  : {rsi:.1f} -> {rsi_mesaji}")
            print("-" * 52)

            if pozisyon:
                if anlik_canli_fiyat > tepe_fiyati: tepe_fiyati = anlik_canli_fiyat
                zirveden_dusus = (tepe_fiyati - anlik_canli_fiyat) / tepe_fiyati

                kaldiracli_kar = ((anlik_canli_fiyat - giris_fiyati) / giris_fiyati) * KALDIRAC
                unrealized_pnl = bakiye * kaldiracli_kar
                toplam_varlik = bakiye + unrealized_pnl
                likidasyon = giris_fiyati * (1 - (1 / KALDIRAC))

                print(f"🚀 POZİSYON AÇIK (3x LONG)")
                print(f"💵 Giriş       : {giris_fiyati:,.2f} $")
                print(f"🏔️ Zirve       : {tepe_fiyati:,.2f} $")
                print(f"⚠️ Düşüş       : %{zirveden_dusus * 100:.2f} (Limit: %5.0)")
                print(f"💀 Likidasyon  : {likidasyon:,.2f} $")
                print("-" * 52)
                print(f"⚡ Anlık Kâr   : {unrealized_pnl:+.2f} TL")
                print(f"💼 TOPLAM      : {toplam_varlik:,.2f} TL")
            else:
                print(f"⚪ DURUM: PUSUDA BEKLİYOR")
                print(f"📉 Şu anki RSI {rsi:.1f} (Hedef < 30)")
                print("-" * 52)
                print(f"💼 Bakiye      : {bakiye:,.2f} TL")
                print(f"💪 Güç (3x)    : {bakiye * KALDIRAC:,.2f} TL")

            print("=" * 52)

            # --- İŞLEMLER ---
            if action == 1 and not pozisyon:
                if rsi < RSI_AL:
                    bakiye -= (bakiye * KALDIRAC * KOMISYON_ORANI)
                    giris_fiyati = anlik_canli_fiyat
                    tepe_fiyati = anlik_canli_fiyat
                    pozisyon = True
                    print("\n🔔 ALIM YAPILDI! (RSI 30 ALTI)")
                    time.sleep(5)

            elif pozisyon:
                degisim = (anlik_canli_fiyat - giris_fiyati) / giris_fiyati
                roe = degisim * KALDIRAC
                zirveden_dusus = (tepe_fiyati - anlik_canli_fiyat) / tepe_fiyati

                sat = False
                sebeb = ""

                if rsi > RSI_SAT: sat = True; sebeb = "RSI Doygunluğu (>65)"
                if degisim > 0.10: sat = True; sebeb = "Kâr Hedefi (%30)"
                if degisim < -0.05: sat = True; sebeb = "Stop Loss"
                if zirveden_dusus > ZIRVEDEN_DONUS_LIMITI and roe > 0.05: sat = True; sebeb = "Trailing Stop"
                if action == 2: sat = True; sebeb = "Robot Satışı"
                if roe <= -0.95: print("\n💀 LİKİDASYON!"); sat = True; sebeb = "BATTI"; bakiye = 0

                if sat and bakiye > 0:
                    bakiye += (bakiye * roe)
                    bakiye -= (bakiye * KALDIRAC * KOMISYON_ORANI)
                    pozisyon = False
                    if bakiye > en_yuksek_bakiye: en_yuksek_bakiye = bakiye
                    print(f"\n💰 SATILDI ({sebeb})")
                    print(f"Yeni Bakiye: {bakiye:.2f} TL")
                    time.sleep(5)

            print("\nGüncelleniyor... (Kapatmak için CTRL+C)", end="", flush=True)
            time.sleep(60)

        except Exception as e:
            print(f"Hesaplama Hatası: {e}");
            time.sleep(10)