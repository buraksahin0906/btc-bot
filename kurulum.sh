#!/bin/bash
# Kronos + BTC Bot Kurulum Scripti

echo "=================================================="
echo "  KRONOS HİBRİT BTC BOT - KURULUM"
echo "=================================================="

# Python kontrolü
python3 --version || { echo "❌ Python 3 bulunamadı!"; exit 1; }

echo ""
echo "📦 Temel bağımlılıklar yükleniyor..."
pip install -q yfinance pandas numpy ta scikit-learn stable-baselines3 torch transformers huggingface_hub

echo ""
echo "📥 Kronos GitHub'dan klonlanıyor..."
if [ ! -d "Kronos" ]; then
    git clone https://github.com/shiyu-coder/Kronos.git
    echo "✅ Kronos klonlandı."
else
    echo "✅ Kronos zaten mevcut, güncelleniyor..."
    cd Kronos && git pull && cd ..
fi

echo ""
echo "📦 Kronos bağımlılıkları yükleniyor..."
pip install -q -r Kronos/requirements.txt

echo ""
echo "🧠 Kronos modeli HuggingFace'den indiriliyor..."
echo "   (Kronos-mini: ~16MB, ilk seferde biraz sürer)"
python3 -c "
import sys
sys.path.insert(0, 'Kronos')
from model import Kronos, KronosTokenizer, KronosPredictor
print('Tokenizer indiriliyor...')
t = KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base')
print('Model indiriliyor...')
m = Kronos.from_pretrained('NeoQuasar/Kronos-mini')
print('✅ Model başarıyla indirildi!')
"

echo ""
echo "=================================================="
echo "  ✅ KURULUM TAMAMLANDI!"
echo "  Botu başlatmak için: python3 canli_vadeli_kronos.py"
echo "=================================================="
