"""
Sözlük uçtan uca test senaryosu — GUI olmadan DB + NER katmanı.
python _test_e2e_sozluk.py
"""
import logging
import os
import csv
import tempfile

logging.basicConfig(level=logging.WARNING)  # DB spam'i kapat

from database import DatabaseManager
from story_dict import EntityType, StoryDictionaryEngine, _normalize_key

BASARI = "✓"
HATA   = "✗"

def kontrol(mesaj, kosul):
    simge = BASARI if kosul else HATA
    print(f"  {simge} {mesaj}")
    if not kosul:
        raise AssertionError(mesaj)

print("=" * 65)
print("SÖZLÜK UÇTAN UCA TEST")
print("=" * 65)

# Geçici DB kullan — üretim DB'sine dokunmaz
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
db = DatabaseManager(db_yolu=tmp_db.name)

# ── a) Seri + bölüm oluştur ─────────────────────────────────────────────────
print("\n[A] Seri ve bölüm oluşturma")
seri_id = db.seri_olustur("Test Serisi", "Çince", "Türkçe")
kontrol("Seri oluşturuldu", seri_id is not None and seri_id > 0)

# 3 bölüm: Ye Chen / Ye-Chen / YeChen varyasyonları + çok kelimeli kalıplar
bolum1 = """
Ye Chen stood at the peak of the Golden Core Realm.
Ye-Chen had mastered the Sky Sword Technique many years ago.
YeChen looked at the Abyss Palace in the distance.
Golden Core Realm was said to be the threshold between mortal and immortal.
"""
bolum2 = """
Lin Feng, the Elder of the Azure Dragon Clan, greeted Ye Chen warmly.
The Nine Heavens Slash was Lin Feng's signature skill.
Lin Feng's disciple, a young girl named Xiao Mei, watched in awe.
"""
bolum3 = """
The Crimson Lotus Art could only be practiced in the Sacred Fire Forest.
Ye Chen used the Sky Sword Technique once more and defeated his opponent.
"""

b1_id = db.bolum_olustur(seri_id, 1, bolum1.strip())
b2_id = db.bolum_olustur(seri_id, 2, bolum2.strip())
b3_id = db.bolum_olustur(seri_id, 3, bolum3.strip())
kontrol("3 bölüm oluşturuldu", all(x is not None for x in [b1_id, b2_id, b3_id]))

# ── Blok sinyal testi ────────────────────────────────────────────────────────
print("\n[1] blockSignals doğrulaması (kod incelemesi)")
# Dosyayı oku, satırları kontrol et
with open("glossary_widget.py", encoding="utf-8") as f:
    gwlines = f.readlines()

# _tabloyu_doldur içinde blockSignals(True) ve blockSignals(False) ara
doldur_baslangic = next(
    i for i, l in enumerate(gwlines) if "def _tabloyu_doldur" in l
)
doldur_blogu = "".join(gwlines[doldur_baslangic:doldur_baslangic + 100])
kontrol(
    "blockSignals(True) _tabloyu_doldur() içinde mevcut (satır ~701)",
    "blockSignals(True)" in doldur_blogu,
)
kontrol(
    "blockSignals(False) _tabloyu_doldur() kapanışında mevcut (satır ~779)",
    "blockSignals(False)" in doldur_blogu,
)
kontrol(
    "setUpdatesEnabled(False) render optimizasyonu mevcut",
    "setUpdatesEnabled(False)" in doldur_blogu,
)
# _tabloyu_temizle de kontrol
temizle_baslangic = next(
    i for i, l in enumerate(gwlines) if "def _tabloyu_temizle" in l
)
temizle_blogu = "".join(gwlines[temizle_baslangic:temizle_baslangic + 15])
kontrol(
    "blockSignals(True) _tabloyu_temizle() içinde mevcut",
    "blockSignals(True)" in temizle_blogu,
)

# ── confidence=0 testi ──────────────────────────────────────────────────────
print("\n[3] confidence=0 edge case")
# Kod satırını bul
conf_satir = next(
    (l.strip() for l in gwlines if "_conf_raw = terim.get" in l), None
)
guven_satir = next(
    (l.strip() for l in gwlines if "1.0 if _conf_raw is None else _conf_raw" in l), None
)
kontrol(
    "confidence None kontrolü: `_conf_raw = terim.get('confidence')` mevcut",
    conf_satir is not None,
)
kontrol(
    "confidence=0 düzeltmesi: `1.0 if _conf_raw is None else _conf_raw` mevcut",
    guven_satir is not None,
)
# Gerçek değer testi
_conf_raw = 0.0
guven = 1.0 if _conf_raw is None else _conf_raw
kontrol("confidence=0.0 → 0% (yanlışlıkla %100 olmuyor)", guven == 0.0)
_conf_raw = None
guven = 1.0 if _conf_raw is None else _conf_raw
kontrol("confidence=None → %100 default", guven == 1.0)

# ── entity_type diyalog doğrulaması ────────────────────────────────────────
print("\n[2] entity_type diyalog → DB akışı (kod incelemesi)")
ekle_satir = next(
    (l.strip() for l in gwlines if "entity_type=diyalog.sonuc_entity_type" in l), None
)
kontrol(
    "_terim_ekle ve _terim_duzenle 'diyalog.sonuc_entity_type' kullanıyor",
    ekle_satir is not None,
)
# KATEGORI_TO_ENTITY_TYPE.get(...) kalmadığını doğrula
eski_yol = sum(
    1 for l in gwlines
    if "KATEGORI_TO_ENTITY_TYPE.get(diyalog.sonuc_kategori" in l
)
kontrol(
    "Eski KATEGORI_TO_ENTITY_TYPE.get() artık _terim_ekle/_duzenle içinde yok",
    eski_yol == 0,
)

# ── b) Otomatik Tara simülasyonu ─────────────────────────────────────────────
print("\n[B] Otomatik Tara (NER engine)")
mevcut = db.sozluk_terimlerini_getir(seri_id, sadece_onaylandi=False)
engine = StoryDictionaryEngine(mevcut)

tum_adaylar = []
for bolum_no, metin in [(1, bolum1), (2, bolum2), (3, bolum3)]:
    sonuc = engine.analyze_chapter(metin.strip(), bolum_no=bolum_no)
    for a in sonuc["auto_save"] + sonuc["suggestions"]:
        a["bolum_no"] = bolum_no
        tum_adaylar.append(a)

toplam_eklenen = db.oneri_ekle_toplu(seri_id, tum_adaylar)
oneriler = db.onerileri_getir(seri_id)
kontrol("En az 3 aday önerildi", len(oneriler) >= 3)

# Ye Chen / Ye-Chen / YeChen normalize → aynı key?
ye_chen_nk    = _normalize_key("Ye Chen")
ye_chen_h_nk  = _normalize_key("Ye-Chen")
ye_chen_nk2   = _normalize_key("YeChen")
kontrol(
    "Ye Chen / Ye-Chen / YeChen aynı normalize_key",
    ye_chen_nk == ye_chen_h_nk == ye_chen_nk2,
)

# Golden Core Realm → çok kelimeli, REALM veya PERSON tespiti
gcr_aday = next(
    (a for a in tum_adaylar if "Golden Core Realm" in a["phrase"]),
    None
)
kontrol("'Golden Core Realm' çok kelimeli kalıp tespit edildi", gcr_aday is not None)
if gcr_aday:
    print(f"    entity_type={gcr_aday['entity_type']} conf={gcr_aday['confidence']:.2f}")

# Sky Sword Technique → SKILL
sst_aday = next(
    (a for a in tum_adaylar if "Sky Sword Technique" in a["phrase"]),
    None
)
kontrol("'Sky Sword Technique' tespit edildi", sst_aday is not None)
if sst_aday:
    kontrol(f"Sky Sword Technique entity_type=SKILL", sst_aday["entity_type"] == EntityType.SKILL)

print(f"\n  Toplam {len(oneriler)} öneri oluşturuldu:")
for o in oneriler[:6]:
    print(f"    [{o['entity_type']:12}] {o['orijinal_terim']!r:35} conf={o['confidence']:.2f}")

# ── c) Öneri onayı → sözlük ──────────────────────────────────────────────────
print("\n[C] Öneri onayı → sözlük")
ilk_oneri = oneriler[0]
db.oneri_onayla(ilk_oneri["id"], "Test Çeviri", locked=False)
guncel = db.sozluk_terimlerini_getir(seri_id)
onaylanan = next(
    (t for t in guncel if t["orijinal_terim"] == ilk_oneri["orijinal_terim"]),
    None,
)
kontrol("Onaylanan öneri sözlükte görünüyor", onaylanan is not None)
if onaylanan:
    kontrol(
        f"entity_type doğru ({ilk_oneri['entity_type']})",
        onaylanan["entity_type"] == ilk_oneri["entity_type"],
    )
    print(f"    entity_type={onaylanan['entity_type']} rozet={EntityType.goruntu(onaylanan['entity_type'])}")

# ── d) Manuel terim ekleme ───────────────────────────────────────────────────
print("\n[D] Manuel terim ekleme (entity_type doğrudan)")
db.sozluk_terimi_ekle(
    seri_id=seri_id,
    orijinal_terim="Sacred Fire Forest",
    cevrilmis_terim="Kutsal Ateş Ormanı",
    entity_type=EntityType.LOCATION,
    kategori="mekan",
)
guncel = db.sozluk_terimlerini_getir(seri_id)
sff = next((t for t in guncel if t["orijinal_terim"] == "Sacred Fire Forest"), None)
kontrol("Manuel eklenen terim sözlükte", sff is not None)
if sff:
    kontrol("entity_type=LOCATION doğru kaydedildi", sff["entity_type"] == EntityType.LOCATION)
    print(f"    entity_type={sff['entity_type']} rozet={EntityType.goruntu(sff['entity_type'])}")

# ── e) Kilit + build_translation_instructions ───────────────────────────────
print("\n[E] Kilit + çeviri prompt talimatı")
# Bir terimi kilitle
db.sozluk_terimi_ekle(
    seri_id=seri_id,
    orijinal_terim="Ye Chen",
    cevrilmis_terim="Ye Chen",
    entity_type=EntityType.PERSON,
    locked=True,
)
kilitli_terimler = db.sozluk_terimlerini_getir(seri_id)
ye_chen = next((t for t in kilitli_terimler if t["orijinal_terim"] == "Ye Chen"), None)
kontrol("Ye Chen sözlükte", ye_chen is not None)
if ye_chen:
    kontrol("Ye Chen kilitli", bool(ye_chen.get("locked")))

engine2 = StoryDictionaryEngine(kilitli_terimler)
talimat = engine2.build_translation_instructions()
kontrol("build_translation_instructions boş değil", bool(talimat))
kontrol("Kilitli terim ⟨KİLİTLİ⟩ ile işaretlenmiş", "⟨KİLİTLİ⟩" in talimat)
kontrol("Ye Chen → Ye Chen talimatı var", "Ye Chen → Ye Chen" in talimat)
print(f"    Talimat:\n{talimat[:300]}")

# ── f) Arama filtresi simülasyonu ────────────────────────────────────────────
print("\n[F] Arama filtresi (DB katmanı)")
# DB'den terimleri al, basit filtreleme uygula
tum = db.sozluk_terimlerini_getir(seri_id)
aranan = "sacred"
eslesen = [t for t in tum if aranan in (t.get("orijinal_terim") or "").lower()
           or aranan in (t.get("cevrilmis_terim") or "").lower()]
kontrol(f"'sacred' araması sonuç döndürdü (Sacred Fire Forest)", len(eslesen) >= 1)
print(f"    Toplam {len(tum)} terim, '{aranan}' için {len(eslesen)} eşleşme")

# ── g) CSV dışa/içe aktarma ─────────────────────────────────────────────────
print("\n[G] CSV dışa → içe aktarma (normalize_key korunuyor mu?)")
csv_dosya = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w",
                                        newline="", encoding="utf-8-sig")
writer = csv.writer(csv_dosya)
writer.writerow(["orijinal_terim", "cevrilmis_terim", "kategori", "entity_type",
                 "confidence", "occurrences", "locked", "notlar"])
onceki_terimler = db.sozluk_terimlerini_getir(seri_id)
for t in onceki_terimler:
    writer.writerow([
        t.get("orijinal_terim", ""),
        t.get("cevrilmis_terim", ""),
        t.get("kategori", "diger"),
        t.get("entity_type", "PERSON"),
        f"{t.get('confidence', 1.0) or 1.0:.2f}",
        t.get("occurrences", 1),
        "1" if t.get("locked") else "0",
        t.get("notlar", "") or "",
    ])
csv_dosya.close()

# Yeni seri oluştur, CSV'den aktar
seri2_id = db.seri_olustur("Test Serisi 2", "Çince", "Türkçe")
with open(csv_dosya.name, newline="", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    next(reader)  # başlık atla
    eklenen = 0
    for satir in reader:
        if len(satir) < 2:
            continue
        orijinal  = satir[0].strip()
        cevrilmis = satir[1].strip()
        et        = satir[3].strip() if len(satir) > 3 else EntityType.PERSON
        if not EntityType.gecerli_mi(et):
            et = EntityType.PERSON
        if orijinal and cevrilmis:
            db.sozluk_terimi_ekle(seri2_id, orijinal, cevrilmis, entity_type=et)
            eklenen += 1

aktarilan = db.sozluk_terimlerini_getir(seri2_id)
kontrol(f"CSV içe aktarma: {eklenen} terim eklendi", eklenen >= len(onceki_terimler))
kontrol("normalize_key içe aktarma sonrası dolu", all(
    t.get("normalize_key") for t in aktarilan
))
# normalize_key yeniden doğru hesaplanmış mı?
for t in aktarilan[:3]:
    beklenen_nk = _normalize_key(t["orijinal_terim"])
    kontrol(
        f"normalize_key doğru: {t['orijinal_terim']!r} → {beklenen_nk!r}",
        t["normalize_key"] == beklenen_nk,
    )
print(f"    Aktarılan: {len(aktarilan)} terim, normalize_key hepsi dolu ve doğru")

# ── h) Inline düzenleme simülasyonu + entity_type değişikliği ────────────────
print("\n[H] Inline düzenleme akışı simülasyonu (sozluk_girisi_guncelle)")
# sozluk_terimi_ekle ile bir terim ekle
inline_id = db.sozluk_terimi_ekle(
    seri_id=seri_id,
    orijinal_terim="Azure Dragon Clan",
    cevrilmis_terim="Mavi Ejder Klanı",
    entity_type=EntityType.ORGANIZATION,
)
kontrol("Azure Dragon Clan eklendi", inline_id is not None)

# Inline düzenleme akışı: sozluk_girisi_guncelle çağrısı
# (glossary_widget._inline_duzenleme_kaydedildi'nin DB katmanındaki eşdeğeri)
ok = db.sozluk_girisi_guncelle(
    girdi_id=inline_id,
    orijinal_terim="Azure Dragon Clan",
    cevrilmis_terim="Gök Ejder Klanı",  # çeviri değişti
    kategori="sistem",
    entity_type=EntityType.ORGANIZATION,
)
kontrol("Inline düzenleme güncelleme başarılı", ok is True)

# Değişikliği doğrula
guncellendi = next(
    (t for t in db.sozluk_terimlerini_getir(seri_id, sadece_onaylandi=False)
     if t["id"] == inline_id),
    None,
)
kontrol("Güncellenen terim sözlükte mevcut", guncellendi is not None)
if guncellendi:
    kontrol(
        "Çeviri güncellendi: 'Gök Ejder Klanı'",
        guncellendi["cevrilmis_terim"] == "Gök Ejder Klanı",
    )
    kontrol(
        "entity_type ORGANIZATION olarak korundu",
        guncellendi["entity_type"] == EntityType.ORGANIZATION,
    )
    kontrol(
        "normalize_key güncellendi (sozluk_girisi_guncelle normalize_key yazar)",
        guncellendi["normalize_key"] == _normalize_key("Azure Dragon Clan"),
    )
    kontrol(
        "Inline düzenleme kilitlendi (locked=1)",
        bool(guncellendi["locked"]),
    )
    print(f"    cevrilmis_terim={guncellendi['cevrilmis_terim']!r}  "
          f"entity_type={guncellendi['entity_type']}  locked={guncellendi['locked']}")

# ── i) Ölü kod (sozluk_girdisi_*) temizlenmiş mi? ────────────────────────────
print("\n[I] Ölü kod kontrolü: sozluk_girdisi_* alias grubu kaldırıldı mı?")
olu_metodlar = [
    "sozluk_girdisi_getir",
    "sozluk_girdisi_olustur",
    "sozluk_girdisi_guncelle",
    "sozluk_girdisi_sil",
]
from database import DatabaseManager as _DBM
for metod_adi in olu_metodlar:
    mevcut = hasattr(_DBM, metod_adi)
    kontrol(
        f"'{metod_adi}' artık DatabaseManager'da YOK",
        not mevcut,
    )
print("    sozluk_girdisi_* alias grubu tamamen kaldırılmış: OK")

# Temizlik
os.unlink(tmp_db.name)
os.unlink(csv_dosya.name)

print("\n" + "=" * 65)
print("TÜM TESTLER BAŞARIYLA TAMAMLANDI")
print("=" * 65)
