@echo off
chcp 65001 >nul
title Canli Yazi Tabelasi - Vercel
cd /d "%~dp0"

echo(
echo ==================================================
echo    CANLI YAZI TABELASI  -  Vercel'e Yayinla
echo ==================================================
echo(

REM --- Node.js / npx kurulu mu? ---
where npx >nul 2>nul
if errorlevel 1 (
  echo [HATA] Node.js bulunamadi.
  echo(
  echo Once https://nodejs.org adresinden Node.js'i indirip kurun,
  echo sonra bu dosyayi tekrar cift tiklayin.
  echo(
  pause
  exit /b 1
)

REM --- Kullanicidan metni al ve HTML'e gom (PowerShell: Turkce/Unicode guvenli) ---
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Read-Host 'Ekranda ne yazsin'; if([string]::IsNullOrWhiteSpace($t)){$t='Merhaba'}; $enc=[System.Net.WebUtility]::HtmlEncode($t); $tpl=[IO.File]::ReadAllText('index.template.html',[Text.Encoding]::UTF8); $out=$tpl.Replace('__MESAJ__',$enc); [IO.File]::WriteAllText('index.html',$out,(New-Object Text.UTF8Encoding($false))); Write-Host ''; Write-Host ('  Kaydedildi: ' + $t)"

if not exist index.html (
  echo [HATA] Metin kaydedilemedi.
  pause
  exit /b 1
)

echo(
echo Vercel'e yayinlaniyor...
echo (Ilk seferde Vercel'e giris yapmaniz istenebilir - ekrandaki
echo  yonergeleri izleyin: GitHub / Google / e-posta ile giris.)
echo(

REM --- Production deploy (varsayilanlari otomatik kabul et) ---
call npx --yes vercel@latest --prod --yes

echo(
echo ==================================================
echo  BITTI!
echo  Yukarida gorunen  https://....vercel.app  linkini
echo  telefonda veya baska bir cihazda acabilirsiniz.
echo  Herkes bu linkten yazinizi gorebilir.
echo(
echo  Yaziyi degistirmek icin bu dosyayi tekrar calistirin;
echo  ayni link guncellenir.
echo ==================================================
echo(
pause
