"""Apple Vision Framework OCR modülü."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import Vision
import Quartz
from Foundation import NSArray


@dataclass
class TextBlock:
    """Algılanan metin bloğu ve pozisyon bilgisi."""

    text: str
    x: float       # Sol üst köşe X (piksel)
    y: float       # Sol üst köşe Y (piksel)
    width: float   # Genişlik (piksel)
    height: float  # Yükseklik (piksel)
    confidence: float  # Güven skoru (0.0 - 1.0)


def recognize_text(
    cg_image,
    languages: list[str] | None = None,
    recognition_level: int = 0,
) -> list[TextBlock]:
    """CGImage üzerinde OCR yapar ve metin blokları döndürür.

    Apple Vision Framework'ün VNRecognizeTextRequest'ini kullanır.

    Args:
        cg_image: Quartz CGImage nesnesi.
        languages: Tanınacak dillerin listesi (örn. ["en", "tr"]).
        recognition_level: 0 = accurate (yüksek doğruluk), 1 = fast (hızlı).

    Returns:
        Algılanan TextBlock nesnelerinin listesi.
    """
    if cg_image is None:
        return []

    if languages is None:
        languages = ["en", "tr", "de", "fr"]

    # Görüntünün piksel boyutlarını al
    img_width = Quartz.CGImageGetWidth(cg_image)
    img_height = Quartz.CGImageGetHeight(cg_image)

    if img_width == 0 or img_height == 0:
        return []

    results: list[TextBlock] = []

    # Callback handler — sonuçları işler
    def handler(request, error):
        if error is not None:
            print(f"[OCR] Hata: {error}")
            return

        observations = request.results()
        if observations is None:
            return

        for observation in observations:
            # En iyi aday metni al
            candidates = observation.topCandidates_(1)
            if candidates is None or len(candidates) == 0:
                continue

            top_candidate = candidates[0]
            text = top_candidate.string()
            confidence = top_candidate.confidence()

            # Normalized bounding box'ı piksel koordinatlarına dönüştür
            # Vision: (0,0) = sol alt, (1,1) = sağ üst
            norm_rect = observation.boundingBox()

            # VNImageRectForNormalizedRect ile piksel koordinatlarına çevir
            pixel_rect = Vision.VNImageRectForNormalizedRect(
                norm_rect, img_width, img_height
            )

            px = pixel_rect.origin.x
            py = pixel_rect.origin.y
            pw = pixel_rect.size.width
            ph = pixel_rect.size.height

            # Vision'ın koordinat sistemi sol-alttan başlar (Cocoa convention)
            # Üst-sol referansa çevir
            py_top_left = img_height - py - ph

            results.append(
                TextBlock(
                    text=text,
                    x=px,
                    y=py_top_left,
                    width=pw,
                    height=ph,
                    confidence=confidence,
                )
            )

    # VNRecognizeTextRequest oluştur
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)

    # Tanıma seviyesi
    if recognition_level == 0:
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    else:
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)

    # Dil desteği
    request.setRecognitionLanguages_(NSArray.arrayWithArray_(languages))

    # Otomatik dil düzeltme
    request.setUsesLanguageCorrection_(True)

    # VNImageRequestHandler oluştur ve isteği çalıştır
    handler_obj = (
        Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_image, {}
        )
    )

    success, error = handler_obj.performRequests_error_([request], None)
    if not success and error:
        print(f"[OCR] İstek başarısız: {error}")

    # Sonuçları Y pozisyonuna göre sırala (yukarıdan aşağıya)
    results.sort(key=lambda b: b.y)

    return results


def blocks_to_text(blocks: list[TextBlock]) -> str:
    """TextBlock listesini birleştirilmiş metin dizesine çevirir.

    Args:
        blocks: TextBlock nesnelerinin listesi.

    Returns:
        Satır satır birleştirilmiş metin.
    """
    return "\n".join(block.text for block in blocks)


def normalize_text(text: str) -> str:
    """Metni karşılaştırma için normalize eder.

    Whitespace farklarını göz ardı eder.

    Args:
        text: Ham metin.

    Returns:
        Normalize edilmiş metin.
    """
    # Birden fazla boşluğu teke indir, satır sonlarını normalize et
    import re
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()
