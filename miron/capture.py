"""Ekran yakalama modülü — macOS CGWindowListCreateImage kullanır."""

from __future__ import annotations

import Quartz
from Quartz import (
    CGRectMake,
    CGWindowListCreateImage,
    kCGWindowListOptionOnScreenBelowWindow,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowImageDefault,
    kCGNullWindowID,
    CGMainDisplayID,
    CGDisplayScreenSize,
    CGPreflightScreenCaptureAccess,
    CGRequestScreenCaptureAccess,
)


def check_screen_capture_permission() -> bool:
    """macOS ekran kaydı iznini kontrol eder.

    Returns:
        True izin verilmişse, False değilse.
    """
    has_access = CGPreflightScreenCaptureAccess()
    if not has_access:
        # İzin isteği dialog'unu tetikler
        CGRequestScreenCaptureAccess()
    return has_access


def get_display_scale_factor() -> float:
    """Ana ekranın scale factor'ünü döndürür (Retina desteği).

    Returns:
        Scale factor (örn. 2.0 Retina ekranlarda).
    """
    main_display = CGMainDisplayID()
    mode = Quartz.CGDisplayCopyDisplayMode(main_display)
    if mode is None:
        return 1.0

    pixel_width = Quartz.CGDisplayModeGetPixelWidth(mode)
    point_width = Quartz.CGDisplayModeGetWidth(mode)

    if point_width == 0:
        return 1.0

    return pixel_width / point_width


def capture_region(
    x: float,
    y: float,
    width: float,
    height: float,
    exclude_window_id: int | None = None,
) -> "Quartz.CGImageRef | None":
    """Ekranın belirtilen bölgesini yakalar.

    Args:
        x: Sol üst köşe X koordinatı (points).
        y: Sol üst köşe Y koordinatı (points).
        width: Genişlik (points).
        height: Yükseklik (points).
        exclude_window_id: Yakalama dışında bırakılacak pencerenin ID'si.
            Bu, overlay penceresinin kendisini yakalamayı önler.

    Returns:
        Yakalanan bölgenin CGImage nesnesi veya None.
    """
    region = CGRectMake(x, y, width, height)

    if exclude_window_id is not None:
        # Belirtilen pencerenin altındaki ekran içeriğini yakala
        # Bu, overlay penceresini yakalamadan kaçınır
        image = CGWindowListCreateImage(
            region,
            kCGWindowListOptionOnScreenBelowWindow,
            exclude_window_id,
            kCGWindowImageDefault,
        )
    else:
        # Tüm görünür pencereler dahil
        image = CGWindowListCreateImage(
            region,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            kCGWindowImageDefault,
        )

    return image


def get_image_dimensions(cg_image) -> "tuple[int, int]":
    """CGImage'ın piksel boyutlarını döndürür.

    Args:
        cg_image: Quartz CGImage nesnesi.

    Returns:
        (width, height) tuple — piksel cinsinden.
    """
    if cg_image is None:
        return (0, 0)
    width = Quartz.CGImageGetWidth(cg_image)
    height = Quartz.CGImageGetHeight(cg_image)
    return (width, height)
