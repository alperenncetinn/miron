"""Ollama asenkron çeviri motoru."""

from __future__ import annotations

import asyncio
import logging
from difflib import SequenceMatcher

from PySide6.QtCore import QObject, Signal, QThread

from ollama import AsyncClient

from .config import config


class TranslationWorker(QObject):
    """Ayrı thread'de çalışan asenkron çeviri worker'ı.

    Qt Signal'ları ile ana thread'e sonuç iletir.
    """

    # Sinyaller
    translation_ready = Signal(str, str)  # (orijinal_metin, çeviri)
    translation_error = Signal(str)       # hata_mesajı
    status_changed = Signal(str)          # durum (scanning, translating, ready, error)

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

    def request_translation(self, text: str):
        """Çeviri isteği gönderir (thread-safe).

        Ana thread'den çağrılır. Debounce mekanizması ile
        hızlı ardışık istekleri birleştirir.

        Args:
            text: Çevrilecek metin.
        """
        if not text or not text.strip():
            return

        # Metin değişim kontrolü
        if self._is_text_similar(text, self._last_text):
            return

        self._last_text = text

        if self._loop is not None and self._loop.is_running():
            logging.info(f"Çeviri isteği alındı (uzunluk: {len(text)})")
            asyncio.run_coroutine_threadsafe(
                self._debounced_translate(text), self._loop
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

    async def _debounced_translate(self, text: str):
        """Debounce ile çeviri yapar.

        500ms bekler, bu süre içinde yeni istek gelirse
        önceki iptal edilir ve yenisi başlatılır.

        Args:
            text: Çevrilecek metin.
        """
        # Önceki debounce task'ını iptal et
        if self._debounce_task is not None and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass

        self._debounce_task = asyncio.ensure_future(
            self._translate_after_delay(text)
        )

    async def _translate_after_delay(self, text: str):
        """Belirli bir gecikme sonrası çeviri yapar.

        Args:
            text: Çevrilecek metin.
        """
        try:
            # Debounce bekleme
            await asyncio.sleep(config.translation_debounce_ms / 1000.0)
        except asyncio.CancelledError:
            return

        # Çeviri yap
        await self._do_translate(text)

    async def _do_translate(self, text: str):
        """Ollama ile çeviri gerçekleştirir.

        Args:
            text: Çevrilecek metin.
        """
        self.status_changed.emit("translating")
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
                }
            )

            translated = response["message"]["content"].strip()
            logging.info("Çeviri başarılı.")

            self.translation_ready.emit(text, translated)
            self.status_changed.emit("ready")

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Çeviri hatası: {error_msg}")
            self.translation_error.emit(error_msg)
            self.status_changed.emit("error")


class TranslationEngine(QObject):
    """Çeviri motorunu yöneten ana sınıf.

    Worker'ı ayrı bir QThread'de çalıştırır.
    """

    # Worker sinyallerini ilet
    translation_ready = Signal(str, str)
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

    def translate(self, text: str):
        """Çeviri isteği gönderir.

        Args:
            text: Çevrilecek metin.
        """
        self._worker.request_translation(text)
