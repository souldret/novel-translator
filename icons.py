"""
Novel Cevirmen - Icon Kutuphanesi
Tum UI ikonlari icin merkezi SVG tabanli icon ureteci.

Her icon bir SVG path tanimindan uretilir ve QIcon olarak dondurulur.
Bu sayede:
- Tum platformlarda tutarli gorunum
- Yuksesksek DPI ekranlarda net (vector tabanli)
- Eklenti/harici dosya gerektirmez
- Tema rengine uyum saglayabilir

Renk semasi (karanlik tema):
  Primary  : #9b59d0 (violet)
  Accent   : #c9a8e8 (light violet)
  Success  : #a0f0b0 (green)
  Warning  : #f0d090 (yellow)
  Danger   : #f0a0b0 (pink-red)
  Muted    : #6b5a7a (muted violet)
  Text     : #e8e0f0 (light)
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize


# =============================================================================
# RENK PALETI (kolay erisim)
# =============================================================================

PRIMARY  = "#9b59d0"
ACCENT   = "#c9a8e8"
SUCCESS  = "#a0f0b0"
WARNING  = "#f0d090"
DANGER   = "#f0a0b0"
INFO     = "#8ec5ff"
MUTED    = "#6b5a7a"
TEXT     = "#e8e0f0"


# =============================================================================
# SVG ICON TANIMLARI
# =============================================================================

# Her icon: (ad, svg_string, primary_renk)
# SVG'ler 24x24 viewBox ile olusturuldu

_ICONS = {
    # --- ANA NAVIGASYON ---
    "book": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5a2.5 2.5 0 0 0 0 5H20" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "books": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M4 4v16a2 2 0 0 0 2 2h12" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<path d="M4 4l2-2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round" fill="none"/>'
        f'<path d="M8 7h8M8 11h8M8 15h5" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "settings": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="3" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "info": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<line x1="12" y1="16" x2="12" y2="12" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="12" y1="8" x2="12.01" y2="8" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),

    # --- ISLEM BUTONLARI ---
    "add": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<line x1="12" y1="8" x2="12" y2="16" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="8" y1="12" x2="16" y2="12" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "save": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<polyline points="17 21 17 13 7 13 7 21" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<polyline points="7 3 7 8 15 8" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "delete": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<polyline points="3 6 5 6 21 6" stroke="{DANGER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" stroke="{DANGER}" stroke-width="2" stroke-linejoin="round"/>'
        f'<line x1="10" y1="11" x2="10" y2="17" stroke="{DANGER}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="14" y1="11" x2="14" y2="17" stroke="{DANGER}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "edit": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "play": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<polygon points="6 4 20 12 6 20 6 4" fill="{PRIMARY}" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "pause": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<rect x="6" y="4" width="4" height="16" fill="{MUTED}" stroke="{MUTED}" stroke-width="2"/>'
        f'<rect x="14" y="4" width="4" height="16" fill="{MUTED}" stroke="{MUTED}" stroke-width="2"/>'
        f'</svg>'
    ),
    "refresh": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<polyline points="23 4 23 10 17 10" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<polyline points="1 20 1 14 7 14" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "search": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="11" cy="11" r="8" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<line x1="21" y1="21" x2="16.65" y2="16.65" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),

    # --- IMPORT / EXPORT ---
    "import": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<polyline points="7 10 12 15 17 10" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<line x1="12" y1="15" x2="12" y2="3" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "export": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<polyline points="17 8 12 3 7 8" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<line x1="12" y1="3" x2="12" y2="15" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "undo": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M3 7v6h6" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M3 13A9 9 0 1 0 5.5 6.5L3 7" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "document": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<polyline points="14 2 14 8 20 8" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<line x1="8" y1="13" x2="16" y2="13" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<line x1="8" y1="17" x2="14" y2="17" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "globe": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<line x1="2" y1="12" x2="22" y2="12" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" '
        f'stroke="{PRIMARY}" stroke-width="2"/>'
        f'</svg>'
    ),

    # --- DURUM / BILDIRIM ---
    "check": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<polyline points="20 6 9 17 4 12" stroke="{SUCCESS}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "check_circle": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{SUCCESS}" stroke-width="2"/>'
        f'<polyline points="8 12 11 15 16 9" stroke="{SUCCESS}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "warning": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" '
        f'stroke="{WARNING}" stroke-width="2" stroke-linejoin="round"/>'
        f'<line x1="12" y1="9" x2="12" y2="13" stroke="{WARNING}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="12" y1="17" x2="12.01" y2="17" stroke="{WARNING}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "error": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{DANGER}" stroke-width="2"/>'
        f'<line x1="15" y1="9" x2="9" y2="15" stroke="{DANGER}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="9" y1="9" x2="15" y2="15" stroke="{DANGER}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "info_circle": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" stroke="{INFO}" stroke-width="2"/>'
        f'<line x1="12" y1="16" x2="12" y2="12" stroke="{INFO}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="12" y1="8" x2="12.01" y2="8" stroke="{INFO}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "star": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" '
        f'fill="{WARNING}" stroke="{WARNING}" stroke-width="1.5" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "hourglass": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M5 22h14M5 2h14M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "bulb": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2v.3h6v-.3c0-.8.4-1.5 1-2A7 7 0 0 0 12 2z" '
        f'stroke="{WARNING}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "circle_green": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<circle cx="12" cy="12" r="10" fill="{SUCCESS}"/>'
        f'</svg>'
    ),

    # --- OZELLIK / AI ---
    "robot": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<rect x="3" y="8" width="18" height="12" rx="2" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<circle cx="8" cy="14" r="1.5" fill="{PRIMARY}"/>'
        f'<circle cx="16" cy="14" r="1.5" fill="{PRIMARY}"/>'
        f'<line x1="12" y1="4" x2="12" y2="8" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'<circle cx="12" cy="3" r="1" fill="{PRIMARY}"/>'
        f'<line x1="7" y1="20" x2="7" y2="22" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="17" y1="20" x2="17" y2="22" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "list": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<rect x="3" y="4" width="18" height="16" rx="2" stroke="{PRIMARY}" stroke-width="2"/>'
        f'<line x1="8" y1="9" x2="16" y2="9" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<line x1="8" y1="13" x2="16" y2="13" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<line x1="8" y1="17" x2="13" y2="17" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/>'
        f'</svg>'
    ),
    "plug": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M18 11V8a2 2 0 0 0-2-2h-3l-1-3h-2l-1 3H6a2 2 0 0 0-2 2v3a6 6 0 0 0 6 6v3h2v-3a6 6 0 0 0 6-6z" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    ),
    "eye": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="{PRIMARY}" stroke-width="2" stroke-linejoin="round"/>'
        f'<circle cx="12" cy="12" r="3" stroke="{PRIMARY}" stroke-width="2"/>'
        f'</svg>'
    ),
    "eye_off": (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        f'<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" '
        f'stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<line x1="1" y1="1" x2="23" y2="23" stroke="{PRIMARY}" stroke-width="2" stroke-linecap="round"/>'
        f'</svg>'
    ),
}


# =============================================================================
# ICON OLUSTURUCU FONKSIYONLAR
# =============================================================================

def _svg_to_icon(svg_str: str, color: str = None) -> QIcon:
    """
    SVG string'inden QIcon uretir.

    Renk degistirme destegi: eger color verilirse SVG icindeki tum renk
    referanslari yenisi ile degistirilir.
    """
    try:
        # Eger renk degistirilecekse, SVG icindeki renkleri yenile
        if color:
            # Bilinen hex renkleri degistir
            for old_color in [PRIMARY, ACCENT, SUCCESS, WARNING, DANGER, MUTED, TEXT]:
                svg_str = svg_str.replace(f'"{old_color}"', f'"{color}"')
                svg_str = svg_str.replace(f"'{old_color}'", f'"{color}"')

        pixmap = QPixmap()
        # SVG'yi QPixmap'a donustur
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray

        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        pixmap = QPixmap(QSize(24, 24))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)
    except Exception:
        # Hata durumunda bos icon dondur
        return QIcon()


def _ensure_svg_support():
    """
    PyQt6.QtSvg modulu import edilebilir mi kontrol eder.
    Eger edilemezse (yani QtSvg yuklu degilse), tum iconlar icin
    fallback olarak renkli Unicode karakterler kullanilir.
    """
    try:
        from PyQt6.QtSvg import QSvgRenderer as _QSvgRenderer
        _ = _QSvgRenderer  # modülün yüklü olduğunu doğrula
        return True
    except ImportError:
        return False


_SVG_AVAILABLE = _ensure_svg_support()


# =============================================================================
# PUBLIC API
# =============================================================================

def icon(name: str, color: str = None, size: int = None) -> QIcon:
    """
    Verilen isimdeki iconu QIcon olarak dondurur.

    Parametreler:
        name  : Icon adi (yukaridaki _ICONS sozlugunden)
        color : Istenirse icon rengini degistirmek icin hex renk kodu
        size  : Istenirse icon boyutunu degistirmek icin piksel degeri

    Dondurur:
        QIcon nesnesi (basarisiz ise bos icon)
    """
    if name not in _ICONS:
        return QIcon()

    svg_str = _ICONS[name]

    try:
        if _SVG_AVAILABLE:
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtCore import QByteArray

            # Renk degisimi
            if color:
                for old_color in [PRIMARY, ACCENT, SUCCESS, WARNING, DANGER, MUTED, TEXT]:
                    svg_str = svg_str.replace(f'"{old_color}"', f'"{color}"')
                    svg_str = svg_str.replace(f"'{old_color}'", f'"{color}"')

            # Hedef boyut
            target_size = size if size else 24
            pixmap = QPixmap(QSize(target_size, target_size))
            pixmap.fill(Qt.GlobalColor.transparent)

            renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter)
            painter.end()

            return QIcon(pixmap)
        else:
            # SVG desteklenmiyorsa yine de QIcon dondur
            # (bazi platformlarda QIcon() bos olabilir)
            return QIcon()
    except Exception:
        return QIcon()


# =============================================================================
# YARDIMCI: QLabel / QPushButton UZERINDE KULLANMAK ICIN
# =============================================================================

def set_icon(widget, name: str, color: str = None, size: int = 16):
    """
    Bir QPushButton veya QAction'a icon atar.

    Parametreler:
        widget : QPushButton veya QAction nesnesi
        name   : Icon adi
        color  : Istenirse renk degisikligi
        size   : Icon boyutu (varsayilan 16px)
    """
    widget.setIcon(icon(name, color=color, size=size))
    if hasattr(widget, "setIconSize"):
        widget.setIconSize(QSize(size, size))


# =============================================================================
# QPIXMAP OLARAK (QLabel icin)
# =============================================================================

def pixmap(name: str, color: str = None, size: int = 64) -> QPixmap:
    """
    Iconu QPixmap olarak dondurur (QLabel'lar icin idealdir).
    """
    ic = icon(name, color=color, size=size)
    return ic.pixmap(QSize(size, size))


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

    app = QApplication(sys.argv)

    w = QWidget()
    w.setWindowTitle("Icon Kutuphanesi Test")
    w.setStyleSheet("background-color: #0f0a1a; color: #e8e0f0;")
    layout = QVBoxLayout(w)
    layout.setSpacing(10)

    # Icon listesini goster
    baslik = QLabel("Tum Iconlar:")
    baslik.setStyleSheet("color: #9b59d0; font-size: 16px; font-weight: bold;")
    layout.addWidget(baslik)

    grid = QVBoxLayout()
    grid.setSpacing(6)

    icon_names = [
        "book", "books", "settings", "info",
        "add", "save", "delete", "edit", "play", "pause", "refresh", "search",
        "import", "export", "document", "globe",
        "check", "check_circle", "warning", "error", "info_circle", "star",
        "hourglass", "bulb", "circle_green",
        "robot", "list", "plug", "eye", "eye_off",
    ]

    for name in icon_names:
        satir = QHBoxLayout()
        satir.setSpacing(10)
        lbl = QLabel()
        lbl.setPixmap(pixmap(name, size=24))
        isim = QLabel(name)
        isim.setStyleSheet("color: #e8e0f0; font-family: monospace;")
        satir.addWidget(lbl)
        satir.addWidget(isim)
        satir.addStretch()
        grid.addLayout(satir)

    layout.addLayout(grid)

    # Test butonlari
    btn_layout = QHBoxLayout()
    for name in ["save", "delete", "add", "edit", "refresh"]:
        b = QPushButton(name)
        set_icon(b, name, size=16)
        btn_layout.addWidget(b)
    layout.addLayout(btn_layout)

    w.resize(300, 800)
    w.show()
    sys.exit(app.exec())