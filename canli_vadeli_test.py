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
# 🎯 HEDEF FİYAT GÖSTERGELİ PRO BOT
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


def hedef_fiyat_tahmin_et(df, hedef_rsi=30):
    """RSI'ın hedef seviyeye gelmesi için fiyatın kaç olması gerektiğini kabaca hesaplar"""
    try:
        son_kapanis = df['Close'].iloc[-1]
        mevcut_rsi = df['RSI'].iloc[-1]
        # Basit bir oranlama ile RSI farkını fiyata yansıtıyoruz
        fark = mevcut_rsi - hedef_rsi
        tahmini_fiyat = son_kapanis * (1 - (fark / 250))  # Yaklaşık bir çarpan
        return tahmini_fiyat
    except:
        return 0


def veri_getir_anlik():
    try:
        df = yf.download("BTC-USD", period="7d", interval="15m", progress=False)
        if df.empty: raise ValueError("Veri boş.")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        ohlc = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        df_4h = df.resample('4h').apply(ohlc).dropna()

        if len(df_4h) < 15: raise ValueError("Yetersiz veri.")

        df_4h['RSI'] = RSIIndicator(close=df_4h['Close'], window=14).rsi()
        df_4h['ATR'] = AverageTrueRange(high=df_4h['High'], low=df_4h['Low'], close=df_4h['Close'],
                                        window=14).average_true_range()
        df_4h['Vol_Norm'] = df_4h['Volume'] / (df_4h['Volume'].rolling(20).max() + 1e-5)

        anlik_fiyat = df['Close'].iloc[-1]
        gun_acilis = df['Open'].iloc[0]

        return df_4h.dropna(), anlik_fiyat, gun_acilis
    except Exception as e:
        print(f"\n❌ VERİ HATASI: {e}")
        return None, None, None


class SanalOrtam:
    def __init__(self, df):
        self.scaler = StandardScaler()
        self.features = df[['Close', 'RSI', 'ATR', 'Vol_Norm']].values.astype(np.float32)
        self.scaler.fit(self.features)


if __name__ == "__main__":
    if not os.path.exists(f"{MODEL_DOSYASI}.zip"):
        print("❌ Model yok!");
        exit()

    model = PPO.load(MODEL_DOSYASI)
    bakiye, pozisyon, giris_fiyati, tepe_fiyati = BASLANGIC_SERMAYE, False, 0, 0

    while True:
        df, anlik_canli_fiyat, gun_acilis = veri_getir_anlik()
        if df is None: time.sleep(5); continue

        try:
            env_sim = SanalOrtam(df)
            son_mum = df.iloc[-1]
            rsi = son_mum['RSI']
            hedef_fiyat = hedef_fiyat_tahmin_et(df, RSI_AL)

            raw_feat = df[['Close', 'RSI', 'ATR', 'Vol_Norm']].iloc[-1].values.reshape(1, -1)
            scaled_feat = env_sim.scaler.transform(raw_feat)
            action, _ = model.predict(scaled_feat[0], deterministic=True)

            ekran_temizle()
            simdi = datetime.now().strftime("%H:%M:%S")
            gunluk_degisim = (anlik_canli_fiyat - gun_acilis) / gun_acilis

            print(f"┌──────────────────────────────────────────────────┐")
            print(f"│  ⏱️ {simdi} | BTC CANLI ANALİZ (PRO)          │")
            print(f"└──────────────────────────────────────────────────┘")
            print(f"💲 Güncel Fiyat : {anlik_canli_fiyat:,.2f} $")
            print(f"📈 Mevcut RSI   : {rsi:.1f}")

            if not pozisyon:
                print(f"🎯 Hedef Fiyat  : ~{hedef_fiyat:,.2f} $ (RSI 30 tahmini)")
                print(f"📉 Alıma Kalan  : {anlik_canli_fiyat - hedef_fiyat:,.2f} $")
                print("-" * 52)
                print(f"⚪ DURUM: PUSUDA BEKLİYOR")
                print(f"💼 Bakiye: {bakiye:,.2f} TL | Güç: {bakiye * 3:,.2f} TL")
            else:
                if anlik_canli_fiyat > tepe_fiyati: tepe_fiyati = anlik_canli_fiyat
                roe = ((anlik_canli_fiyat - giris_fiyati) / giris_fiyati) * KALDIRAC
                print("-" * 52)
                print(f"🚀 POZİSYON AÇIK (3x LONG)")
                print(f"💵 Giriş: {giris_fiyati:,.2f} $ | 🏔️ Zirve: {tepe_fiyati:,.2f} $")
                print(f"⚡ Anlık Kâr: {bakiye * roe:+.2f} TL (%{roe * 100:.2f})")
                print(f"💼 TOPLAM: {bakiye + (bakiye * roe):,.2f} TL")

            print("=" * 52)

            # --- İŞLEMLER ---
            if action == 1 and not pozisyon and rsi < RSI_AL:
                bakiye -= (bakiye * KALDIRAC * KOMISYON_ORANI)
                giris_fiyati, tepe_fiyati, pozisyon = anlik_canli_fiyat, anlik_canli_fiyat, True
                print("\n🔔 ALIM YAPILDI!");
                time.sleep(5)
            elif pozisyon:
                degisim = (anlik_canli_fiyat - giris_fiyati) / giris_fiyati
                roe = degisim * KALDIRAC
                zirveden_dusus = (tepe_fiyati - anlik_canli_fiyat) / tepe_fiyati
                if rsi > RSI_SAT or roe > 0.30 or roe < -0.15 or (
                        zirveden_dusus > ZIRVEDEN_DONUS_LIMITI and roe > 0.05) or action == 2:
                    bakiye += (bakiye * roe) - (bakiye * KALDIRAC * KOMISYON_ORANI)
                    pozisyon = False
                    print(f"\n💰 SATILDI!");
                    time.sleep(5)

            print("\nGüncelleniyor...", end="", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"Hata: {e}");
            time.sleep(10)