# ================================================================
# DASHBOARD.PY - Web Panel (Flask ile)
# ================================================================
# Tarayıcıdan http://localhost:5000 adresinde açılır.
# Bot verileri JSON API olarak sunulur.
# HTML panel 5 saniyede bir otomatik güncellenir.
# ================================================================

from flask import Flask, render_template, jsonify
import bot
import ayarlar

# Flask uygulaması oluştur
# "templates" klasöründeki HTML dosyalarını kullanır
app = Flask(__name__)

# Flask'ın gereksiz loglarını bastır (terminal daha temiz görünsün)
import logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


@app.route("/")
def ana_sayfa():
    """Tarayıcı localhost:5000'e girince bu sayfa açılır"""
    return render_template("index.html")


@app.route("/api/durum")
def api_durum():
    """
    Bot verilerini JSON formatında döndürür.
    Tarayıcıdaki JavaScript bu endpoint'i her 5 saniyede çağırır.
    """
    with bot.durum_kilidi:
        # Sözlüğün kopyasını alarak thread güvenliğini sağla
        veri = dict(bot.paylasilan_durum)
    return jsonify(veri)


@app.route("/api/islemler")
def api_islemler():
    """Tüm işlem geçmişini döndürür"""
    with bot.durum_kilidi:
        islemler = list(bot.paylasilan_durum.get("son_islemler", []))
    return jsonify({"islemler": islemler})


def dashboard_baslat():
    """Flask web sunucusunu başlatır. Ana thread'de çalışır."""
    print(f"\n{'='*55}")
    print(f"  WEB PANELİ BAŞLATILIYOR")
    print(f"  Adres: http://localhost:{ayarlar.PANEL_PORT}")
    print(f"  Tarayıcınızda bu adresi açın!")
    print(f"{'='*55}\n")

    app.run(
        host=ayarlar.PANEL_HOST,
        port=ayarlar.PANEL_PORT,
        debug=False,
        use_reloader=False  # Thread çakışmasını önlemek için kapalı
    )
