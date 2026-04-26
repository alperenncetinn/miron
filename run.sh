#!/bin/bash
# Miron — macOS Ekran Çeviri Overlay Uygulaması
# Kullanım: ./run.sh

set -e

cd "$(dirname "$0")"

# Virtual environment kontrolü
if [ ! -d ".venv" ]; then
    echo "🔧 Virtual environment oluşturuluyor..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "📦 Bağımlılıklar yükleniyor..."
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Ollama servis kontrolü
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama servisi çalışmıyor!"
    echo "   Lütfen 'ollama serve' komutunu çalıştırın."
    echo "   Model çekmek için: ollama pull llama3:8b"
    exit 1
fi

echo "🚀 Miron başlatılıyor..."
python -m miron.main
