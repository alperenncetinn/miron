"""Ana overlay kontrolcüsü — tüm bileşenleri koordine eder."""

from PySide6.QtCore import QObject, QTimer, QRect, Signal
import logging

from .config import config
from .capture import capture_region, check_screen_capture_permission
from .ocr import recognize_text, blocks_to_text, normalize_text
from .translator import TranslationEngine
from .selection_window import SelectionWindow


class OverlayController(QObject):
    """OCR → Çeviri → UI pipeline'ını yöneten ana kontrolcü.

    Bileşenler:
        - SelectionWindow: Kullanıcının taranacak alanı seçmesi
        - TranslationPanel: Çeviri sonuçlarının gösterilmesi
        - TranslationEngine: Ollama ile çeviri
        - QTimer: Periyodik OCR tarama
    """

    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._last_normalized_text: str = ""

        # --- Bileşenleri oluştur ---
        self._selection = SelectionWindow()
        self._engine = TranslationEngine()

        # --- OCR zamanlayıcı ---
        self._ocr_timer = QTimer(self)
        self._ocr_timer.setInterval(config.ocr_interval_ms)
        self._ocr_timer.timeout.connect(self._on_ocr_tick)

        # --- Sinyal bağlantıları ---

        # Seçim penceresi
        self._selection.scanning_toggled.connect(self._on_scanning_toggled)
        self._selection.region_changed.connect(self._on_region_changed)

        # Çeviri motoru
        self._engine.translation_ready.connect(self._on_translation_ready)
        self._engine.translation_error.connect(self._on_translation_error)
        self._engine.status_changed.connect(self._on_engine_status_changed)

    # --- Başlatma / Durdurma ---

    def start(self):
        """Uygulamayı başlatır — pencereleri gösterir."""
        # Ekran kaydı izni kontrolü
        has_permission = check_screen_capture_permission()
        if not has_permission:
            print(
                "[Miron] ⚠ Ekran kaydı izni gerekli.\n"
                "        Sistem Ayarları → Gizlilik ve Güvenlik → Ekran Kaydı\n"
                "        bölümünden izin verin ve uygulamayı yeniden başlatın."
            )

        # Çeviri motorunu başlat
        self._engine.start()

        # Pencereleri göster
        self._selection.show()

        print("[Miron] ✓ Uygulama başlatıldı.")
        print("[Miron]   Tarama alanını sürükleyip boyutlandırın.")
        print("[Miron]   Çift tıklayarak taramayı başlatın.")

    def stop(self):
        """Uygulamayı durdurur — temizlik yapar."""
        self._ocr_timer.stop()
        self._engine.stop()
        self._selection.close()
        print("[Miron] Uygulama durduruldu.")

    # --- Slot'lar ---

    def _on_scanning_toggled(self, is_scanning: bool):
        """Tarama durumu değiştiğinde çağrılır."""
        if is_scanning:
            self._selection.set_status("scanning")
            self._ocr_timer.start()
            print("[Miron] ▶ Tarama başlatıldı.")
        else:
            self._ocr_timer.stop()
            self._selection.set_status("idle")
            print("[Miron] ⏸ Tarama durduruldu.")

    def _on_region_changed(self, rect: QRect):
        """Seçim alanı değiştiğinde çağrılır."""
        pass  # Artık paneli konumlandırmaya gerek yok

    def _on_translation_ready(self, original: str, translation: str):
        """Çeviri tamamlandığında paneli günceller."""
        logging.info("Arayüz güncelleniyor (Çeviri hazır)")
        self._selection.set_translation(translation)

    def _on_translation_error(self, error_msg: str):
        """Çeviri hatasında paneli günceller."""
        logging.error(f"Arayüz güncelleniyor (Hata): {error_msg}")
        self._selection.set_status("error")
        self.error_occurred.emit(error_msg)

    def _on_engine_status_changed(self, status: str):
        """Motor durumu değiştiğinde paneli günceller."""
        logging.info(f"Arayüz durumu güncelleniyor: {status}")
        self._selection.set_status(status)

    # --- OCR Pipeline ---

    def _on_ocr_tick(self):
        """Periyodik OCR tarama — timer tarafından çağrılır."""
        if not self._selection.is_scanning():
            return

        try:
            # 1. Ekran koordinatlarını al
            x, y, w, h = self._selection.get_screen_region()
            if w < 10 or h < 10:
                return

            # 2. Ekranı yakala (overlay pencerelerini hariç tut)
            selection_wid = self._selection.get_window_id()
            cg_image = capture_region(x, y, w, h, exclude_window_id=selection_wid)

            if cg_image is None:
                logging.warning("Ekran yakalanamadı.")
                return

            # 3. OCR yap
            blocks = recognize_text(
                cg_image,
                languages=config.ocr_languages,
                recognition_level=config.ocr_recognition_level,
            )

            if not blocks:
                logging.debug("OCR: Metin bulunamadı")
                return

            # 4. Metin oluştur
            full_text = blocks_to_text(blocks)
            if not full_text.strip():
                return

            # 5. Değişim kontrolü
            normalized = normalize_text(full_text)
            if normalized == self._last_normalized_text:
                return  # Metin değişmedi, çeviri atla

            self._last_normalized_text = normalized
            logging.info(f"OCR metin bulundu ({len(blocks)} blok): {full_text[:50]}...")

            # 6. Orijinal metni göster
            # Orijinal metni loglayabilir veya göstermeyebiliriz (artık panel yok)

            # 7. Çeviriye gönder
            logging.info("Çeviri motoruna gönderiliyor...")
            self._engine.translate(full_text)

        except Exception as e:
            logging.error(f"OCR hatası: {e}")
            self._selection.set_status("error")

    # --- Yardımcılar ---
