"""Ollama asenkron çeviri motoru — yabancı alfabe fallback destekli."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from difflib import SequenceMatcher

from PySide6.QtCore import QObject, Signal, QThread

from ollama import AsyncClient

from .config import config
from .ocr import TextBlock

# Anlamsız çeviri filtresi — sadece noktalama/boşluk olan çevirileri reddet
_MEANINGFUL_TEXT_PATTERN = re.compile(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]{2,}')

# --- Yabancı alfabe algılama ---

# Türkçe'de kullanılmayan yabancı script Unicode aralıkları
_FOREIGN_SCRIPT_RANGES = [
    (0x0400, 0x04FF),   # Kiril (Rusça, Ukraynaca, vb.)
    (0x0500, 0x052F),   # Kiril ek
    (0x0600, 0x06FF),   # Arapça
    (0x0750, 0x077F),   # Arapça ek
    (0x08A0, 0x08FF),   # Arapça genişletilmiş-A
    (0xFB50, 0xFDFF),   # Arapça sunum biçimleri-A
    (0xFE70, 0xFEFF),   # Arapça sunum biçimleri-B
    (0x4E00, 0x9FFF),   # CJK birleşik ideograflar (Çince)
    (0x3040, 0x309F),   # Hiragana (Japonca)
    (0x30A0, 0x30FF),   # Katakana (Japonca)
    (0xAC00, 0xD7AF),   # Hangul heceleri (Korece)
    (0x0E00, 0x0E7F),   # Tayca
    (0x10A0, 0x10FF),   # Gürcü
    (0x0530, 0x058F),   # Ermeni
    (0x0590, 0x05FF),   # İbranice
    (0x0900, 0x097F),   # Devanagari (Hintçe)
    (0x0980, 0x09FF),   # Bengal
    (0x0A80, 0x0AFF),   # Gujarati
]

# Ön-derlenmiş regex — performans için
_FOREIGN_CHAR_PATTERN = re.compile(
    "[" + "".join(
        f"\\u{start:04X}-\\u{end:04X}"
        for start, end in _FOREIGN_SCRIPT_RANGES
    ) + "]"
)

# Yabancı karakter eşiği: çeviri metnindeki karakterlerin
# bu oranı yabancıysa fallback tetiklenir
_FOREIGN_RATIO_THRESHOLD = 0.05  # %5


def _contains_foreign_script(text: str) -> bool:
    """Metnin Türkçe dışı yabancı alfabe karakterleri içerip içermediğini kontrol eder.

    Latin, Türkçe özel karakterler (çğıöşü), rakamlar ve
    noktalama işaretleri normal kabul edilir. Kiril, Arap, CJK gibi
    alfabeler yabancı sayılır.

    Args:
        text: Kontrol edilecek metin.

    Returns:
        True eğer yabancı alfabe karakterleri anlamlı oranda varsa.
    """
    if not text:
        return False

    # Sadece harf karakterlerini say (boşluk, rakam, noktalama hariç)
    letters_only = [ch for ch in text if ch.isalpha()]
    if not letters_only:
        return False

    foreign_count = len(_FOREIGN_CHAR_PATTERN.findall(text))
    ratio = foreign_count / len(letters_only)

    if foreign_count > 0:
        logging.info(
            f"Yabancı karakter algılandı: {foreign_count}/{len(letters_only)} "
            f"({ratio:.1%}) — eşik: {_FOREIGN_RATIO_THRESHOLD:.0%}"
        )

    return ratio >= _FOREIGN_RATIO_THRESHOLD


def _is_translation_valid(text: str) -> bool:
    """Çeviri sonucunun anlamlı olup olmadığını kontrol eder.

    Sadece noktalama işaretleri (. ; / - vb.), boşluk veya
    çok kısa anlamsız çıktılar reddedilir.

    Args:
        text: Kontrol edilecek çeviri metni.

    Returns:
        True eğer çeviri anlamlı ise.
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()

    # Çok kısa (1-2 karakter) ve harf içermeyen
    if len(stripped) <= 2 and not any(c.isalpha() for c in stripped):
        logging.warning(f"Çeviri çok kısa ve anlamsız: '{stripped}'")
        return False

    # En az 2 ardışık harf içermeli
    if not _MEANINGFUL_TEXT_PATTERN.search(stripped):
        logging.warning(f"Çeviri anlamlı metin içermiyor: '{stripped}'")
        return False

    return True


async def _fallback_translate(text: str) -> str:
    """Google Translate (deep-translator) ile AI'sız fallback çeviri yapar.

    Bu fonksiyon, Ollama çevirisi yabancı alfabe ürettiğinde
    devreye girer.

    Args:
        text: Orijinal (çevrilmemiş) metin.

    Returns:
        Türkçeye çevrilmiş metin.

    Raises:
        Exception: Google Translate erişilemezse.
    """
    from deep_translator import GoogleTranslator

    loop = asyncio.get_event_loop()

    def _do_google_translate():
        translator = GoogleTranslator(source="auto", target="tr")
        # deep-translator 5000 karakter limiti var, uzun metinleri böl
        if len(text) > 4500:
            chunks = [text[i:i + 4500] for i in range(0, len(text), 4500)]
            results = [translator.translate(chunk) for chunk in chunks]
            return " ".join(results)
        return translator.translate(text)

    # Senkron Google Translate çağrısını thread pool'da çalıştır
    result = await loop.run_in_executor(None, _do_google_translate)
    return result


class TranslationWorker(QObject):
    """Ayrı thread'de çalışan asenkron çeviri worker'ı.

    Qt Signal'ları ile ana thread'e sonuç iletir.
    Ollama çevirisi yabancı alfabe içerirse Google Translate
    fallback'i otomatik olarak devreye girer.
    """

    # Sinyaller
    translation_ready = Signal(list, list, bool)  # (blocks, translated_lines, is_fallback)
    translation_error = Signal(str)              # hata_mesajı
    status_changed = Signal(str)                 # durum (scanning, translating, ready, error)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_text: str = ""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._debounce_task: asyncio.Task | None = None
        self._running: bool = False

    def start_loop(self):
        """Async event loop'u başlatır (QThread.run içinden çağrılır)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._running = True
        self._loop.run_forever()

    def stop_loop(self):
        """Async event loop'u durdurur."""
        self._running = False
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def request_translation(self, blocks: list[TextBlock]):
        """Çeviri isteği gönderir (thread-safe).

        Ana thread'den çağrılır. Debounce mekanizması ile
        hızlı ardışık istekleri birleştirir.

        Args:
            blocks: Çevrilecek metin blokları.
        """
        if not blocks:
            return
            
        text = "\n".join(b.text for b in blocks)

        # Metin değişim kontrolü
        if self._is_text_similar(text, self._last_text):
            return

        self._last_text = text

        if self._loop is not None and self._loop.is_running():
            logging.info(f"Çeviri isteği alındı (uzunluk: {len(text)})")
            asyncio.run_coroutine_threadsafe(
                self._debounced_translate(blocks, text), self._loop
            )

    def _is_text_similar(self, text1: str, text2: str) -> bool:
        """İki metnin benzerlik oranını kontrol eder.

        Args:
            text1: İlk metin.
            text2: İkinci metin.

        Returns:
            True eğer benzerlik eşiğinin üzerindeyse.
        """
        if not text1 or not text2:
            return False

        # Normalize et
        t1 = " ".join(text1.split()).lower()
        t2 = " ".join(text2.split()).lower()

        ratio = SequenceMatcher(None, t1, t2).ratio()
        return ratio >= config.min_text_similarity

    async def _debounced_translate(self, blocks: list[TextBlock], text: str):
        """Debounce ile çeviri yapar.

        500ms bekler, bu süre içinde yeni istek gelirse
        önceki iptal edilir ve yenisi başlatılır.

        Args:
            blocks: Metin blokları.
            text: Birleştirilmiş metin.
        """
        # Önceki debounce task'ını iptal et
        if self._debounce_task is not None and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass

        self._debounce_task = asyncio.ensure_future(
            self._translate_after_delay(blocks, text)
        )

    async def _translate_after_delay(self, blocks: list[TextBlock], text: str):
        """Belirli bir gecikme sonrası çeviri yapar."""
        try:
            # Debounce bekleme
            await asyncio.sleep(config.translation_debounce_ms / 1000.0)
        except asyncio.CancelledError:
            return

        # Çeviri yap
        await self._do_translate(blocks, text)

    async def _do_translate(self, blocks: list[TextBlock], text: str):
        """Ollama veya Google ile çeviri gerçekleştirir."""
        self.status_changed.emit("translating")

        # --- Hızlı Çeviri Modu (Sadece Google Translate) ---
        if config.fast_translation:
            logging.info("Hızlı Çeviri (Google) devrede, Ollama atlanıyor...")
            try:
                result = await _fallback_translate(text)
                if result and _is_translation_valid(result):
                    lines = [line.strip() for line in result.strip().split('\n')]
                    self.translation_ready.emit(blocks, lines, True)
                    self.status_changed.emit("ready")
                    logging.info("✓ Hızlı çeviri başarılı.")
                    return
                else:
                    logging.warning("Hızlı çeviri sonucu anlamsız, boş dönülüyor.")
                    return
            except Exception as e:
                logging.error(f"Hızlı çeviri hatası: {e}")
                self.translation_error.emit(str(e))
                self.status_changed.emit("error")
                return

        # --- Ollama Çeviri Modu ---
        logging.info("Ollama API çağrısı yapılıyor...")

        try:
            client = AsyncClient(host=config.ollama_host)

            messages = [
                {
                    "role": "system",
                    "content": config.system_prompt,
                },
                {
                    "role": "user",
                    "content": text,
                },
            ]

            response = await client.chat(
                model=config.ollama_model,
                messages=messages,
                options={
                    "num_predict": 1024,
                    "temperature": 0,
                }
            )

            translated = response["message"]["content"].strip()
            logging.info(f"Ollama çevirisi alındı: {translated[:60]}...")
            used_fallback = False

            # --- Anlamsız çeviri kontrolü ---
            if not _is_translation_valid(translated):
                logging.warning(f"⚠ Ollama anlamsız çeviri döndü: '{translated}' — Fallback deneniyor...")
                try:
                    fallback_result = await _fallback_translate(text)
                    if fallback_result and _is_translation_valid(fallback_result):
                        translated = fallback_result.strip()
                        used_fallback = True
                        logging.info(f"✓ Fallback çeviri başarılı: {translated[:60]}...")
                    else:
                        logging.warning("Fallback da anlamsız döndü, atlanıyor.")
                        return  # Hiçbir şey gösterme
                except Exception as fb_err:
                    logging.error(f"Fallback çeviri hatası: {fb_err}")
                    return  # Hiçbir şey gösterme

            # --- Yabancı alfabe kontrolü ---
            elif _contains_foreign_script(translated):
                logging.warning(
                    "⚠ Ollama çevirisinde yabancı alfabe tespit edildi! "
                    "Google Translate fallback devreye giriyor..."
                )
                try:
                    fallback_result = await _fallback_translate(text)
                    if fallback_result and _is_translation_valid(fallback_result):
                        translated = fallback_result.strip()
                        used_fallback = True
                        logging.info(f"✓ Fallback çeviri başarılı: {translated[:60]}...")
                    else:
                        logging.warning("Fallback boş döndü, Ollama sonucu kullanılıyor.")
                except Exception as fb_err:
                    logging.error(f"Fallback çeviri hatası: {fb_err}")
                    # Fallback da başarısız olursa Ollama sonucundan yabancı
                    # karakterleri temizleyip kalan kısmı göster
                    cleaned = _FOREIGN_CHAR_PATTERN.sub("", translated).strip()
                    if cleaned and _is_translation_valid(cleaned):
                        translated = cleaned
                        logging.info("Yabancı karakterler temizlendi, kalan metin kullanılıyor.")

            translated_lines = [line.strip() for line in translated.split('\n')]
            
            # Eğer satır sayıları uyuşmazsa, fallback (veya genel çeviriyi tek satıra koy) deneyebiliriz,
            # ama şimdilik doğrudan UI'a verelim.
            self.translation_ready.emit(blocks, translated_lines, used_fallback)
            self.status_changed.emit("ready")

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Çeviri hatası: {error_msg}")

            # Ollama tamamen başarısız olursa da fallback dene
            try:
                logging.info("Ollama başarısız — fallback deneniyor...")
                fallback_result = await _fallback_translate(text)
                if fallback_result and _is_translation_valid(fallback_result):
                    fb_lines = [line.strip() for line in fallback_result.strip().split('\n')]
                    self.translation_ready.emit(blocks, fb_lines, True)
                    self.status_changed.emit("ready")
                    logging.info("✓ Fallback ile kurtarıldı.")
                    return
            except Exception as fb_err:
                logging.error(f"Fallback de başarısız: {fb_err}")

            self.translation_error.emit(error_msg)
            self.status_changed.emit("error")


class TranslationEngine(QObject):
    """Çeviri motorunu yöneten ana sınıf.

    Worker'ı ayrı bir QThread'de çalıştırır.
    """

    # Worker sinyallerini ilet
    translation_ready = Signal(list, list, bool)
    translation_error = Signal(str)
    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = TranslationWorker()

        # Worker'ı thread'e taşı
        self._worker.moveToThread(self._thread)

        # Thread başladığında worker loop'u başlat
        self._thread.started.connect(self._worker.start_loop)

        # Sinyalleri bağla
        self._worker.translation_ready.connect(self.translation_ready.emit)
        self._worker.translation_error.connect(self.translation_error.emit)
        self._worker.status_changed.connect(self.status_changed.emit)

    def start(self):
        """Çeviri motorunu başlatır."""
        self._thread.start()

    def stop(self):
        """Çeviri motorunu durdurur."""
        self._worker.stop_loop()
        self._thread.quit()
        self._thread.wait(3000)

    def translate(self, blocks: list[TextBlock]):
        """Çeviri isteği gönderir.

        Args:
            blocks: Çevrilecek metin blokları.
        """
        self._worker.request_translation(blocks)
