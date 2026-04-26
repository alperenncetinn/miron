"""macOS NSVisualEffectView blur efekti entegrasyonu."""

import ctypes

import objc
from AppKit import (
    NSVisualEffectView,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectStateActive,
)
from Foundation import NSMakeRect


def apply_blur_effect(widget) -> bool:
    """PySide6 widget'ına macOS native blur efekti uygular.

    NSVisualEffectView kullanarak pencerenin arkasındaki içeriği
    bulanıklaştırır (glassmorphism efekti).

    Args:
        widget: PySide6 QWidget nesnesi (pencere olmalı).

    Returns:
        True başarılıysa, False değilse.
    """
    try:
        # Widget'ın native window ID'sini al
        window_handle = widget.windowHandle()
        if window_handle is None:
            widget.winId()  # winId() çağrısı window handle oluşturur
            window_handle = widget.windowHandle()

        if window_handle is None:
            print("[Blur] Window handle alınamadı.")
            return False

        # Native NSView pointer'ını al
        win_id = int(widget.winId())

        # NSView'a eriş
        ns_view = objc.objc_object(c_void_p=ctypes.c_void_p(win_id))

        if ns_view is None:
            print("[Blur] NSView alınamadı.")
            return False

        # NSWindow'a eriş
        ns_window = ns_view.window()
        if ns_window is None:
            print("[Blur] NSWindow alınamadı.")
            return False

        # Pencere arka planını şeffaf yap
        ns_window.setOpaque_(False)
        ns_window.setBackgroundColor_(
            objc.lookUpClass("NSColor").clearColor()
        )

        # Content view'ı al
        content_view = ns_window.contentView()
        if content_view is None:
            print("[Blur] Content view alınamadı.")
            return False

        # Mevcut blur view'ları temizle
        for subview in list(content_view.subviews()):
            if isinstance(subview, NSVisualEffectView):
                subview.removeFromSuperview()

        # NSVisualEffectView oluştur
        frame = content_view.bounds()
        blur_view = NSVisualEffectView.alloc().initWithFrame_(frame)

        # Efekt ayarları
        blur_view.setMaterial_(NSVisualEffectMaterialHUDWindow)
        blur_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        blur_view.setState_(NSVisualEffectStateActive)
        blur_view.setWantsLayer_(True)

        # Köşe yuvarlaklığı
        blur_view.layer().setCornerRadius_(14.0)
        blur_view.layer().setMasksToBounds_(True)

        # AutoresizingMask — pencere boyutlandırıldığında otomatik uyum
        # NSViewWidthSizable | NSViewHeightSizable = 18
        blur_view.setAutoresizingMask_(18)

        # En alt katmana ekle (diğer widget'lar üzerinde kalır)
        # -1 = NSWindowBelow
        content_view.addSubview_positioned_relativeTo_(
            blur_view, -1, None
        )

        return True

    except Exception as e:
        print(f"[Blur] Efekt uygulanamadı: {e}")
        return False


def remove_blur_effect(widget) -> bool:
    """Widget'tan blur efektini kaldırır.

    Args:
        widget: PySide6 QWidget nesnesi.

    Returns:
        True başarılıysa, False değilse.
    """
    try:
        win_id = int(widget.winId())
        ns_view = objc.objc_object(c_void_p=ctypes.c_void_p(win_id))

        if ns_view is None:
            return False

        ns_window = ns_view.window()
        if ns_window is None:
            return False

        content_view = ns_window.contentView()
        if content_view is None:
            return False

        for subview in list(content_view.subviews()):
            if isinstance(subview, NSVisualEffectView):
                subview.removeFromSuperview()

        return True

    except Exception as e:
        print(f"[Blur] Efekt kaldırılamadı: {e}")
        return False
