import requests
import json
from datetime import datetime

SEMBOL   = "SOLUSDT"
INTERVAL = "4h"
LIMIT    = 100

def veri_cek():
    url = f"https://api.binance.com/api/v3/klines?symbol={SEMBOL}&interval={INTERVAL}&limit={LIMIT}"
    r   = requests.get(url, timeout=10)
    raw = r.json()
    mumlar = []
    for m in raw:
        mumlar.append({
            "open" : float(m[1]),
            "high" : float(m[2]),
            "low"  : float(m[3]),
            "close": float(m[4]),
        })
    return mumlar

def rsi_hesapla(mumlar, period=14):
    kapanislar = [m["close"] for m in mumlar]
    kazanc, kayip = [], []
    for i in range(1, len(kapanislar)):
        fark = kapanislar[i] - kapanislar[i-1]
        kazanc.append(max(fark, 0))
        kayip.append(max(-fark, 0))
    ort_k = sum(kazanc[-period:]) / period
    ort_ka = sum(kayip[-period:]) / period
    if ort_ka == 0:
        return 100
    rs = ort_k / ort_ka
    return 100 - (100 / (1 + rs))

def destek_direnc(mumlar, pencere=20):
    son = mumlar[-pencere:]
    destek  = min(m["low"]  for m in son)
    direnc  = max(m["high"] for m in son)
    return destek, direnc

def zirve_mi(mumlar, esik=0.02):
    son_fiyat = mumlar[-1]["close"]
    son20_max = max(m["high"] for m in mumlar[-20:])
    return (son20_max - son_fiyat) / son20_max < esik

def analiz():
    print("=" * 46)
    print(f"  SOL/USDT  —  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 46)

    mumlar = veri_cek()

    fiyat        = mumlar[-1]["close"]
    rsi          = rsi_hesapla(mumlar)
    destek, direnc = destek_direnc(mumlar)
    zirvede      = zirve_mi(mumlar)

    # Alım seviyesi: son 20 mumun en düşüğü + küçük buffer
    al_seviye  = round(destek * 1.002, 2)

    # Satım seviyesi: son 20 mumun en yükseği - küçük buffer
    sat_seviye = round(direnc * 0.997, 2)

    # Beklenen kazanç
    kazanc_pct = ((sat_seviye - al_seviye) / al_seviye) * 100

    print(f"  Güncel Fiyat : {fiyat:.2f} $")
    print(f"  RSI          : {rsi:.1f}")
    print()

    if zirvede:
        print("  ⚠️  UYARI: Fiyat şu an ZİRVEYE yakın!")
        print("  Alım için daha iyi fırsat beklenebilir.")
        print()

    print(f"  🟢 AL  SEVİYESİ : {al_seviye:.2f} $")
    print(f"  🔴 SAT SEVİYESİ : {sat_seviye:.2f} $")
    print(f"  💰 Beklenen Kâr : %{kazanc_pct:.2f}")
    print()

    # RSI yorumu
    if rsi < 30:
        print("  RSI: Aşırı satım — AL fırsatı güçlü 🟢")
    elif rsi < 45:
        print("  RSI: Nötr/düşük — Alım makul ⚪")
    elif rsi > 70:
        print("  RSI: Aşırı alım — Alım riskli 🔴")
    else:
        print("  RSI: Nötr — Normal bölge ⚪")

    print()
    print("  OKX'e gir → Limit emir:")
    print(f"  Buy  Limit → {al_seviye:.2f} $")
    print(f"  Sell Limit → {sat_seviye:.2f} $")
    print("=" * 46)

if __name__ == "__main__":
    analiz()
