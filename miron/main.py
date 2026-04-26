"""Miron uygulama giriş noktası."""

import sys
import signal
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase

from .overlay import OverlayController


def main():
    """Uygulamayı başlatır."""
    logging.basicConfig(
        filename="miron.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logging.info("--- Miron Başlatılıyor ---")
    # macOS'ta yüksek DPI desteği
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Miron")
    app.setOrganizationName("Miron")

    # macOS: Uygulamayı "Accessory" (Dock ikonu olmayan, arkaplan/menü çubuğu stili) yap
    # Bu sayede macOS tam ekran oyunlarında veya farklı spacelerdeyken
    # uygulamanın pencereleri zorla masaüstüne (Desktop) geri atılmaz.
    try:
        import AppKit
        ns_app = AppKit.NSApplication.sharedApplication()
        # 1 = NSApplicationActivationPolicyAccessory
        ns_app.setActivationPolicy_(1)
    except Exception as e:
        logging.warning(f"macOS Activation Policy ayarlanamadı: {e}")

    # --- Font yükleme ---
    # SF Pro varsa kullan, yoksa Inter'e düş
    _load_fonts()

    # --- Uygulama stili ---
    app.setStyle("Fusion")  # Platform bağımsız temel stil

    # --- Kontrolcü ---
    controller = OverlayController()
    controller.start()

    # --- Graceful Shutdown ---
    # Ctrl+C ile temiz kapatma
    def handle_sigint(*args):
        print("\n[Miron] Kapatılıyor...")
        controller.stop()
        app.quit()

    signal.signal(signal.SIGINT, handle_sigint)

    # SIGINT'in Qt event loop tarafından yakalanması için timer
    signal_timer = QTimer()
    signal_timer.start(200)
    signal_timer.timeout.connect(lambda: None)

    # --- Event loop ---
    sys.exit(app.exec())


def _load_fonts():
    """Sistem fontlarını kontrol eder, gerekirse fallback font ayarlar."""
    # SF Pro Display macOS'ta varsayılan olarak bulunur
    available = QFontDatabase.families()

    preferred_fonts = [
        "SF Pro Display",
        "SF Pro Text",
        ".AppleSystemUIFont",
        "Inter",
        "Helvetica Neue",
    ]

    for font_name in preferred_fonts:
        if font_name in available:
            default_font = QFont(font_name, 13)
            QApplication.setFont(default_font)
            return

    # Hiçbiri bulunamazsa sistem varsayılanı kullanılır


if __name__ == "__main__":
    main()
