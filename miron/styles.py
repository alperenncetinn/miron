"""QSS stil tanımları — Apple estetiğine uygun modern tasarım."""

from .config import config


def get_selection_window_style() -> str:
    """Seçim penceresi QSS stilini döndürür."""
    return f"""
        QWidget#SelectionWindow {{
            background: transparent;
        }}
    """


def get_translation_panel_style() -> str:
    """Çeviri paneli QSS stilini döndürür."""
    return f"""
        QWidget#TranslationPanel {{
            background: transparent;
            border: none;
        }}

        QWidget#PanelInner {{
            background: {config.bg_panel};
            border: 1px solid {config.border_color};
            border-radius: 14px;
        }}

        /* Başlık çubuğu */
        QWidget#TitleBar {{
            background: transparent;
            border: none;
            min-height: 36px;
            max-height: 36px;
        }}

        QLabel#AppTitle {{
            color: {config.accent_glow};
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 1.5px;
            padding-left: 14px;
        }}

        QPushButton#CloseButton {{
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.25);
            border-radius: 7px;
            color: #EF4444;
            font-size: 13px;
            font-weight: bold;
            min-width: 26px;
            max-width: 26px;
            min-height: 26px;
            max-height: 26px;
            margin-right: 10px;
        }}

        QPushButton#CloseButton:hover {{
            background: rgba(239, 68, 68, 0.35);
            border-color: rgba(239, 68, 68, 0.5);
        }}

        /* Durum göstergesi */
        QLabel#StatusLabel {{
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 11px;
            font-weight: 500;
            padding: 3px 10px;
            border-radius: 8px;
            margin-right: 8px;
        }}

        /* Orijinal metin */
        QLabel#OriginalTextLabel {{
            color: {config.text_muted};
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 11px;
            font-weight: 400;
            padding: 4px 16px 0px 16px;
        }}

        /* Orijinal metin içeriği */
        QTextEdit#OriginalText {{
            color: {config.text_secondary};
            background: transparent;
            border: none;
            font-family: "Menlo", "SF Mono", monospace;
            font-size: 12px;
            padding: 4px 14px;
            selection-background-color: rgba(139, 92, 246, 0.3);
        }}

        /* Ayırıcı çizgi */
        QFrame#Separator {{
            background: {config.border_color};
            border: none;
            max-height: 1px;
            min-height: 1px;
            margin: 2px 16px;
        }}

        /* Çeviri başlığı */
        QLabel#TranslationLabel {{
            color: {config.accent_glow};
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 16px 0px 16px;
        }}

        /* Çeviri metni */
        QTextEdit#TranslationText {{
            color: {config.text_primary};
            background: transparent;
            border: none;
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 14px;
            font-weight: 400;
            line-height: 1.5;
            padding: 4px 14px 10px 14px;
            selection-background-color: rgba(139, 92, 246, 0.3);
        }}

        /* Scroll bar */
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 4px 2px;
        }}

        QScrollBar::handle:vertical {{
            background: rgba(139, 92, 246, 0.35);
            border-radius: 3px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: rgba(139, 92, 246, 0.55);
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
            height: 0px;
        }}
    """


def get_control_bar_style() -> str:
    """Kontrol çubuğu QSS stilini döndürür."""
    return f"""
        QPushButton#ControlButton {{
            background: {config.bg_panel};
            border: 1px solid {config.border_color};
            border-radius: 10px;
            color: {config.text_primary};
            font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
            font-size: 12px;
            font-weight: 500;
            padding: 6px 14px;
            min-height: 28px;
        }}

        QPushButton#ControlButton:hover {{
            background: rgba(139, 92, 246, 0.2);
            border-color: {config.accent_color};
        }}

        QPushButton#ControlButton:checked {{
            background: rgba(139, 92, 246, 0.3);
            border-color: {config.accent_color};
            color: {config.accent_glow};
        }}
    """


def status_color(status: str) -> str:
    """Durum string'ine göre renk döndürür."""
    colors = {
        "scanning": config.status_scanning,
        "translating": config.status_translating,
        "ready": config.status_ready,
        "error": config.status_error,
        "idle": config.text_muted,
    }
    return colors.get(status, config.text_muted)


def status_label_style(status: str) -> str:
    """Durum label'ı için dinamik QSS stili döndürür."""
    color = status_color(status)
    return f"""
        color: {color};
        background: rgba({_hex_to_rgb(color)}, 0.12);
        border: 1px solid rgba({_hex_to_rgb(color)}, 0.25);
    """


def _hex_to_rgb(hex_color: str) -> str:
    """Hex renk kodunu 'r, g, b' formatına çevirir."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"{r}, {g}, {b}"
    return "255, 255, 255"
