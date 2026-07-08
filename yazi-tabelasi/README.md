# Canlı Yazı Tabelası

Bir kutuya yazarsın, ekranı kaplayan **dev punto** ile anında gösterir — dijital
tabela / afiş gibi. Renk, zemin, punto ayarlanır; tam ekran ve kayan yazı modu var.
Backend yok, tek `index.html` dosyası. Yazdığın metin tarayıcıda hatırlanır.

## Kullanım (yerelde)

`index.html`'e çift tıkla — tarayıcıda açılır. Yaz, ekranda görün. Bu kadar.

- **Tam Ekran ▶** butonu: kontroller gizlenir, sadece dev yazı kalır. Çıkmak için `ESC`
  veya ekrana dokun.
- **Kayan yazı**: uzun metinleri soldan sağa kaydırır.
- Hazır tema butonları (beyaz/siyah, sarı, kırmızı, neon...) veya kendi renklerini seç.

## Vercel'e yayınlama

### 1) En kolay — sürükle-bırak
1. https://vercel.com hesabına gir → **Add New… → Project**.
2. `yazi-tabelasi` klasörünü sürükle-bırak (veya "deploy a folder").
3. **Deploy** de. Ayar gerekmez (statik site). Sana bir `.vercel.app` linki verir.

### 2) GitHub ile (otomatik)
1. Vercel'de **Add New… → Project → Import Git Repository** → bu repoyu seç.
2. **Root Directory** olarak `yazi-tabelasi` seç.
3. Framework: **Other** (build komutu yok). **Deploy**.
4. Bundan sonra her `git push`'ta site otomatik güncellenir.

### 3) Vercel CLI
```bash
npm i -g vercel
cd yazi-tabelasi
vercel        # ilk sefer sorulara cevap ver
vercel --prod # canlıya al
```

## Notlar
- Tamamen istemci taraflı (JavaScript), sunucu/veritabanı yok.
- Metin ve ayarlar tarayıcının `localStorage`'ında tutulur — cihaz/tarayıcı değişince gitmez.
