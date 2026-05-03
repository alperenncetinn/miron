"""Miron uygulama giriş noktası."""

import sys
import signal
import logging

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPainter, QColor

from .overlay import OverlayController
from .config import config


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
    # Ctrl+C veya Tray üzerinden temiz kapatma
    def quit_app(*args):
        print("\n[Miron] Kapatılıyor...")
        controller.stop()
        app.quit()

    signal.signal(signal.SIGINT, quit_app)

    # SIGINT'in Qt event loop tarafından yakalanması için timer
    signal_timer = QTimer()
    signal_timer.start(200)
    signal_timer.timeout.connect(lambda: None)

    # --- System Tray ---
    # Basit bir ikon oluştur
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(139, 92, 246)) # Mor renk
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.setPen(Qt.GlobalColor.white)
    font = painter.font()
    font.setPixelSize(16)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
    painter.end()

    tray_icon = QSystemTrayIcon(QIcon(pixmap), app)
    
    tray_menu = QMenu()
    toggle_action = tray_menu.addAction("Taramayı Başlat / Durdur")
    toggle_action.triggered.connect(controller.toggle_scanning)
    
    tray_menu.addSeparator()
    
    # Oyun Modu
    game_mode_action = tray_menu.addAction("Oyun Modu (Hızlı Kaydırma Kapalı)")
    game_mode_action.setCheckable(True)
    game_mode_action.setChecked(config.game_mode)
    def toggle_game_mode(checked):
        from .config import config
        config.game_mode = checked
    game_mode_action.toggled.connect(toggle_game_mode)
    
    # Hızlı Çeviri Modu
    fast_trans_action = tray_menu.addAction("Hızlı Çeviri (Google Translate)")
    fast_trans_action.setCheckable(True)
    fast_trans_action.setChecked(config.fast_translation)
    def toggle_fast_trans(checked):
        from .config import config
        config.fast_translation = checked
    fast_trans_action.toggled.connect(toggle_fast_trans)

    tray_menu.addSeparator()
    
    quit_action = tray_menu.addAction("Çıkış")
    quit_action.triggered.connect(quit_app)
    
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

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
