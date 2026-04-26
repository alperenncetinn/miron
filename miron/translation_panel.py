"""Glassmorphism çeviri sonuç paneli."""

from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    QRect,
    Property,
)
from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QFrame,
    QPushButton,
    QGraphicsOpacityEffect,
    QSizePolicy,
)

from .config import config
from .styles import (
    get_translation_panel_style,
    status_label_style,
)
from .blur_effect import apply_blur_effect


class TranslationPanel(QWidget):
    """Çeviri sonuçlarını gösteren glassmorphism panel.

    Seçim penceresinin altında konumlanır ve otomatik takip eder.

    Features:
        - macOS native blur efekti (NSVisualEffectView)
        - Fade-in animasyonu ile metin güncelleme
        - Orijinal metin + çeviri metni ayrımı
        - Dinamik durum göstergesi
        - Otomatik yükseklik ayarlama
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_status = "idle"
        self._last_selection_rect = QRect()

        # Pencere ayarları
        self.setObjectName("TranslationPanel")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(300)
        self.setMaximumHeight(500)

        self.setStyleSheet(get_translation_panel_style())

        # Ana layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(6, 6, 6, 6)
        self._main_layout.setSpacing(0)

        # İç panel (border-radius arka planı için)
        self._inner = QWidget()
        self._inner.setObjectName("PanelInner")
        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        # --- Başlık çubuğu ---
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 6, 0, 4)
        title_layout.setSpacing(6)

        # Uygulama başlığı
        app_title = QLabel("MIRON")
        app_title.setObjectName("AppTitle")
        title_layout.addWidget(app_title)

        title_layout.addStretch()

        # Durum göstergesi
        self._status_label = QLabel("Hazır")
        self._status_label.setObjectName("StatusLabel")
        self._update_status_style("idle")
        title_layout.addWidget(self._status_label)

        # Kapatma butonu
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseButton")
        close_btn.setToolTip("Paneli Kapat")
        close_btn.clicked.connect(self.hide)
        title_layout.addWidget(close_btn)

        inner_layout.addWidget(title_bar)

        # --- Orijinal metin bölümü ---
        orig_label = QLabel("KAYNAK METİN")
        orig_label.setObjectName("OriginalTextLabel")
        inner_layout.addWidget(orig_label)

        self._original_text = QTextEdit()
        self._original_text.setObjectName("OriginalText")
        self._original_text.setReadOnly(True)
        self._original_text.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._original_text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._original_text.setMaximumHeight(80)
        self._original_text.setPlaceholderText("Metin bekleniyor...")
        inner_layout.addWidget(self._original_text)

        # Ayırıcı çizgi
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        inner_layout.addWidget(separator)

        # --- Çeviri metni bölümü ---
        trans_label = QLabel("TÜRKÇESİ")
        trans_label.setObjectName("TranslationLabel")
        inner_layout.addWidget(trans_label)

        self._translation_text = QTextEdit()
        self._translation_text.setObjectName("TranslationText")
        self._translation_text.setReadOnly(True)
        self._translation_text.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._translation_text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._translation_text.setMinimumHeight(60)
        self._translation_text.setPlaceholderText("Çeviri burada görünecek...")
        inner_layout.addWidget(self._translation_text)

        self._main_layout.addWidget(self._inner)

        # Opacity efekti — fade animasyonu için
        self._opacity_effect = QGraphicsOpacityEffect(self._translation_text)
        self._opacity_effect.setOpacity(1.0)
        self._translation_text.setGraphicsEffect(self._opacity_effect)

        # Blur efekti uygula (show sonrası)
        QTimer.singleShot(100, self._apply_native_blur)

    # --- Public API ---

    def update_original_text(self, text: str):
        """Orijinal metin alanını günceller.

        Args:
            text: OCR ile algılanan orijinal metin.
        """
        self._original_text.setPlainText(text)
        self._adjust_height()

    def update_translation(self, original: str, translation: str):
        """Çeviri sonucunu günceller ve fade-in animasyonu oynatır.

        Args:
            original: Orijinal metin.
            translation: Çevrilmiş metin.
        """
    def update_translation(self, original: str, translation: str):
        """Çeviri sonucunu günceller.

        Args:
            original: Orijinal metin.
            translation: Çevrilmiş metin.
        """
        # Orijinal metni de güncelle
        self._original_text.setPlainText(original)
        self._set_translation_and_fade_in(translation)

    def update_status(self, status: str):
        """Durum göstergesini günceller.

        Args:
            status: "scanning" | "translating" | "ready" | "error" | "idle"
        """
        self._current_status = status
        labels = {
            "scanning": "⟳ Taranıyor",
            "translating": "◉ Çevriliyor",
            "ready": "✓ Hazır",
            "error": "✕ Hata",
            "idle": "○ Bekliyor",
        }
        self._status_label.setText(labels.get(status, "○ Bekliyor"))
        self._update_status_style(status)

    def position_below(self, selection_rect: QRect):
        """Paneli seçim penceresinin altına konumlar.

        Args:
            selection_rect: Seçim penceresinin geometrisi.
        """
        from PySide6.QtWidgets import QApplication

        if not selection_rect.isValid() or selection_rect.width() == 0:
            return

        self._last_selection_rect = selection_rect

        # Yüksekliği mevcut içeriğe göre kesinleştir
        self._adjust_height(reposition=False)

        x = selection_rect.x()
        y = selection_rect.y() + selection_rect.height() + 8
        width = max(selection_rect.width(), self.minimumWidth())
        height = self.height()

        # Ekran sınırlarını kontrol et
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            if y + height > screen_geo.bottom():
                # Ekrana sığmıyorsa, seçim penceresinin üstüne al
                y = selection_rect.y() - height - 8
                
                # Eğer üstteyken de taşıyorsa (ekran çok küçükse) ekrana sığdır
                if y < screen_geo.top():
                    y = screen_geo.top() + 8

        self.setGeometry(x, y, width, height)

    # --- Private ---

    def _set_translation_and_fade_in(self, translation: str):
        """Çeviri metnini ayarlar."""
        self._translation_text.setPlainText(translation)
        self._adjust_height()

    def _adjust_height(self, reposition: bool = True):
        """Panel yüksekliğini içerik uzunluğuna göre ayarlar."""
        # Orijinal metin yüksekliği
        orig_doc = self._original_text.document()
        orig_height = min(80, int(orig_doc.size().height()) + 10)
        self._original_text.setFixedHeight(max(30, orig_height))

        # Çeviri metni yüksekliği
        trans_doc = self._translation_text.document()
        trans_height = min(250, int(trans_doc.size().height()) + 10)
        self._translation_text.setFixedHeight(max(40, trans_height))

        # Toplam yükseklik: başlık(36) + label(20) + orijinal + separator(5) + label(20) + çeviri + padding
        total = 36 + 20 + orig_height + 5 + 20 + trans_height + 30
        self.setFixedHeight(min(500, total + 12))  # +12 dış margin

        if reposition and self._last_selection_rect.isValid():
            self.position_below(self._last_selection_rect)

    def _update_status_style(self, status: str):
        """Durum label'ının stilini günceller."""
        self._status_label.setStyleSheet(
            f"QLabel#StatusLabel {{ {status_label_style(status)} }}"
        )

    def _apply_native_blur(self):
        """macOS native blur efektini uygular."""
        apply_blur_effect(self)

    def paintEvent(self, event):
        """Fallback arka plan çizimi (blur desteklenmezse)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dış gölge efekti
        shadow_color = QColor(0, 0, 0, 30)
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            4, 4, self.width() - 4, self.height() - 4, 16, 16
        )

        painter.end()
        super().paintEvent(event)

    def showEvent(self, event):
        """Panel gösterildiğinde blur efektini yeniden uygula."""
        super().showEvent(event)
        QTimer.singleShot(50, self._apply_native_blur)
