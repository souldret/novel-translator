"""
Novel Çevirmen - İçe/Dışa Aktarım Fonksiyonları
TXT ve EPUB formatlarında içe ve dışa aktarım işlemleri.
"""

import os
import re

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from database import DatabaseManager

# chardet opsiyonel; yüklü değilse sabit kodlama listesi kullanılır
try:
    import chardet as _chardet
    _CHARDET_MEVCUT = True
except ImportError:
    _chardet = None
    _CHARDET_MEVCUT = False

_VARSAYILAN_KODLAMALAR = ("utf-8-sig", "utf-8", "cp1254", "latin-1")


def _dosya_icerigini_oku(dosya_yolu: str) -> str | None:
    """
    Verilen dosyayı uygun kodlamayla okur ve içeriği döner.
    chardet yüklüyse önce otomatik tespit dener; başarısız olursa
    sabit kodlama listesini dener. Hiçbiri işe yaramazsa None döner.
    """
    if _CHARDET_MEVCUT:
        try:
            with open(dosya_yolu, "rb") as fb:
                ham = fb.read()
            tespit = _chardet.detect(ham)
            enc = tespit.get("encoding") or "utf-8"
            return ham.decode(enc, errors="replace").strip()
        except Exception:
            pass  # Hata olursa sabit listeye düş

    for enc in _VARSAYILAN_KODLAMALAR:
        try:
            with open(dosya_yolu, encoding=enc) as f:
                return f.read().strip()
        except UnicodeDecodeError:
            continue
    return None


# =============================================================================
# TXT İÇE AKTARIM
# =============================================================================

def txt_bolum_ice_aktar(
    seri_id: int,
    db_manager: DatabaseManager,
    parent_widget=None,
) -> int:
    """
    Kullanıcıdan bir veya daha fazla TXT dosyası seçmesini ister,
    her dosyayı verilen seriye yeni bölüm olarak ekler.

    Returns:
        Eklenen bölüm sayısı (0 dahil).
    """
    dosyalar, _ = QFileDialog.getOpenFileNames(
        parent_widget,
        "TXT Dosyası Seç",
        "",
        "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)",
    )
    if not dosyalar:
        return 0

    mevcut_bolumler = db_manager.serinin_bolumlerini_getir(seri_id)
    sonraki_no = max((b.get("bolum_no", 0) for b in mevcut_bolumler), default=0) + 1
    eklenen = 0

    for dosya in sorted(dosyalar):
        icerik = _dosya_icerigini_oku(dosya)
        if not icerik:
            continue

        baslik = os.path.splitext(os.path.basename(dosya))[0]
        db_manager.bolum_olustur(
            seri_id=seri_id,
            bolum_no=sonraki_no,
            bolum_baslik=baslik,
            orijinal_metin=icerik,
        )
        sonraki_no += 1
        eklenen += 1

    if eklenen:
        QMessageBox.information(
            parent_widget,
            "İçe Aktarım",
            f"{eklenen} bölüm başarıyla eklendi.",
        )

    return eklenen


# =============================================================================
# EPUB İÇE AKTARIM
# =============================================================================

def epub_ice_aktar(
    seri_id: int,
    db_manager: DatabaseManager,
    parent_widget=None,
) -> int:
    """
    Kullanıcıdan bir EPUB dosyası seçmesini ister, içindeki HTML/XHTML
    bölümlerini ayrıştırarak verilen seriye yeni bölümler olarak ekler.

    Returns:
        Eklenen bölüm sayısı (0 dahil).
    """
    dosya, _ = QFileDialog.getOpenFileName(
        parent_widget,
        "EPUB Dosyası Seç",
        "",
        "EPUB Dosyaları (*.epub);;Tüm Dosyalar (*)",
    )
    if not dosya:
        return 0

    try:
        import zipfile
        from html.parser import HTMLParser

        class _HtmlMetinCikartici(HTMLParser):
            def __init__(self):
                super().__init__()
                self.metin_parcalari = []
                self._atla = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "head"):
                    self._atla = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "head"):
                    self._atla = False
                if tag in ("p", "div", "br", "h1", "h2", "h3", "h4"):
                    self.metin_parcalari.append("\n")

            def handle_data(self, data):
                if not self._atla:
                    self.metin_parcalari.append(data)

        def _html_den_metin(html_str: str) -> str:
            p = _HtmlMetinCikartici()
            p.feed(html_str)
            satirlar = "".join(p.metin_parcalari).splitlines()
            temiz = [s.strip() for s in satirlar if s.strip()]
            return "\n\n".join(temiz)

        eklenen = 0
        mevcut = db_manager.serinin_bolumlerini_getir(seri_id)
        sonraki_no = max((b.get("bolum_no", 0) for b in mevcut), default=0) + 1

        with zipfile.ZipFile(dosya, "r") as epub:
            icerik_dosyalari = sorted([
                n for n in epub.namelist()
                if n.endswith((".html", ".xhtml", ".htm"))
                and "toc" not in n.lower()
                and "nav" not in n.lower()
                and "ncx" not in n.lower()
            ])

            for dosya_adi in icerik_dosyalari:
                try:
                    html_bytes = epub.read(dosya_adi)
                    html_str = html_bytes.decode("utf-8", errors="replace")
                    metin = _html_den_metin(html_str)
                    if len(metin.strip()) < 50:
                        continue  # Çok kısa — bölüm değil
                    baslik = os.path.splitext(os.path.basename(dosya_adi))[0]
                    baslik = re.sub(r"[-_]", " ", baslik).title()
                    db_manager.bolum_olustur(
                        seri_id=seri_id,
                        bolum_no=sonraki_no,
                        bolum_baslik=baslik,
                        orijinal_metin=metin,
                    )
                    sonraki_no += 1
                    eklenen += 1
                except Exception:
                    continue

        if eklenen:
            QMessageBox.information(
                parent_widget,
                "EPUB İçe Aktarım",
                f"{eklenen} bölüm başarıyla içe aktarıldı.",
            )
        else:
            QMessageBox.warning(
                parent_widget,
                "EPUB İçe Aktarım",
                "Bölüm içeriği bulunamadı. Dosya standart EPUB formatında olmayabilir.",
            )

        return eklenen

    except Exception as hata:
        QMessageBox.critical(
            parent_widget,
            "EPUB Hatası",
            f"EPUB dosyası işlenirken hata oluştu:\n{hata}",
        )
        return 0


# =============================================================================
# TXT DIŞA AKTARIM
# =============================================================================

def txt_disa_aktar(
    seri_id: int,
    db_manager: DatabaseManager,
    parent_widget=None,
) -> bool:
    """
    Verilen serinin çevrilmiş bölümlerini tek bir TXT dosyasına dışa aktarır.

    Returns:
        True — dosya başarıyla kaydedildiyse,
        False — kullanıcı iptal ettiyse veya hata oluştuysa.
    """
    bolumler = db_manager.serinin_bolumlerini_getir(seri_id)
    cevirilen = [b for b in bolumler if b.get("cevrilmis_metin", "").strip()]
    if not cevirilen:
        QMessageBox.information(
            parent_widget,
            "Dışa Aktarım",
            "Dışa aktarılacak çevrilmiş bölüm bulunamadı.",
        )
        return False

    seri = db_manager.seri_getir(seri_id)
    varsayilan_ad = f"{seri.get('baslik', 'seri')}_ceviri.txt" if seri else "ceviri.txt"

    kayit_yolu, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "TXT Olarak Kaydet",
        varsayilan_ad,
        "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)",
    )
    if not kayit_yolu:
        return False

    try:
        with open(kayit_yolu, "w", encoding="utf-8") as f:
            for bolum in cevirilen:
                baslik = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no', '')}"
                f.write(f"{'=' * 60}\n{baslik}\n{'=' * 60}\n\n")
                f.write(bolum.get("cevrilmis_metin", "").strip())
                f.write("\n\n")

        QMessageBox.information(
            parent_widget,
            "Dışa Aktarım",
            f"{len(cevirilen)} bölüm başarıyla kaydedildi:\n{kayit_yolu}",
        )
        return True

    except Exception as hata:
        QMessageBox.critical(
            parent_widget,
            "Yazma Hatası",
            f"Dosya yazılamadı:\n{hata}",
        )
        return False


# =============================================================================
# EPUB DIŞA AKTARIM
# =============================================================================

def epub_disa_aktar(
    seri_id: int,
    db_manager: DatabaseManager,
    seri_baslik: str,
    parent_widget=None,
) -> bool:
    """
    Verilen serinin çevrilmiş bölümlerini standart EPUB 2.0 formatında dışa aktarır.

    Args:
        seri_id:      Hedef serinin veritabanı kimliği.
        db_manager:   Veritabanı yöneticisi.
        seri_baslik:  EPUB metadata başlığı için kullanılan seri adı.
        parent_widget: Mesaj kutularının üst penceresi.

    Returns:
        True — dosya başarıyla kaydedildiyse,
        False — kullanıcı iptal ettiyse veya hata oluştuysa.
    """
    bolumler = db_manager.serinin_bolumlerini_getir(seri_id)
    cevirilen = [b for b in bolumler if b.get("cevrilmis_metin", "").strip()]
    if not cevirilen:
        QMessageBox.information(
            parent_widget,
            "EPUB Dışa Aktarım",
            "Dışa aktarılacak çevrilmiş bölüm bulunamadı.",
        )
        return False

    varsayilan_ad = f"{seri_baslik}_ceviri.epub"
    kayit_yolu, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "EPUB Olarak Kaydet",
        varsayilan_ad,
        "EPUB Dosyaları (*.epub);;Tüm Dosyalar (*)",
    )
    if not kayit_yolu:
        return False

    try:
        import zipfile
        import uuid
        from datetime import datetime

        kitap_id = str(uuid.uuid4())
        simdi = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        def _html_kacis(metin: str) -> str:
            return (
                metin.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace('"', "&quot;")
            )

        def _bolum_html(baslik: str, metin: str) -> str:
            paragraflar = "\n".join(
                f"<p>{_html_kacis(p.strip())}</p>"
                for p in metin.split("\n\n")
                if p.strip()
            )
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">'
                f'<head><title>{_html_kacis(baslik)}</title>'
                '<meta charset="UTF-8"/>'
                '<style>body{font-family:serif;line-height:1.7;margin:2em;} '
                'h2{color:#333;margin-bottom:1em;} p{text-indent:1.5em;margin:0.4em 0;}</style>'
                f'</head><body><h2>{_html_kacis(baslik)}</h2>{paragraflar}</body></html>'
            )

        manifest_girisler = []
        spine_girisler = []
        toc_girisler = []

        with zipfile.ZipFile(kayit_yolu, "w", zipfile.ZIP_DEFLATED) as epub:
            # mimetype sıkıştırılmadan yazılmalı (EPUB standardı)
            epub.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")

            # META-INF/container.xml
            epub.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?>\n'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                '  <rootfiles>\n'
                '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
                '  </rootfiles>\n'
                '</container>',
            )

            # Bölüm dosyaları
            for i, bolum in enumerate(cevirilen):
                dosya_id = f"bolum{i + 1}"
                dosya_adi = f"OEBPS/{dosya_id}.xhtml"
                baslik = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no', i + 1)}"
                html = _bolum_html(baslik, bolum.get("cevrilmis_metin", ""))
                epub.writestr(dosya_adi, html.encode("utf-8"))
                manifest_girisler.append(
                    f'<item id="{dosya_id}" href="{dosya_id}.xhtml"'
                    f' media-type="application/xhtml+xml"/>'
                )
                spine_girisler.append(f'<itemref idref="{dosya_id}"/>')
                toc_girisler.append(
                    f'<navPoint id="nav{i + 1}" playOrder="{i + 1}">'
                    f'<navLabel><text>{_html_kacis(baslik)}</text></navLabel>'
                    f'<content src="{dosya_id}.xhtml"/></navPoint>'
                )

            # OEBPS/content.opf
            opf = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">'
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f'<dc:title>{_html_kacis(seri_baslik)}</dc:title>'
                f'<dc:identifier id="bookid">{kitap_id}</dc:identifier>'
                '<dc:language>tr</dc:language>'
                f'<dc:date>{simdi}</dc:date>'
                '</metadata>'
                '<manifest>'
                + "\n".join(manifest_girisler)
                + '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                '</manifest>'
                '<spine toc="ncx">'
                + "\n".join(spine_girisler)
                + '</spine>'
                '</package>'
            )
            epub.writestr("OEBPS/content.opf", opf.encode("utf-8"))

            # OEBPS/toc.ncx
            ncx = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
                '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
                '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
                f'<head><meta name="dtb:uid" content="{kitap_id}"/></head>'
                f'<docTitle><text>{_html_kacis(seri_baslik)}</text></docTitle>'
                '<navMap>'
                + "\n".join(toc_girisler)
                + '</navMap>'
                '</ncx>'
            )
            epub.writestr("OEBPS/toc.ncx", ncx.encode("utf-8"))

        QMessageBox.information(
            parent_widget,
            "EPUB Dışa Aktarım",
            f"{len(cevirilen)} bölüm EPUB olarak kaydedildi:\n{kayit_yolu}",
        )
        return True

    except Exception as hata:
        QMessageBox.critical(
            parent_widget,
            "EPUB Hatası",
            f"EPUB oluşturulamadı:\n{hata}",
        )
        return False