"""Miron uygulama yapılandırması."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Ana uygulama yapılandırması."""

    # --- Ollama Ayarları ---
    ollama_model: str = "translategemma"
    ollama_host: str = "http://localhost:11434"
    system_prompt: str = (
        "Translate the following text into Turkish line by line. "
        "You MUST preserve the exact number of lines and all newlines. "
        "Output ONLY the Turkish translation. Do not include original text, notes, or any other language."
    )

    # --- OCR Ayarları ---
    ocr_interval_ms: int = 2000  # OCR tarama aralığı (milisaniye)
    ocr_languages: list[str] = field(
        default_factory=lambda: ["en", "tr", "de", "fr"]
    )
    ocr_recognition_level: int = 0  # 0 = accurate, 1 = fast
    min_text_similarity: float = 0.90  # Metin değişim eşiği

    # --- UI Ayarları ---
    selection_min_width: int = 150
    selection_min_height: int = 80
    selection_default_width: int = 500
    selection_default_height: int = 300
    translation_debounce_ms: int = 500  # Çeviri debounce süresi
    subtitle_clear_ms: int = 7000       # Altyazının kaybolma süresi (7 saniye)

    # --- Oyun Modu Ayarları ---
    game_mode: bool = False             # Tam ekranda kaydırma takibini devre dışı bırakır
    fast_translation: bool = False      # Sadece Google Translate (hızlı) veya Ollama (kaliteli)

    # --- Renk Paleti ---
    accent_color: str = "#8B5CF6"       # Mor (ana aksan)
    accent_secondary: str = "#6366F1"   # İndigo
    accent_glow: str = "#A78BFA"        # Açık mor (glow)
    bg_dark: str = "#0F0F14"            # Koyu arka plan
    bg_panel: str = "rgba(15, 15, 20, 0.75)"  # Panel arka plan
    text_primary: str = "#F8FAFC"       # Ana metin
    text_secondary: str = "#94A3B8"     # İkincil metin
    text_muted: str = "#64748B"         # Soluk metin
    status_scanning: str = "#3B82F6"    # Mavi (taranıyor)
    status_translating: str = "#F59E0B" # Turuncu (çevriliyor)
    status_ready: str = "#10B981"       # Yeşil (hazır)
    status_error: str = "#EF4444"       # Kırmızı (hata)
    border_color: str = "rgba(139, 92, 246, 0.4)"  # Kenarlık


# Singleton config instance
config = AppConfig()
