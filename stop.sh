#!/bin/bash
# Miron — Uygulamayı Durdur
# Kullanım: ./stop.sh

set -e

echo "🛑 Miron durduruluyor..."

# Miron proseslerini bul ve sonlandır
PIDS=$(pgrep -f "python.*miron\.main" 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "ℹ️  Çalışan Miron prosesi bulunamadı."
    exit 0
fi

for PID in $PIDS; do
    echo "   PID $PID sonlandırılıyor..."
    kill -SIGINT "$PID" 2>/dev/null || true
done

# Graceful shutdown için 3 saniye bekle
sleep 2

# Hâlâ çalışıyorsa zorla kapat
REMAINING=$(pgrep -f "python.*miron\.main" 2>/dev/null || true)
if [ -n "$REMAINING" ]; then
    echo "⚠️  Graceful shutdown başarısız, zorla kapatılıyor..."
    for PID in $REMAINING; do
        kill -9 "$PID" 2>/dev/null || true
    done
fi

echo "✅ Miron durduruldu."
