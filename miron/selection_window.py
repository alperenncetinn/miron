"""Sürüklenebilir ve boyutlandırılabilir seçim penceresi."""

from __future__ import annotations

from enum import IntEnum, auto

from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
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
        self._translation_text = ""

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
        """Seçim çerçevesini çizer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = 12

        # Yarı-şeffaf arka plan dolgusu
        if self._is_scanning:
            # Taranırken hafif mavi-mor glow
            alpha = int(12 + 8 * self._pulse_value)
            bg_color = QColor(139, 92, 246, alpha)
        else:
            bg_color = QColor(139, 92, 246, 8)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # Kenarlık — gradient efekti
        border_pen = QPen()
        border_pen.setWidth(2)

        if self._is_scanning:
            # Taranırken animasyonlu parlak kenarlık
            glow_alpha = int(120 + 100 * self._pulse_value)
            border_pen.setColor(QColor(139, 92, 246, glow_alpha))
        else:
            border_pen.setColor(QColor(139, 92, 246, 80))

        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)

        # Köşe tutamaçları
        handle_size = 10
        handle_color = QColor(139, 92, 246, 200) if self._is_scanning else QColor(139, 92, 246, 120)
        painter.setBrush(QBrush(handle_color))
        painter.setPen(Qt.PenStyle.NoPen)

        corners = [
            (2, 2),                   # Sol üst
            (w - handle_size - 2, 2), # Sağ üst
            (2, h - handle_size - 2), # Sol alt
            (w - handle_size - 2, h - handle_size - 2),  # Sağ alt
        ]
        for cx, cy in corners:
            painter.drawRoundedRect(cx, cy, handle_size, handle_size, 3, 3)

        # Merkez bilgi metni veya Çeviri Metni
        font = QFont("Helvetica Neue", 12)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        if self._is_scanning:
            if self._translation_text:
                # Tüm pencereyi (seçim alanını) yarı şeffaf siyahla kapla
                painter.setBrush(QBrush(QColor(0, 0, 0, 190)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(0, 0, w, h, radius, radius)
                
                # Metni çiz (tam ortaya hizala)
                text_flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
                text_rect = QRect(20, 20, w - 40, h - 40)
                
                painter.setPen(QColor(255, 255, 255, 255))
                painter.drawText(text_rect, text_flags, self._translation_text)
                
            # Durum metni çizimi (sol üste ufak)
            status_font = QFont("Helvetica Neue", 10)
            status_font.setWeight(QFont.Weight.Medium)
            painter.setFont(status_font)
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(15, 20, self._current_status)
        else:
            text_color = QColor(148, 163, 184, 160)
            painter.setPen(text_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Çevirmek için çift tıklayın")

        painter.end()

    # --- API ---
    def set_translation(self, text: str):
        """Çeviri metnini günceller ve pencereyi yeniden çizer."""
        self._translation_text = text
        self.update()

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
            self._is_scanning = not self._is_scanning
            self.scanning_toggled.emit(self._is_scanning)
            self.update()

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
