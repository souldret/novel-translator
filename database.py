"""
Novel Çevirmen - Veritabanı Yöneticisi
SQLite veritabanı işlemlerini yöneten ana modül.
Veritabanı dosyası: novel_cevirmen.db (uygulama klasöründe)
"""

import sqlite3
import json
import os
import hashlib
import logging
import shutil
from datetime import datetime
from typing import Optional

from secure_store import sifrele as _api_sifrele, coz as _api_coz, sifreli_mi as _api_sifreli_mi
from text_utils import sozlukte_eslesenleri_bul


# Veritabanı dosyasının yolu — bu dosyayla aynı klasörde oluşturulur
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novel_cevirmen.db")

# Mevcut şema sürümü — yeni migrasyon ekleyince artır
SCHEMA_SURUMU = 4  # v4: sozluk/sozluk_oneri üzerinde performans index'leri

# Modül düzeyinde logger
logger = logging.getLogger("novel_cevirmen.database")


class DatabaseManager:
    """
    Novel Çevirmen uygulamasının tüm veritabanı işlemlerini yöneten sınıf.
    Tüm metodlar bağlantıyı context manager ile açıp kapatır;
    kalıcı bir bağlantı tutulmaz.
    """

    def __init__(self, db_yolu: str = DB_YOLU):
        self.db_yolu = db_yolu
        # Uygulama ilk çalıştığında tabloları oluştur ve migrasyonları uygula
        self._tablolari_olustur()
        self._migrasyonlari_uygula()

    # -------------------------------------------------------------------------
    # YARDIMCI METODLAR
    # -------------------------------------------------------------------------

    def _baglanti_ac(self) -> sqlite3.Connection:
        """
        Yeni bir SQLite bağlantısı açar.
        - row_factory ile sorgu sonuçları dict olarak döner.
        - Foreign key desteği her bağlantıda açıkça etkinleştirilir.
        """
        conn = sqlite3.connect(self.db_yolu)
        conn.row_factory = sqlite3.Row          # Sütun adıyla erişim için
        conn.execute("PRAGMA foreign_keys = ON") # Yabancı anahtar kısıtlamaları aktif
        return conn

    def _satiri_sozluge_cevir(self, satir) -> Optional[dict]:
        """sqlite3.Row nesnesini Python dict'e dönüştürür."""
        if satir is None:
            return None
        return dict(satir)

    def _satirlari_listeye_cevir(self, satirlar) -> list:
        """sqlite3.Row nesnelerinin listesini dict listesine dönüştürür."""
        return [dict(satir) for satir in satirlar]

    # -------------------------------------------------------------------------
    # VERİTABANI ŞEMASI — İLK ÇALIŞMADA TABLOLAR OLUŞTURULUR
    # -------------------------------------------------------------------------

    def _tablolari_olustur(self):
        """
        Uygulama ilk çalıştığında gerekli tüm tabloları oluşturur.
        Tablolar zaten varsa hiçbir şey yapmaz (IF NOT EXISTS).
        """
        try:
            with self._baglanti_ac() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS seriler (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        baslik          TEXT NOT NULL,
                        kaynak_dil      TEXT NOT NULL,
                        hedef_dil       TEXT NOT NULL,
                        aciklama        TEXT,
                        olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bolumler (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        seri_id          INTEGER NOT NULL REFERENCES seriler(id) ON DELETE CASCADE,
                        bolum_no         INTEGER NOT NULL,
                        bolum_baslik     TEXT,
                        orijinal_metin   TEXT,
                        cevrilmis_metin  TEXT,
                        durum            TEXT DEFAULT 'beklemede',
                        onceki_ceviri    TEXT,
                        olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sozluk (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        seri_id             INTEGER NOT NULL REFERENCES seriler(id) ON DELETE CASCADE,
                        orijinal_terim      TEXT NOT NULL,
                        cevrilmis_terim     TEXT NOT NULL,
                        kategori            TEXT DEFAULT 'diger',
                        entity_type         TEXT DEFAULT 'PERSON',
                        notlar              TEXT,
                        confidence          REAL DEFAULT 1.0,
                        occurrences         INTEGER DEFAULT 1,
                        first_chapter       INTEGER DEFAULT 0,
                        last_chapter        INTEGER DEFAULT 0,
                        locked              INTEGER DEFAULT 0,
                        oneri_durumu        TEXT DEFAULT 'onaylandi',
                        normalize_key       TEXT,
                        olusturma_tarihi    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sozluk_oneri (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        seri_id          INTEGER NOT NULL REFERENCES seriler(id) ON DELETE CASCADE,
                        orijinal_terim   TEXT NOT NULL,
                        entity_type      TEXT DEFAULT 'PERSON',
                        confidence       REAL DEFAULT 0.0,
                        occurrences      INTEGER DEFAULT 1,
                        bolum_no         INTEGER DEFAULT 0,
                        normalize_key    TEXT,
                        durum            TEXT DEFAULT 'bekliyor',
                        olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_ayarlar (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        saglayici        TEXT NOT NULL,
                        model_adi        TEXT NOT NULL,
                        api_anahtari     TEXT NOT NULL,
                        aktif            INTEGER DEFAULT 0,
                        ekstra_konfig    TEXT,
                        olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS db_version (
                        surumu INTEGER PRIMARY KEY
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ceviri_onbellegi (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        metin_hash       TEXT NOT NULL,
                        saglayici        TEXT NOT NULL,
                        model_adi        TEXT NOT NULL,
                        kaynak_dil       TEXT NOT NULL,
                        hedef_dil        TEXT NOT NULL,
                        cevrilmis_metin  TEXT NOT NULL,
                        olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(metin_hash, saglayici, model_adi, kaynak_dil, hedef_dil)
                    )
                """)

                conn.commit()
                logger.info("Tablolar başarıyla oluşturuldu veya zaten mevcut.")

        except sqlite3.Error as hata:
            logger.error(f"Tablolar oluşturulamadı: {hata}")

    def _migrasyonlari_uygula(self):
        """
        Mevcut DB sürümünü kontrol eder ve gerekli migrasyonları sırayla uygular.
        Her migrasyon idempotent'tir (birden fazla kez çalıştırılabilir).
        """
        try:
            with self._baglanti_ac() as conn:
                satir = conn.execute(
                    "SELECT surumu FROM db_version ORDER BY surumu DESC LIMIT 1"
                ).fetchone()
                mevcut_surum = satir[0] if satir else 0

                if mevcut_surum >= SCHEMA_SURUMU:
                    return  # Zaten güncel

                # Migrasyon v1 → v2: bolumler'e onceki_ceviri kolonu ekle
                if mevcut_surum < 2:
                    try:
                        conn.execute(
                            "ALTER TABLE bolumler ADD COLUMN onceki_ceviri TEXT"
                        )
                        logger.info("v2: 'onceki_ceviri' kolonu eklendi.")
                    except sqlite3.OperationalError:
                        pass  # Kolon zaten mevcut

                # Migrasyon v2 → v3: sozluk tablosuna story-consistency alanları ekle
                if mevcut_surum < 3:
                    v3_kolonlar = [
                        ("entity_type",   "TEXT DEFAULT 'PERSON'"),
                        ("confidence",    "REAL DEFAULT 1.0"),
                        ("occurrences",   "INTEGER DEFAULT 1"),
                        ("first_chapter", "INTEGER DEFAULT 0"),
                        ("last_chapter",  "INTEGER DEFAULT 0"),
                        ("locked",        "INTEGER DEFAULT 0"),
                        ("oneri_durumu",  "TEXT DEFAULT 'onaylandi'"),
                        ("normalize_key", "TEXT"),
                    ]
                    for kolon_adi, kolon_tanim in v3_kolonlar:
                        try:
                            conn.execute(
                                f"ALTER TABLE sozluk ADD COLUMN {kolon_adi} {kolon_tanim}"
                            )
                            logger.info(f"v3: sozluk.{kolon_adi} kolonu eklendi.")
                        except sqlite3.OperationalError:
                            pass  # Kolon zaten mevcut

                    # Öneri tablosunu oluştur (yeni tablo, CREATE IF NOT EXISTS)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS sozluk_oneri (
                            id               INTEGER PRIMARY KEY AUTOINCREMENT,
                            seri_id          INTEGER NOT NULL REFERENCES seriler(id) ON DELETE CASCADE,
                            orijinal_terim   TEXT NOT NULL,
                            entity_type      TEXT DEFAULT 'PERSON',
                            confidence       REAL DEFAULT 0.0,
                            occurrences      INTEGER DEFAULT 1,
                            bolum_no         INTEGER DEFAULT 0,
                            normalize_key    TEXT,
                            durum            TEXT DEFAULT 'bekliyor',
                            olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    # Mevcut kayıtlarda normalize_key doldur
                    from story_dict import _normalize_key as _nk
                    satirlar = conn.execute(
                        "SELECT id, orijinal_terim FROM sozluk WHERE normalize_key IS NULL"
                    ).fetchall()
                    for satir in satirlar:
                        conn.execute(
                            "UPDATE sozluk SET normalize_key = ? WHERE id = ?",
                            (_nk(satir["orijinal_terim"]), satir["id"])
                        )
                    logger.info(f"v3: {len(satirlar)} sözlük kaydı normalize edildi.")

                # Migrasyon v3 → v4: sozluk ve sozluk_oneri üzerinde index'ler
                if mevcut_surum < 4:
                    index_tanimlari = [
                        # sozluk aramaları: seri_id + normalize_key (sozluk_terimi_ekle, getir)
                        ("CREATE INDEX IF NOT EXISTS idx_sozluk_seri_nk "
                         "ON sozluk (seri_id, normalize_key)"),
                        # sozluk aramaları: seri_id + oneri_durumu (sozluk_terimlerini_getir filtresi)
                        ("CREATE INDEX IF NOT EXISTS idx_sozluk_seri_oneri "
                         "ON sozluk (seri_id, oneri_durumu)"),
                        # sozluk_oneri aramaları: seri_id + durum + normalize_key (oneri_ekle/getir)
                        ("CREATE INDEX IF NOT EXISTS idx_sozluk_oneri_seri_durum_nk "
                         "ON sozluk_oneri (seri_id, durum, normalize_key)"),
                    ]
                    for ddl in index_tanimlari:
                        try:
                            conn.execute(ddl)
                            logger.info(f"v4: Index oluşturuldu: {ddl.split('idx_')[1].split(' ')[0]}")
                        except sqlite3.OperationalError as e:
                            logger.warning(f"v4: Index oluşturulamadı (zaten var?): {e}")

                conn.execute(
                    "INSERT OR REPLACE INTO db_version (surumu) VALUES (?)",
                    (SCHEMA_SURUMU,)
                )
                conn.commit()
                logger.info(f"Şema sürümü {SCHEMA_SURUMU}'a güncellendi.")

        except sqlite3.Error as hata:
            logger.error(f"Migrasyon başarısız: {hata}")

    def yedekle(self) -> Optional[str]:
        """
        Veritabanını .bak uzantılı tarih damgalı dosyaya yedekler.
        Yıkıcı işlemlerden (seri silme vb.) önce çağrılır.

        Döndürür:
            Yedek dosyasının tam yolu; hata durumunda None.
        """
        try:
            zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
            yedek_yolu = f"{self.db_yolu}.{zaman}.bak"
            shutil.copy2(self.db_yolu, yedek_yolu)
            logger.info(f"Veritabanı yedeklendi: {yedek_yolu}")
            return yedek_yolu
        except Exception as hata:
            logger.error(f"Yedekleme başarısız: {hata}")
            return None

    # =========================================================================
    # SERİ METODLARI
    # =========================================================================

    def seri_olustur(
        self,
        baslik: str,
        kaynak_dil: str,
        hedef_dil: str,
        aciklama: str = None
    ) -> Optional[int]:
        """Yeni bir roman serisi oluşturur. Döndürür: yeni serinin id'si."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    """
                    INSERT INTO seriler (baslik, kaynak_dil, hedef_dil, aciklama)
                    VALUES (?, ?, ?, ?)
                    """,
                    (baslik, kaynak_dil, hedef_dil, aciklama)
                )
                conn.commit()
                yeni_id = imleç.lastrowid
                logger.info(f"'{baslik}' serisi oluşturuldu (id={yeni_id}).")
                return yeni_id

        except sqlite3.Error as hata:
            logger.error(f"Seri oluşturulamadı: {hata}")
            return None

    def tum_serileri_getir(self) -> list:
        """Veritabanındaki tüm serileri döndürür (oluşturma tarihine göre azalan)."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    "SELECT * FROM seriler ORDER BY olusturma_tarihi DESC"
                )
                return self._satirlari_listeye_cevir(imleç.fetchall())

        except sqlite3.Error as hata:
            logger.error(f"Seriler getirilemedi: {hata}")
            return []

    def seri_getir(self, seri_id: int) -> Optional[dict]:
        """Belirtilen id'ye sahip seriyi döndürür; bulunamazsa None."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    "SELECT * FROM seriler WHERE id = ?",
                    (seri_id,)
                )
                return self._satiri_sozluge_cevir(imleç.fetchone())

        except sqlite3.Error as hata:
            logger.error(f"Seri getirilemedi (id={seri_id}): {hata}")
            return None

    def seri_guncelle(
        self,
        seri_id: int,
        baslik: str,
        kaynak_dil: str,
        hedef_dil: str,
        aciklama: str = None
    ) -> bool:
        """Mevcut bir serinin bilgilerini günceller. Döndürür: True/False."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    """
                    UPDATE seriler
                    SET baslik = ?, kaynak_dil = ?, hedef_dil = ?, aciklama = ?
                    WHERE id = ?
                    """,
                    (baslik, kaynak_dil, hedef_dil, aciklama, seri_id)
                )
                conn.commit()
                logger.info(f"Seri güncellendi (id={seri_id}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Seri güncellenemedi (id={seri_id}): {hata}")
            return False

    def seri_sil(self, seri_id: int) -> bool:
        """
        Belirtilen seriyi ve ona bağlı TÜM bölümleri ve sözlük girişlerini siler.
        Foreign key cascade silme yerine açıkça üç tablo da temizlenir.
        """
        try:
            with self._baglanti_ac() as conn:
                conn.execute("DELETE FROM sozluk   WHERE seri_id = ?", (seri_id,))
                conn.execute("DELETE FROM bolumler WHERE seri_id = ?", (seri_id,))
                conn.execute("DELETE FROM seriler  WHERE id = ?",      (seri_id,))
                conn.commit()
                logger.info(f"Seri ve ilişkili veriler silindi (id={seri_id}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Seri silinemedi (id={seri_id}): {hata}")
            return False

    # =========================================================================
    # BÖLÜM METODLARI
    # =========================================================================

    def bolum_olustur(
        self,
        seri_id: int,
        bolum_no: int,
        bolum_baslik: str = None,
        orijinal_metin: str = None
    ) -> Optional[int]:
        """Bir seriye yeni bölüm ekler. Döndürür: yeni bölümün id'si."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    """
                    INSERT INTO bolumler
                        (seri_id, bolum_no, bolum_baslik, orijinal_metin)
                    VALUES (?, ?, ?, ?)
                    """,
                    (seri_id, bolum_no, bolum_baslik, orijinal_metin)
                )
                conn.commit()
                yeni_id = imleç.lastrowid
                logger.info(f"Bölüm {bolum_no} oluşturuldu (id={yeni_id}, seri_id={seri_id}).")
                return yeni_id

        except sqlite3.Error as hata:
            logger.error(f"Bölüm oluşturulamadı: {hata}")
            return None

    def bolum_getir(self, bolum_id: int) -> Optional[dict]:
        """Belirtilen id'ye sahip bölümü döndürür; bulunamazsa None."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    "SELECT * FROM bolumler WHERE id = ?",
                    (bolum_id,)
                )
                return self._satiri_sozluge_cevir(imleç.fetchone())

        except sqlite3.Error as hata:
            logger.error(f"Bölüm getirilemedi (id={bolum_id}): {hata}")
            return None

    def serinin_bolumlerini_getir(self, seri_id: int) -> list:
        """
        Bir seriye ait tüm bölümleri bölüm numarasına göre artan sırayla döndürür.
        """
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    """
                    SELECT * FROM bolumler
                    WHERE seri_id = ?
                    ORDER BY bolum_no ASC
                    """,
                    (seri_id,)
                )
                return self._satirlari_listeye_cevir(imleç.fetchall())

        except sqlite3.Error as hata:
            logger.error(f"Bölümler getirilemedi (seri_id={seri_id}): {hata}")
            return []

    def seri_bolum_sayilarini_getir(self) -> dict:
        """
        Tüm serilerin bölüm sayısını tek SQL sorgusunda döndürür.
        _serileri_yukle içinde her seri için ayrı sorgu atmaktan kaçınır.

        Döndürür:
            {seri_id: bolum_sayisi} biçiminde dict
        """
        try:
            with self._baglanti_ac() as conn:
                rows = conn.execute(
                    "SELECT seri_id, COUNT(*) as sayi FROM bolumler GROUP BY seri_id"
                ).fetchall()
            return {r["seri_id"]: r["sayi"] for r in rows}
        except sqlite3.Error as hata:
            logger.error(f"Bölüm sayıları getirilemedi: {hata}")
            return {}

    def bolum_guncelle(
        self,
        bolum_id: int,
        bolum_baslik: str = None,
        orijinal_metin: str = None,
        cevrilmis_metin: str = None,
        durum: str = None
    ) -> bool:
        """
        Mevcut bir bölümün içeriğini ve durumunu günceller.
        Yalnızca None olmayan alanlar güncellenir.
        """
        try:
            with self._baglanti_ac() as conn:
                mevcut = conn.execute(
                    "SELECT * FROM bolumler WHERE id = ?", (bolum_id,)
                ).fetchone()
                if not mevcut:
                    logger.error(f"Bölüm bulunamadı (id={bolum_id}).")
                    return False

                yeni_baslik   = bolum_baslik   if bolum_baslik   is not None else mevcut["bolum_baslik"]
                yeni_orijinal = orijinal_metin if orijinal_metin is not None else mevcut["orijinal_metin"]
                yeni_ceviri   = cevrilmis_metin if cevrilmis_metin is not None else mevcut["cevrilmis_metin"]
                yeni_durum    = durum          if durum          is not None else mevcut["durum"]

                conn.execute(
                    """
                    UPDATE bolumler
                    SET bolum_baslik = ?, orijinal_metin = ?,
                        cevrilmis_metin = ?, durum = ?
                    WHERE id = ?
                    """,
                    (yeni_baslik, yeni_orijinal, yeni_ceviri, yeni_durum, bolum_id)
                )
                conn.commit()
                logger.info(f"Bölüm güncellendi (id={bolum_id}, durum={yeni_durum}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Bölüm güncellenemedi (id={bolum_id}): {hata}")
            return False

    def bolum_sil(self, bolum_id: int) -> bool:
        """Belirtilen bölümü siler."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute("DELETE FROM bolumler WHERE id = ?", (bolum_id,))
                conn.commit()
                logger.info(f"Bölüm silindi (id={bolum_id}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Bölüm silinemedi (id={bolum_id}): {hata}")
            return False

    def onceki_cevirileri_kaydet(self, bolum_id: int, ceviri: str) -> bool:
        """Mevcut çeviriyi onceki_ceviri alanına taşıyarak geçmişe ekler."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    "UPDATE bolumler SET onceki_ceviri = ? WHERE id = ?",
                    (ceviri, bolum_id)
                )
                conn.commit()
                return True
        except sqlite3.Error as hata:
            logger.error(f"Önceki çeviri kaydedilemedi (id={bolum_id}): {hata}")
            return False

    # =========================================================================
    # SÖZLÜK METODLARI — Story Consistency Dictionary
    # =========================================================================

    def sozluk_terimi_ekle(
        self,
        seri_id: int,
        orijinal_terim: str,
        cevrilmis_terim: str,
        kategori: str = "diger",
        notlar: str = None,
        # Story-consistency ek alanlar (isteğe bağlı)
        entity_type: str = "PERSON",
        confidence: float = 1.0,
        occurrences: int = 1,
        first_chapter: int = 0,
        last_chapter: int = 0,
        locked: bool = False,
        oneri_durumu: str = "onaylandi",
    ) -> Optional[int]:
        """Sözlüğe yeni bir terim ekler veya günceller.
        Kilitli kayıtlar sadece cevrilmis_terim güncelleme ile dokunulabilir (AI tarafından güncellenmez).
        """
        if not orijinal_terim or not cevrilmis_terim:
            logger.error("Orijinal veya çevrilmiş terim boş olamaz.")
            return None

        from story_dict import _normalize_key as _nk
        nkey = _nk(orijinal_terim)

        try:
            with self._baglanti_ac() as conn:
                mevcut = conn.execute(
                    "SELECT id, locked FROM sozluk WHERE seri_id = ? AND normalize_key = ?",
                    (seri_id, nkey)
                ).fetchone()

                if mevcut:
                    if mevcut["locked"] and locked is False:
                        # Kilitli giriş: yalnızca occurrences ve last_chapter güncellenir
                        conn.execute(
                            """UPDATE sozluk
                               SET occurrences = occurrences + ?, last_chapter = ?
                               WHERE id = ?""",
                            (occurrences, last_chapter, mevcut["id"])
                        )
                    else:
                        conn.execute(
                            """UPDATE sozluk
                               SET cevrilmis_terim = ?, kategori = ?, entity_type = ?,
                                   notlar = ?, confidence = ?, occurrences = occurrences + ?,
                                   last_chapter = ?, locked = ?, oneri_durumu = ?
                               WHERE id = ?""",
                            (cevrilmis_terim, kategori, entity_type,
                             notlar, confidence, occurrences,
                             last_chapter, int(locked), oneri_durumu, mevcut["id"])
                        )
                    conn.commit()
                    logger.info(f"Sözlük terimi güncellendi: '{orijinal_terim}'.")
                    return mevcut["id"]
                else:
                    imleç = conn.execute(
                        """INSERT INTO sozluk
                               (seri_id, orijinal_terim, cevrilmis_terim, kategori,
                                entity_type, notlar, confidence, occurrences,
                                first_chapter, last_chapter, locked, oneri_durumu, normalize_key)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (seri_id, orijinal_terim, cevrilmis_terim, kategori,
                         entity_type, notlar, confidence, occurrences,
                         first_chapter, last_chapter, int(locked), oneri_durumu, nkey)
                    )
                    conn.commit()
                    yeni_id = imleç.lastrowid
                    logger.info(f"Sözlük terimi eklendi: '{orijinal_terim}' (id={yeni_id}).")
                    return yeni_id

        except sqlite3.Error as hata:
            logger.error(f"Sözlük terimi eklenemedi: {hata}")
            return None

    def sozluk_terimlerini_getir(self, seri_id: int, sadece_onaylandi: bool = True) -> list:
        """Bir seriye ait sözlük terimlerini döndürür.
        sadece_onaylandi=True ise yalnızca onaylanmış (locked veya onaylandi durumlu) kayıtlar.
        """
        try:
            with self._baglanti_ac() as conn:
                if sadece_onaylandi:
                    imleç = conn.execute(
                        """SELECT * FROM sozluk
                           WHERE seri_id = ? AND oneri_durumu IN ('onaylandi', 'kilitli')
                           ORDER BY orijinal_terim ASC""",
                        (seri_id,)
                    )
                else:
                    imleç = conn.execute(
                        "SELECT * FROM sozluk WHERE seri_id = ? ORDER BY orijinal_terim ASC",
                        (seri_id,)
                    )
                return self._satirlari_listeye_cevir(imleç.fetchall())

        except sqlite3.Error as hata:
            logger.error(f"Sözlük terimleri getirilemedi (seri_id={seri_id}): {hata}")
            return []

    def sozluk_terimi_kilitle(self, girdi_id: int, kilitli: bool = True) -> bool:
        """Bir sözlük girişini kilitler veya kilidini açar."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    "UPDATE sozluk SET locked = ?, oneri_durumu = ? WHERE id = ?",
                    (int(kilitli), "kilitli" if kilitli else "onaylandi", girdi_id)
                )
                conn.commit()
                return True
        except sqlite3.Error as hata:
            logger.error(f"Kilit işlemi başarısız (id={girdi_id}): {hata}")
            return False

    def sozluk_occurrence_guncelle(self, girdi_id: int, bolum_no: int) -> bool:
        """Bir terimin geçiş sayısını ve son_bölümü günceller."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    "UPDATE sozluk SET occurrences = occurrences + 1, last_chapter = ? WHERE id = ?",
                    (bolum_no, girdi_id)
                )
                conn.commit()
                return True
        except sqlite3.Error as hata:
            logger.error(f"Occurrence güncellenemedi (id={girdi_id}): {hata}")
            return False

    # ── Öneri yönetimi ────────────────────────────────────────────────────────

    def oneri_ekle(
        self,
        seri_id: int,
        orijinal_terim: str,
        entity_type: str = "PERSON",
        confidence: float = 0.65,
        occurrences: int = 1,
        bolum_no: int = 0,
    ) -> Optional[int]:
        """Yeni otomatik öneri ekler. Aynı terim mevcutsa günceller."""
        from story_dict import _normalize_key as _nk
        nkey = _nk(orijinal_terim)
        try:
            with self._baglanti_ac() as conn:
                mevcut = conn.execute(
                    "SELECT id FROM sozluk_oneri WHERE seri_id = ? AND normalize_key = ? AND durum = 'bekliyor'",
                    (seri_id, nkey)
                ).fetchone()
                if mevcut:
                    conn.execute(
                        "UPDATE sozluk_oneri SET occurrences = occurrences + ?, confidence = ? WHERE id = ?",
                        (occurrences, confidence, mevcut["id"])
                    )
                    conn.commit()
                    return mevcut["id"]
                else:
                    imleç = conn.execute(
                        """INSERT INTO sozluk_oneri
                               (seri_id, orijinal_terim, entity_type, confidence, occurrences, bolum_no, normalize_key)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (seri_id, orijinal_terim, entity_type, confidence, occurrences, bolum_no, nkey)
                    )
                    conn.commit()
                    return imleç.lastrowid
        except sqlite3.Error as hata:
            logger.error(f"Öneri eklenemedi: {hata}")
            return None

    def oneri_ekle_toplu(self, seri_id: int, adaylar: list[dict]) -> int:
        """
        Birden fazla öneriyi tek bir transaction ile ekler/günceller.
        Tekli oneri_ekle() çağrıları yerine bu metodu kullan (46x daha hızlı).

        adaylar: [{"phrase", "entity_type", "confidence", "frequency", "bolum_no"}, ...]
        Döndürür: eklenen/güncellenen toplam kayıt sayısı.
        """
        if not adaylar:
            return 0

        from story_dict import _normalize_key as _nk

        eklenen = 0
        try:
            with self._baglanti_ac() as conn:
                # Mevcut bekleyen önerileri tek sorguda al
                mevcut_map: dict[str, int] = {}
                satirlar = conn.execute(
                    "SELECT id, normalize_key FROM sozluk_oneri WHERE seri_id = ? AND durum = 'bekliyor'",
                    (seri_id,)
                ).fetchall()
                for s in satirlar:
                    mevcut_map[s["normalize_key"]] = s["id"]

                insert_rows = []
                update_rows = []

                for aday in adaylar:
                    nkey = _nk(aday["phrase"])
                    occ  = aday.get("frequency", 1)
                    conf = aday.get("confidence", 0.65)
                    if nkey in mevcut_map:
                        update_rows.append((occ, conf, mevcut_map[nkey]))
                    else:
                        insert_rows.append((
                            seri_id,
                            aday["phrase"],
                            aday.get("entity_type", "PERSON"),
                            conf,
                            occ,
                            aday.get("bolum_no", 0),
                            nkey,
                        ))
                        mevcut_map[nkey] = -1  # Sonraki adayda duplicate önle

                if insert_rows:
                    conn.executemany(
                        """INSERT INTO sozluk_oneri
                               (seri_id, orijinal_terim, entity_type, confidence,
                                occurrences, bolum_no, normalize_key)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        insert_rows,
                    )
                if update_rows:
                    conn.executemany(
                        "UPDATE sozluk_oneri SET occurrences = occurrences + ?, confidence = ? WHERE id = ?",
                        update_rows,
                    )
                conn.commit()
                eklenen = len(insert_rows) + len(update_rows)
                logger.info(f"Toplu öneri eklendi/güncellendi: {eklenen} kayıt (seri_id={seri_id}).")
        except sqlite3.Error as hata:
            logger.error(f"Toplu öneri eklenemedi: {hata}")

        return eklenen

    def onerileri_getir(self, seri_id: int) -> list:
        """Bekleyen önerileri döndürür."""
        try:
            with self._baglanti_ac() as conn:
                imleç = conn.execute(
                    "SELECT * FROM sozluk_oneri WHERE seri_id = ? AND durum = 'bekliyor' ORDER BY confidence DESC",
                    (seri_id,)
                )
                return self._satirlari_listeye_cevir(imleç.fetchall())
        except sqlite3.Error as hata:
            logger.error(f"Öneriler getirilemedi: {hata}")
            return []

    def oneri_onayla(self, oneri_id: int, cevrilmis_terim: str, locked: bool = False) -> bool:
        """Öneriyi onaylar ve ana sözlüğe aktarır."""
        try:
            with self._baglanti_ac() as conn:
                oneri = conn.execute(
                    "SELECT * FROM sozluk_oneri WHERE id = ?", (oneri_id,)
                ).fetchone()
                if not oneri:
                    return False
                oneri = dict(oneri)
            # Ana sözlüğe ekle
            self.sozluk_terimi_ekle(
                seri_id=oneri["seri_id"],
                orijinal_terim=oneri["orijinal_terim"],
                cevrilmis_terim=cevrilmis_terim,
                entity_type=oneri.get("entity_type", "PERSON"),
                confidence=oneri.get("confidence", 0.70),
                occurrences=oneri.get("occurrences", 1),
                first_chapter=oneri.get("bolum_no", 0),
                locked=locked,
            )
            with self._baglanti_ac() as conn:
                conn.execute(
                    "UPDATE sozluk_oneri SET durum = 'onaylandi' WHERE id = ?", (oneri_id,)
                )
                conn.commit()
            return True
        except Exception as hata:
            logger.error(f"Öneri onaylanamadı: {hata}")
            return False

    def oneri_reddet(self, oneri_id: int) -> bool:
        """Öneriyi reddeder."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    "UPDATE sozluk_oneri SET durum = 'reddedildi' WHERE id = ?", (oneri_id,)
                )
                conn.commit()
                return True
        except sqlite3.Error as hata:
            logger.error(f"Öneri reddedilemedi: {hata}")
            return False

    def sozluk_girisi_guncelle(
        self,
        girdi_id: int,
        orijinal_terim: str,
        cevrilmis_terim: str,
        kategori: str = "diger",
        notlar: str = None,
        entity_type: str = None,
    ) -> bool:
        """Belirtilen sözlük girişini günceller. Kilitler (kullanıcı düzenlemesi).
        entity_type verilmezse mevcut değer korunur.
        """
        from story_dict import _normalize_key as _nk
        nkey = _nk(orijinal_terim)
        try:
            with self._baglanti_ac() as conn:
                if entity_type is not None:
                    conn.execute(
                        """UPDATE sozluk
                           SET orijinal_terim = ?, cevrilmis_terim = ?, kategori = ?,
                               entity_type = ?, notlar = ?, normalize_key = ?,
                               locked = 1, oneri_durumu = 'kilitli'
                           WHERE id = ?""",
                        (orijinal_terim, cevrilmis_terim, kategori,
                         entity_type, notlar, nkey, girdi_id)
                    )
                else:
                    conn.execute(
                        """UPDATE sozluk
                           SET orijinal_terim = ?, cevrilmis_terim = ?, kategori = ?,
                               notlar = ?, normalize_key = ?,
                               locked = 1, oneri_durumu = 'kilitli'
                           WHERE id = ?""",
                        (orijinal_terim, cevrilmis_terim, kategori, notlar, nkey, girdi_id)
                    )
                conn.commit()
                logger.info(f"Sözlük girişi güncellendi ve kilitlendi (id={girdi_id}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Sözlük girişi güncellenemedi (id={girdi_id}): {hata}")
            return False

    def sozluk_girisi_sil(self, girdi_id: int) -> bool:
        """Belirtilen sözlük girişini siler."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute("DELETE FROM sozluk WHERE id = ?", (girdi_id,))
                conn.commit()
                logger.info(f"Sözlük girişi silindi (id={girdi_id}).")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Sözlük girişi silinemedi (id={girdi_id}): {hata}")
            return False

    def metinde_sozluk_terimlerini_bul(self, seri_id: int, metin: str) -> list:
        """
        Verilen metinde geçen sözlük terimlerini bulur ve döndürür.
        Uzun terimler önce eşleştirilir (greedy); büyük/küçük harf duyarsızdır.
        """
        try:
            terimler = self.sozluk_terimlerini_getir(seri_id)
            if not metin or not terimler:
                return []
            bulunanlar = sozlukte_eslesenleri_bul(metin, terimler)
            logger.info(
                f"Sözlük taraması: {len(bulunanlar)}/{len(terimler)} terim bulundu."
            )
            return bulunanlar
        except Exception as hata:
            logger.error(f"Sözlük terim taraması başarısız: {hata}")
            return []

    # =========================================================================
    # ÇEVİRİ ÖNBELLEĞİ
    # =========================================================================

    def onbellekten_getir(
        self,
        orijinal_metin: str,
        saglayici: str,
        model_adi: str,
        kaynak_dil: str,
        hedef_dil: str
    ) -> Optional[str]:
        """Önbellekte eşleşen çeviri varsa döndürür; yoksa None."""
        try:
            metin_hash = hashlib.sha256(orijinal_metin.encode("utf-8")).hexdigest()
            with self._baglanti_ac() as conn:
                satir = conn.execute(
                    """SELECT cevrilmis_metin FROM ceviri_onbellegi
                       WHERE metin_hash = ? AND saglayici = ? AND model_adi = ?
                         AND kaynak_dil = ? AND hedef_dil = ?""",
                    (metin_hash, saglayici, model_adi, kaynak_dil, hedef_dil)
                ).fetchone()
                if satir:
                    logger.info("Önbellekten çeviri bulundu.")
                    return satir["cevrilmis_metin"]
                return None
        except sqlite3.Error as hata:
            logger.error(f"Önbellek sorgusu başarısız: {hata}")
            return None

    def onbellege_kaydet(
        self,
        orijinal_metin: str,
        saglayici: str,
        model_adi: str,
        kaynak_dil: str,
        hedef_dil: str,
        cevrilmis_metin: str
    ) -> bool:
        """Çeviriyi önbelleğe kaydeder."""
        try:
            metin_hash = hashlib.sha256(orijinal_metin.encode("utf-8")).hexdigest()
            with self._baglanti_ac() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO ceviri_onbellegi
                           (metin_hash, saglayici, model_adi, kaynak_dil, hedef_dil, cevrilmis_metin)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (metin_hash, saglayici, model_adi, kaynak_dil, hedef_dil, cevrilmis_metin)
                )
                conn.commit()
                return True
        except sqlite3.Error as hata:
            logger.error(f"Önbelleğe kaydedilemedi: {hata}")
            return False

    def onbellegi_temizle(self) -> bool:
        """Tüm çeviri önbelleğini siler."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute("DELETE FROM ceviri_onbellegi")
                conn.commit()
                logger.info("Önbellek temizlendi.")
                return True
        except sqlite3.Error as hata:
            logger.error(f"Önbellek temizlenemedi: {hata}")
            return False

    # =========================================================================
    # AI AYARLARI
    # =========================================================================

    def _ai_ayari_normalize_et(self, ayar: dict) -> dict:
        """AI ayar satırını dict'e çevirir; API anahtarını çözer, JSON parse eder."""
        if ayar is None:
            return None
        sonuc = dict(ayar)
        ham = sonuc.get("api_anahtari") or ""
        sonuc["api_anahtari"] = _api_coz(ham)
        sonuc["_api_anahtari_sifreli"] = _api_sifreli_mi(ham)
        if sonuc.get("ekstra_konfig"):
            try:
                sonuc["ekstra_konfig"] = json.loads(sonuc["ekstra_konfig"])
            except (json.JSONDecodeError, TypeError):
                sonuc["ekstra_konfig"] = None
        return sonuc

    def _legacy_api_anahtarlarini_sifrele(self):
        """Düz metin saklanan API anahtarlarını şifreler (idempotent)."""
        try:
            with self._baglanti_ac() as conn:
                satirlar = conn.execute(
                    "SELECT id, api_anahtari FROM ai_ayarlar"
                ).fetchall()
                guncellendi = False
                for satir in satirlar:
                    ham = satir["api_anahtari"] or ""
                    if ham and not _api_sifreli_mi(ham):
                        conn.execute(
                            "UPDATE ai_ayarlar SET api_anahtari = ? WHERE id = ?",
                            (_api_sifrele(ham), satir["id"]),
                        )
                        guncellendi = True
                if guncellendi:
                    conn.commit()
                    logger.info("Eski API anahtarları şifrelenerek güncellendi.")
        except Exception as hata:
            logger.warning("Legacy API anahtarı şifreleme atlandı: %s", hata)

    def ai_ayar_kaydet(
        self,
        saglayici: str,
        model_adi: str,
        api_anahtari: str,
        aktif: bool = False,
        ekstra_konfig: dict = None
    ) -> bool:
        """AI sağlayıcı ayarını kaydeder veya günceller. API anahtarı şifrelenir."""
        try:
            ekstra_json = json.dumps(ekstra_konfig) if ekstra_konfig else None
            saklanacak = api_anahtari if _api_sifreli_mi(api_anahtari) else _api_sifrele(api_anahtari)
            with self._baglanti_ac() as conn:
                mevcut = conn.execute(
                    "SELECT id FROM ai_ayarlar WHERE saglayici = ?", (saglayici,)
                ).fetchone()

                if mevcut:
                    conn.execute(
                        """UPDATE ai_ayarlar
                           SET model_adi = ?, api_anahtari = ?, aktif = ?, ekstra_konfig = ?
                           WHERE saglayici = ?""",
                        (model_adi, saklanacak, int(aktif), ekstra_json, saglayici)
                    )
                    logger.info(f"'{saglayici}' AI ayarları güncellendi.")
                else:
                    conn.execute(
                        """INSERT INTO ai_ayarlar
                               (saglayici, model_adi, api_anahtari, aktif, ekstra_konfig)
                           VALUES (?, ?, ?, ?, ?)""",
                        (saglayici, model_adi, saklanacak, int(aktif), ekstra_json)
                    )
                    logger.info(f"'{saglayici}' AI ayarları eklendi.")

                conn.commit()
                return True

        except sqlite3.Error as hata:
            logger.error(f"AI ayarı kaydedilemedi: {hata}")
            return False

    def aktif_ai_ayar_getir(self) -> Optional[dict]:
        """Aktif AI sağlayıcı ayarını döndürür; yoksa None. API anahtarı çözülmüş gelir."""
        try:
            self._legacy_api_anahtarlarini_sifrele()
            with self._baglanti_ac() as conn:
                satir = conn.execute(
                    "SELECT * FROM ai_ayarlar WHERE aktif = 1 LIMIT 1"
                ).fetchone()
                if satir is None:
                    return None
                return self._ai_ayari_normalize_et(dict(satir))

        except sqlite3.Error as hata:
            logger.error(f"Aktif AI ayarı getirilemedi: {hata}")
            return None

    def tum_ai_ayarlarini_getir(self) -> list:
        """Tüm kayıtlı AI sağlayıcı ayarlarını döndürür (API anahtarları çözülmüş)."""
        try:
            self._legacy_api_anahtarlarini_sifrele()
            with self._baglanti_ac() as conn:
                satirlar = conn.execute(
                    "SELECT * FROM ai_ayarlar ORDER BY olusturma_tarihi ASC"
                ).fetchall()
                return [self._ai_ayari_normalize_et(dict(s)) for s in satirlar]

        except sqlite3.Error as hata:
            logger.error(f"Tüm AI ayarları getirilemedi: {hata}")
            return []

    def aktif_saglayici_ayarla(self, saglayici: str) -> bool:
        """Belirtilen sağlayıcıyı aktif yapar, diğerlerini pasif yapar."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute("UPDATE ai_ayarlar SET aktif = 0")
                conn.execute(
                    "UPDATE ai_ayarlar SET aktif = 1 WHERE saglayici = ?", (saglayici,)
                )
                conn.commit()
                logger.info(f"Aktif sağlayıcı: '{saglayici}'.")
                return True

        except sqlite3.Error as hata:
            logger.error(f"Aktif sağlayıcı ayarlanamadı: {hata}")
            return False

    def ai_ayar_sil(self, saglayici: str) -> bool:
        """Belirtilen sağlayıcının ayarlarını siler."""
        try:
            with self._baglanti_ac() as conn:
                conn.execute(
                    "DELETE FROM ai_ayarlar WHERE saglayici = ?", (saglayici,)
                )
                conn.commit()
                logger.info(f"'{saglayici}' AI ayarları silindi.")
                return True

        except sqlite3.Error as hata:
            logger.error(f"AI ayarı silinemedi: {hata}")
            return False

    # =========================================================================
    # GERİYE DÖNÜK UYUMLULUK — ALIAS METODLAR
    # glossary_widget.py eski isimleri kullanıyor; buradan yönlendiriliyor.
    # =========================================================================

    def sozluk_girdisi_getir(self, seri_id: int) -> list:
        """Alias: sozluk_terimlerini_getir"""
        return self.sozluk_terimlerini_getir(seri_id)

    def sozluk_girdisi_olustur(
        self,
        seri_id: int,
        orijinal_terim: str,
        cevrilmis_terim: str,
        kategori: str = "diger",
        notlar: str = None
    ) -> Optional[int]:
        """Alias: sozluk_terimi_ekle"""
        return self.sozluk_terimi_ekle(
            seri_id, orijinal_terim, cevrilmis_terim, kategori, notlar
        )

    def sozluk_girdisi_guncelle(
        self,
        girdi_id: int,
        orijinal_terim: str,
        cevrilmis_terim: str,
        kategori: str = "diger",
        notlar: str = None,
        entity_type: str = None,
    ) -> bool:
        """Alias: sozluk_girisi_guncelle"""
        return self.sozluk_girisi_guncelle(
            girdi_id, orijinal_terim, cevrilmis_terim, kategori, notlar, entity_type
        )

    def sozluk_girdisi_sil(self, girdi_id: int) -> bool:
        """Alias: sozluk_girisi_sil"""
        return self.sozluk_girisi_sil(girdi_id)

    def metinde_terimleri_bul(self, seri_id: int, metin: str) -> list:
        """Alias: metinde_sozluk_terimlerini_bul"""
        return self.metinde_sozluk_terimlerini_bul(seri_id, metin)

    def onceki_cevirii_kaydet(self, bolum_id: int, ceviri: str) -> bool:
        """Alias: onceki_cevirileri_kaydet (yazım farkını kapsar)"""
        return self.onceki_cevirileri_kaydet(bolum_id, ceviri)

    def ai_ayar_getir(self, saglayici: str) -> Optional[dict]:
        """Belirtilen sağlayıcının ayarını döndürür (API anahtarı çözülmüş)."""
        try:
            with self._baglanti_ac() as conn:
                satir = conn.execute(
                    "SELECT * FROM ai_ayarlar WHERE saglayici = ?", (saglayici,)
                ).fetchone()
                if satir is None:
                    return None
                return self._ai_ayari_normalize_et(dict(satir))

        except sqlite3.Error as hata:
            logger.error(f"AI ayarı getirilemedi (sağlayıcı={saglayici}): {hata}")
            return None

    # Standart alias isimleri (tek API ailesi)
    def saglayiciya_gore_ayar_getir(self, saglayici: str) -> Optional[dict]:
        """Alias: ai_ayar_getir"""
        return self.ai_ayar_getir(saglayici)

    def tum_ai_ayarlari_getir(self) -> list:
        """Alias: tum_ai_ayarlarini_getir"""
        return self.tum_ai_ayarlarini_getir()

    def onceki_ceviri_kaydet(self, bolum_id: int, ceviri: str) -> bool:
        """Standart ad: onceki_cevirileri_kaydet"""
        return self.onceki_cevirileri_kaydet(bolum_id, ceviri)

    def sozluk_terimi_guncelle(
        self,
        girdi_id: int,
        orijinal_terim: str,
        cevrilmis_terim: str,
        kategori: str = "diger",
        notlar: str = None,
        entity_type: str = None,
    ) -> bool:
        """Standart ad: sozluk_girisi_guncelle"""
        return self.sozluk_girisi_guncelle(
            girdi_id, orijinal_terim, cevrilmis_terim, kategori, notlar, entity_type
        )

    def sozluk_terimi_sil(self, girdi_id: int) -> bool:
        """Standart ad: sozluk_girisi_sil"""
        return self.sozluk_girisi_sil(girdi_id)


# =============================================================================
# KOMÜNİTE TESTİ — doğrudan çalıştırma
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Novel Çevirmen — Veritabanı Testi")
    print("=" * 60)

    db = DatabaseManager()

    print("\n[TEST] Seri oluşturuluyor...")
    seri_id = db.seri_olustur(
        baslik="Test Serisi",
        kaynak_dil="Japonca",
        hedef_dil="Türkçe",
        aciklama="Bu bir test serisidir."
    )
    print(f"  -> Oluşturulan seri id: {seri_id}")

    print("\n[TEST] Tüm seriler getiriliyor...")
    seriler = db.tum_serileri_getir()
    print(f"  -> Toplam seri sayısı: {len(seriler)}")
    for s in seriler:
        print(f"     - [{s['id']}] {s['baslik']} ({s['kaynak_dil']} -> {s['hedef_dil']})")

    print("\n[TEST] Bölüm oluşturuluyor...")
    bolum_id = db.bolum_olustur(
        seri_id=seri_id,
        bolum_no=1,
        bolum_baslik="İlk Bölüm",
        orijinal_metin="Bu test metnidir."
    )
    print(f"  -> Oluşturulan bölüm id: {bolum_id}")

    print("\n[TEST] Bölüm sayıları getiriliyor...")
    sayilar = db.seri_bolum_sayilarini_getir()
    print(f"  -> Bölüm sayıları: {sayilar}")

    print("\n" + "=" * 60)
    print("Tüm testler tamamlandı.")
    print(f"Veritabanı konumu: {DB_YOLU}")
    print("=" * 60)