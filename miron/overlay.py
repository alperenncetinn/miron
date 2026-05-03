"""Ana overlay kontrolçüsü — tüm bileşenleri koordine eder."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, QRect, Signal
from PySide6.QtGui import QImage
import logging

import Quartz
import Vision

from .config import config
from .capture import capture_region, check_screen_capture_permission
from .ocr import recognize_text, blocks_to_text, normalize_text
from .translator import TranslationEngine
from .selection_window import SelectionWindow


def _cgimage_to_qimage(cg_image) -> QImage | None:
    """CGImage'ı QImage'a dönüştürür (blur arka plan için).

    Args:
        cg_image: Quartz CGImage nesnesi.

    Returns:
        QImage nesnesi veya dönüştürülemezse None.
    """
    if cg_image is None:
        return None

    try:
        width = Quartz.CGImageGetWidth(cg_image)
        height = Quartz.CGImageGetHeight(cg_image)

        if width == 0 or height == 0:
            return None

        # CGImage'dan bitmap veri al
        color_space = Quartz.CGColorSpaceCreateDeviceRGB()
        bytes_per_row = width * 4  # RGBA

        context = Quartz.CGBitmapContextCreate(
            None,
            width, height,
            8,  # bits per component
            bytes_per_row,
            color_space,
            Quartz.kCGImageAlphaPremultipliedLast,  # RGBA
        )

        if context is None:
            return None

        rect = Quartz.CGRectMake(0, 0, width, height)
        Quartz.CGContextDrawImage(context, rect, cg_image)

        # Bitmap verisini al
        data = Quartz.CGBitmapContextGetData(context)
        if data is None:
            return None

        # ctypes pointer'dan bytes'a çevir
        import ctypes
        buf = (ctypes.c_uint8 * (bytes_per_row * height)).from_address(data)
        raw_bytes = bytes(buf)

        # QImage oluştur (RGBA formatı)
        qimage = QImage(
            raw_bytes,
            width, height,
            bytes_per_row,
            QImage.Format.Format_RGBA8888_Premultiplied,
        )
        # QImage veriyi kopyalasın (context GC olabilir)
        return qimage.copy()

    except Exception as e:
        logging.error(f"CGImage → QImage dönüşüm hatası: {e}")
        return None


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
        self._ocr_cg_image = None  # Scroll tracking için son OCR görüntüsü

        # --- Bileşenleri oluştur ---
        self._selection = SelectionWindow()
        self._engine = TranslationEngine()

        # --- OCR zamanlayıcı ---
        self._ocr_timer = QTimer(self)
        self._ocr_timer.setInterval(config.ocr_interval_ms)
        self._ocr_timer.timeout.connect(self._on_ocr_tick)

        # --- Kaydırma (Scroll) zamanlayıcı ---
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(40)  # 25 FPS ile kaydırma takibi
        self._scroll_timer.timeout.connect(self._on_scroll_tick)

        # --- Temizleme (Clear) zamanlayıcı ---
        self._clear_timer = QTimer(self)
        self._clear_timer.setInterval(config.subtitle_clear_ms)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._on_clear_timeout)

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
        self._scroll_timer.stop()
        self._clear_timer.stop()
        self._engine.stop()
        self._selection.close()
        print("[Miron] Uygulama durduruldu.")

    def toggle_scanning(self):
        """Taramayı başlatır / durdurur."""
        self._selection.toggle_scanning()

    # --- Slot'lar ---

    def _on_scanning_toggled(self, is_scanning: bool):
        """Tarama durumu değiştiğinde çağrılır."""
        if is_scanning:
            self._selection.set_status("scanning")
            self._ocr_timer.start()
            self._scroll_timer.start()
            print("[Miron] ▶ Tarama başlatıldı.")
        else:
            self._ocr_timer.stop()
            self._scroll_timer.stop()
            self._clear_timer.stop()
            self._selection.set_status("idle")
            self._ocr_cg_image = None
            print("[Miron] ⏸ Tarama durduruldu.")

    def _on_region_changed(self, rect: QRect):
        """Seçim alanı değiştiğinde çağrılır."""
        pass  # Artık paneli konumlandırmaya gerek yok

    def _on_translation_ready(self, blocks: list, translated_lines: list, is_fallback: bool):
        """Çeviri tamamlandığında paneli günceller."""
        logging.info(f"Arayüz güncelleniyor (Çeviri hazır, fallback={is_fallback})")
        self._selection.set_translation_blocks(blocks, translated_lines, is_fallback)

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

            self._ocr_cg_image = cg_image

            # 3. Yakalanan görüntüyü blur arka plan olarak kaydet
            bg_qimage = _cgimage_to_qimage(cg_image)
            if bg_qimage is not None:
                self._selection.set_background_capture(bg_qimage)

            # 4. OCR yap
            blocks = recognize_text(
                cg_image,
                languages=config.ocr_languages,
                recognition_level=config.ocr_recognition_level,
            )

            # 4.5. Retina Ekran (Piksel -> Point) koordinat dönüşümü
            img_width = Quartz.CGImageGetWidth(cg_image)
            scale_factor = img_width / w if w > 0 else 1.0
            
            if scale_factor != 1.0 and scale_factor > 0:
                for b in blocks:
                    b.x /= scale_factor
                    b.y /= scale_factor
                    b.width /= scale_factor
                    b.height /= scale_factor

            if not blocks:
                logging.debug("OCR: Metin bulunamadı")
                if not self._clear_timer.isActive():
                    self._clear_timer.start()
                return

            # Metin bulunduysa temizleme zamanlayıcısını durdur
            self._clear_timer.stop()

            # 5. Metin oluştur
            full_text = blocks_to_text(blocks)
            if not full_text.strip():
                return

            # 6. Değişim kontrolü
            normalized = normalize_text(full_text)
            if normalized == self._last_normalized_text:
                return  # Metin değişmedi, çeviri atla

            self._last_normalized_text = normalized
            logging.info(f"OCR metin bulundu ({len(blocks)} blok): {full_text[:50]}...")

            # 7. Orijinal metni göster
            # Orijinal metni loglayabilir veya göstermeyebiliriz (artık panel yok)

            # 8. Çeviriye gönder
            logging.info("Çeviri motoruna gönderiliyor...")
            self._engine.translate(blocks)

        except Exception as e:
            logging.error(f"OCR hatası: {e}")
            self._selection.set_status("error")

    def _on_scroll_tick(self):
        """Kaydırma takibi — çok yüksek hızda (25 FPS) çalışarak çeviri kutularını kaydırır."""
        if config.game_mode:
            return  # Oyun modunda kaydırma takibini kapat
            
        if not self._selection.is_scanning() or self._ocr_cg_image is None:
            return

        try:
            x, y, w, h = self._selection.get_screen_region()
            if w < 10 or h < 10:
                return

            selection_wid = self._selection.get_window_id()
            curr_image = capture_region(x, y, w, h, exclude_window_id=selection_wid)

            if curr_image is None:
                return

            # Apple Vision Registration Request
            req = Vision.VNTranslationalImageRegistrationRequest.alloc().initWithTargetedCGImage_options_(self._ocr_cg_image, None)
            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(curr_image, None)
            success, error = handler.performRequests_error_([req], None)

            if success:
                results = req.results()
                if results and len(results) > 0:
                    t = results[0].alignmentTransform()
                    
                    # Retina faktörünü uygula
                    img_width = Quartz.CGImageGetWidth(curr_image)
                    scale_factor = img_width / w if w > 0 else 1.0
                    
                    # t.tx ve t.ty piksel cinsinden dönüşümü verir
                    # Eğer ekran aşağı kaydırılırsa, yeni görüntü eskiye göre yukarı gitmiş gibi olur,
                    # Dolayısıyla çeviri kutularının da aynı oranda (-t.tx, -t.ty) kaydırılması gerekir.
                    # Aslında transformation offseti doğrudan kutulara eklenince hizalanır.
                    # Retina'ya göre normalize edelim:
                    
                    dx = t.tx / scale_factor if scale_factor > 0 else 0
                    dy = -t.ty / scale_factor if scale_factor > 0 else 0  # y ekseni Vision'da ters
                    
                    self._selection.set_scroll_offset(dx, dy)

        except Exception as e:
            logging.debug(f"Scroll tracking hatası: {e}")

    def _on_clear_timeout(self):
        """Uzun süre metin bulunamadığında çevirileri ekrandan kaldırır."""
        logging.info("Metin bulunamadı, çeviriler temizleniyor.")
        self._selection.set_translation_blocks([], [], False)
        self._last_normalized_text = ""
        self._ocr_cg_image = None

    # --- Yardımcılar ---
