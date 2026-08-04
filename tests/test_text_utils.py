"""text_utils ve secure_store birim testleri."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from text_utils import (
    metni_parcala, parcalari_birlestir, sozlukte_eslesenleri_bul,
    sozluk_uyum_kontrolu, metin_diff_html, metin_icerisinde_ara,
)
from secure_store import sifrele, coz, sifreli_mi


class TestParcalama:
    def test_kisa_metin_tek_parca(self):
        assert metni_parcala("Merhaba dünya", 100) == ["Merhaba dünya"]

    def test_uzun_metin_parcalanir(self):
        p1 = "A" * 100
        p2 = "B" * 100
        metin = p1 + "\n\n" + p2
        parcalar = metni_parcala(metin, max_karakter=120)
        assert len(parcalar) >= 2
        assert "A" in parcalar[0]
        assert parcalari_birlestir(parcalar)

    def test_bos_metin(self):
        assert metni_parcala("") == []
        assert metni_parcala("   ") == []


class TestSozlukTarama:
    def test_greedy_uzun_terim_once(self):
        terimler = [
            {"orijinal_terim": "an", "cevrilmis_terim": "X"},
            {"orijinal_terim": "and", "cevrilmis_terim": "ve"},
        ]
        bulunan = sozlukte_eslesenleri_bul("cats and dogs", terimler)
        orijinaller = {t["orijinal_terim"] for t in bulunan}
        assert "and" in orijinaller

    def test_uyum_kontrolu(self):
        sozluk = [
            {"orijinal_terim": "Kirito", "cevrilmis_terim": "Kirito"},
            {"orijinal_terim": "Aincrad", "cevrilmis_terim": "Aincrad"},
        ]
        sonuc = sozluk_uyum_kontrolu("Kirito savaştı.", sozluk)
        assert len(sonuc["uyumlu"]) == 1
        assert len(sonuc["eksik"]) == 1
        assert sonuc["eksik"][0]["orijinal_terim"] == "Aincrad"


class TestDiffVeArama:
    def test_diff_html(self):
        html = metin_diff_html("satir1\n", "satir2\n")
        assert "div" in html

    def test_arama(self):
        assert metin_icerisinde_ara("Merhaba Dünya", "dünya") == 8
        assert metin_icerisinde_ara("abc", "xyz") is None


class TestSecureStore:
    def test_sifrele_coz_dongusu(self):
        anahtar = "sk-test-anahtar-12345"
        sakli = sifrele(anahtar)
        assert sifreli_mi(sakli)
        assert coz(sakli) == anahtar

    def test_legacy_duz_metin(self):
        assert coz("sk-legacy") == "sk-legacy"

    def test_cift_sifreleme_yok(self):
        a = sifrele("abc")
        b = sifrele(a)
        assert a == b
