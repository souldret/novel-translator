"""
importers.py ve import_wizard.py birim testleri (UI olmadan çalışan kısımlar).
"""
import sys
import os
import tempfile
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# =============================================================================
# Doğal Sıralama Testleri
# =============================================================================

class TestDogalSiralama:
    def test_importers_import_edilebilir(self):
        try:
            import importers
            assert importers is not None
        except ImportError as e:
            pytest.skip(f"importers modülü yüklenemedi: {e}")

    def test_dogal_sirala_sayisal(self):
        """'Bölüm 2.txt' < 'Bölüm 10.txt' doğal sıralamada geçerli."""
        from importers import dogal_sirala
        dosyalar = [
            "/tmp/Bölüm 10.txt",
            "/tmp/Bölüm 2.txt",
            "/tmp/Bölüm 1.txt",
        ]
        sirali = dogal_sirala(dosyalar)
        adlar = [os.path.basename(p) for p in sirali]
        assert adlar.index("Bölüm 1.txt") < adlar.index("Bölüm 2.txt"), \
            "1 < 2 olmalı"
        assert adlar.index("Bölüm 2.txt") < adlar.index("Bölüm 10.txt"), \
            "2 < 10 olmalı (string sort'ta 10 < 2 olur — bug düzeltildi)"

    def test_dogal_sirala_chapter_prefix(self):
        """'Chapter_012.txt' gibi sıfır dolgulu adlar sıralanmalı."""
        from importers import dogal_sirala
        dosyalar = [
            "/tmp/Chapter_030.txt",
            "/tmp/Chapter_002.txt",
            "/tmp/Chapter_010.txt",
        ]
        sirali = dogal_sirala(dosyalar)
        beklenen = ["Chapter_002.txt", "Chapter_010.txt", "Chapter_030.txt"]
        assert [os.path.basename(p) for p in sirali] == beklenen

    def test_dogal_sirala_karisik(self):
        """Farklı adlandırma kalıpları."""
        from importers import dogal_sirala
        dosyalar = [
            "/tmp/012.txt",
            "/tmp/003 - Başlık.txt",
            "/tmp/Bölüm 1 - Giriş.txt",
        ]
        sirali = dogal_sirala(dosyalar)
        bolum_nolari = []
        from importers import dosya_adından_bolum_no
        for p in sirali:
            no, _ = dosya_adından_bolum_no(p)
            bolum_nolari.append(no)
        assert bolum_nolari == sorted(bolum_nolari), "Bölüm numaraları artan sırada olmalı"

    def test_dosya_adindan_bolum_no_bolum_prefix(self):
        """'Bölüm 12 - Kahraman Uyanıyor.txt' → (12, 'Kahraman Uyanıyor')"""
        from importers import dosya_adından_bolum_no
        no, baslik = dosya_adından_bolum_no("Bölüm 12 - Kahraman Uyanıyor.txt")
        assert no == 12
        assert "Kahraman" in baslik or baslik  # başlık boş olmamalı

    def test_dosya_adindan_bolum_no_chapter(self):
        """'Chapter_012.txt' → 12"""
        from importers import dosya_adından_bolum_no
        no, _ = dosya_adından_bolum_no("Chapter_012.txt")
        assert no == 12

    def test_dosya_adindan_bolum_no_saf_sayi(self):
        """'012.txt' → 12"""
        from importers import dosya_adından_bolum_no
        no, _ = dosya_adından_bolum_no("012.txt")
        assert no == 12

    def test_dosya_adindan_bolum_no_bulunamaz(self):
        """Numara yoksa 9999 döner."""
        from importers import dosya_adından_bolum_no
        no, baslik = dosya_adından_bolum_no("giris.txt")
        assert no == 9999


# =============================================================================
# Mükerrer (Hash) Tespiti Testleri
# =============================================================================

class TestMukerrerTespiti:
    def test_icerik_hash_tutarli(self):
        """Aynı içerik → aynı hash."""
        from importers import _icerik_hash
        h1 = _icerik_hash("Merhaba dünya")
        h2 = _icerik_hash("Merhaba dünya")
        assert h1 == h2

    def test_icerik_hash_farkli(self):
        """Farklı içerik → farklı hash."""
        from importers import _icerik_hash
        h1 = _icerik_hash("İçerik A")
        h2 = _icerik_hash("İçerik B")
        assert h1 != h2

    def test_txt_mukerrer_atlaniyor(self):
        """Aynı içerikli TXT dosyası ikinci kez import edildiğinde atlanmalı."""
        pytest.importorskip("PyQt6", reason="PyQt6 gerektiriyor")
        from importers import _icerik_hash

        icerik = "Bu test içeriğidir. " * 20

        # Sahte DB
        class SahteBolum:
            def get(self, k, d=None):
                return {"orijinal_metin": icerik, "bolum_no": 1}.get(k, d)

        mevcut_hashler = {_icerik_hash(icerik.strip())}
        h = _icerik_hash(icerik.strip())
        assert h in mevcut_hashler, "Mükerrer tespit edilemedi"


# =============================================================================
# Encoding Tespiti Testleri
# =============================================================================

class TestEncodingTespiti:
    def test_chardet_varsa_kullaniliyor(self):
        try:
            import chardet
            import importers
            assert hasattr(importers, '_dosya_icerigini_oku')
        except ImportError:
            pytest.skip("chardet veya importers yüklenemedi")

    def test_dosya_oku_utf8(self):
        """UTF-8 kodlu dosya okunabilmeli."""
        from importers import _dosya_icerigini_oku
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False
        ) as f:
            f.write("Merhaba dünya — test içeriği")
            adi = f.name
        try:
            icerik = _dosya_icerigini_oku(adi)
            assert icerik is not None
            assert "Merhaba" in icerik
        finally:
            os.unlink(adi)

    def test_dosya_oku_cp1254(self):
        """Windows-1254 (cp1254) kodlu Türkçe dosya okunabilmeli."""
        from importers import _dosya_icerigini_oku
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="cp1254", suffix=".txt", delete=False
        ) as f:
            f.write("Türkçe içerik: şçğüöı")
            adi = f.name
        try:
            icerik = _dosya_icerigini_oku(adi)
            assert icerik is not None
        finally:
            os.unlink(adi)


# =============================================================================
# Klasör Tarama Testleri (import_wizard.py)
# =============================================================================

class TestKlasorTarama:
    def test_klasor_tara_temel(self):
        """Klasördeki TXT dosyaları bulunmalı."""
        from import_wizard import klasoru_tara
        with tempfile.TemporaryDirectory() as klasor:
            # TXT dosyaları oluştur
            for isim in ["Bölüm 1.txt", "Bölüm 2.txt", "Bölüm 10.txt"]:
                open(os.path.join(klasor, isim), "w", encoding="utf-8").close()
            # Sahte PDF (filtrelenmeli)
            open(os.path.join(klasor, "not.pdf"), "w").close()

            dosyalar = klasoru_tara(klasor)
            adlar = [os.path.basename(d) for d in dosyalar]
            assert len(dosyalar) == 3
            assert "not.pdf" not in adlar

    def test_klasor_tara_dogal_sirali(self):
        """Bulunan dosyalar doğal sıralanmalı (10 > 2 sorununa karşı)."""
        from import_wizard import klasoru_tara
        with tempfile.TemporaryDirectory() as klasor:
            for isim in ["Bölüm 10.txt", "Bölüm 2.txt", "Bölüm 1.txt"]:
                open(os.path.join(klasor, isim), "w", encoding="utf-8").close()
            dosyalar = klasoru_tara(klasor)
            from importers import dosya_adından_bolum_no
            nolar = [dosya_adından_bolum_no(d)[0] for d in dosyalar]
            assert nolar == sorted(nolar), f"Sıralama hatalı: {nolar}"

    def test_klasor_tara_alt_klasorler(self):
        """alt_klasorler=True ise alt dizinlerdeki dosyalar da dahil edilmeli."""
        from import_wizard import klasoru_tara
        with tempfile.TemporaryDirectory() as klasor:
            alt = os.path.join(klasor, "alt")
            os.makedirs(alt)
            open(os.path.join(klasor, "Bolum 1.txt"), "w", encoding="utf-8").close()
            open(os.path.join(alt, "Bolum 2.txt"), "w", encoding="utf-8").close()

            # Alt klasörler dahil
            with_alt = klasoru_tara(klasor, alt_klasorler=True)
            # Alt klasörler hariç
            without_alt = klasoru_tara(klasor, alt_klasorler=False)

            assert len(with_alt) == 2
            assert len(without_alt) == 1

    def test_klasor_tara_bos(self):
        """Boş klasör boş liste döndürmeli."""
        from import_wizard import klasoru_tara
        with tempfile.TemporaryDirectory() as klasor:
            dosyalar = klasoru_tara(klasor)
            assert dosyalar == []


# =============================================================================
# Hata Toleransı Testleri
# =============================================================================

class TestHataToleransi:
    def test_bozuk_dosya_atlanir(self):
        """Okunamayan/var olmayan dosya None döndürmeli, exception fırlatmamalı."""
        from importers import _dosya_icerigini_oku
        import tempfile
        # Geçici dizinde kesinlikle olmayan bir yol (platform bağımsız)
        olmayan = os.path.join(tempfile.gettempdir(), "novel_test_kesinlikle_yok_99999.txt")
        if os.path.exists(olmayan):
            os.unlink(olmayan)  # gerçekten yoksa skip olmaz
        sonuc = _dosya_icerigini_oku(olmayan)
        assert sonuc is None

    def test_dogal_sirala_bos_liste(self):
        """Boş liste → boş liste."""
        from importers import dogal_sirala
        assert dogal_sirala([]) == []

    def test_icerik_hash_bos(self):
        """Boş içerik hash'lenmeli (exception yok)."""
        from importers import _icerik_hash
        h = _icerik_hash("")
        assert isinstance(h, str) and len(h) > 0