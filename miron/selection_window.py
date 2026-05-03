"""Sürüklenebilir ve boyutlandırılabilir seçim penceresi."""

from __future__ import annotations

from enum import IntEnum, auto

from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QImage, QPixmap, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QApplication

from .config import config
from .styles import get_selection_window_style

try:
    import objc
    import ctypes
except ImportError:
    pass


class _Edge(IntEnum):
    """Pencere kenarları — boyutlandırma yönlerini belirler."""

    NONE = 0
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()


# Kenar algılama eşiği (piksel)
_EDGE_THRESHOLD = 8


class SelectionWindow(QWidget):
    """Ekran üzerinde sürüklenip boyutlandırılabilen seçim çerçevesi.

    Kullanıcı bu pencereyi hareket ettirip boyutunu değiştirerek
    OCR taranacak alanı belirler.

    Signals:
        region_changed(QRect): Seçim alanı değiştiğinde yayılır.
        scanning_toggled(bool): Tarama durumu değiştiğinde yayılır.
    """

    region_changed = Signal(QRect)
    scanning_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._is_scanning = False
        self._drag_edge = _Edge.NONE
        self._drag_start_pos = QPoint()
        self._drag_start_geo = QRect()
        self._cached_window_id: int | None = None

        self._is_fullscreen = False
        self._normal_geo = QRect()

        # Pencere ayarları
        self.setObjectName("SelectionWindow")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setMinimumSize(
            config.selection_min_width, config.selection_min_height
        )

        # Durum ve Çeviri Metinleri
        self._current_status = "Bekliyor"
        self._blocks = []
        self._translated_lines = []
        self._is_fallback = False
        
        self._scroll_x = 0.0
        self._scroll_y = 0.0

        # Blur arka plan için yakalanan ekran görüntüsü
        self._blurred_bg: QPixmap | None = None

        # Varsayılan boyut ve konum — ekranın ortası
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - config.selection_default_width) // 2
            y = (screen_geo.height() - config.selection_default_height) // 2
            self.setGeometry(
                x, y,
                config.selection_default_width,
                config.selection_default_height,
            )

        self.setStyleSheet(get_selection_window_style())

        # Pulse animasyonu için timer
        self._pulse_value = 0.0
        self._pulse_direction = 1
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(30)

        # macOS overlay enforcing timer
        self._enforce_timer = QTimer(self)
        self._enforce_timer.timeout.connect(self._enforce_mac_overlay)
        self._enforce_timer.setInterval(1000) # her 1 saniyede bir

    def showEvent(self, event):
        super().showEvent(event)
        self._enable_fullscreen_overlay()
        self._enforce_timer.start()

    # --- Boyama ---

    def paintEvent(self, event):
        """Seçim çerçevesini çizer — blur arka plan + çeviri metni overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        radius = 12

        # Clipping path — rounded rect
        clip_path = QPainterPath()
        clip_path.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setClipPath(clip_path)

        if self._is_scanning and self._blocks and self._translated_lines:
            # --- ÇEVİRİ MODU ---
            # Arka plan tamamen şeffaf (kullanıcı oyunu görebilsin)

            # Blokları orijinal konumlarında çiz
            for i, block in enumerate(self._blocks):
                # Çeviri satırı var mı kontrol et (Ollama satır sayısını bozmuş olabilir)
                trans_text = self._translated_lines[i] if i < len(self._translated_lines) else ""
                if not trans_text:
                    continue

                # Kaydırma offsetlerini ekle
                bx = int(block.x + self._scroll_x)
                by = int(block.y + self._scroll_y)

                # Metni çiz
                font = QFont("Helvetica Neue")
                # Font boyutunu bloğun yüksekliğine göre ayarla
                font.setPixelSize(max(10, int(block.height * 0.75)))
                font.setWeight(QFont.Weight.Bold)
                painter.setFont(font)
                
                # Gerçekte kaplayacağı alanı bul (kelime kaydırma yapıldığında)
                base_rect = QRect(bx, by, int(block.width), int(block.height))
                flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
                fm = painter.fontMetrics()
                bounding_rect = fm.boundingRect(base_rect, flags, trans_text)
                
                # Gerekli yüksekliği ayarla (orijinalden büyükse büyüt)
                text_h = max(int(block.height), bounding_rect.height())
                draw_rect = QRect(bx, by, int(block.width), text_h)

                # Arka plan
                bg_rect = QRect(draw_rect)
                bg_rect.adjust(-6, -4, 6, 4) # Sağdan/soldan biraz daha pay verelim
                
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bg_rect, 4, 4)
                
                # Metin gölgesi
                painter.setPen(QColor(0, 0, 0, 200))
                shadow_rect = draw_rect.translated(1, 1)
                painter.drawText(shadow_rect, flags, trans_text)
                
                # Metin
                painter.setPen(QColor(255, 255, 255, 255))
                painter.drawText(draw_rect, flags, trans_text)

            # Durum metni (sol üst)
            status_font = QFont("Helvetica Neue", 10)
            status_font.setWeight(QFont.Weight.Medium)
            painter.setFont(status_font)
            painter.setPen(QColor(255, 255, 255, 180))
            painter.drawText(10, 18, self._current_status)

            # Fallback rozeti (sağ üst)
            if self._is_fallback:
                badge_font = QFont("Helvetica Neue", 9)
                badge_font.setWeight(QFont.Weight.Bold)
                painter.setFont(badge_font)
                badge_text = "⚡ Fallback"
                fm = painter.fontMetrics()
                badge_w = fm.horizontalAdvance(badge_text) + 14
                badge_h = fm.height() + 6
                badge_x = w - badge_w - 8
                badge_y = 6
                painter.setBrush(QBrush(QColor(245, 158, 11, 200)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 6, 6)
                painter.setPen(QColor(0, 0, 0, 230))
                painter.drawText(
                    QRect(badge_x, badge_y, badge_w, badge_h),
                    Qt.AlignmentFlag.AlignCenter,
                    badge_text,
                )

        elif self._is_scanning:
            # --- TARAMA MODU (henüz çeviri yok) ---
            alpha = int(12 + 8 * self._pulse_value)
            painter.setBrush(QBrush(QColor(139, 92, 246, alpha)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, w, h)

            status_font = QFont("Helvetica Neue", 11)
            status_font.setWeight(QFont.Weight.Medium)
            painter.setFont(status_font)
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(15, 20, self._current_status)

        else:
            # --- BEKLEME MODU ---
            painter.setBrush(QBrush(QColor(139, 92, 246, 8)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, w, h)

            text_color = QColor(148, 163, 184, 160)
            font = QFont("Helvetica Neue", 24)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(text_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Çevirmek için çift tıklayın\nTam ekran için 'F' tuşuna basın")

        # Clipping'i kaldır, kenarlık ve tutamaçları üzerine çiz
        painter.setClipping(False)

        # Kenarlık
        border_pen = QPen()
        border_pen.setWidth(2)
        if self._is_scanning:
            glow_alpha = int(120 + 100 * self._pulse_value)
            border_pen.setColor(QColor(139, 92, 246, glow_alpha))
        else:
            border_pen.setColor(QColor(139, 92, 246, 80))
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)

        # Köşe tutamaçları
        handle_size = 10
        hc = QColor(139, 92, 246, 200) if self._is_scanning else QColor(139, 92, 246, 120)
        painter.setBrush(QBrush(hc))
        painter.setPen(Qt.PenStyle.NoPen)
        for cx, cy in [(2, 2), (w - 12, 2), (2, h - 12), (w - 12, h - 12)]:
            painter.drawRoundedRect(cx, cy, handle_size, handle_size, 3, 3)

        painter.end()

    # --- API ---
    def set_translation_blocks(self, blocks: list, translated_lines: list, is_fallback: bool = False):
        """Çeviri metnini günceller ve pencereyi yeniden çizer.

        Args:
            blocks: Orijinal metin blokları.
            translated_lines: Çeviri satırları.
            is_fallback: True ise Google Translate fallback kullanıldı.
        """
        self._blocks = blocks
        self._translated_lines = translated_lines
        self._is_fallback = is_fallback
        self._scroll_x = 0.0
        self._scroll_y = 0.0
        self.update()

    def set_scroll_offset(self, dx: float, dy: float):
        """Kaydırma offsetini günceller."""
        if abs(self._scroll_x - dx) > 0.5 or abs(self._scroll_y - dy) > 0.5:
            self._scroll_x = dx
            self._scroll_y = dy
            self.update()

    def set_background_capture(self, qimage: QImage):
        """OCR sırasında yakalanan ekran görüntüsünü blur arka plan olarak ayarlar.

        Gaussian blur uygulanarak saklanır ve paintEvent'te arka plan olarak çizilir.

        Args:
            qimage: Yakalanan ekran bölgesinin QImage nesnesi.
        """
        try:
            # Performans için küçült, sonra bulanıklaştır
            # Küçük boyuta ölçekle → tekrar büyüt = doğal Gaussian blur etkisi
            small = qimage.scaled(
                max(1, qimage.width() // 8),
                max(1, qimage.height() // 8),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Tekrar orijinal boyuta büyüt (bulanık efekt)
            blurred = small.scaled(
                qimage.width(),
                qimage.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._blurred_bg = QPixmap.fromImage(blurred)
        except Exception:
            self._blurred_bg = None

    def set_status(self, status: str):
        """Durum metnini günceller ve pencereyi yeniden çizer."""
        labels = {
            "scanning": "⟳ Taranıyor...",
            "translating": "◉ Çevriliyor...",
            "ready": "✓ Hazır",
            "error": "✕ Hata",
            "idle": "○ Bekliyor",
        }
        self._current_status = labels.get(status, "○ Bekliyor")
        self.update()

    # --- Pulse animasyonu ---

    def _update_pulse(self):
        """Pulse animasyon değerini günceller."""
        step = 0.03
        self._pulse_value += step * self._pulse_direction
        if self._pulse_value >= 1.0:
            self._pulse_value = 1.0
            self._pulse_direction = -1
        elif self._pulse_value <= 0.0:
            self._pulse_value = 0.0
            self._pulse_direction = 1
        if self._is_scanning:
            self.update()

    # --- Mouse etkileşimi ---

    def mouseDoubleClickEvent(self, event):
        """Çift tıklama ile taramayı başlat/durdur."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_scanning()

    def toggle_scanning(self):
        """Taramayı başlatır veya durdurur. Tray ikon veya kısayol ile çağrılabilir."""
        self._is_scanning = not self._is_scanning
        self.scanning_toggled.emit(self._is_scanning)
        self.update()
        self._enable_fullscreen_overlay()

    def mousePressEvent(self, event):
        """Mouse basma — sürükleme veya boyutlandırma başlat."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._drag_edge = self._detect_edge(pos)
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_start_geo = self.geometry()

    def mouseMoveEvent(self, event):
        """Mouse hareketi — sürükleme veya boyutlandırma uygula."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            geo = QRect(self._drag_start_geo)

            if self._drag_edge == _Edge.NONE:
                # Pencereyi sürükle
                geo.moveTopLeft(geo.topLeft() + delta)
            else:
                # Boyutlandır
                geo = self._resize_geometry(geo, delta, self._drag_edge)

            self.setGeometry(geo)
            self.region_changed.emit(geo)
        else:
            # İmleç şeklini güncelle
            edge = self._detect_edge(event.position().toPoint())
            self._update_cursor(edge)

    def mouseReleaseEvent(self, event):
        """Mouse bırakma — sürükleme bitir."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_edge = _Edge.NONE
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.region_changed.emit(self.geometry())
            # Pencere taşındığında cache'i temizle (bir sonraki lookup doğru eşleşsin)
            self._cached_window_id = None

    def keyPressEvent(self, event):
        """Klavye kısayolları."""
        if event.key() == Qt.Key.Key_F:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen()
        super().keyPressEvent(event)

    def _toggle_fullscreen(self):
        """Tam ekran modunu açar/kapatır."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        if self._is_fullscreen:
            # Normal boyuta dön
            if not self._normal_geo.isEmpty():
                self.setGeometry(self._normal_geo)
            self._is_fullscreen = False
        else:
            # Tam ekran yap
            self._normal_geo = self.geometry()
            self.setGeometry(screen.geometry())
            self._is_fullscreen = True
        
        self.region_changed.emit(self.geometry())
        self._cached_window_id = None
        self.update()

    # --- Kenar algılama ---

    def _detect_edge(self, pos: QPoint) -> _Edge:
        """Mouse pozisyonuna göre hangi kenarda olduğunu belirler."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        t = _EDGE_THRESHOLD

        on_left = x < t
        on_right = x > w - t
        on_top = y < t
        on_bottom = y > h - t

        if on_top and on_left:
            return _Edge.TOP_LEFT
        if on_top and on_right:
            return _Edge.TOP_RIGHT
        if on_bottom and on_left:
            return _Edge.BOTTOM_LEFT
        if on_bottom and on_right:
            return _Edge.BOTTOM_RIGHT
        if on_top:
            return _Edge.TOP
        if on_bottom:
            return _Edge.BOTTOM
        if on_left:
            return _Edge.LEFT
        if on_right:
            return _Edge.RIGHT

        return _Edge.NONE

    def _update_cursor(self, edge: _Edge):
        """Kenar durumuna göre imleç şeklini günceller."""
        cursors = {
            _Edge.NONE: Qt.CursorShape.OpenHandCursor,
            _Edge.TOP: Qt.CursorShape.SizeVerCursor,
            _Edge.BOTTOM: Qt.CursorShape.SizeVerCursor,
            _Edge.LEFT: Qt.CursorShape.SizeHorCursor,
            _Edge.RIGHT: Qt.CursorShape.SizeHorCursor,
            _Edge.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            _Edge.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            _Edge.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            _Edge.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))

    def _resize_geometry(
        self, geo: QRect, delta: QPoint, edge: _Edge
    ) -> QRect:
        """Kenar yönüne göre pencere geometrisini hesaplar."""
        min_w = config.selection_min_width
        min_h = config.selection_min_height

        if edge in (_Edge.RIGHT, _Edge.TOP_RIGHT, _Edge.BOTTOM_RIGHT):
            new_w = max(min_w, geo.width() + delta.x())
            geo.setWidth(new_w)

        if edge in (_Edge.LEFT, _Edge.TOP_LEFT, _Edge.BOTTOM_LEFT):
            new_x = geo.x() + delta.x()
            new_w = geo.width() - delta.x()
            if new_w >= min_w:
                geo.setX(new_x)
                geo.setWidth(new_w)

        if edge in (_Edge.BOTTOM, _Edge.BOTTOM_LEFT, _Edge.BOTTOM_RIGHT):
            new_h = max(min_h, geo.height() + delta.y())
            geo.setHeight(new_h)

        if edge in (_Edge.TOP, _Edge.TOP_LEFT, _Edge.TOP_RIGHT):
            new_y = geo.y() + delta.y()
            new_h = geo.height() - delta.y()
            if new_h >= min_h:
                geo.setY(new_y)
                geo.setHeight(new_h)

        return geo

    # --- Public API ---

    def get_screen_region(self) -> tuple[int, int, int, int]:
        """Seçim penceresinin ekran koordinatlarını döndürür.

        Returns:
            (x, y, width, height) tuple — points cinsinden.
        """
        geo = self.geometry()
        return (geo.x(), geo.y(), geo.width(), geo.height())

    def _enable_fullscreen_overlay(self):
        """macOS'ta tam ekran oyunların/uygulamaların üzerinde görünmesini sağlar."""
        try:
            win_id = int(self.winId())
            ns_view = objc.objc_object(c_void_p=ctypes.c_void_p(win_id))
            ns_window = ns_view.window()
            if ns_window is not None:
                # 1 = NSWindowCollectionBehaviorCanJoinAllSpaces
                # 256 = NSWindowCollectionBehaviorFullScreenAuxiliary
                # İkisi birlikte: 257
                behavior = ns_window.collectionBehavior()
                
                # PySide6 varsayılan olarak "MoveToActiveSpace" (2) davranışını ekleyebilir.
                # "CanJoinAllSpaces" (1) ile bu davranış çakıştığı için hata verir.
                # Önce MoveToActiveSpace bayrağını temizliyoruz:
                behavior &= ~2
                
                # Sonra CanJoinAllSpaces (1) ve FullScreenAuxiliary (256) ekliyoruz
                ns_window.setCollectionBehavior_(behavior | 257)
                
                # Çok yüksek bir Z-index (Oyunların ve tam ekranların üzerinde)
                # 2000 = NSScreenSaverWindowLevel
                ns_window.setLevel_(2000)

                # Arka plana dokunabilmek için fare olaylarını yok say (Eğer taranıyorsa)
                ns_window.setIgnoresMouseEvents_(self._is_scanning)
        except Exception as e:
            print(f"[Miron] Tam ekran overlay aktif edilemedi: {e}")

    def _enforce_mac_overlay(self):
        """Qt'nin macOS native değerlerini ezmesini önlemek için periyodik kontrol."""
        self._enable_fullscreen_overlay()

    def is_scanning(self) -> bool:
        """Tarama durumunu döndürür."""
        return self._is_scanning

    def get_window_id(self) -> int | None:
        """Pencerenin native CGWindowID'sini döndürür (yakalamadan hariç tutmak için).

        QWidget.winId() macOS'ta NSView pointer'ı döndürür ve bu değer
        unsigned 32-bit int sınırını aşabilir. Bunun yerine Quartz
        pencere listesinden gerçek CGWindowID'yi buluruz.
        Pencere geometrisini karşılaştırarak doğru pencereyi tespit ederiz.

        Returns:
            CGWindowID (uint32) veya bulunamazsa None.
        """
        import os
        import Quartz

        try:
            # Önce cache'e bak
            if self._cached_window_id is not None:
                return self._cached_window_id

            # Mevcut prosesin tüm pencerelerini listele
            my_pid = os.getpid()
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionAll
                | Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
            )
            if window_list is None:
                return None

            # Widget'ın mevcut geometrisini al
            geo = self.geometry()

            for win_info in window_list:
                owner_pid = win_info.get(Quartz.kCGWindowOwnerPID, -1)
                if owner_pid != my_pid:
                    continue

                # Pencere sınırlarını karşılaştır
                bounds = win_info.get(Quartz.kCGWindowBounds, {})
                bx = int(bounds.get("X", -9999))
                by = int(bounds.get("Y", -9999))
                bw = int(bounds.get("Width", -1))
                bh = int(bounds.get("Height", -1))

                # Geometri eşleşmesi — SelectionWindow'u benzersiz tanımlar
                if (abs(bx - geo.x()) <= 2
                        and abs(by - geo.y()) <= 2
                        and abs(bw - geo.width()) <= 2
                        and abs(bh - geo.height()) <= 2):
                    wid = win_info.get(Quartz.kCGWindowNumber, 0)
                    self._cached_window_id = int(wid)
                    return self._cached_window_id

            # Geometri eşleşmezse PID'ye göre ilk pencereyi dön
            for win_info in window_list:
                owner_pid = win_info.get(Quartz.kCGWindowOwnerPID, -1)
                if owner_pid != my_pid:
                    continue
                wid = win_info.get(Quartz.kCGWindowNumber, 0)
                if wid:
                    self._cached_window_id = int(wid)
                    return self._cached_window_id

            return None
        except Exception:
            return None
