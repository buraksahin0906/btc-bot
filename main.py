#!/usr/bin/env python3
# ================================================================
# MAIN.PY - Botu Başlatan Dosya
# ================================================================
# Kullanım: python main.py
#
# Bu dosya hem botu hem de web panelini aynı anda başlatır.
# Bot arka planda çalışır, web paneli ana thread'de çalışır.
#
# Durdurmak için: Ctrl+C tuşlarına basın
# ================================================================

import threading
import sys
import time
import ayarlar
import bot
import dashboard


def main():
    """Ana giriş noktası"""

    print()
    print("=" * 60)
    print("   ₿  KRİPTO TRADİNG SİMÜLASYON BOTU  ₿")
    print("=" * 60)
    print()
    print("  ⚠️  UYARI: Bu bir SİMÜLASYONDUR!")
    print("  Gerçek para kullanılmaz. Gerçek işlem açılmaz.")
    print("  Binance'den sadece VERİ OKUNUR.")
    print()
    print(f"  Başlangıç sanal bakiyesi : {ayarlar.BASLANGIC_BAKIYE:,.2f} USDT")
    print(f"  Takip edilen coinler     : {', '.join(ayarlar.COINLER)}")
    print(f"  Döngü süresi             : {ayarlar.DONGÜ_SURESI} sn ({ayarlar.DONGÜ_SURESI//60} dk)")
    print()
    print("=" * 60)
    print(f"  WEB PANELİ  → http://localhost:{ayarlar.PANEL_PORT}")
    print(f"  LOG DOSYASI → {ayarlar.LOG_DOSYASI}")
    print("  DURDURMAK   → Ctrl+C")
    print("=" * 60)
    print()

    # 1 saniye bekle (kullanıcı mesajı okusun)
    time.sleep(1)

    # ─── Bot Thread'ini Başlat ────────────────────────────────────
    # daemon=True: Ana program kapanınca bu thread de kapanır
    bot_thread = threading.Thread(
        target=bot.bot_baslat,
        name="BotThread",
        daemon=True
    )
    bot_thread.start()
    print("[✓] Bot thread'i başlatıldı")

    # Bot'un ilk veriyi çekip yüklemesi için kısa bekleme
    time.sleep(2)

    print("[✓] Web paneli başlatılıyor...\n")

    # ─── Flask Web Panelini Başlat (Ana Thread'de) ────────────────
    try:
        dashboard.dashboard_baslat()

    except KeyboardInterrupt:
        print("\n\n[BİTİŞ] Program Ctrl+C ile durduruldu.")
        print(f"[BİLGİ] İşlem geçmişi '{ayarlar.LOG_DOSYASI}' dosyasına kaydedildi.")
        sys.exit(0)

    except OSError as hata:
        if "Address already in use" in str(hata):
            print(f"\n[HATA] Port {ayarlar.PANEL_PORT} zaten kullanımda!")
            print(f"  Çözüm: ayarlar.py dosyasında PANEL_PORT değerini değiştirin")
            print(f"  Örnek: PANEL_PORT = 5001")
        else:
            print(f"\n[HATA] Web paneli başlatılamadı: {hata}")
        sys.exit(1)


if __name__ == "__main__":
    main()
