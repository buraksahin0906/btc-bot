"""
kurulum.py — Tek komutluk kurulum sihirbazı.

PC'de bunu çalıştır:  python kurulum.py

Yaptıkları:
  1. Gerekli kütüphaneleri kurar (isteğe bağlı).
  2. OKX API anahtarlarını sorar ve senin yerine .env dosyasını oluşturur.
  3. Sonraki adımları söyler.

Hiçbir şey elle yazmana gerek yok — sadece soruları cevapla.
Gizli anahtarlar YALNIZCA bu bilgisayarda .env dosyasına yazılır, git'e gitmez.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")


def satir(char="─", n=56):
    print(char * n)


def sor_evet_hayir(soru: str, varsayilan: bool = True) -> bool:
    ek = "[E/h]" if varsayilan else "[e/H]"
    cevap = input(f"{soru} {ek}: ").strip().lower()
    if not cevap:
        return varsayilan
    return cevap in ("e", "evet", "y", "yes")


def main():
    satir("═")
    print("  CRYPTO FUTURES BOT — KURULUM SİHİRBAZI")
    satir("═")
    print("Bu sihirbaz senin yerine .env dosyasını oluşturur.")
    print("Sadece soruları cevapla, gerisini bot halleder.\n")

    # ---------------- 1) Kütüphaneler ----------------
    if sor_evet_hayir("Gerekli kütüphaneler kurulsun mu? (pip install)", True):
        req = os.path.join(HERE, "requirements.txt")
        print("\nKütüphaneler kuruluyor...\n")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], check=True)
            print("\n✅ Kütüphaneler kuruldu.\n")
        except subprocess.CalledProcessError:
            print("\n⚠️  Kurulum hatası oldu — yine de devam edebilirsin, "
                  "sonra elle 'pip install -r requirements.txt' dene.\n")

    # ---------------- 2) .env var mı? ----------------
    if os.path.exists(ENV_PATH):
        print(f"⚠️  Zaten bir .env dosyası var: {ENV_PATH}")
        if not sor_evet_hayir("Üzerine yazılsın mı?", False):
            print("Kurulum iptal edildi. Mevcut .env korundu.")
            return

    # ---------------- 3) Mod seçimi ----------------
    satir()
    print("Nasıl başlamak istersin?\n")
    print("  1) Sadece paper (simülasyon) — API anahtarı GEREKMEZ, en güvenli")
    print("  2) Demo (testnet) — sahte parayla gerçek emir testi (OKX demo key gerekir)")
    print("  3) Gerçek (canlı) — GERÇEK PARA (dikkatli ol, önce demo öneririz)")
    secim = input("\nSeçimin [1/2/3] (varsayılan 1): ").strip() or "1"

    api_key = api_secret = passphrase = ""
    demo = "false"

    if secim in ("2", "3"):
        print("\nOKX API bilgilerini gir (OKX → Profil → API → Yeni anahtar):")
        print("(Girerken secret ve passphrase güvenlik için ekranda GÖRÜNMEZ)\n")
        api_key = input("  OKX API Key      : ").strip()
        api_secret = getpass.getpass("  OKX Secret Key   : ").strip()
        passphrase = getpass.getpass("  OKX Passphrase   : ").strip()
        demo = "true" if secim == "2" else "false"
        if secim == "2":
            print("\n→ DEMO modu seçildi (OKX_DEMO=true). Sahte parayla test.")
        else:
            print("\n⚠️  GERÇEK mod seçildi. Bot yine de varsayılan olarak paper başlar;")
            print("    canlıya geçmek için config.py'de paper_trade=False, live_trading=True")
            print("    yapıp çalıştırınca terminalde 'LIVE' onayı istenecek.")
    else:
        print("\n→ Paper (simülasyon) modu. API anahtarı olmadan çalışır.")

    # ---------------- 4) Telegram (opsiyonel) ----------------
    tg_token = tg_chat = ""
    if sor_evet_hayir("\nTelegram bildirimi ekleyecek misin? (opsiyonel)", False):
        tg_token = input("  Telegram Bot Token : ").strip()
        tg_chat = input("  Telegram Chat ID   : ").strip()

    # ---------------- 5) .env yaz ----------------
    icerik = (
        "# Bu dosya kurulum.py tarafından oluşturuldu. Gizli — git'e gitmez.\n\n"
        f"OKX_API_KEY={api_key}\n"
        f"OKX_API_SECRET={api_secret}\n"
        f"OKX_API_PASSPHRASE={passphrase}\n"
        f"OKX_DEMO={demo}\n\n"
        f"TELEGRAM_BOT_TOKEN={tg_token}\n"
        f"TELEGRAM_CHAT_ID={tg_chat}\n"
    )
    with open(ENV_PATH, "w") as f:
        f.write(icerik)

    satir("═")
    print(f"✅ .env dosyası oluşturuldu:\n   {ENV_PATH}")
    satir("═")

    # ---------------- 6) Sonraki adımlar ----------------
    print("\nSIRADAKİ ADIM — botu başlat:\n")
    print("    python main.py\n")
    if secim == "1":
        print("Paper modda çalışacak (güvenli). Sinyalleri ve özeti göreceksin.")
    elif secim == "2":
        print("Demo emirlerini denemek için config.py'de:")
        print("    paper_trade = False")
        print("    live_trading = True")
        print("yapıp 'python main.py' çalıştır, terminalde LIVE yaz.")
    else:
        print("⚠️  Canlıya geçmeden önce MUTLAKA uzun paper/demo testi yap.")
    print("\nBaşarılar! Detaylar için README.md ve PROGRESS.md dosyalarına bak.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nKurulum iptal edildi.")
