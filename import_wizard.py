"""
Novel Çevirmen — İçe Aktarma Sihirbazı (import_wizard.py)

Bölüm 2.1 — Klasör bazlı TXT içe aktarma (önizleme + doğal sıralama)
Bölüm 2.2 — Çoklu klasör / çoklu seri batch import
Bölüm 2.3 — İçe aktarma + toplu çeviri entegrasyonu
Bölüm 2.4 — EPUB toplu import (çoklu dosya)

Tüm uzun işlemler QThread worker'da çalışır; UI donmaz, iptal edilebilir.
"""

from __future__ import annotations

import os
import time
from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QHeaderView, QAbstractItemView, QLineEdit,
)

from importers import (
    _dosya_icerigini_oku,
    _epub_icerik_dosyalari_bul,
    _HtmlMetinCikartici,
    _icerik_hash,
    dogal_sirala,
    dosya_adından_bolum_no,
)

import zipfile as _zipfile


# =============================================================================
# WORKER — TXT/EPUB arka plan içe aktarma
# =============================================================================

class IceAktarmaWorker(QThread):
    """
    TXT ve EPUB dosyalarını arka planda içe aktaran QThread.

    Sinyaller:
        ilerleme(tamamlanan, toplam, mesaj)
        bolum_eklendi(seri_id, bolum_baslik)
        tamamlandi(basarili, atlanan, basarisiz_liste)
        hata(mesaj)
    """
    ilerleme      = pyqtSignal(int, int, str)     # (tamamlanan, toplam, mesaj)
    bolum_eklendi = pyqtSignal(int, str)           # (seri_id, baslik)
    tamamlandi    = pyqtSignal(int, int, list)     # (basarili, atlanan, hatalar)
    hata          = pyqtSignal(str)

    def __init__(
        self,
        gorevler: list[dict],
        db_manager,
        parent=None,
    ):
        """
        gorevler: [
            {
              "dosya_yolu": str,
              "seri_id": int,
              "bolum_no": int,
              "baslik": str,
              "tip": "txt" | "epub_bolum",  # epub_bolum → epub_zip_yolu da var
              "epub_zip_yolu": str (epub_bolum için),
              "epub_dosya_adi": str (epub_bolum için),
            }, ...
        ]
        """
        super().__init__(parent)
        self.gorevler   = gorevler
        self.db_manager = db_manager
        self._durdur    = False

    def dur(self):
        self._durdur = True
        self.requestInterruption()

    def run(self):
        toplam    = len(self.gorevler)
        basarili  = 0
        atlanan   = 0
        hatalar: list[tuple[str, str]] = []

        mevcut_hashler: dict[int, set[str]] = {}  # seri_id → hash seti

        def _hash_seti(seri_id: int) -> set[str]:
            if seri_id not in mevcut_hashler:
                bolumler = self.db_manager.serinin_bolumlerini_getir(seri_id)
                mevcut_hashler[seri_id] = {
                    _icerik_hash((b.get("orijinal_metin") or "").strip())
                    for b in bolumler
                    if (b.get("orijinal_metin") or "").strip()
                }
            return mevcut_hashler[seri_id]

        # Açık EPUB zip'leri cache'le (aynı dosya tekrar açılmasın)
        acik_zipler: dict[str, _zipfile.ZipFile] = {}

        try:
            for i, gorev in enumerate(self.gorevler):
                if self._durdur or self.isInterruptionRequested():
                    break

                dosya_adi = gorev.get("dosya_yolu") or gorev.get("epub_zip_yolu", "")
                baslik    = gorev.get("baslik", os.path.basename(dosya_adi))
                seri_id   = gorev.get("seri_id", 0)
                bolum_no  = gorev.get("bolum_no", i + 1)
                tip       = gorev.get("tip", "txt")

                self.ilerleme.emit(i, toplam, f"{baslik[:40]}")

                try:
                    if tip == "txt":
                        icerik = _dosya_icerigini_oku(dosya_adi)
                        if not icerik:
                            hatalar.append((baslik, "dosya okunamadı"))
                            continue
                    elif tip == "epub_bolum":
                        zip_yolu      = gorev.get("epub_zip_yolu", "")
                        epub_dosya_adi = gorev.get("epub_dosya_adi", "")
                        if zip_yolu not in acik_zipler:
                            acik_zipler[zip_yolu] = _zipfile.ZipFile(zip_yolu, "r")
                        epub = acik_zipler[zip_yolu]
                        html_bytes = epub.read(epub_dosya_adi)
                        html_str   = html_bytes.decode("utf-8", errors="replace")
                        icerik     = _HtmlMetinCikartici.cevir(html_str)
                        if len(icerik.strip()) < 50:
                            atlanan += 1
                            continue
                    else:
                        hatalar.append((baslik, f"bilinmeyen görev tipi: {tip}"))
                        continue

                    # Mükerrer kontrolü
                    h = _icerik_hash(icerik)
                    hs = _hash_seti(seri_id)
                    if h in hs:
                        atlanan += 1
                        continue

                    self.db_manager.bolum_olustur(
                        seri_id=seri_id,
                        bolum_no=bolum_no,
                        bolum_baslik=baslik,
                        orijinal_metin=icerik,
                    )
                    hs.add(h)
                    basarili += 1
                    self.bolum_eklendi.emit(seri_id, baslik)

                except Exception as exc:
                    hatalar.append((baslik, str(exc)[:120]))

        finally:
            for z in acik_zipler.values():
                try:
                    z.close()
                except Exception:
                    pass

        self.tamamlandi.emit(basarili, atlanan, hatalar)


# =============================================================================
# YARDIMCI — klasör tarama
# =============================================================================

def klasoru_tara(
    klasor_yolu: str,
    alt_klasorler: bool = False,
    uzantilar: tuple[str, ...] = (".txt",),
) -> list[str]:
    """
    Klasördeki dosyaları bulur ve doğal sırayla döner.
    alt_klasorler=True ise alt dizinler de dahil edilir.
    """
    bulunan: list[str] = []
    if alt_klasorler:
        for kok, _dizinler, dosyalar in os.walk(klasor_yolu):
            for d in dosyalar:
                if d.lower().endswith(uzantilar):
                    bulunan.append(os.path.join(kok, d))
    else:
        try:
            for d in os.listdir(klasor_yolu):
                if d.lower().endswith(uzantilar):
                    bulunan.append(os.path.join(klasor_yolu, d))
        except OSError:
            pass
    return dogal_sirala(bulunan)


def epub_bolum_gorevleri_olustur(
    epub_yolu: str,
    seri_id: int,
    baslangic_bolum_no: int,
) -> list[dict]:
    """EPUB dosyasındaki her bölüm için worker görevi dict'i döner."""
    try:
        with _zipfile.ZipFile(epub_yolu, "r") as epub:
            dosya_listesi = _epub_icerik_dosyalari_bul(epub)
    except Exception:
        return []

    gorevler = []
    for i, dosya_adi in enumerate(dosya_listesi):
        baslik = os.path.splitext(os.path.basename(dosya_adi))[0]
        import re as _re
        baslik = _re.sub(r"[-_]", " ", baslik).title()
        gorevler.append({
            "tip":            "epub_bolum",
            "epub_zip_yolu":  epub_yolu,
            "epub_dosya_adi": dosya_adi,
            "seri_id":        seri_id,
            "bolum_no":       baslangic_bolum_no + i,
            "baslik":         baslik,
        })
    return gorevler


# =============================================================================
# 2.1 — KLASÖR ÖNIZLEME DİYALOĞU
# =============================================================================

class KlasorOnizlemeDiyalogu(QDialog):
    """
    Klasör taramasından bulunan dosyaları listeler; kullanıcı
    onay kutularıyla hangileri eklensin seçebilir.
    """

    def __init__(self, dosyalar: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("İçe Aktarma Önizlemesi")
        self.setMinimumSize(640, 460)
        self.setModal(True)
        self._dosyalar = dosyalar
        self._satirlar: list[tuple[QCheckBox, str, str]] = []  # (cb, yol, baslik)
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(14, 14, 14, 10)
        duzen.setSpacing(8)

        baslik_label = QLabel(
            f"<b>{len(self._dosyalar)}</b> dosya bulundu. "
            "İçe aktarmak istemediklerinizin işaretini kaldırın:"
        )
        baslik_label.setWordWrap(True)
        duzen.addWidget(baslik_label)

        # Tümünü seç / kaldır
        secim_satiri = QHBoxLayout()
        hepsini_sec = QPushButton("Tümünü Seç")
        hepsini_kaldir = QPushButton("Tümünü Kaldır")
        hepsini_sec.clicked.connect(lambda: self._hepsini_isle(True))
        hepsini_kaldir.clicked.connect(lambda: self._hepsini_isle(False))
        secim_satiri.addWidget(hepsini_sec)
        secim_satiri.addWidget(hepsini_kaldir)
        secim_satiri.addStretch()
        duzen.addLayout(secim_satiri)

        # Dosya listesi (scroll)
        alan = QScrollArea()
        alan.setWidgetResizable(True)
        alan.setFrameShape(QScrollArea.Shape.NoFrame)
        kap = QWidget()
        kap_duzen = QVBoxLayout(kap)
        kap_duzen.setSpacing(2)
        kap_duzen.setContentsMargins(2, 2, 2, 2)

        for dosya in self._dosyalar:
            no, baslik = dosya_adından_bolum_no(dosya)
            no_str = f"[{no:4d}]" if no != 9999 else "[  —  ]"
            cb = QCheckBox(f"{no_str}  {baslik}  —  {os.path.basename(dosya)}")
            cb.setChecked(True)
            cb.setToolTip(dosya)
            kap_duzen.addWidget(cb)
            self._satirlar.append((cb, dosya, baslik))

        kap_duzen.addStretch()
        alan.setWidget(kap)
        duzen.addWidget(alan, stretch=1)

        # Butonlar
        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.accepted.connect(self.accept)
        butonlar.rejected.connect(self.reject)
        duzen.addWidget(butonlar)

    def _hepsini_isle(self, durum: bool):
        for cb, _, __ in self._satirlar:
            cb.setChecked(durum)

    def secili_dosyalar(self) -> list[str]:
        return [yol for cb, yol, _ in self._satirlar if cb.isChecked()]


# =============================================================================
# 2.2 — ÇOKLU KLASÖr EŞLEŞTİRME DİYALOĞU
# =============================================================================

class SeriEslestirmeDiyalogu(QDialog):
    """
    Her klasör için: mevcut seriye ekle veya yeni seri olarak oluştur.
    """

    def __init__(
        self,
        klasorler: list[str],
        mevcut_seriler: list[dict],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Klasör — Seri Eşleştirmesi")
        self.setMinimumSize(700, 480)
        self.setModal(True)
        self._klasorler    = klasorler
        self._mevcut_seriler = mevcut_seriler
        self._satirlar: list[dict] = []
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(14, 14, 14, 10)
        duzen.setSpacing(8)

        aciklama = QLabel(
            "Her klasör için bir hedef seri seçin veya yeni seri oluşturun.\n"
            "Seri adını düzenleyebilirsiniz."
        )
        aciklama.setWordWrap(True)
        duzen.addWidget(aciklama)

        tablo = QTableWidget(len(self._klasorler), 3)
        tablo.setHorizontalHeaderLabels(["Klasör", "Seri", "Seri Adı"])
        tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tablo.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tablo.verticalHeader().setVisible(False)

        seri_secenekleri = ["— Yeni Seri Oluştur —"] + [
            s.get("baslik", "") for s in self._mevcut_seriler
        ]

        for i, klasor in enumerate(self._klasorler):
            klasor_adi = os.path.basename(klasor.rstrip("/\\")) or klasor

            # Klasör hücresi
            tablo.setItem(i, 0, QTableWidgetItem(klasor_adi))
            tablo.item(i, 0).setToolTip(klasor)

            # Seri seçici
            combo = QComboBox()
            combo.addItems(seri_secenekleri)
            tablo.setCellWidget(i, 1, combo)

            # Seri adı giriş
            ad_edit = QLineEdit(klasor_adi)
            tablo.setCellWidget(i, 2, ad_edit)

            # combo değişince ad_edit güncelle
            def _combo_degisti(idx, combo=combo, ad_edit=ad_edit, klasor_adi=klasor_adi):
                if idx == 0:
                    ad_edit.setEnabled(True)
                else:
                    ad_edit.setText(seri_secenekleri[idx])
                    ad_edit.setEnabled(False)
            combo.currentIndexChanged.connect(_combo_degisti)

            self._satirlar.append({
                "klasor":   klasor,
                "combo":    combo,
                "ad_edit":  ad_edit,
            })

        duzen.addWidget(tablo, stretch=1)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.accepted.connect(self.accept)
        butonlar.rejected.connect(self.reject)
        duzen.addWidget(butonlar)

    def eslestirmeler(self) -> list[dict]:
        """
        Döndürür: [
            {
              "klasor": str,
              "seri_id": int | None,   # None → yeni seri oluştur
              "seri_adi": str,
            }, ...
        ]
        """
        sonuc = []
        for satir in self._satirlar:
            combo   = satir["combo"]
            ad_edit = satir["ad_edit"]
            idx     = combo.currentIndex()
            if idx == 0:
                seri_id = None
            else:
                seri_id = self._mevcut_seriler[idx - 1]["id"]
            sonuc.append({
                "klasor":   satir["klasor"],
                "seri_id":  seri_id,
                "seri_adi": ad_edit.text().strip() or os.path.basename(satir["klasor"]),
            })
        return sonuc


# =============================================================================
# İLERLEME DİYALOĞU
# =============================================================================

class IlerlemeDialogu(QDialog):
    """Import/çeviri sırasında ilerleme gösteren iptal edilebilir diyalog."""

    def __init__(self, baslik: str, toplam: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.setMinimumWidth(440)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self._iptal_istendi = False
        self._arayuz_olustur(toplam)

    def _arayuz_olustur(self, toplam: int):
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 16, 16, 12)
        duzen.setSpacing(10)

        self._mesaj_label = QLabel("Hazırlanıyor...")
        self._mesaj_label.setWordWrap(True)
        duzen.addWidget(self._mesaj_label)

        self._cubuk = QProgressBar()
        self._cubuk.setRange(0, max(toplam, 1))
        self._cubuk.setValue(0)
        duzen.addWidget(self._cubuk)

        self._detay_label = QLabel("")
        self._detay_label.setStyleSheet("color: #8888aa; font-size: 11px;")
        self._detay_label.setWordWrap(True)
        duzen.addWidget(self._detay_label)

        self._iptal_btn = QPushButton("İptal")
        self._iptal_btn.clicked.connect(self._iptal_et)
        satir = QHBoxLayout()
        satir.addStretch()
        satir.addWidget(self._iptal_btn)
        duzen.addLayout(satir)

    def _iptal_et(self):
        self._iptal_istendi = True
        self._iptal_btn.setEnabled(False)
        self._mesaj_label.setText("İptal ediliyor...")

    def iptal_mi(self) -> bool:
        return self._iptal_istendi

    def guncelle(self, tamamlanan: int, toplam: int, mesaj: str):
        self._cubuk.setRange(0, max(toplam, 1))
        self._cubuk.setValue(tamamlanan)
        self._mesaj_label.setText(f"({tamamlanan}/{toplam}) {mesaj}")

    def detay_guncelle(self, detay: str):
        self._detay_label.setText(detay)


# =============================================================================
# ANA SIHIRBAZ — KLASÖR / TOPLU IMPORT
# =============================================================================

class IceAktarmaSihirbazi(QDialog):
    """
    Ana import sihirbazı.
    Mod: "klasor" (2.1), "coklu_klasor" (2.2), "epub_toplu" (2.4)
    """

    # Sinyaller — main_window.py bağlanabilir
    seri_guncellendi = pyqtSignal(int)  # import tamamlanan seri_id'leri

    def __init__(
        self,
        db_manager,
        translator=None,
        mod: str = "klasor",          # "klasor" | "coklu_klasor" | "epub_toplu"
        baslangic_seri_id: int = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager       = db_manager
        self.translator       = translator
        self.mod              = mod
        self.baslangic_seri_id = baslangic_seri_id
        self._worker: IceAktarmaWorker | None = None
        self._ilerleme_dlg: IlerlemeDialogu | None = None
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        basliklar = {
            "klasor":        "Klasör Bazlı İçe Aktarma",
            "coklu_klasor":  "Çoklu Klasör / Çoklu Seri İçe Aktarma",
            "epub_toplu":    "Çoklu EPUB Dosyası İçe Aktarma",
        }
        self.setWindowTitle(basliklar.get(self.mod, "İçe Aktarma Sihirbazı"))
        self.setMinimumSize(580, 200)
        self.setModal(True)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 16, 16, 12)
        duzen.setSpacing(12)

        # --- Seçenekler ---
        if self.mod == "klasor":
            self._klasor_widget(duzen)
        elif self.mod == "coklu_klasor":
            self._coklu_klasor_widget(duzen)
        elif self.mod == "epub_toplu":
            self._epub_toplu_widget(duzen)

        # --- Ortak seçenekler ---
        secenekler_grup = QGroupBox("Seçenekler")
        sec_duzen = QVBoxLayout(secenekler_grup)

        self._alt_klasor_cb = QCheckBox("Alt klasörleri de tara")
        self._alt_klasor_cb.setChecked(False)
        if self.mod in ("klasor", "coklu_klasor"):
            sec_duzen.addWidget(self._alt_klasor_cb)

        self._sozluk_tara_cb = QCheckBox("İçe aktarırken sözlük önerilerini çıkar (NER analizi)")
        self._sozluk_tara_cb.setChecked(False)
        sec_duzen.addWidget(self._sozluk_tara_cb)

        self._ceviri_cb = QCheckBox("İçe aktarılan bölümleri hemen otomatik çevir")
        self._ceviri_cb.setChecked(False)
        if self.translator is None:
            self._ceviri_cb.setEnabled(False)
            self._ceviri_cb.setToolTip("Çeviri için önce bir AI sağlayıcı ekleyin.")
        sec_duzen.addWidget(self._ceviri_cb)

        duzen.addWidget(secenekler_grup)

        # Butonlar
        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.button(QDialogButtonBox.StandardButton.Ok).setText("İçe Aktar")
        butonlar.accepted.connect(self._basla)
        butonlar.rejected.connect(self.reject)
        duzen.addWidget(butonlar)

    # ── Mod bazlı widget'lar ─────────────────────────────────────────────────

    def _klasor_widget(self, duzen: QVBoxLayout):
        satir = QHBoxLayout()
        self._klasor_edit = QLineEdit()
        self._klasor_edit.setPlaceholderText("Klasör seçin...")
        self._klasor_edit.setReadOnly(True)
        sec_btn = QPushButton("Gözat...")
        sec_btn.clicked.connect(self._klasor_sec)
        satir.addWidget(QLabel("Klasör:"))
        satir.addWidget(self._klasor_edit, stretch=1)
        satir.addWidget(sec_btn)
        duzen.addLayout(satir)

    def _coklu_klasor_widget(self, duzen: QVBoxLayout):
        satir = QHBoxLayout()
        self._klasor_listesi = QListWidget()
        self._klasor_listesi.setMaximumHeight(110)
        ekle_btn = QPushButton("Klasör Ekle...")
        ekle_btn.clicked.connect(self._coklu_klasor_ekle)
        sil_btn = QPushButton("Seçiliyi Sil")
        sil_btn.clicked.connect(lambda: self._klasor_listesi.takeItem(
            self._klasor_listesi.currentRow()
        ))
        btn_col = QVBoxLayout()
        btn_col.addWidget(ekle_btn)
        btn_col.addWidget(sil_btn)
        btn_col.addStretch()
        satir.addWidget(self._klasor_listesi, stretch=1)
        satir.addLayout(btn_col)
        duzen.addLayout(satir)

    def _epub_toplu_widget(self, duzen: QVBoxLayout):
        satir = QHBoxLayout()
        self._epub_listesi = QListWidget()
        self._epub_listesi.setMaximumHeight(110)
        ekle_btn = QPushButton("EPUB Ekle...")
        ekle_btn.clicked.connect(self._epub_ekle)
        sil_btn = QPushButton("Seçiliyi Sil")
        sil_btn.clicked.connect(lambda: self._epub_listesi.takeItem(
            self._epub_listesi.currentRow()
        ))
        btn_col = QVBoxLayout()
        btn_col.addWidget(ekle_btn)
        btn_col.addWidget(sil_btn)
        btn_col.addStretch()
        satir.addWidget(self._epub_listesi, stretch=1)
        satir.addLayout(btn_col)
        duzen.addLayout(satir)

    # ── Yardımcı slotlar ─────────────────────────────────────────────────────

    def _klasor_sec(self):
        klasor = QFileDialog.getExistingDirectory(self, "Klasör Seç", "")
        if klasor:
            self._klasor_edit.setText(klasor)

    def _coklu_klasor_ekle(self):
        klasor = QFileDialog.getExistingDirectory(self, "Klasör Seç", "")
        if klasor:
            self._klasor_listesi.addItem(klasor)

    def _epub_ekle(self):
        dosyalar, _ = QFileDialog.getOpenFileNames(
            self, "EPUB Dosyaları Seç", "",
            "EPUB Dosyaları (*.epub);;Tüm Dosyalar (*)"
        )
        for d in dosyalar:
            self._epub_listesi.addItem(d)

    # ── Başlat ───────────────────────────────────────────────────────────────

    def _basla(self):
        if self.mod == "klasor":
            self._klasor_modu_baslat()
        elif self.mod == "coklu_klasor":
            self._coklu_klasor_modu_baslat()
        elif self.mod == "epub_toplu":
            self._epub_toplu_modu_baslat()

    def _klasor_modu_baslat(self):
        klasor = self._klasor_edit.text().strip()
        if not klasor or not os.path.isdir(klasor):
            QMessageBox.warning(self, "Klasör Seçilmedi", "Lütfen geçerli bir klasör seçin.")
            return

        alt_kl = self._alt_klasor_cb.isChecked()
        dosyalar = klasoru_tara(klasor, alt_kl, uzantilar=(".txt",))
        if not dosyalar:
            QMessageBox.information(self, "Klasör Boş", "Seçilen klasörde TXT dosyası bulunamadı.")
            return

        # Önizleme diyaloğu
        onizleme = KlasorOnizlemeDiyalogu(dosyalar, self)
        if onizleme.exec() != QDialog.DialogCode.Accepted:
            return
        secili = onizleme.secili_dosyalar()
        if not secili:
            return

        # Seri belirleme
        seri_id = self.baslangic_seri_id
        if not seri_id:
            seri_id = self._seri_sec_veya_olustur(os.path.basename(klasor.rstrip("/\\")))
        if not seri_id:
            return

        gorevler = self._txt_gorevleri_olustur(secili, seri_id)
        self._worker_baslat(gorevler, [seri_id])

    def _coklu_klasor_modu_baslat(self):
        klasorler = [
            self._klasor_listesi.item(i).text()
            for i in range(self._klasor_listesi.count())
        ]
        if not klasorler:
            QMessageBox.warning(self, "Klasör Yok", "Lütfen en az bir klasör ekleyin.")
            return

        mevcut_seriler = self.db_manager.tum_serileri_getir()
        eslestirme_dlg = SeriEslestirmeDiyalogu(klasorler, mevcut_seriler, self)
        if eslestirme_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        eslestirmeler = eslestirme_dlg.eslestirmeler()
        alt_kl = self._alt_klasor_cb.isChecked()

        tum_gorevler: list[dict] = []
        seri_idler:   list[int]  = []

        for eslesme in eslestirmeler:
            klasor   = eslesme["klasor"]
            seri_id  = eslesme["seri_id"]
            seri_adi = eslesme["seri_adi"]

            if seri_id is None:
                # Yeni seri oluştur
                seri_id = self.db_manager.seri_olustur(
                    baslik=seri_adi,
                    kaynak_dil="Çince",
                    hedef_dil="Türkçe",
                )

            if not seri_id:
                continue

            dosyalar = klasoru_tara(klasor, alt_kl, uzantilar=(".txt",))
            gorevler = self._txt_gorevleri_olustur(dosyalar, seri_id)
            tum_gorevler.extend(gorevler)
            if seri_id not in seri_idler:
                seri_idler.append(seri_id)

        if not tum_gorevler:
            QMessageBox.information(self, "Dosya Yok", "İçe aktarılacak TXT dosyası bulunamadı.")
            return

        self._worker_baslat(tum_gorevler, seri_idler)

    def _epub_toplu_modu_baslat(self):
        epub_yollari = [
            self._epub_listesi.item(i).text()
            for i in range(self._epub_listesi.count())
        ]
        if not epub_yollari:
            QMessageBox.warning(self, "Dosya Yok", "Lütfen en az bir EPUB ekleyin.")
            return

        mevcut_seriler = self.db_manager.tum_serileri_getir()
        # Her EPUB için klasör olarak muamele et
        eslestirmeler = []
        for epub_yolu in epub_yollari:
            ad = os.path.splitext(os.path.basename(epub_yolu))[0]
            eslestirmeler.append({
                "epub_yolu": epub_yolu,
                "seri_id":   None,
                "seri_adi":  ad,
            })

        eslestirme_dlg = SeriEslestirmeDiyalogu(
            [e["epub_yolu"] for e in eslestirmeler],
            mevcut_seriler,
            self,
        )
        if eslestirme_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        sonuclar = eslestirme_dlg.eslestirmeler()

        tum_gorevler: list[dict] = []
        seri_idler:   list[int]  = []

        for eslesme, epub_yolu in zip(sonuclar, epub_yollari):
            seri_id  = eslesme["seri_id"]
            seri_adi = eslesme["seri_adi"]

            if seri_id is None:
                seri_id = self.db_manager.seri_olustur(
                    baslik=seri_adi,
                    kaynak_dil="Çince",
                    hedef_dil="Türkçe",
                )

            if not seri_id:
                continue

            mevcut = self.db_manager.serinin_bolumlerini_getir(seri_id)
            bas_no  = max((b.get("bolum_no", 0) for b in mevcut), default=0) + 1
            gorevler = epub_bolum_gorevleri_olustur(epub_yolu, seri_id, bas_no)
            tum_gorevler.extend(gorevler)
            if seri_id not in seri_idler:
                seri_idler.append(seri_id)

        if not tum_gorevler:
            QMessageBox.information(self, "Bölüm Yok", "EPUB dosyalarından bölüm çıkarılamadı.")
            return

        self._worker_baslat(tum_gorevler, seri_idler)

    # ── Yardımcı metodlar ────────────────────────────────────────────────────

    def _txt_gorevleri_olustur(self, dosyalar: list[str], seri_id: int) -> list[dict]:
        mevcut = self.db_manager.serinin_bolumlerini_getir(seri_id)
        sonraki_no = max((b.get("bolum_no", 0) for b in mevcut), default=0) + 1
        gorevler = []
        for i, dosya in enumerate(dogal_sirala(dosyalar)):
            _no, baslik = dosya_adından_bolum_no(dosya)
            gorevler.append({
                "tip":        "txt",
                "dosya_yolu": dosya,
                "seri_id":    seri_id,
                "bolum_no":   sonraki_no + i,
                "baslik":     baslik,
            })
        return gorevler

    def _seri_sec_veya_olustur(self, onerilenseri_adi: str) -> int | None:
        """Kullanıcıya mevcut seri seçtir veya yeni seri adı gir."""
        seriler = self.db_manager.tum_serileri_getir()
        secenekler = ["— Yeni Seri Oluştur —"] + [s.get("baslik", "") for s in seriler]

        dlg = QDialog(self)
        dlg.setWindowTitle("Seri Seç")
        dlg.setMinimumWidth(360)
        dlg.setModal(True)
        duzen = QVBoxLayout(dlg)

        combo = QComboBox()
        combo.addItems(secenekler)
        duzen.addWidget(QLabel("Hangi seriye eklensin?"))
        duzen.addWidget(combo)

        ad_edit = QLineEdit(onerilenseri_adi)
        ad_label = QLabel("Yeni seri adı:")
        duzen.addWidget(ad_label)
        duzen.addWidget(ad_edit)

        def _combo_degisti(idx):
            gizle = idx != 0
            ad_label.setVisible(not gizle)
            ad_edit.setVisible(not gizle)
        combo.currentIndexChanged.connect(_combo_degisti)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.accepted.connect(dlg.accept)
        butonlar.rejected.connect(dlg.reject)
        duzen.addWidget(butonlar)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        idx = combo.currentIndex()
        if idx == 0:
            ad = ad_edit.text().strip() or onerilenseri_adi
            return self.db_manager.seri_olustur(
                baslik=ad, kaynak_dil="Çince", hedef_dil="Türkçe"
            )
        else:
            return seriler[idx - 1]["id"]

    def _worker_baslat(self, gorevler: list[dict], seri_idler: list[int]):
        self._hedef_seri_idler = seri_idler
        toplam = len(gorevler)

        self._ilerleme_dlg = IlerlemeDialogu("İçe Aktarılıyor...", toplam, self)

        self._worker = IceAktarmaWorker(gorevler, self.db_manager, self)
        self._worker.ilerleme.connect(self._ilerleme_guncelle)
        self._worker.tamamlandi.connect(self._worker_tamamlandi)

        # İlerleme diyaloğundaki iptal butonu worker'ı durdursun
        self._ilerleme_dlg._iptal_btn.clicked.connect(self._worker.dur)

        self._worker.start()
        self._ilerleme_dlg.exec()  # Modal → worker bitince kapatılır

    def _ilerleme_guncelle(self, tamamlanan: int, toplam: int, mesaj: str):
        if self._ilerleme_dlg:
            self._ilerleme_dlg.guncelle(tamamlanan, toplam, mesaj)

    def _worker_tamamlandi(self, basarili: int, atlanan: int, hatalar: list):
        # İlerleme diyaloğunu kapat
        if self._ilerleme_dlg:
            self._ilerleme_dlg.close()
            self._ilerleme_dlg = None

        # Sözlük NER analizi (isteğe bağlı)
        if self._sozluk_tara_cb.isChecked() and basarili > 0:
            self._sozluk_analizi_yap()

        # Özet mesaj
        mesaj_satirlari = [f"✓ {basarili} bölüm başarıyla eklendi."]
        if atlanan:
            mesaj_satirlari.append(f"⏭ {atlanan} bölüm atlandı (mükerrer).")
        if hatalar:
            detay = "\n".join(f"  • {a}: {n}" for a, n in hatalar[:8])
            if len(hatalar) > 8:
                detay += f"\n  ... ve {len(hatalar) - 8} hata daha."
            mesaj_satirlari.append(f"✗ {len(hatalar)} dosyada hata:\n{detay}")

        QMessageBox.information(
            self, "İçe Aktarma Tamamlandı", "\n".join(mesaj_satirlari)
        )

        # Güncellenen serileri bildir
        for sid in self._hedef_seri_idler:
            self.seri_guncellendi.emit(sid)

        # Toplu çeviri
        if self._ceviri_cb.isChecked() and self.translator and basarili > 0:
            self._toplu_ceviri_baslat()
        else:
            self.accept()

    def _sozluk_analizi_yap(self):
        """Eklenen bölümlerde NER analizi çalıştır (opsiyonel, ana thread'de)."""
        try:
            from story_dict import StoryDictionaryEngine
            for seri_id in getattr(self, "_hedef_seri_idler", []):
                mevcut = self.db_manager.sozluk_terimlerini_getir(seri_id, sadece_onaylandi=False)
                bolumler = self.db_manager.serinin_bolumlerini_getir(seri_id)
                engine = StoryDictionaryEngine(mevcut)
                adaylar = []
                for b in bolumler[-50:]:  # Son 50 bölümü tara
                    orijinal = (b.get("orijinal_metin") or "").strip()
                    if not orijinal:
                        continue
                    sonuc = engine.analyze_chapter(orijinal, bolum_no=b.get("bolum_no", 0))
                    for a in sonuc["auto_save"] + sonuc["suggestions"]:
                        adaylar.append({
                            "phrase":      a["phrase"],
                            "entity_type": a["entity_type"],
                            "confidence":  a["confidence"],
                            "frequency":   a["frequency"],
                            "bolum_no":    b.get("bolum_no", 0),
                        })
                if adaylar:
                    self.db_manager.oneri_ekle_toplu(seri_id, adaylar)
        except Exception as exc:
            import logging
            logging.getLogger("novel_cevirmen").warning(f"NER analizi başarısız: {exc}")

    def _toplu_ceviri_baslat(self):
        """
        Yeni eklenen bölümleri mevcut BatchTranslationWorker kuyruğuna ekler.
        chapters_widget.py'deki _toplu_ceviri_baslat() ile aynı mantığı kullanır.
        """
        # parent (main_window) üzerinden chapters_widget'a ulaş
        mw = self.parent()
        if mw and hasattr(mw, "chapters_widget") and mw.chapters_widget:
            cw = mw.chapters_widget
            if hasattr(cw, "_toplu_ceviri_baslat"):
                cw._toplu_ceviri_baslat()
        self.accept()


# =============================================================================
# KOLAYLIK FONKSİYONLARI — main_window.py'den çağrılır
# =============================================================================

def klasor_ice_aktar_ac(
    db_manager,
    translator=None,
    seri_id: int = None,
    parent=None,
) -> IceAktarmaSihirbazi:
    """Klasör bazlı import sihirbazını açar ve döndürür."""
    dlg = IceAktarmaSihirbazi(
        db_manager=db_manager,
        translator=translator,
        mod="klasor",
        baslangic_seri_id=seri_id,
        parent=parent,
    )
    dlg.exec()
    return dlg


def coklu_klasor_ice_aktar_ac(
    db_manager,
    translator=None,
    parent=None,
) -> IceAktarmaSihirbazi:
    """Çoklu klasör / çoklu seri import sihirbazını açar."""
    dlg = IceAktarmaSihirbazi(
        db_manager=db_manager,
        translator=translator,
        mod="coklu_klasor",
        parent=parent,
    )
    dlg.exec()
    return dlg


def epub_toplu_ice_aktar_ac(
    db_manager,
    translator=None,
    parent=None,
) -> IceAktarmaSihirbazi:
    """Çoklu EPUB import sihirbazını açar."""
    dlg = IceAktarmaSihirbazi(
        db_manager=db_manager,
        translator=translator,
        mod="epub_toplu",
        parent=parent,
    )
    dlg.exec()
    return dlg