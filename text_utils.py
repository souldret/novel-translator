"""
Novel Çevirmen — Metin yardımcıları
Uzun bölüm parçalama, sözlük tarama ve kalite kontrolleri.
"""

from __future__ import annotations

import difflib
import re
from typing import Iterable, Optional


# Ortalama model bağlamı için güvenli parça boyutu (karakter)
VARSAYILAN_PARCA_BOYUTU = 5500
MIN_PARCA_BOYUTU = 800


def metni_parcala(metin: str, max_karakter: int = VARSAYILAN_PARCA_BOYUTU) -> list[str]:
    """
    Uzun metni paragraf/cümle sınırlarında parçalara böler.
    max_karakter altındaki metinler tek parça olarak döner.
    """
    if not metin or not metin.strip():
        return []
    metin = metin.strip()
    if len(metin) <= max_karakter:
        return [metin]

    # Önce çift satır sonu ile paragraflara böl
    paragraflar = re.split(r"\n\s*\n", metin)
    parcalar: list[str] = []
    mevcut: list[str] = []
    mevcut_uzunluk = 0

    def _flush():
        nonlocal mevcut, mevcut_uzunluk
        if mevcut:
            parcalar.append("\n\n".join(mevcut).strip())
            mevcut = []
            mevcut_uzunluk = 0

    for p in paragraflar:
        p = p.strip()
        if not p:
            continue
        ek = len(p) + (2 if mevcut else 0)
        if mevcut and mevcut_uzunluk + ek > max_karakter:
            _flush()
        # Tek paragraf limitten büyükse cümlelere böl
        if len(p) > max_karakter:
            _flush()
            for cumle_parcasi in _cumlelere_bol(p, max_karakter):
                parcalar.append(cumle_parcasi)
            continue
        mevcut.append(p)
        mevcut_uzunluk += ek

    _flush()
    return [p for p in parcalar if p]


def _cumlelere_bol(metin: str, max_karakter: int) -> list[str]:
    """Paragrafı cümle sınırlarında böler; gerekirse sert keser."""
    cumleler = re.split(r"(?<=[.!?。！？…])\s+", metin)
    parcalar: list[str] = []
    mevcut = ""
    for c in cumleler:
        if not c:
            continue
        aday = f"{mevcut} {c}".strip() if mevcut else c
        if len(aday) <= max_karakter:
            mevcut = aday
            continue
        if mevcut:
            parcalar.append(mevcut)
        if len(c) <= max_karakter:
            mevcut = c
        else:
            # Sert kesim
            for i in range(0, len(c), max_karakter):
                parcalar.append(c[i:i + max_karakter])
            mevcut = ""
    if mevcut:
        parcalar.append(mevcut)
    return parcalar


def parcalari_birlestir(parcalar: Iterable[str]) -> str:
    """Çevrilmiş parçaları birleştirir."""
    temiz = [p.strip() for p in parcalar if p and p.strip()]
    return "\n\n".join(temiz)


def sozlukte_eslesenleri_bul(metin: str, terimler: list[dict]) -> list[dict]:
    """
    Metinde geçen sözlük terimlerini bulur.
    Uzun terimler önce denenir (greedy); böylece kısa alt-eşleşmeler
    uzun ifadeyi gölgelemez. Büyük/küçük harf duyarsızdır.
    """
    if not metin or not terimler:
        return []

    metin_lower = metin.lower()
    # Uzun terim önce
    sirali = sorted(
        terimler,
        key=lambda t: len((t.get("orijinal_terim") or "")),
        reverse=True,
    )
    bulunan: list[dict] = []
    isgal_edilen: list[tuple[int, int]] = []  # (start, end) aralıkları

    for terim in sirali:
        orijinal = (terim.get("orijinal_terim") or "").strip()
        if not orijinal:
            continue
        hedef = orijinal.lower()
        bas = 0
        eslesti = False
        while True:
            idx = metin_lower.find(hedef, bas)
            if idx < 0:
                break
            bit = idx + len(hedef)
            # Önceki daha uzun eşleşmenin içinde mi?
            ic_ice = any(s <= idx and bit <= e for s, e in isgal_edilen)
            if not ic_ice:
                isgal_edilen.append((idx, bit))
                eslesti = True
                break
            bas = idx + 1
        if eslesti:
            bulunan.append(terim)

    # Orijinal listedeki sıraya yakın tut (orijinal_terim alfabetik)
    bulunan.sort(key=lambda t: (t.get("orijinal_terim") or "").lower())
    return bulunan


def sozluk_uyum_kontrolu(
    cevrilmis_metin: str,
    sozluk_terimleri: list[dict],
) -> dict:
    """
    Çeviride zorunlu sözlük karşılıklarının kullanılıp kullanılmadığını kontrol eder.

    Döndürür:
        {
          "toplam": int,
          "uyumlu": list[dict],
          "eksik": list[dict],   # cevrilmis_terim çeviride yok
        }
    """
    if not sozluk_terimleri:
        return {"toplam": 0, "uyumlu": [], "eksik": []}

    ceviri_lower = (cevrilmis_metin or "").lower()
    uyumlu = []
    eksik = []
    for t in sozluk_terimleri:
        hedef = (t.get("cevrilmis_terim") or "").strip()
        if not hedef:
            continue
        if hedef.lower() in ceviri_lower:
            uyumlu.append(t)
        else:
            eksik.append(t)
    return {
        "toplam": len(uyumlu) + len(eksik),
        "uyumlu": uyumlu,
        "eksik": eksik,
    }


def metin_diff_html(eski: str, yeni: str) -> str:
    """İki metin arasındaki farkı basit HTML olarak üretir."""
    eski_satirlar = (eski or "").splitlines()
    yeni_satirlar = (yeni or "").splitlines()
    diff = difflib.unified_diff(
        eski_satirlar, yeni_satirlar,
        fromfile="Önceki", tofile="Yeni", lineterm="",
    )
    satirlar = []
    for line in diff:
        guvenli = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if line.startswith("+++") or line.startswith("---"):
            satirlar.append(f'<div style="color:#c9a8e8;font-weight:700;">{guvenli}</div>')
        elif line.startswith("@@"):
            satirlar.append(f'<div style="color:#6b5a7a;">{guvenli}</div>')
        elif line.startswith("+"):
            satirlar.append(f'<div style="color:#a0f0b0;background:#0a1a0f;">{guvenli}</div>')
        elif line.startswith("-"):
            satirlar.append(f'<div style="color:#f0a0b0;background:#1a0a10;">{guvenli}</div>')
        else:
            satirlar.append(f'<div style="color:#e8e0f0;">{guvenli}</div>')
    if not satirlar:
        return '<div style="color:#6b5a7a;">Fark yok.</div>'
    return (
        '<div style="font-family:Consolas,monospace;font-size:12px;'
        'white-space:pre-wrap;line-height:1.45;">'
        + "".join(satirlar)
        + "</div>"
    )


def metin_icerisinde_ara(metin: str, sorgu: str, baslangic: int = 0) -> Optional[int]:
    """Büyük/küçük harf duyarsız arama; bulunursa indeks, yoksa None."""
    if not metin or not sorgu:
        return None
    idx = metin.lower().find(sorgu.lower(), max(0, baslangic))
    return idx if idx >= 0 else None
