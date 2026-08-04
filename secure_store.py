"""
Novel Çevirmen — API anahtarı güvenli depolama.

Windows'ta DPAPI (CryptProtectData) kullanır; diğer platformlarda
makineye özgü türetilmiş anahtarla XOR + Base64 şifreleme uygular.

Depolanan biçim:  enc:v1:<base64>
Eski düz metin anahtarlar okunurken otomatik kabul edilir (geriye uyum).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger("novel_cevirmen.secure_store")

_PREFIX = "enc:v1:"


def _makine_anahtari() -> bytes:
    """Makine/kullanıcıya özgü 32 baytlık anahtar üretir."""
    parcalar = [
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("HOSTNAME", ""),
        "NovelCevirmen.secure.v1",
    ]
    return hashlib.sha256("|".join(parcalar).encode("utf-8")).digest()


def _xor_sifrele(veri: bytes, anahtar: bytes) -> bytes:
    return bytes(b ^ anahtar[i % len(anahtar)] for i, b in enumerate(veri))


# ── Windows DPAPI ────────────────────────────────────────────────────────────

def _dpapi_sifrele(duz: bytes) -> Optional[bytes]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = DATA_BLOB(len(duz), ctypes.create_string_buffer(duz, len(duz)))
        blob_out = DATA_BLOB()

        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return None

        try:
            sifreli = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return sifreli
    except Exception as hata:
        logger.debug("DPAPI şifreleme başarısız: %s", hata)
        return None


def _dpapi_coz(sifreli: bytes) -> Optional[bytes]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = DATA_BLOB(len(sifreli), ctypes.create_string_buffer(sifreli, len(sifreli)))
        blob_out = DATA_BLOB()

        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return None

        try:
            duz = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return duz
    except Exception as hata:
        logger.debug("DPAPI çözme başarısız: %s", hata)
        return None


# ── Genel API ────────────────────────────────────────────────────────────────

def sifrele(duz_metin: str) -> str:
    """
    API anahtarını güvenli biçime çevirir.
    Zaten şifreliyse olduğu gibi döner. Boş string için boş döner.
    """
    if not duz_metin:
        return duz_metin
    if duz_metin.startswith(_PREFIX):
        return duz_metin

    ham = duz_metin.encode("utf-8")
    dpapi = _dpapi_sifrele(ham)
    if dpapi is not None:
        # DPAPI bayraklı: enc:v1:d:<b64>
        return _PREFIX + "d:" + base64.urlsafe_b64encode(dpapi).decode("ascii")

    # Yerel makine anahtarı
    sifreli = _xor_sifrele(ham, _makine_anahtari())
    return _PREFIX + "x:" + base64.urlsafe_b64encode(sifreli).decode("ascii")


def coz(sakli: str) -> str:
    """
    Saklı API anahtarını düz metne çevirir.
    Şifreli değilse (eski kayıt) olduğu gibi döner.
    """
    if not sakli:
        return sakli
    if not sakli.startswith(_PREFIX):
        return sakli  # legacy plaintext

    govde = sakli[len(_PREFIX):]
    try:
        if govde.startswith("d:"):
            ham = base64.urlsafe_b64decode(govde[2:].encode("ascii"))
            duz = _dpapi_coz(ham)
            if duz is None:
                logger.error("DPAPI ile API anahtarı çözülemedi.")
                return ""
            return duz.decode("utf-8")
        if govde.startswith("x:"):
            ham = base64.urlsafe_b64decode(govde[2:].encode("ascii"))
            return _xor_sifrele(ham, _makine_anahtari()).decode("utf-8")
        # Eski biçim: enc:v1:<b64> (XOR varsay)
        ham = base64.urlsafe_b64decode(govde.encode("ascii"))
        return _xor_sifrele(ham, _makine_anahtari()).decode("utf-8")
    except Exception as hata:
        logger.error("API anahtarı çözülemedi: %s", hata)
        return ""


def sifreli_mi(deger: str) -> bool:
    return bool(deger) and deger.startswith(_PREFIX)
