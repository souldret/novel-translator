"""
Novel Çevirmen - İçe/Dışa Aktarım Fonksiyonları
TXT ve EPUB formatlarında içe ve dışa aktarım işlemleri.
"""

import hashlib
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

# Encoding tespiti için okunacak maksimum bayt miktarı (64 KB yeterli)
_ENCODING_ORNEK_BOYUTU = 65536


# =============================================================================
# DOĞAL SIRALAMA — sayısal farkındalıklı dosya sıralaması
# =============================================================================

# Dosya adından bölüm numarası çıkarmak için alternatif regex kalıpları
# (öncelik sırasına göre; ilk eşleşen kullanılır)
_BOLUM_NO_KALIPLARI = [
    # "Bölüm 12 - Başlık.txt", "Chapter 012.txt", "볼룸 3.txt" vb.
    re.compile(r'(?:b[oö]l[uü]m|chapter|ch|bap|kısım|part|ep(?:isode)?)'
               r'\s*[._\-]?\s*(\d+)', re.IGNORECASE),
    # "012.txt", "012 - Başlık.txt" gibi saf sayı
    re.compile(r'^(\d+)'),
    # Sondaki sayı: "Başlık 3.txt"
    re.compile(r'(\d+)\s*$'),
    # Herhangi bir yerdeki sayı
    re.compile(r'(\d+)'),
]


def dosya_adından_bolum_no(dosya_adi: str) -> tuple[int, str]:
    """
    Dosya adından (uzantısız) bölüm numarası ve başlık çıkarır.

    Döndürür:
        (bolum_no, baslik)
        Numara bulunamazsa bolum_no=9999 (alfabetik sonuna düşer).
    """
    kok = os.path.splitext(os.path.basename(dosya_adi))[0]
    for kalip in _BOLUM_NO_KALIPLARI:
        m = kalip.search(kok)
        if m:
            no = int(m.group(1))
            # Başlığı temizle: numarayı, ayırıcıları ve "Bölüm/Chapter" öncesini sil
            baslik = kalip.sub("", kok).strip(" -_.")
            # Kalan tire/alt çizgi ayırıcıları boşluğa çevir
            baslik = re.sub(r'[\-_]+', ' ', baslik).strip()
            return no, baslik if baslik else kok
    return 9999, kok


def dogal_sirala(dosyalar: list[str]) -> list[str]:
    """
    Dosya yollarını bölüm numarasına göre doğal (numeric-aware) sıralar.
    Numara bulunamazsa alfabetik sıraya düşer.
    """
    return sorted(dosyalar, key=lambda p: dosya_adından_bolum_no(p))


def _icerik_hash(icerik: str) -> str:
    """İçerik karması (mükerrer tespiti için)."""
    return hashlib.md5(icerik.encode("utf-8", errors="replace")).hexdigest()


def _dosya_icerigini_oku(dosya_yolu: str) -> str | None:
    """
    Verilen dosyayı uygun kodlamayla okur ve içeriği döner.
    chardet yüklüyse dosyanın ilk 64 KB'ından örnekleme yaparak encoding
    tespiti yapar (büyük dosyalarda performans için); başarısız olursa
    sabit kodlama listesini dener. Hiçbiri işe yaramazsa None döner.
    """
    if _CHARDET_MEVCUT:
        try:
            with open(dosya_yolu, "rb") as fb:
                ornek = fb.read(_ENCODING_ORNEK_BOYUTU)
            tespit = _chardet.detect(ornek)
            enc = tespit.get("encoding") or "utf-8"
            # Tam dosyayı seçilen kodlamayla oku
            with open(dosya_yolu, encoding=enc, errors="replace") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None
        except Exception:
            pass  # Encoding hatası → sabit listeye düş

    for enc in _VARSAYILAN_KODLAMALAR:
        try:
            with open(dosya_yolu, encoding=enc) as f:
                return f.read().strip()
        except UnicodeDecodeError:
            continue
        except (FileNotFoundError, PermissionError, OSError):
            return None
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

    - Doğal sıralama (numeric-aware) uygulanır.
    - İçerik hash'i ile mükerrer bölüm kontrolü yapılır.

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

    # Mükerrer tespiti: mevcut bölümlerin içerik hash'leri
    mevcut_hashler: set[str] = set()
    for b in mevcut_bolumler:
        icerik = (b.get("orijinal_metin") or "").strip()
        if icerik:
            mevcut_hashler.add(_icerik_hash(icerik))

    eklenen = 0
    atlanan = 0

    for dosya in dogal_sirala(dosyalar):
        icerik = _dosya_icerigini_oku(dosya)
        if not icerik:
            continue

        # Mükerrer kontrolü
        h = _icerik_hash(icerik)
        if h in mevcut_hashler:
            atlanan += 1
            continue

        _bolum_no, baslik = dosya_adından_bolum_no(dosya)
        db_manager.bolum_olustur(
            seri_id=seri_id,
            bolum_no=sonraki_no,
            bolum_baslik=baslik,
            orijinal_metin=icerik,
        )
        mevcut_hashler.add(h)
        sonraki_no += 1
        eklenen += 1

    mesaj_parcalari = []
    if eklenen:
        mesaj_parcalari.append(f"{eklenen} bölüm başarıyla eklendi.")
    if atlanan:
        mesaj_parcalari.append(f"{atlanan} bölüm zaten mevcut olduğu için atlandı.")

    if mesaj_parcalari:
        QMessageBox.information(
            parent_widget,
            "İçe Aktarım",
            "\n".join(mesaj_parcalari),
        )

    return eklenen


# =============================================================================
# EPUB İÇE AKTARIM
# =============================================================================

def _epub_opf_yolu_bul(epub_zip) -> str | None:
    """
    META-INF/container.xml dosyasından OPF dosyasının yolunu okur.
    Bulunamazsa None döner.
    """
    try:
        container_xml = epub_zip.read("META-INF/container.xml").decode("utf-8", errors="replace")
        m = re.search(r'full-path=["\']([^"\']+\.opf)["\']', container_xml, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _epub_spine_sirasi(epub_zip, opf_yolu: str) -> list[str] | None:
    """
    OPF dosyasındaki <spine> sırasına göre içerik dosyalarının tam yollarını döner.
    Başarısız olursa None döner (fallback için).
    """
    try:
        opf_icerik = epub_zip.read(opf_yolu).decode("utf-8", errors="replace")
        opf_klasor = opf_yolu.rsplit("/", 1)[0] + "/" if "/" in opf_yolu else ""

        # manifest: id → href eşleşmesi
        manifest: dict[str, str] = {}
        for m in re.finditer(
            r'<item\b[^>]*\bid=["\']([^"\']+)["\'][^>]*\bhref=["\']([^"\']+)["\']',
            opf_icerik, re.IGNORECASE
        ):
            manifest[m.group(1)] = m.group(2)
        # href → id yönünde de ara (attr sırası farklı olabilir)
        for m in re.finditer(
            r'<item\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*\bid=["\']([^"\']+)["\']',
            opf_icerik, re.IGNORECASE
        ):
            manifest[m.group(2)] = m.group(1)  # id→href yönü doğru değil; tekrar düzelt
        # Doğrudan id→href haritası kur
        id_to_href: dict[str, str] = {}
        for m in re.finditer(
            r'<item\b([^>]+)>', opf_icerik, re.IGNORECASE
        ):
            attrs_str = m.group(1)
            id_m   = re.search(r'\bid=["\']([^"\']+)["\']', attrs_str)
            href_m = re.search(r'\bhref=["\']([^"\']+)["\']', attrs_str)
            if id_m and href_m:
                id_to_href[id_m.group(1)] = href_m.group(1)

        # spine: idref sırası
        spine_kismi = re.search(r'<spine\b[^>]*>(.*?)</spine>', opf_icerik, re.DOTALL | re.IGNORECASE)
        if not spine_kismi:
            return None

        siradaki: list[str] = []
        for m in re.finditer(r'<itemref\b[^>]*\bidref=["\']([^"\']+)["\']', spine_kismi.group(1), re.IGNORECASE):
            idref = m.group(1)
            href = id_to_href.get(idref)
            if href:
                # OPF klasörüne göreli yolu mutlaklaştır
                tam_yol = opf_klasor + href if not href.startswith("/") else href.lstrip("/")
                siradaki.append(tam_yol)

        return siradaki if siradaki else None
    except Exception:
        return None


def _epub_icerik_dosyalari_bul(epub_zip) -> list[str]:
    """
    EPUB içindeki içerik (bölüm) dosyalarını spine sırasıyla döner.
    OPF/spine okunamazsa dosya adına göre fallback kullanır.
    """
    opf_yolu = _epub_opf_yolu_bul(epub_zip)
    if opf_yolu:
        spine = _epub_spine_sirasi(epub_zip, opf_yolu)
        if spine:
            # ZIP içinde gerçekten var olan dosyaları filtrele
            mevcut = set(epub_zip.namelist())
            return [p for p in spine if p in mevcut]

    # Fallback: dosya adı bazlı filtreleme (eski davranış)
    return sorted([
        n for n in epub_zip.namelist()
        if n.endswith((".html", ".xhtml", ".htm"))
        and "toc" not in n.lower()
        and "nav" not in n.lower()
        and "ncx" not in n.lower()
    ])


class _HtmlMetinCikartici:
    """Basit HTML → düz metin dönüştürücü (html.parser tabanlı)."""
    from html.parser import HTMLParser as _HP

    class _Parser(_HP):
        def __init__(self):
            super().__init__()
            self.metin_parcalari: list[str] = []
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

    @classmethod
    def cevir(cls, html_str: str) -> str:
        p = cls._Parser()
        p.feed(html_str)
        satirlar = "".join(p.metin_parcalari).splitlines()
        temiz = [s.strip() for s in satirlar if s.strip()]
        return "\n\n".join(temiz)


def epub_ice_aktar(
    seri_id: int,
    db_manager: DatabaseManager,
    parent_widget=None,
) -> int:
    """
    Kullanıcıdan bir EPUB dosyası seçmesini ister, içindeki HTML/XHTML
    bölümlerini ayrıştırarak verilen seriye yeni bölümler olarak ekler.

    - OPF/spine sırası kullanılır (kırılgan dosya adı sıralaması yerine).
    - İçerik hash'i ile mükerrer bölüm kontrolü yapılır.
    - Atlanan dosyalar kullanıcıya raporlanır.

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

        eklenen = 0
        atlanan_hashler = 0
        atlanalar: list[tuple[str, str]] = []   # [(dosya_adi, neden)]

        mevcut = db_manager.serinin_bolumlerini_getir(seri_id)
        sonraki_no = max((b.get("bolum_no", 0) for b in mevcut), default=0) + 1

        mevcut_hashler: set[str] = set()
        for b in mevcut:
            ic = (b.get("orijinal_metin") or "").strip()
            if ic:
                mevcut_hashler.add(_icerik_hash(ic))

        with zipfile.ZipFile(dosya, "r") as epub:
            icerik_dosyalari = _epub_icerik_dosyalari_bul(epub)

            for dosya_adi in icerik_dosyalari:
                try:
                    html_bytes = epub.read(dosya_adi)
                    html_str = html_bytes.decode("utf-8", errors="replace")
                    metin = _HtmlMetinCikartici.cevir(html_str)
                    if len(metin.strip()) < 50:
                        atlanalar.append((dosya_adi, "çok kısa içerik (<50 karakter)"))
                        continue

                    h = _icerik_hash(metin)
                    if h in mevcut_hashler:
                        atlanan_hashler += 1
                        atlanalar.append((dosya_adi, "zaten mevcut (mükerrer)"))
                        continue

                    baslik = os.path.splitext(os.path.basename(dosya_adi))[0]
                    baslik = re.sub(r"[-_]", " ", baslik).title()
                    db_manager.bolum_olustur(
                        seri_id=seri_id,
                        bolum_no=sonraki_no,
                        bolum_baslik=baslik,
                        orijinal_metin=metin,
                    )
                    mevcut_hashler.add(h)
                    sonraki_no += 1
                    eklenen += 1
                except Exception as dosya_hatasi:
                    atlanalar.append((dosya_adi, str(dosya_hatasi)[:120]))

        # Özet rapor
        mesaj_parcalari = []
        if eklenen:
            mesaj_parcalari.append(f"{eklenen} bölüm başarıyla içe aktarıldı.")
        if atlanan_hashler:
            mesaj_parcalari.append(f"{atlanan_hashler} bölüm zaten mevcut olduğu için atlandı.")
        if atlanalar:
            detay = "\n".join(
                f"  • {os.path.basename(a)}: {n}" for a, n in atlanalar[:10]
            )
            if len(atlanalar) > 10:
                detay += f"\n  ... ve {len(atlanalar) - 10} dosya daha."
            mesaj_parcalari.append(f"Atlanan dosyalar ({len(atlanalar)}):\n{detay}")

        if not mesaj_parcalari:
            QMessageBox.warning(
                parent_widget,
                "EPUB İçe Aktarım",
                "Bölüm içeriği bulunamadı. Dosya standart EPUB formatında olmayabilir.",
            )
        else:
            seviye = QMessageBox.information if eklenen else QMessageBox.warning
            seviye(
                parent_widget,
                "EPUB İçe Aktarım",
                "\n\n".join(mesaj_parcalari),
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