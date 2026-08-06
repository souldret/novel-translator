"""
Novel Çevirmen - Bölümler Widget'ı
Seri bölümlerini listeleme, metin girişi, AI çevirisi ve kaydetme işlemlerini
yöneten ana çeviri bileşeni.
"""

import sys
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QSplitter, QTextEdit, QLineEdit,
    QComboBox, QDialog, QFormLayout, QSpinBox, QGroupBox,
    QMessageBox, QFileDialog, QProgressBar, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QFrame,
    QSizePolicy, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QKeySequence, QTextCursor, QShortcut
from icons import pixmap, set_icon
from text_utils import metni_parcala, parcalari_birlestir, metin_icerisinde_ara, VARSAYILAN_PARCA_BOYUTU
from quality_tools import sozluk_uyum_goster, diff_goster


# =============================================================================
# DURUM SABİTLERİ
# =============================================================================

# Veritabanı durum kodları → görünen metin eşlemesi
DURUM_GORUNUM = {
    "beklemede": "Beklemede",
    "cevirildi": "Çevrildi",
    "incelendi": "İncelendi",
}

# Görünen metin → veritabanı kodu (ters eşleme)
GORUNUM_DURUM = {v: k for k, v in DURUM_GORUNUM.items()}

# Durum renkleri
DURUM_RENKLER = {
    "beklemede": "#6b5a7a",
    "cevirildi": "#9b59d0",
    "incelendi": "#a0f0b0",
}

# Kategori görünen adları (sözlük önizleme için)
KATEGORI_GORUNUM = {
    "karakter": "Karakter",
    "mekan":    "Mekan",
    "beceri":   "Beceri",
    "esya":     "Eşya",
    "sistem":   "Sistem Mesajı",
    "diger":    "Diğer",
}


# =============================================================================
# ÇEVİRİ WORKER (QThread)
# =============================================================================

class TranslationWorker(QThread):
    """
    AI çeviri işlemini arka planda yürüten QThread alt sınıfı.
    Streaming destekleyen sağlayıcılar için token token sinyal yayar.

    Sinyaller:
        tamamlandi(str)  : Çeviri başarıyla tamamlandığında çevrilmiş metni taşır
        hata(str)        : Hata oluştuğunda Türkçe hata mesajını taşır
        token_geldi(str) : Streaming modunda her token geldiğinde tetiklenir
    """

    tamamlandi      = pyqtSignal(str)
    hata            = pyqtSignal(str)
    token_geldi     = pyqtSignal(str)
    sure_hesaplandi = pyqtSignal(float)

    def __init__(
        self,
        translator,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list,
        db_manager=None,
        saglayici: str = "",
        model_adi: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.translator       = translator
        self.orijinal_metin   = orijinal_metin
        self.kaynak_dil       = kaynak_dil
        self.hedef_dil        = hedef_dil
        self.sozluk_terimleri = sozluk_terimleri
        self.db_manager       = db_manager
        self.saglayici        = saglayici
        self.model_adi        = model_adi

    def _token_yay(self, token: str):
        """İptal edilmediyse streaming token'ını UI'ya iletir."""
        if not self.isInterruptionRequested():
            self.token_geldi.emit(token)

    def _tek_parca_cevir(self, metin: str) -> str:
        """Tek bir metin parçasını çevirir (streaming veya normal)."""
        if getattr(self.translator, "streaming_destekli", False) and len(metin) <= VARSAYILAN_PARCA_BOYUTU:
            return self.translator.translate_bolum_stream(
                orijinal_metin=metin,
                kaynak_dil=self.kaynak_dil,
                hedef_dil=self.hedef_dil,
                sozluk_terimleri=self.sozluk_terimleri,
                on_token=self._token_yay,
            )
        return self.translator.translate_bolum(
            orijinal_metin=metin,
            kaynak_dil=self.kaynak_dil,
            hedef_dil=self.hedef_dil,
            sozluk_terimleri=self.sozluk_terimleri,
        )

    def run(self):
        """
        Thread başlatıldığında çalışır.
        Önce önbellekte çeviri arar; varsa anında döner.
        Uzun metinler parçalanarak çevrilir ve birleştirilir.
        """
        _baslangic = time.time()
        try:
            # ── Önbellek kontrolü ────────────────────────────────────────
            if self.db_manager and self.saglayici and self.model_adi:
                onbellekteki = self.db_manager.onbellekten_getir(
                    self.orijinal_metin, self.saglayici, self.model_adi,
                    self.kaynak_dil, self.hedef_dil
                )
                if onbellekteki:
                    if not self.isInterruptionRequested():
                        self.sure_hesaplandi.emit(time.time() - _baslangic)
                        self.tamamlandi.emit(onbellekteki)
                    return

            # ── Uzun metin parçalama ─────────────────────────────────────
            parcalar = metni_parcala(self.orijinal_metin, VARSAYILAN_PARCA_BOYUTU)
            cevrilen_parcalar: list[str] = []

            for i, parca in enumerate(parcalar):
                if self.isInterruptionRequested():
                    return
                sonuc = self._tek_parca_cevir(parca)
                if sonuc and sonuc.startswith("HATA:"):
                    if not self.isInterruptionRequested():
                        self.hata.emit(sonuc)
                    return
                cevrilen_parcalar.append(sonuc or "")
                # Parçalar arası kısa nefes (rate-limit dostu)
                if i < len(parcalar) - 1 and not self.isInterruptionRequested():
                    time.sleep(0.15)

            if self.isInterruptionRequested():
                return

            sonuc = parcalari_birlestir(cevrilen_parcalar)
            gecen_sure = time.time() - _baslangic

            # Başarılı çeviriyi önbelleğe kaydet
            if self.db_manager and self.saglayici and self.model_adi and sonuc:
                self.db_manager.onbellege_kaydet(
                    self.orijinal_metin, self.saglayici, self.model_adi,
                    self.kaynak_dil, self.hedef_dil, sonuc
                )
            self.sure_hesaplandi.emit(gecen_sure)
            self.tamamlandi.emit(sonuc or "")

        except Exception as exc:
            if not self.isInterruptionRequested():
                self.hata.emit(f"Çeviri sırasında beklenmeyen hata oluştu:\n{exc}")


# =============================================================================
# TOPLU ÇEVİRİ WORKER
# =============================================================================

class BatchTranslationWorker(QThread):
    """
    Birden fazla bölümü sırayla çeviren QThread.
    Her bölüm tamamlandığında ilerleme sinyali yayar.
    Duraklat/Devam Et desteği içerir.
    """
    ilerleme     = pyqtSignal(int, int, str)   # (tamamlanan, toplam, bolum_baslik)
    bolum_bitti  = pyqtSignal(int, str)         # (bolum_id, cevrilmis_metin)
    tamamlandi   = pyqtSignal(int, int)         # (basarili, basarisiz)
    hata         = pyqtSignal(str)
    duraklatildi = pyqtSignal()
    devam_edildi = pyqtSignal()

    def __init__(
        self,
        translator,
        bolumler: list,
        seri: dict,
        sozluk_terimleri: list,
        db_manager=None,
        saglayici: str = "",
        model_adi: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.translator       = translator
        self.bolumler         = bolumler
        self.seri             = seri
        self.sozluk_terimleri = sozluk_terimleri
        self.db_manager       = db_manager
        self.saglayici        = saglayici
        self.model_adi        = model_adi
        self._durdur          = False
        self._duraklatildi    = False

    def dur(self):
        self._durdur = True
        self.requestInterruption()

    def duraklat(self):
        """Toplu çeviriyi duraklatır."""
        self._duraklatildi = True
        self.duraklatildi.emit()

    def devam_et(self):
        """Duraklatılmış toplu çeviriyi devam ettirir."""
        self._duraklatildi = False
        self.devam_edildi.emit()

    def _bolum_cevir(self, orijinal: str, kaynak_dil: str, hedef_dil: str) -> str:
        """Uzun metinleri parçalayarak çevirir."""
        parcalar = metni_parcala(orijinal, VARSAYILAN_PARCA_BOYUTU)
        cevrilen = []
        for parca in parcalar:
            if self._durdur or self.isInterruptionRequested():
                return "HATA: Çeviri iptal edildi."
            sonuc = self.translator.translate_bolum(
                orijinal_metin=parca,
                kaynak_dil=kaynak_dil,
                hedef_dil=hedef_dil,
                sozluk_terimleri=self.sozluk_terimleri,
            )
            if sonuc and sonuc.startswith("HATA:"):
                return sonuc
            cevrilen.append(sonuc or "")
        return parcalari_birlestir(cevrilen)

    def run(self):
        kaynak_dil = self.seri.get("kaynak_dil", "")
        hedef_dil  = self.seri.get("hedef_dil",  "")
        toplam     = len(self.bolumler)
        basarili   = 0
        basarisiz  = 0

        for i, bolum in enumerate(self.bolumler):
            if self._durdur or self.isInterruptionRequested():
                break

            bolum_id    = bolum["id"]
            baslik      = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no', i+1)}"
            orijinal    = (bolum.get("orijinal_metin") or "").strip()

            self.ilerleme.emit(i, toplam, baslik)

            if not orijinal:
                basarisiz += 1
                continue

            try:
                # Önbellek kontrolü
                sonuc = None
                if self.db_manager and self.saglayici and self.model_adi:
                    sonuc = self.db_manager.onbellekten_getir(
                        orijinal, self.saglayici, self.model_adi, kaynak_dil, hedef_dil
                    )

                if not sonuc:
                    sonuc = self._bolum_cevir(orijinal, kaynak_dil, hedef_dil)

                if self._durdur or self.isInterruptionRequested():
                    break

                if sonuc and sonuc.startswith("HATA:"):
                    basarisiz += 1
                else:
                    if self.db_manager and self.saglayici and self.model_adi and sonuc:
                        self.db_manager.onbellege_kaydet(
                            orijinal, self.saglayici, self.model_adi,
                            kaynak_dil, hedef_dil, sonuc
                        )
                    self.bolum_bitti.emit(bolum_id, sonuc or "")
                    basarili += 1

            except Exception as exc:
                basarisiz += 1
                print(f"[Toplu Çeviri] Bölüm {bolum_id} hatası: {exc}")

            # Duraklatma kontrolü
            while self._duraklatildi and not self._durdur and not self.isInterruptionRequested():
                time.sleep(0.1)

        self.tamamlandi.emit(basarili, basarisiz)


# =============================================================================
# METRİKLER WIDGET'I
# =============================================================================

class MetriklerWidget(QWidget):
    """
    Çeviri istatistiklerini gösteren küçük katlanabilir panel.
    Çeviri metin alanının altında görüntülenir.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._acik = False
        self._sure: float | None = None
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        self.setStyleSheet(
            "background-color: #0a0612; border-top: 1px solid #1a1225;"
        )
        dis_layout = QVBoxLayout(self)
        dis_layout.setContentsMargins(0, 0, 0, 0)
        dis_layout.setSpacing(0)

        # ── Başlık çubuğu (tıklanabilir) ─────────────────────────────────
        self._baslik_bar = QPushButton("▶  Çeviri Metrikleri")
        self._baslik_bar.setFlat(True)
        self._baslik_bar.setFixedHeight(28)
        self._baslik_bar.setStyleSheet("""
            QPushButton {
                background-color: #0a0612;
                color: #6b5a7a;
                border: none;
                text-align: left;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #110820;
                color: #9b59d0;
            }
        """)
        self._baslik_bar.clicked.connect(self._toggle)
        dis_layout.addWidget(self._baslik_bar)

        # ── İçerik alanı (başlangıçta gizli) ─────────────────────────────
        self._icerik = QWidget()
        self._icerik.setStyleSheet("background-color: #0a0612;")
        self._icerik.setVisible(False)
        icerik_layout = QHBoxLayout(self._icerik)
        icerik_layout.setContentsMargins(14, 6, 14, 8)
        icerik_layout.setSpacing(24)

        self._orijinal_kar_lbl  = self._metrik_label("Orijinal: —")
        self._ceviri_kar_lbl    = self._metrik_label("Çeviri: —")
        self._oran_lbl          = self._metrik_label("Oran: —")
        self._sure_lbl          = self._metrik_label("Süre: —")
        self._token_lbl         = self._metrik_label("Tahmini Token: —")

        for lbl in (
            self._orijinal_kar_lbl,
            self._ceviri_kar_lbl,
            self._oran_lbl,
            self._sure_lbl,
            self._token_lbl,
        ):
            icerik_layout.addWidget(lbl)

        icerik_layout.addStretch()
        dis_layout.addWidget(self._icerik)

    def _metrik_label(self, metin: str) -> QLabel:
        lbl = QLabel(metin)
        lbl.setStyleSheet("color: #9b59d0; font-size: 11px; background: transparent;")
        return lbl

    def _toggle(self):
        self._acik = not self._acik
        self._icerik.setVisible(self._acik)
        ok = "▼" if self._acik else "▶"
        self._baslik_bar.setText(f"{ok}  Çeviri Metrikleri")

    def guncelle(self, orijinal_metin: str, ceviri_metin: str, sure: float | None = None):
        """
        Metrikleri verilen metinlere göre yeniden hesaplar ve etiketleri günceller.
        sure: saniye cinsinden çeviri süresi (bilinmiyorsa None).
        """
        if sure is not None:
            self._sure = sure

        orig_kar  = len(orijinal_metin)
        cev_kar   = len(ceviri_metin)
        oran      = (cev_kar / orig_kar * 100) if orig_kar > 0 else 0.0
        tahmini_token = max(1, orig_kar // 4)

        self._orijinal_kar_lbl.setText(f"Orijinal: {orig_kar:,} kar")
        self._ceviri_kar_lbl.setText(f"Çeviri: {cev_kar:,} kar")
        self._oran_lbl.setText(f"Oran: {oran:.1f}%")

        if self._sure is not None:
            self._sure_lbl.setText(f"Süre: {self._sure:.1f}s")
        else:
            self._sure_lbl.setText("Süre: —")

        self._token_lbl.setText(f"Tahmini Token: ~{tahmini_token:,}")

    def sure_guncelle(self, sure: float):
        """Sadece süreyi günceller (sure_hesaplandi sinyaline bağlanır)."""
        self._sure = sure
        self._sure_lbl.setText(f"Süre: {sure:.1f}s")


# =============================================================================
# KARŞILAŞTIRMA DİYALOĞU
# =============================================================================

class KarsilastirmaDiyalogu(QDialog):
    """
    Orijinal metin ile çeviriyi yan yana gösteren karşılaştırma diyaloğu.
    İki metin alanının kaydırma çubukları senkronize çalışır.
    """

    def __init__(self, orijinal_metin: str, ceviri_metin: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Orijinal ↔ Çeviri Karşılaştırma")
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)
        self.setModal(True)
        self._arayuz_olustur(orijinal_metin, ceviri_metin)

    def _arayuz_olustur(self, orijinal_metin: str, ceviri_metin: str):
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(16, 16, 16, 12)
        ana_layout.setSpacing(10)

        # ── Başlık ────────────────────────────────────────────────────────
        baslik = QLabel("Orijinal ↔ Çeviri Karşılaştırma")
        baslik.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #9b59d0;")
        ana_layout.addWidget(baslik)

        # ── Yatay bölücü ──────────────────────────────────────────────────
        bolucü = QSplitter(Qt.Orientation.Horizontal)
        bolucü.setHandleWidth(6)
        bolucü.setStyleSheet("""
            QSplitter::handle {
                background-color: #1a1225;
                border-radius: 3px;
            }
            QSplitter::handle:hover { background-color: #9b59d0; }
        """)

        # Sol panel — Orijinal
        sol_panel = QWidget()
        sol_panel.setStyleSheet("background-color: #0f0a1a;")
        sol_layout = QVBoxLayout(sol_panel)
        sol_layout.setContentsMargins(0, 0, 4, 0)
        sol_layout.setSpacing(4)

        sol_baslik = QLabel("Orijinal Metin")
        sol_baslik.setStyleSheet(
            "color: #9b59d0; font-size: 12px; font-weight: 600; padding: 4px 0;"
        )
        sol_layout.addWidget(sol_baslik)

        self._sol_metin = QTextEdit()
        self._sol_metin.setReadOnly(True)
        self._sol_metin.setFont(QFont("Consolas", 11))
        self._sol_metin.setPlainText(orijinal_metin)
        self._sol_metin.setStyleSheet(self._metin_edit_stili())
        sol_layout.addWidget(self._sol_metin)

        # Sağ panel — Çeviri
        sag_panel = QWidget()
        sag_panel.setStyleSheet("background-color: #0f0a1a;")
        sag_layout = QVBoxLayout(sag_panel)
        sag_layout.setContentsMargins(4, 0, 0, 0)
        sag_layout.setSpacing(4)

        sag_baslik = QLabel("Çeviri")
        sag_baslik.setStyleSheet(
            "color: #a0f0b0; font-size: 12px; font-weight: 600; padding: 4px 0;"
        )
        sag_layout.addWidget(sag_baslik)

        self._sag_metin = QTextEdit()
        self._sag_metin.setReadOnly(True)
        self._sag_metin.setFont(QFont("Consolas", 11))
        self._sag_metin.setPlainText(ceviri_metin)
        self._sag_metin.setStyleSheet(self._metin_edit_stili())
        sag_layout.addWidget(self._sag_metin)

        bolucü.addWidget(sol_panel)
        bolucü.addWidget(sag_panel)
        bolucü.setSizes([580, 580])
        ana_layout.addWidget(bolucü, stretch=1)

        # ── Scroll senkronizasyonu ─────────────────────────────────────────
        sol_scroll = self._sol_metin.verticalScrollBar()
        sag_scroll = self._sag_metin.verticalScrollBar()
        sol_scroll.valueChanged.connect(sag_scroll.setValue)
        sag_scroll.valueChanged.connect(sol_scroll.setValue)

        # ── Alt buton ─────────────────────────────────────────────────────
        buton_layout = QHBoxLayout()
        buton_layout.addStretch()

        kapat_btn = QPushButton("Kapat")
        kapat_btn.setFixedWidth(100)
        kapat_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d1a40; color: #e8e0f0;
                border: none; border-radius: 6px;
                padding: 7px 16px; font-weight: 600;
            }
            QPushButton:hover { background-color: #3d2d55; }
        """)
        kapat_btn.clicked.connect(self.accept)
        buton_layout.addWidget(kapat_btn)
        ana_layout.addLayout(buton_layout)

    def _metin_edit_stili(self) -> str:
        return """
            QTextEdit {
                background-color: #130c20;
                color: #e8e0f0;
                border: none;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #9b59d0;
                selection-color: #0f0a1a;
            }
            QScrollBar:vertical {
                background: #0f0a1a; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2d1a40; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #3d2d55; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0; background: none;
            }
        """


# =============================================================================
# YENİ BÖLÜM DİYALOĞU
# =============================================================================

class YeniBolumDialog(QDialog):
    """Yeni bölüm oluşturma formu."""

    def __init__(self, parent=None, varsayilan_bolum_no: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Yeni Bölüm Ekle")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self.setModal(True)
        self._arayuz_olustur(varsayilan_bolum_no)

    def _arayuz_olustur(self, varsayilan_no: int):
        ana_layout = QVBoxLayout(self)
        ana_layout.setSpacing(14)
        ana_layout.setContentsMargins(24, 24, 24, 20)

        # ── Başlık ────────────────────────────────────────────────────────
        baslik = QLabel("Yeni Bölüm Ekle")
        baslik.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #9b59d0;")
        ana_layout.addWidget(baslik)

        # ── Form ──────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Bölüm No
        self.bolum_no_spin = QSpinBox()
        self.bolum_no_spin.setMinimum(0)
        self.bolum_no_spin.setMaximum(9999)
        self.bolum_no_spin.setValue(varsayilan_no)
        self.bolum_no_spin.setFixedWidth(100)
        form.addRow("Bölüm No:", self.bolum_no_spin)

        # Bölüm Başlığı
        self.baslik_input = QLineEdit()
        self.baslik_input.setPlaceholderText("Başlık girin veya boş bırakın")
        form.addRow("Bölüm Başlığı:", self.baslik_input)

        ana_layout.addLayout(form)

        # ── Orijinal Metin ────────────────────────────────────────────────
        metin_label = QLabel("Orijinal Metin:")
        metin_label.setStyleSheet("color: #6b5a7a; font-size: 12px;")
        ana_layout.addWidget(metin_label)

        self.metin_edit = QTextEdit()
        self.metin_edit.setPlaceholderText("Çevrilecek metni buraya yapıştırın...")
        self.metin_edit.setMinimumHeight(200)
        self.metin_edit.setFont(QFont("Consolas", 11))
        ana_layout.addWidget(self.metin_edit, stretch=1)

        # ── Butonlar ──────────────────────────────────────────────────────
        buton_layout = QHBoxLayout()
        buton_layout.addStretch()

        self.iptal_btn = QPushButton("İptal")
        self.iptal_btn.setFixedWidth(90)
        self.iptal_btn.setStyleSheet(self._ikincil_stil())
        self.iptal_btn.clicked.connect(self.reject)

        self.ekle_btn = QPushButton("Ekle")
        self.ekle_btn.setFixedWidth(100)
        self.ekle_btn.setStyleSheet(self._birincil_stil())
        self.ekle_btn.clicked.connect(self.accept)
        self.ekle_btn.setDefault(True)

        buton_layout.addWidget(self.iptal_btn)
        buton_layout.addSpacing(8)
        buton_layout.addWidget(self.ekle_btn)
        ana_layout.addLayout(buton_layout)

    def _birincil_stil(self):
        return """
            QPushButton {
                background-color: #9b59d0; color: #0f0a1a;
                border: none; border-radius: 6px;
                padding: 7px 16px; font-weight: 600;
            }
            QPushButton:hover { background-color: #b06ad9; }
        """

    def _ikincil_stil(self):
        return """
            QPushButton {
                background-color: #2d1a40; color: #e8e0f0;
                border: none; border-radius: 6px;
                padding: 7px 16px; font-weight: 600;
            }
            QPushButton:hover { background-color: #3d2d55; }
        """


# =============================================================================
# BÖLÜM LİSTESİ ÖGE WIDGET'I
# =============================================================================

class BolumListeOgesi(QWidget):
    """
    Sol paneldeki bölüm listesinde tek bir bölümü gösteren özel widget.
    Üst satır: bölüm numarası ve başlık (kalın)
    Alt satır: durum rozeti (renkli)
    """

    def __init__(self, bolum: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 5, 4, 5)

        # Bölüm başlığı satırı
        baslik_metni = f"Bölüm {bolum.get('bolum_no', '?')}"
        if bolum.get("bolum_baslik"):
            baslik_metni += f" — {bolum['bolum_baslik']}"

        baslik_label = QLabel(baslik_metni)
        baslik_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        baslik_label.setStyleSheet("color: #e8e0f0;")
        baslik_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Durum rozeti satırı
        durum_kodu    = bolum.get("durum", "beklemede")
        durum_metin   = DURUM_GORUNUM.get(durum_kodu, durum_kodu)
        durum_renk    = DURUM_RENKLER.get(durum_kodu, "#6b5a7a")

        durum_label = QLabel(durum_metin)
        durum_label.setStyleSheet(f"color: {durum_renk}; font-size: 11px;")
        durum_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(baslik_label)
        layout.addWidget(durum_label)


# =============================================================================
# ANA BÖLÜM WIDGET'I
# =============================================================================

class ChaptersWidget(QWidget):
    """
    Bir serinin bölümlerini listeleyen, metin girişi yapan,
    AI ile çeviren ve sonuçları kaydeden ana bileşen.
    """

    def __init__(self, seri_id=None, db_manager=None, translator=None, parent=None):
        super().__init__(parent)
        self.seri_id       = seri_id
        self.db_manager    = db_manager
        self.translator    = translator

        # Aktif bölüm durumu
        self.aktif_bolum_id: int | None = None
        self.aktif_bolum:    dict | None = None

        # Kaydedilmemiş değişiklik takibi
        self._kaydedilmemis = False

        # Devam eden çeviri worker'ı
        self._worker: TranslationWorker | None = None

        # Toplu çeviri worker
        self._batch_worker: "BatchTranslationWorker | None" = None

        # Streaming: anlık metin biriktirici
        self._streaming_birikim: list[str] = []

        # Senkronize scroll aktif mi?
        self._sync_scroll_aktif: bool = True

        # Durum filtresi (None = hepsi)
        self._filtre_durum: str | None = None

        # Arama metni filtresi
        self._arama_metni: str = ""

        # Geçici durum mesajı için timer
        self._durum_timer = QTimer(self)
        self._durum_timer.setSingleShot(True)
        self._durum_timer.timeout.connect(self._durum_mesajini_temizle)

        # Otomatik kaydetme — 30 saniyede bir çalışır
        self._otomatik_kaydet_timer = QTimer(self)
        self._otomatik_kaydet_timer.setInterval(30_000)
        self._otomatik_kaydet_timer.timeout.connect(self._otomatik_kaydet)
        self._otomatik_kaydet_timer.start()

        # Metin içi arama durumu
        self._metin_arama_son_idx: int = 0
        self._okuma_modu: bool = False

        self._arayuz_olustur()
        self._kisayollari_kur()

        if self.seri_id and self.db_manager:
            self.bolum_listesini_yukle()

    # =========================================================================
    # ARAYÜZ KURULUMU
    # =========================================================================

    def _arayuz_olustur(self):
        ana_layout = QHBoxLayout(self)
        ana_layout.setContentsMargins(0, 0, 0, 0)
        ana_layout.setSpacing(0)

        # Ana yatay bölücü: sol liste + sağ içerik
        self.ana_bolucu = QSplitter(Qt.Orientation.Horizontal)
        self.ana_bolucu.setHandleWidth(1)
        ana_layout.addWidget(self.ana_bolucu)

        # Sol panel
        self.sol_panel = self._sol_panel_olustur()
        self.ana_bolucu.addWidget(self.sol_panel)

        # Sağ panel — başlangıçta boş durum
        self.sag_panel_kapsayici = QWidget()
        self.sag_panel_kapsayici.setStyleSheet("background-color: #0f0a1a;")
        self.sag_layout = QVBoxLayout(self.sag_panel_kapsayici)
        self.sag_layout.setContentsMargins(0, 0, 0, 0)
        self._bos_durum_goster()
        self.ana_bolucu.addWidget(self.sag_panel_kapsayici)

        self.ana_bolucu.setSizes([280, 900])
        self.ana_bolucu.setStretchFactor(0, 0)
        self.ana_bolucu.setStretchFactor(1, 1)

    # ── Sol Panel ────────────────────────────────────────────────────────────

    def _sol_panel_olustur(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(280)
        panel.setStyleSheet("background-color: #0a0612;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Üst çubuk: başlık + buton
        ust_alan = QWidget()
        ust_alan.setStyleSheet("background-color: #0a0612; padding: 0;")
        ust_layout = QHBoxLayout(ust_alan)
        ust_layout.setContentsMargins(12, 10, 12, 10)
        ust_layout.setSpacing(8)

        bolumler_label = QLabel("BÖLÜMLER")
        bolumler_label.setStyleSheet(
            "color: #6b5a7a; font-size: 10px; font-weight: 600; letter-spacing: 1px;"
        )

        self.yeni_bolum_btn = QPushButton("  Yeni Bölüm")
        self.yeni_bolum_btn.setFixedHeight(30)
        self.yeni_bolum_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59d0; color: #0f0a1a;
                border: none; border-radius: 5px;
                padding: 4px 10px; font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background-color: #b06ad9; }
        """)
        set_icon(self.yeni_bolum_btn, "add", size=16)
        self.yeni_bolum_btn.clicked.connect(self._yeni_bolum_ekle)

        ust_layout.addWidget(bolumler_label)
        ust_layout.addStretch()
        ust_layout.addWidget(self.yeni_bolum_btn)
        layout.addWidget(ust_alan)

        # Ayırıcı
        layout.addWidget(self._ayirici())

        # ── Arama çubuğu ─────────────────────────────────────────────────
        arama_widget = QWidget()
        arama_widget.setStyleSheet("background-color: #0a0612;")
        arama_layout = QHBoxLayout(arama_widget)
        arama_layout.setContentsMargins(8, 6, 8, 4)
        arama_layout.setSpacing(4)

        self.arama_input = QLineEdit()
        self.arama_input.setPlaceholderText("Bölüm ara...")
        self.arama_input.setFixedHeight(28)
        self.arama_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #2d1a40;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #9b59d0; }
        """)
        self.arama_input.textChanged.connect(self._arama_degisti)
        arama_layout.addWidget(self.arama_input)
        layout.addWidget(arama_widget)

        layout.addWidget(self._ayirici())

        # ── Durum filtresi ────────────────────────────────────────────────
        filtre_widget = QWidget()
        filtre_widget.setStyleSheet("background-color: #0a0612;")
        filtre_layout = QHBoxLayout(filtre_widget)
        filtre_layout.setContentsMargins(8, 4, 8, 4)
        filtre_layout.setSpacing(4)

        self.filtre_combo = QComboBox()
        self.filtre_combo.addItem("Tümü", userData=None)
        for kod, gorunum in DURUM_GORUNUM.items():
            self.filtre_combo.addItem(gorunum, userData=kod)
        self.filtre_combo.setFixedHeight(26)
        self.filtre_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a1225; color: #9b59d0;
                border: 1px solid #2d1a40; border-radius: 4px;
                padding: 2px 8px; font-size: 10px;
            }
            QComboBox::drop-down { border: none; width: 16px; }
            QComboBox::down-arrow {
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid #9b59d0;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1225; color: #e8e0f0;
                border: 1px solid #3d2d55;
                selection-background-color: #2d1a40;
            }
        """)
        # NOT: filtre_combo sinyali bolum_listesi oluşturulduktan SONRA bağlanacak
        filtre_etiketi = QLabel("Filtre:")
        filtre_etiketi.setStyleSheet("color: #6b5a7a; font-size: 10px; background: transparent;")
        filtre_layout.addWidget(filtre_etiketi)
        filtre_layout.addWidget(self.filtre_combo, stretch=1)
        layout.addWidget(filtre_widget)

        # Ayırıcı
        layout.addWidget(self._ayirici())

        # Bölüm listesi
        self.bolum_listesi = QListWidget()

        # Sinyal artık güvenle bağlanabilir (bolum_listesi hazır)
        self.filtre_combo.currentIndexChanged.connect(self._filtre_degisti)
        self.bolum_listesi.setStyleSheet("""
            QListWidget {
                background-color: #0a0612;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 6px;
                margin: 2px 6px;
            }
            QListWidget::item:selected {
                background-color: #1a1225;
                border-left: 3px solid #9b59d0;
                padding-left: 5px;
            }
            QListWidget::item:hover:!selected {
                background-color: #130c20;
            }
        """)
        self.bolum_listesi.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.bolum_listesi.itemClicked.connect(self._bolum_secildi)
        self.bolum_listesi.itemDoubleClicked.connect(self._bolum_secildi)
        self.bolum_listesi.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.bolum_listesi.customContextMenuRequested.connect(
            self._baglan_menu_goster
        )
        layout.addWidget(self.bolum_listesi, stretch=1)

        # Ayırıcı
        layout.addWidget(self._ayirici())

        # Alt istatistik etiketi
        alt_alan = QWidget()
        alt_alan.setStyleSheet("background-color: #0a0612;")
        alt_layout = QVBoxLayout(alt_alan)
        alt_layout.setContentsMargins(12, 6, 12, 10)

        self.istatistik_label = QLabel("Toplam: 0 bölüm | Çevrilen: 0")
        self.istatistik_label.setStyleSheet(
            "color: #6b5a7a; font-size: 11px;"
        )
        alt_layout.addWidget(self.istatistik_label)
        layout.addWidget(alt_alan)

        return panel

    # ── Sağ Panel — Boş Durum ────────────────────────────────────────────────

    def _bos_durum_goster(self):
        """Bölüm seçili olmadığında karşılama ekranını gösterir."""
        self._sag_paneli_temizle()

        kapsayici = QWidget()
        ic_layout = QVBoxLayout(kapsayici)
        ic_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_layout.setSpacing(12)

        ikon = QLabel()
        ikon.setPixmap(pixmap("book", size=56))
        ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mesaj = QLabel("← Çevrilecek bölümü seçin\nveya yeni bölüm ekleyin")
        mesaj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mesaj.setStyleSheet("color: #6b5a7a; font-size: 14px;")

        ic_layout.addWidget(ikon)
        ic_layout.addWidget(mesaj)
        self.sag_layout.addWidget(kapsayici)

    # ── Sağ Panel — Bölüm İçeriği ────────────────────────────────────────────

    def _bolum_icerigi_goster(self, bolum: dict):
        """Seçilen bölümün düzenleme/çeviri panelini oluşturur."""
        self._sag_paneli_temizle()

        icerik = QWidget()
        icerik.setStyleSheet("background-color: #0f0a1a;")
        icerik_layout = QVBoxLayout(icerik)
        icerik_layout.setContentsMargins(14, 10, 14, 10)
        icerik_layout.setSpacing(8)

        # ── 1. Başlık çubuğu ─────────────────────────────────────────────
        icerik_layout.addLayout(self._baslik_cubugu_olustur(bolum))

        # ── 2. AI durum çubuğu ───────────────────────────────────────────
        self.ai_durum_widget = self._ai_durum_cubugu_olustur()
        icerik_layout.addWidget(self.ai_durum_widget)
        self._ai_durumunu_guncelle()

        # ── 3. Metin panelleri (yatay bölücü) ────────────────────────────
        metin_bolucü = QSplitter(Qt.Orientation.Horizontal)
        metin_bolucü.setHandleWidth(6)
        metin_bolucü.setStyleSheet("""
            QSplitter::handle {
                background-color: #1a1225;
                border-radius: 3px;
                margin: 4px 0;
            }
            QSplitter::handle:hover { background-color: #9b59d0; }
        """)

        # Orijinal metin paneli
        orijinal_grup = self._orijinal_panel_olustur(bolum)
        metin_bolucü.addWidget(orijinal_grup)

        # Çeviri metin paneli
        ceviri_grup = self._ceviri_panel_olustur(bolum)
        metin_bolucü.addWidget(ceviri_grup)

        metin_bolucü.setSizes([500, 500])
        icerik_layout.addWidget(metin_bolucü, stretch=1)

        # ── 4. Alt eylem çubuğu ──────────────────────────────────────────
        icerik_layout.addWidget(self._eylem_cubugu_olustur())

        # ── 5. Sözlük önizleme (katlanabilir) ────────────────────────────
        self.sozluk_onizleme = self._sozluk_onizleme_olustur()
        icerik_layout.addWidget(self.sozluk_onizleme)

        self.sag_layout.addWidget(icerik)

        # Metin değişiklik izleyicilerini bağla
        self.orijinal_metin_edit.textChanged.connect(self._degisiklik_isaretlendir)
        self.ceviri_metin_edit.textChanged.connect(self._degisiklik_isaretlendir)
        self.orijinal_metin_edit.textChanged.connect(self._karakter_sayaci_guncelle)
        self.ceviri_metin_edit.textChanged.connect(self._karakter_sayaci_guncelle_ceviri)
        self.orijinal_metin_edit.textChanged.connect(self._token_tahminini_guncelle)

        # Senkronize scroll bağlantıları
        self.orijinal_metin_edit.verticalScrollBar().valueChanged.connect(
            self._orijinal_scroll_degisti
        )
        self.ceviri_metin_edit.verticalScrollBar().valueChanged.connect(
            self._ceviri_scroll_degisti
        )

    def _baslik_cubugu_olustur(self, bolum: dict) -> QHBoxLayout:
        """Düzenlenebilir bölüm başlığı + kaydedilmemiş gösterge + durum seçici."""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # Bölüm başlığı (düzenlenebilir)
        varsayilan_baslik = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no', '')}"
        self.baslik_input = QLineEdit(varsayilan_baslik)
        self.baslik_input.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.baslik_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                border-bottom: 2px solid #1a1225;
                border-radius: 0px;
                color: #e8e0f0;
                padding: 4px 2px;
                font-size: 14px;
                font-weight: 700;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #9b59d0;
                background-color: #130c20;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        self.baslik_input.textChanged.connect(self._degisiklik_isaretlendir)

        # Kaydedilmemiş değişiklik göstergesi — sadece içerik olduğunda yer kaplar
        self.degisiklik_label = QLabel("")
        self.degisiklik_label.setStyleSheet(
            "color: #f0d090; font-size: 11px; padding: 0 4px;"
        )
        self.degisiklik_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

        # Durum ComboBox
        self.durum_combo = QComboBox()
        for kod, gorunum in DURUM_GORUNUM.items():
            self.durum_combo.addItem(gorunum, userData=kod)
        mevcut_durum = bolum.get("durum", "beklemede")
        idx = self.durum_combo.findData(mevcut_durum)
        if idx >= 0:
            self.durum_combo.setCurrentIndex(idx)
        self.durum_combo.setFixedWidth(155)
        self.durum_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QComboBox:focus { border-color: #9b59d0; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9b59d0;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                selection-background-color: #2d1a40;
                selection-color: #9b59d0;
            }
        """)

        layout.addWidget(self.baslik_input, stretch=1)
        layout.addWidget(self.degisiklik_label)
        layout.addWidget(self.durum_combo)
        return layout

    def _ai_durum_cubugu_olustur(self) -> QWidget:
        """AI sağlayıcı durumunu gösteren ince bilgi çubuğu."""
        widget = QWidget()
        widget.setFixedHeight(26)
        widget.setStyleSheet("background-color: #0a0612; border-bottom: 1px solid #130c20;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)

        self.ai_bilgi_label = QLabel("")
        self.ai_bilgi_label.setStyleSheet("color: #6b5a7a; font-size: 11px; background: transparent;")
        layout.addWidget(self.ai_bilgi_label)
        layout.addStretch()

        return widget

    def _orijinal_panel_olustur(self, bolum: dict) -> QGroupBox:
        """Orijinal metin girişi grubu."""
        grup = QGroupBox("  Orijinal Metin")
        grup.setStyleSheet(self._grup_kutusu_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        self.orijinal_metin_edit = QTextEdit()
        self.orijinal_metin_edit.setFont(QFont("Consolas", 11))
        self.orijinal_metin_edit.setPlaceholderText(
            "Çevrilecek orijinal metni buraya yapıştırın..."
        )
        self.orijinal_metin_edit.setStyleSheet(self._metin_edit_stili())
        self.orijinal_metin_edit.setPlainText(bolum.get("orijinal_metin", "") or "")
        layout.addWidget(self.orijinal_metin_edit, stretch=1)

        # Karakter / satır sayacı
        self.orijinal_sayac = QLabel("0 karakter | 0 satır")
        self.orijinal_sayac.setStyleSheet("color: #6b5a7a; font-size: 10px; padding: 2px 4px;")
        layout.addWidget(self.orijinal_sayac)
        self._karakter_sayaci_guncelle()

        return grup

    def _ceviri_panel_olustur(self, bolum: dict) -> QGroupBox:
        """Çevrilmiş metin görüntüleme ve düzenleme grubu."""
        grup = QGroupBox("  Çevrilmiş Metin")
        grup.setStyleSheet(self._grup_kutusu_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        self.ceviri_metin_edit = QTextEdit()
        self.ceviri_metin_edit.setFont(QFont("Segoe UI", 11))
        self.ceviri_metin_edit.setPlaceholderText(
            "Çeviri burada görünecek — 'Çevir' butonuna basın veya doğrudan yazın..."
        )
        self.ceviri_metin_edit.setStyleSheet(self._metin_edit_stili())
        self.ceviri_metin_edit.setPlainText(bolum.get("cevrilmis_metin", "") or "")
        layout.addWidget(self.ceviri_metin_edit, stretch=1)

        # Karakter / satır sayacı
        self.ceviri_sayac = QLabel("0 karakter | 0 satır")
        self.ceviri_sayac.setStyleSheet("color: #6b5a7a; font-size: 10px; padding: 2px 4px;")
        layout.addWidget(self.ceviri_sayac)
        self._karakter_sayaci_guncelle_ceviri()

        # Metrikler paneli
        self.metrikler_widget = MetriklerWidget()
        layout.addWidget(self.metrikler_widget)

        # Başlangıçta mevcut metinlerle metrikleri doldur
        orijinal_baslangic = bolum.get("orijinal_metin", "") or ""
        ceviri_baslangic   = bolum.get("cevrilmis_metin", "") or ""
        if orijinal_baslangic or ceviri_baslangic:
            self.metrikler_widget.guncelle(orijinal_baslangic, ceviri_baslangic)

        return grup

    def _eylem_cubugu_olustur(self) -> QWidget:
        """
        Yeniden tasarlanmış alt eylem çubuğu:
          - İnce üst çizgi ile içerik alanından ayrılmış
          - Çevir butonu solda belirgin şekilde öne çıkar
          - İkincil butonlar ince dikey ayırıcıyla gruplar halinde
          - İlerleme + durum mesajı inline, butonların sağında
          - Token etiketi en sağda
        """
        kapsayici = QWidget()
        kapsayici.setFixedHeight(56)
        kapsayici.setStyleSheet("""
            QWidget#eylemCubugu {
                background-color: #080410;
                border-top: 2px solid #1e1030;
            }
        """)
        kapsayici.setObjectName("eylemCubugu")

        ana_layout = QHBoxLayout(kapsayici)
        ana_layout.setContentsMargins(14, 0, 14, 0)
        ana_layout.setSpacing(0)

        # ── Çevir butonu (birincil, sol) ──────────────────────────────────
        self.cevir_btn = QPushButton("  Çevir")
        self.cevir_btn.setFixedSize(108, 36)
        self.cevir_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59d0;
                color: #0f0a1a;
                border: none;
                border-radius: 7px;
                padding: 0 18px;
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover { background-color: #b06ad9; }
            QPushButton:pressed { background-color: #7b3cb5; }
            QPushButton:disabled { background-color: #231540; color: #4a3a60; }
        """)
        set_icon(self.cevir_btn, "play", size=16)
        self.cevir_btn.clicked.connect(self._cevirmeyi_baslat)
        self.cevir_btn.setEnabled(self.translator is not None)
        ana_layout.addWidget(self.cevir_btn)

        # ── Dikey ince ayırıcı ────────────────────────────────────────────
        def _ayirici() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setFixedWidth(1)
            f.setFixedHeight(28)
            f.setStyleSheet("background-color: #1e1030; border: none;")
            return f

        ana_layout.addSpacing(10)
        ana_layout.addWidget(_ayirici())
        ana_layout.addSpacing(10)

        # ── Grup 1: Kaydet / İncelendi ────────────────────────────────────
        _stili = """
            QPushButton {
                background-color: transparent;
                color: #c8b8e8;
                border: 1px solid #2a1848;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1a1030;
                border-color: #9b59d0;
                color: #e8d8ff;
            }
            QPushButton:pressed { background-color: #231540; }
            QPushButton:disabled { color: #3a2a50; border-color: #1a1030; }
        """

        self.kaydet_btn = QPushButton("  Kaydet")
        self.kaydet_btn.setFixedHeight(34)
        self.kaydet_btn.setMinimumWidth(80)
        self.kaydet_btn.setStyleSheet(_stili)
        self.kaydet_btn.setShortcut("Ctrl+S")
        self.kaydet_btn.setToolTip("Kaydet (Ctrl+S)")
        set_icon(self.kaydet_btn, "save", size=15)
        self.kaydet_btn.clicked.connect(self._kaydet)
        ana_layout.addWidget(self.kaydet_btn)

        ana_layout.addSpacing(4)

        self.incelendi_btn = QPushButton("  İncelendi")
        self.incelendi_btn.setFixedHeight(34)
        self.incelendi_btn.setMinimumWidth(90)
        self.incelendi_btn.setStyleSheet(_stili)
        self.incelendi_btn.setToolTip("İncelendi olarak işaretle ve kaydet")
        set_icon(self.incelendi_btn, "star", size=15)
        self.incelendi_btn.clicked.connect(self._incelendi_olarak_isaretle)
        ana_layout.addWidget(self.incelendi_btn)

        ana_layout.addSpacing(10)
        ana_layout.addWidget(_ayirici())
        ana_layout.addSpacing(10)

        # ── Grup 2: Geri Al / Toplu Çevir / .txt ─────────────────────────
        self.geri_al_btn = QPushButton("  Geri Al")
        self.geri_al_btn.setFixedHeight(34)
        self.geri_al_btn.setMinimumWidth(80)
        self.geri_al_btn.setStyleSheet(_stili)
        self.geri_al_btn.setToolTip("Son çeviriyi geri al")
        set_icon(self.geri_al_btn, "undo", size=15)
        self.geri_al_btn.clicked.connect(self._cevirmeyi_geri_al)
        ana_layout.addWidget(self.geri_al_btn)

        ana_layout.addSpacing(4)

        self.toplu_cevir_btn = QPushButton("  Toplu Çevir")
        self.toplu_cevir_btn.setFixedHeight(34)
        self.toplu_cevir_btn.setMinimumWidth(100)
        self.toplu_cevir_btn.setStyleSheet(_stili)
        self.toplu_cevir_btn.setToolTip("Birden fazla bölümü sırayla çevir")
        set_icon(self.toplu_cevir_btn, "play", size=15)
        self.toplu_cevir_btn.clicked.connect(self._toplu_ceviri_baslat)
        self.toplu_cevir_btn.setEnabled(self.translator is not None)
        ana_layout.addWidget(self.toplu_cevir_btn)

        ana_layout.addSpacing(4)

        self.disaaktar_btn = QPushButton("  .txt")
        self.disaaktar_btn.setFixedHeight(34)
        self.disaaktar_btn.setMinimumWidth(60)
        self.disaaktar_btn.setStyleSheet(_stili)
        self.disaaktar_btn.setToolTip("Çeviriyi .txt dosyası olarak dışa aktar")
        set_icon(self.disaaktar_btn, "export", size=15)
        self.disaaktar_btn.clicked.connect(self._txt_olarak_disa_aktar)
        ana_layout.addWidget(self.disaaktar_btn)

        ana_layout.addSpacing(4)

        self.karsilastir_btn = QPushButton("  Karşılaştır")
        self.karsilastir_btn.setFixedHeight(34)
        self.karsilastir_btn.setMinimumWidth(100)
        self.karsilastir_btn.setStyleSheet(_stili)
        self.karsilastir_btn.setToolTip("Orijinal ve çeviriyi yan yana karşılaştır")
        self.karsilastir_btn.clicked.connect(self._karsilastirma_ac)
        ana_layout.addWidget(self.karsilastir_btn)

        ana_layout.addSpacing(4)

        self.uyum_btn = QPushButton("  Sözlük Uyum")
        self.uyum_btn.setFixedHeight(34)
        self.uyum_btn.setMinimumWidth(100)
        self.uyum_btn.setStyleSheet(_stili)
        self.uyum_btn.setToolTip("Çeviride sözlük karşılıklarını kontrol et (Ctrl+Shift+G)")
        self.uyum_btn.clicked.connect(self._sozluk_uyum_kontrol)
        ana_layout.addWidget(self.uyum_btn)

        ana_layout.addSpacing(4)

        self.diff_btn = QPushButton("  Diff")
        self.diff_btn.setFixedHeight(34)
        self.diff_btn.setMinimumWidth(60)
        self.diff_btn.setStyleSheet(_stili)
        self.diff_btn.setToolTip("Önceki ve güncel çeviriyi karşılaştır (Ctrl+D)")
        self.diff_btn.clicked.connect(self._diff_goster)
        ana_layout.addWidget(self.diff_btn)

        ana_layout.addSpacing(4)

        self.okuma_modu_btn = QPushButton("  Okuma")
        self.okuma_modu_btn.setFixedHeight(34)
        self.okuma_modu_btn.setMinimumWidth(70)
        self.okuma_modu_btn.setCheckable(True)
        self.okuma_modu_btn.setStyleSheet(_stili)
        self.okuma_modu_btn.setToolTip("Okuma modu — yalnızca çeviri (Ctrl+R)")
        self.okuma_modu_btn.toggled.connect(self._okuma_modu_degisti)
        ana_layout.addWidget(self.okuma_modu_btn)

        ana_layout.addSpacing(4)

        self.ceviri_iptal_btn = QPushButton("  İptal")
        self.ceviri_iptal_btn.setFixedHeight(34)
        self.ceviri_iptal_btn.setMinimumWidth(60)
        self.ceviri_iptal_btn.setVisible(False)
        self.ceviri_iptal_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225; color: #f08080;
                border: 1px solid #3d2d55; border-radius: 6px;
                padding: 0 10px; font-size: 12px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #f08080; }
        """)
        self.ceviri_iptal_btn.setToolTip("Devam eden çeviriyi iptal et (Esc)")
        self.ceviri_iptal_btn.clicked.connect(self._tek_ceviri_iptal)
        ana_layout.addWidget(self.ceviri_iptal_btn)

        # ── Orta: ilerleme + durum mesajı ────────────────────────────────
        ana_layout.addStretch()

        self.ilerleme_cubugu = QProgressBar()
        self.ilerleme_cubugu.setRange(0, 0)
        self.ilerleme_cubugu.setFixedSize(100, 4)
        self.ilerleme_cubugu.setVisible(False)
        self.ilerleme_cubugu.setStyleSheet("""
            QProgressBar {
                background-color: #1a1225;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #9b59d0;
                border-radius: 2px;
            }
        """)
        ana_layout.addWidget(self.ilerleme_cubugu)
        ana_layout.addSpacing(6)

        self.ceviriliyor_label = QLabel("Çevriliyor...")
        self.ceviriliyor_label.setStyleSheet(
            "color: #9b59d0; font-size: 11px; background: transparent;"
        )
        self.ceviriliyor_label.setVisible(False)
        ana_layout.addWidget(self.ceviriliyor_label)

        self.durum_label = QLabel("")
        self.durum_label.setStyleSheet(
            "color: #a0f0b0; font-size: 11px; background: transparent;"
        )
        ana_layout.addWidget(self.durum_label)

        ana_layout.addSpacing(12)

        # ── Toplu çeviri: Duraklat/Devam Et + İptal butonları (başlangıçta gizli) ──
        self._toplu_duraklat_btn = QPushButton("  ⏸ Duraklat")
        self._toplu_duraklat_btn.setFixedHeight(28)
        self._toplu_duraklat_btn.setMinimumWidth(100)
        self._toplu_duraklat_btn.setVisible(False)
        self._toplu_duraklat_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225; color: #f0d090;
                border: 1px solid #3d2d55; border-radius: 5px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #f0d090; }
        """)
        self._toplu_duraklat_btn.clicked.connect(self._toplu_ceviri_duraklat_toggle)
        ana_layout.addWidget(self._toplu_duraklat_btn)

        ana_layout.addSpacing(4)

        self._toplu_iptal_btn = QPushButton("  ✕ İptal")
        self._toplu_iptal_btn.setFixedHeight(28)
        self._toplu_iptal_btn.setMinimumWidth(70)
        self._toplu_iptal_btn.setVisible(False)
        self._toplu_iptal_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225; color: #f08080;
                border: 1px solid #3d2d55; border-radius: 5px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #f08080; }
        """)
        self._toplu_iptal_btn.clicked.connect(self._toplu_ceviri_iptal)
        ana_layout.addWidget(self._toplu_iptal_btn)

        ana_layout.addSpacing(8)

        # ── Token etiketi (en sağ) ────────────────────────────────────────
        self.token_label = QLabel("")
        self.token_label.setStyleSheet(
            "color: #3a2a50; font-size: 10px; background: transparent;"
        )
        ana_layout.addWidget(self.token_label)

        return kapsayici

    def _sozluk_onizleme_olustur(self) -> QWidget:
        """
        Metindeki sözlük terimlerini gösteren katlanabilir panel.
        Başlık çubuğuna tıklanınca açılır/kapanır.
        """
        # ── Dış kapsayıcı ────────────────────────────────────────────────────
        self.sozluk_grup = QWidget()
        self.sozluk_grup.setStyleSheet(
            "background-color: #0a0612; border-top: 1px solid #1a1225;"
        )
        dis_layout = QVBoxLayout(self.sozluk_grup)
        dis_layout.setContentsMargins(0, 0, 0, 0)
        dis_layout.setSpacing(0)

        # ── Başlık çubuğu (tıklanabilir) ─────────────────────────────────────
        self._sozluk_baslik_bar = QPushButton()
        self._sozluk_baslik_bar.setFlat(True)
        self._sozluk_baslik_bar.setFixedHeight(32)
        self._sozluk_baslik_bar.setStyleSheet("""
            QPushButton {
                background-color: #0a0612;
                color: #6b5a7a;
                border: none;
                text-align: left;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #110820;
                color: #9b59d0;
            }
        """)
        self._sozluk_acik = False
        self._sozluk_baslik_bar.setText("▶  Metinde Bulunan Sözlük Terimleri (0 adet)")
        self._sozluk_baslik_bar.clicked.connect(self._sozluk_toggle)
        dis_layout.addWidget(self._sozluk_baslik_bar)

        # ── İçerik alanı (başlangıçta gizli) ─────────────────────────────────
        self._sozluk_icerik = QWidget()
        self._sozluk_icerik.setStyleSheet("background-color: #0a0612;")
        self._sozluk_icerik.setVisible(False)
        icerik_layout = QVBoxLayout(self._sozluk_icerik)
        icerik_layout.setContentsMargins(10, 6, 10, 8)
        icerik_layout.setSpacing(6)

        # Tara butonu
        kontrol_layout = QHBoxLayout()
        kontrol_layout.setSpacing(6)
        self.sozluk_tara_btn = QPushButton("  Sözlüğü Tara")
        self.sozluk_tara_btn.setFixedHeight(28)
        self.sozluk_tara_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225;
                color: #9b59d0;
                border: 1px solid #2d1a40;
                border-radius: 5px;
                padding: 0 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2d1a40;
                color: #c080f0;
            }
        """)
        set_icon(self.sozluk_tara_btn, "search", size=14)
        self.sozluk_tara_btn.clicked.connect(self._sozlugu_tara)
        kontrol_layout.addWidget(self.sozluk_tara_btn)
        kontrol_layout.addStretch()
        icerik_layout.addLayout(kontrol_layout)

        # Tablo
        self.sozluk_tablo = QTableWidget()
        self.sozluk_tablo.setColumnCount(3)
        self.sozluk_tablo.setHorizontalHeaderLabels([
            "Orijinal Terim", "Çevrilmiş Terim", "Kategori"
        ])
        self.sozluk_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.sozluk_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.sozluk_tablo.verticalHeader().setVisible(False)
        self.sozluk_tablo.horizontalHeader().setStretchLastSection(True)
        self.sozluk_tablo.setColumnWidth(0, 180)
        self.sozluk_tablo.setColumnWidth(1, 180)
        self.sozluk_tablo.setFixedHeight(130)
        self.sozluk_tablo.setShowGrid(False)
        self.sozluk_tablo.setAlternatingRowColors(True)
        self.sozluk_tablo.setStyleSheet("""
            QTableWidget {
                background-color: #0f0a1a;
                alternate-background-color: #130c20;
                color: #c8b8e8;
                border: none;
                font-size: 11px;
            }
            QTableWidget::item { padding: 4px 8px; border: none; }
            QTableWidget::item:selected {
                background-color: #1a1225;
                color: #9b59d0;
            }
            QHeaderView::section {
                background-color: #0a0612;
                color: #6b5a7a;
                border: none;
                border-bottom: 1px solid #1a1225;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 600;
            }
        """)
        icerik_layout.addWidget(self.sozluk_tablo)
        dis_layout.addWidget(self._sozluk_icerik)

        return self.sozluk_grup

    # =========================================================================
    # VERİ YÜKLEME
    # =========================================================================

    def set_seri(self, seri_id: int):
        """Aktif seriyi günceller ve bölüm listesini yeniden yükler."""
        farkli_seri = (self.seri_id != seri_id)

        # Seri değişiyorsa çeviri worker'ını güvenli şekilde iptal et
        if farkli_seri:
            self._ceviri_worker_iptal()

        self.seri_id = seri_id

        if farkli_seri:
            # Yeni seri: aktif bölümü ve değişiklik bayrağını sıfırla
            self.aktif_bolum_id = None
            self.aktif_bolum    = None
            self._kaydedilmemis = False
            self.bolum_listesini_yukle()
            self._bos_durum_goster()
        else:
            # Aynı seri: yalnızca bölüm listesini yenile (içe aktarım sonrası vb.)
            self.bolum_listesini_yukle()

    # Geriye dönük uyumluluk için alias
    def seri_yukle(self, seri_id: int):
        self.set_seri(seri_id)

    def _ceviri_worker_iptal(self):
        """
        Çalışan çeviri worker'ını güvenli şekilde iptal eder.
        Sinyalleri keser, interruption ister ve kısa süre bekler.
        """
        worker = getattr(self, "_worker", None)
        if worker is None:
            return

        try:
            worker.tamamlandi.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.hata.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.token_geldi.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.sure_hesaplandi.disconnect()
        except (RuntimeError, TypeError):
            pass

        if worker.isRunning():
            worker.requestInterruption()
            # Ağ çağrısı sürüyorsa kısa bekle; UI'yı kilitlememek için sınırlı timeout
            if not worker.wait(1500):
                # Thread hâlâ API yanıtı bekliyor olabilir; referansı bırakıp
                # Qt'nin yaşam döngüsüne bırak (parent varsa otomatik temizlenir)
                worker.setParent(None)

        self._worker = None

    def set_translator(self, translator):
        """Aktif AI translator'ı günceller ve arayüzü yeniler."""
        self.translator = translator
        self._ai_durumunu_guncelle()
        # Çevir butonu etkinliğini güncelle
        if hasattr(self, "cevir_btn"):
            self.cevir_btn.setEnabled(translator is not None)

    def bolum_listesini_yukle(self):
        """Veritabanından bölümleri alır ve sol listeyi doldurur."""
        self.bolum_listesi.clear()

        if not self.seri_id or not self.db_manager:
            self._istatistikleri_guncelle([], [])
            return

        bolumler = self.db_manager.serinin_bolumlerini_getir(self.seri_id)

        # Durum filtresini uygula
        if self._filtre_durum:
            gosterilen = [b for b in bolumler if b.get("durum") == self._filtre_durum]
        else:
            gosterilen = bolumler

        # Arama metnini uygula (başlık ve bölüm no üzerinden)
        if self._arama_metni:
            ara = self._arama_metni.lower()
            gosterilen = [
                b for b in gosterilen
                if ara in (b.get("bolum_baslik") or "").lower()
                or ara in str(b.get("bolum_no", ""))
            ]

        # Büyük listelerde UI donmasını azalt
        self.bolum_listesi.setUpdatesEnabled(False)
        try:
            for bolum in gosterilen:
                oge_widget = BolumListeOgesi(bolum)
                oge = QListWidgetItem(self.bolum_listesi)
                oge.setSizeHint(oge_widget.sizeHint())
                oge.setData(Qt.ItemDataRole.UserRole, bolum["id"])
                self.bolum_listesi.addItem(oge)
                self.bolum_listesi.setItemWidget(oge, oge_widget)
        finally:
            self.bolum_listesi.setUpdatesEnabled(True)

        self._istatistikleri_guncelle(
            bolumler,
            [b for b in bolumler if b.get("durum") in ("cevirildi", "incelendi")]
        )

    def _istatistikleri_guncelle(self, bolumler: list, cevrilen: list):
        toplam   = len(bolumler)
        cevirlen = len(cevrilen)
        self.istatistik_label.setText(
            f"Toplam: {toplam} bölüm | Çevrilen: {cevirlen}"
        )

    def _ai_durumunu_guncelle(self):
        """AI durum çubuğunu mevcut translator durumuna göre günceller."""
        if not hasattr(self, "ai_bilgi_label"):
            return

        if self.translator is None:
            self.ai_bilgi_label.setText(
                "AI sağlayıcısı yapılandırılmamış. Araçlar menüsünden API anahtarı ekleyin."
            )
            self.ai_bilgi_label.setStyleSheet(
                "color: #f0d090; font-size: 11px; background: transparent;"
            )
        else:
            # Sınıf adı → sağlayıcı kodu eşlemesi (TranslatorFactory import etmeden)
            _SINIF_SAGLAYICI = {
                "OpenAITranslator":     "openai",
                "AnthropicTranslator":  "anthropic",
                "GeminiTranslator":     "google",
                "GrokTranslator":       "xai",
                "OpenRouterTranslator": "openrouter",
            }
            sinif_adi    = type(self.translator).__name__
            saglayici_kodu = _SINIF_SAGLAYICI.get(sinif_adi, "openai")
            model = getattr(self.translator, "model_adi", "")

            try:
                from translator import TranslatorFactory
                goruntu_adi = TranslatorFactory.get_saglayici_display_name(saglayici_kodu)
            except Exception:
                goruntu_adi = sinif_adi.replace("Translator", "")

            self.ai_bilgi_label.setText(f"AI: {goruntu_adi}  ·  {model}")
            self.ai_bilgi_label.setStyleSheet(
                "color: #6b5a7a; font-size: 11px; background: transparent;"
            )

    # =========================================================================
    # BÖLÜM SEÇİMİ
    # =========================================================================

    def _bolum_secildi(self, oge: QListWidgetItem):
        """Listeden bir bölüme tıklandığında içeriği sağ panele yükler."""
        bolum_id = oge.data(Qt.ItemDataRole.UserRole)
        if not bolum_id:
            return

        # Kaydedilmemiş değişiklik varsa kullanıcıya sor
        if self._kaydedilmemis and self.aktif_bolum_id:
            cevap = QMessageBox.question(
                self,
                "Kaydedilmemiş Değişiklikler",
                "Mevcut bölümde kaydedilmemiş değişiklikler var.\n"
                "Kaydetmeden devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.No:
                # Eski seçimi geri yükle
                self._aktif_ogeyi_sec()
                return

        bolum = self.db_manager.bolum_getir(bolum_id)
        if not bolum:
            return

        self.aktif_bolum_id = bolum_id
        self.aktif_bolum    = bolum
        self._kaydedilmemis = False

        self._bolum_icerigi_goster(bolum)

    def _aktif_ogeyi_sec(self):
        """Listedeki mevcut aktif bölümü programatik olarak seçer."""
        for i in range(self.bolum_listesi.count()):
            oge = self.bolum_listesi.item(i)
            if oge and oge.data(Qt.ItemDataRole.UserRole) == self.aktif_bolum_id:
                self.bolum_listesi.setCurrentItem(oge)
                break

    # =========================================================================
    # BAĞLAM MENÜSÜ
    # =========================================================================

    def _baglan_menu_goster(self, konum):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        oge = self.bolum_listesi.itemAt(konum)
        if not oge:
            return

        bolum_id = oge.data(Qt.ItemDataRole.UserRole)
        if not bolum_id:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #2d1a40; color: #9b59d0; }
            QMenu::separator { height: 1px; background: #3d2d55; margin: 4px 8px; }
        """)

        duzenle_action = QAction("  Başlığı Düzenle", self)
        set_icon(duzenle_action, "edit", size=14)
        duzenle_action.triggered.connect(lambda: self._bolum_basligini_duzenle(bolum_id))

        sil_action = QAction("  Bölümü Sil", self)
        set_icon(sil_action, "delete", size=14)
        sil_action.triggered.connect(lambda: self._bolum_sil(bolum_id))

        menu.addAction(duzenle_action)
        menu.addSeparator()
        menu.addAction(sil_action)
        menu.exec(self.bolum_listesi.mapToGlobal(konum))

    # =========================================================================
    # BÖLÜM İŞLEMLERİ
    # =========================================================================

    def _yeni_bolum_ekle(self):
        """Yeni bölüm ekleme diyaloğunu açar."""
        if not self.seri_id:
            QMessageBox.warning(self, "Seri Seçilmedi",
                                "Lütfen önce sol panelden bir seri seçin.")
            return

        # Varsayılan bölüm numarası: son bölüm + 1
        mevcut = self.db_manager.serinin_bolumlerini_getir(self.seri_id)
        sonraki_no = (max((b["bolum_no"] for b in mevcut), default=0)) + 1

        diyalog = YeniBolumDialog(parent=self, varsayilan_bolum_no=sonraki_no)
        self._diyalog_stili_uygula(diyalog)

        if diyalog.exec() == QDialog.DialogCode.Accepted:
            yeni_id = self.db_manager.bolum_olustur(
                seri_id=self.seri_id,
                bolum_no=diyalog.bolum_no_spin.value(),
                bolum_baslik=diyalog.baslik_input.text().strip() or None,
                orijinal_metin=diyalog.metin_edit.toPlainText().strip() or None,
            )
            if yeni_id:
                self.bolum_listesini_yukle()
                self._bolum_id_ile_sec(yeni_id)

    def _bolum_id_ile_sec(self, bolum_id: int):
        """Verilen id'ye sahip bölümü listede seçer ve içeriği yükler."""
        for i in range(self.bolum_listesi.count()):
            oge = self.bolum_listesi.item(i)
            if oge and oge.data(Qt.ItemDataRole.UserRole) == bolum_id:
                self.bolum_listesi.setCurrentItem(oge)
                self._bolum_secildi(oge)
                return

    def _bolum_basligini_duzenle(self, bolum_id: int):
        """Bölüm başlığını düzenlemek için basit bir giriş diyaloğu açar."""
        from PyQt6.QtWidgets import QInputDialog
        bolum = self.db_manager.bolum_getir(bolum_id)
        if not bolum:
            return

        mevcut_baslik = bolum.get("bolum_baslik") or ""
        yeni_baslik, tamam = QInputDialog.getText(
            self, "Başlığı Düzenle",
            "Yeni bölüm başlığı:",
            text=mevcut_baslik
        )
        if tamam:
            self.db_manager.bolum_guncelle(
                bolum_id=bolum_id,
                bolum_baslik=yeni_baslik.strip() or None,
                orijinal_metin=bolum.get("orijinal_metin"),
                cevrilmis_metin=bolum.get("cevrilmis_metin"),
                durum=bolum.get("durum", "beklemede"),
            )
            self.bolum_listesini_yukle()
            # Aktif bölüm başlığını güncelle
            if bolum_id == self.aktif_bolum_id and hasattr(self, "baslik_input"):
                self.baslik_input.setText(yeni_baslik.strip() or f"Bölüm {bolum.get('bolum_no','')}")

    def _bolum_sil(self, bolum_id: int):
        """Silme onayı alır ve bölümü siler."""
        onay = QMessageBox(self)
        onay.setWindowTitle("Bölümü Sil")
        onay.setIcon(QMessageBox.Icon.Warning)
        onay.setText("Bu bölüm silinecek. Devam etmek istiyor musunuz?")
        evet_btn  = onay.addButton("Evet, Sil",  QMessageBox.ButtonRole.DestructiveRole)
        hayir_btn = onay.addButton("Hayır, İptal", QMessageBox.ButtonRole.RejectRole)
        onay.setDefaultButton(hayir_btn)
        self._diyalog_stili_uygula(onay)
        onay.exec()

        if onay.clickedButton() == evet_btn:
            self.db_manager.bolum_sil(bolum_id)
            if bolum_id == self.aktif_bolum_id:
                self.aktif_bolum_id = None
                self.aktif_bolum    = None
                self._kaydedilmemis = False
                self._bos_durum_goster()
            self.bolum_listesini_yukle()

    # =========================================================================
    # ÇEVİRİ AKIŞI
    # =========================================================================

    def _cevirmeyi_baslat(self):
        """
        'Çevir' butonuna basıldığında çalışır.
        Metni doğrular, sözlüğü tarar ve TranslationWorker'ı başlatır.
        """
        if not self.aktif_bolum_id:
            return

        # Önceki worker hâlâ çalışıyorsa yeni çeviri başlatma
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Çeviri Sürüyor",
                "Önceki çeviri işlemi henüz tamamlanmadı. Lütfen bekleyin."
            )
            return

        # Zaten çevrilmiş bölümü yeniden çevirme kontrolü
        mevcut_durum = None
        if hasattr(self, "durum_combo"):
            mevcut_durum = self.durum_combo.currentData()
        elif self.aktif_bolum:
            mevcut_durum = self.aktif_bolum.get("durum")

        if mevcut_durum in ("cevirildi", "incelendi"):
            cevap = QMessageBox.question(
                self,
                "Zaten Çevrilmiş",
                "Bu bölüm zaten çevrilmiş. Yeniden çevirmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.No:
                return

        orijinal = self.orijinal_metin_edit.toPlainText().strip()
        if not orijinal:
            QMessageBox.warning(self, "Boş Metin", "Önce orijinal metni girin.")
            return

        if self.translator is None:
            QMessageBox.warning(
                self, "AI Yapılandırılmamış",
                "Lütfen Araçlar → Ayarlar menüsünden bir AI sağlayıcısı ekleyin."
            )
            return

        # Seri dil bilgilerini al
        seri = self.db_manager.seri_getir(self.seri_id)
        kaynak_dil = seri.get("kaynak_dil", "").strip() if seri else ""
        hedef_dil  = seri.get("hedef_dil",  "").strip() if seri else ""

        if not kaynak_dil or not hedef_dil:
            QMessageBox.warning(
                self, "Dil Bilgisi Eksik",
                "Seri için kaynak ve hedef dil tanımlanmamış.\n"
                "Lütfen 'Seri Bilgisi' sekmesinden dil seçimini yapın."
            )
            return

        # Sözlükteki eşleşmeleri bul ve önizleme tablosunu güncelle
        sozluk_terimleri = self.db_manager.metinde_sozluk_terimlerini_bul(
            self.seri_id, orijinal
        )
        self._sozluk_onizlemesini_guncelle(sozluk_terimleri)
        self._son_sozluk_terimleri = sozluk_terimleri

        # Çeviri başlamadan önce mevcut çeviriyi undo için sakla
        mevcut_ceviri = self.ceviri_metin_edit.toPlainText()
        if mevcut_ceviri.strip():
            self.db_manager.onceki_ceviri_kaydet(self.aktif_bolum_id, mevcut_ceviri)

        # UI'ı meşgul duruma al
        self._aktif_bolum_id_ceviride = self.aktif_bolum_id
        self.cevir_btn.setEnabled(False)
        if hasattr(self, "toplu_cevir_btn"):
            self.toplu_cevir_btn.setEnabled(False)
        if hasattr(self, "ceviri_iptal_btn"):
            self.ceviri_iptal_btn.setVisible(True)
        self.ilerleme_cubugu.setVisible(True)
        parca_sayisi = len(metni_parcala(orijinal, VARSAYILAN_PARCA_BOYUTU))
        if parca_sayisi > 1:
            self.ceviriliyor_label.setText(f"Çevriliyor... ({parca_sayisi} parça)")
        else:
            self.ceviriliyor_label.setText("Çevriliyor...")
        self.ceviriliyor_label.setVisible(True)
        self.durum_label.setText("")

        # Streaming modunda metin kutusunu temizle (tek parça ise)
        self._streaming_birikim = []
        if getattr(self.translator, "streaming_destekli", False) and parca_sayisi == 1:
            self.ceviri_metin_edit.setPlainText("")

        # Sağlayıcı ve model bilgisini al
        ayar = self.db_manager.aktif_ai_ayar_getir() if self.db_manager else None
        saglayici_kodu = ayar.get("saglayici", "") if ayar else ""
        model_kodu     = ayar.get("model_adi", "") if ayar else getattr(self.translator, "model_adi", "")

        # Çeviri worker'ını oluştur ve başlat
        self._worker = TranslationWorker(
            translator=self.translator,
            orijinal_metin=orijinal,
            kaynak_dil=kaynak_dil,
            hedef_dil=hedef_dil,
            sozluk_terimleri=sozluk_terimleri,
            db_manager=self.db_manager,
            saglayici=saglayici_kodu,
            model_adi=model_kodu,
            parent=self,
        )
        self._worker.tamamlandi.connect(self._ceviri_tamamlandi)
        self._worker.hata.connect(self._ceviri_hatasi)
        if getattr(self.translator, "streaming_destekli", False) and parca_sayisi == 1:
            self._worker.token_geldi.connect(self._streaming_token_al)
        if hasattr(self, "metrikler_widget"):
            self._worker.sure_hesaplandi.connect(self.metrikler_widget.sure_guncelle)
        self._worker.start()

    def _ceviri_tamamlandi(self, cevrilmis_metin: str):
        """Worker'dan başarı sinyali geldiğinde çağrılır."""
        self._worker = None

        # Çeviri başladıktan sonra kullanıcı farklı bölüme geçtiyse sonucu yoksay
        baslangic_id = getattr(self, "_aktif_bolum_id_ceviride", None)
        if baslangic_id != self.aktif_bolum_id:
            return

        # Çeviriyi metin kutusuna yaz (widget silinmişse hata almamak için kontrol)
        if not hasattr(self, "ceviri_metin_edit"):
            return
        self.ceviri_metin_edit.setPlainText(cevrilmis_metin)

        # UI'ı normal duruma getir
        self.ilerleme_cubugu.setVisible(False)
        self.ceviriliyor_label.setVisible(False)
        self.cevir_btn.setEnabled(True)
        if hasattr(self, "ceviri_iptal_btn"):
            self.ceviri_iptal_btn.setVisible(False)
        if hasattr(self, "toplu_cevir_btn"):
            self.toplu_cevir_btn.setEnabled(self.translator is not None)

        # Durum rozeti güncelle
        if hasattr(self, "durum_combo"):
            idx = self.durum_combo.findData("cevirildi")
            if idx >= 0:
                self.durum_combo.setCurrentIndex(idx)

        # Metrikleri güncelle
        if hasattr(self, "metrikler_widget") and hasattr(self, "orijinal_metin_edit"):
            self.metrikler_widget.guncelle(
                self.orijinal_metin_edit.toPlainText(),
                cevrilmis_metin,
            )

        # Geçici başarı mesajı
        self._gecici_durum_goster("Çeviri tamamlandı", "#a0f0b0", 3000)

        # Değişiklik bayrağı
        self._kaydedilmemis = True
        self._degisiklik_isaretlendir()

        # Otomatik sözlük önerisi (arka planda, QTimer ile UI settle sonrası)
        QTimer.singleShot(500, lambda: self._otomatik_sozluk_onerisi(
            self.orijinal_metin_edit.toPlainText() if hasattr(self, "orijinal_metin_edit") else "",
            cevrilmis_metin
        ))

    def _ceviri_hatasi(self, hata_mesaji: str):
        """Worker'dan hata sinyali geldiğinde çağrılır."""
        self._worker = None

        # Çeviri başladıktan sonra bölüm değiştirildiyse sessizce çık
        baslangic_id = getattr(self, "_aktif_bolum_id_ceviride", None)
        if baslangic_id != self.aktif_bolum_id:
            return

        if hasattr(self, "ilerleme_cubugu"):
            self.ilerleme_cubugu.setVisible(False)
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setVisible(False)
        if hasattr(self, "cevir_btn"):
            self.cevir_btn.setEnabled(True)
        if hasattr(self, "ceviri_iptal_btn"):
            self.ceviri_iptal_btn.setVisible(False)
        if hasattr(self, "toplu_cevir_btn"):
            self.toplu_cevir_btn.setEnabled(self.translator is not None)

        QMessageBox.critical(
            self, "Çeviri Hatası",
            f"Çeviri tamamlanamadı:\n\n{hata_mesaji}"
        )

    def _tek_ceviri_iptal(self):
        """Devam eden tek bölüm çevirisini iptal eder."""
        self._ceviri_worker_iptal()
        if hasattr(self, "ilerleme_cubugu"):
            self.ilerleme_cubugu.setVisible(False)
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setVisible(False)
        if hasattr(self, "cevir_btn"):
            self.cevir_btn.setEnabled(self.translator is not None)
        if hasattr(self, "ceviri_iptal_btn"):
            self.ceviri_iptal_btn.setVisible(False)
        if hasattr(self, "toplu_cevir_btn"):
            self.toplu_cevir_btn.setEnabled(self.translator is not None)
        self._gecici_durum_goster("Çeviri iptal edildi.", "#f0d090", 2500)

    # =========================================================================
    # KAYDET / İŞARETLE / DIŞA AKTAR
    # =========================================================================

    def _kaydet(self):
        """Mevcut bölümü veritabanına kaydeder."""
        if not self.aktif_bolum_id:
            return

        baslik     = self.baslik_input.text().strip() or None
        orijinal   = self.orijinal_metin_edit.toPlainText()
        cevrilmis  = self.ceviri_metin_edit.toPlainText()
        durum_kodu = self.durum_combo.currentData()

        basari = self.db_manager.bolum_guncelle(
            bolum_id=self.aktif_bolum_id,
            bolum_baslik=baslik,
            orijinal_metin=orijinal,
            cevrilmis_metin=cevrilmis,
            durum=durum_kodu,
        )

        if not basari:
            QMessageBox.critical(
                self, "Kayıt Hatası",
                "Bölüm veritabanına kaydedilemedi. Lütfen tekrar deneyin."
            )
            return

        # Kaydedilmemiş değişiklik bayrağını temizle
        self._kaydedilmemis = False
        self.degisiklik_label.setText("")

        # Bölüm listesini güncelle ve seçili ögeyi görünür yap
        self.bolum_listesini_yukle()
        self._aktif_ogeyi_sec()
        aktif_oge = self.bolum_listesi.currentItem()
        if aktif_oge:
            self.bolum_listesi.scrollToItem(aktif_oge)

        self._gecici_durum_goster("Kaydedildi.", "#a0f0b0", 2000)

    def _incelendi_olarak_isaretle(self):
        """Bölüm durumunu 'incelendi' yapar ve kaydeder."""
        if not hasattr(self, "durum_combo"):
            return
        idx = self.durum_combo.findData("incelendi")
        if idx >= 0:
            self.durum_combo.setCurrentIndex(idx)
        self._kaydet()

    def _txt_olarak_disa_aktar(self):
        """Çevrilmiş metni .txt dosyasına aktarır."""
        if not self.aktif_bolum:
            return

        cevrilmis = self.ceviri_metin_edit.toPlainText().strip()
        if not cevrilmis:
            QMessageBox.warning(self, "Boş Çeviri",
                                "Dışa aktarılacak çeviri metni yok.")
            return

        # Varsayılan dosya adı
        bolum_no  = self.aktif_bolum.get("bolum_no", 0)
        seri      = self.db_manager.seri_getir(self.seri_id)
        seri_adi  = seri.get("baslik", "seri").replace(" ", "_") if seri else "seri"
        varsayilan = f"Bolum_{bolum_no}_{seri_adi}.txt"

        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self,
            "Çeviriyi Kaydet",
            varsayilan,
            "Metin Dosyası (*.txt);;Tüm Dosyalar (*)"
        )
        if not dosya_yolu:
            return

        try:
            with open(dosya_yolu, "w", encoding="utf-8") as f:
                f.write(cevrilmis)
            self._gecici_durum_goster("Dışa aktarıldı.", "#a0f0b0", 2500)
        except Exception as hata:
            QMessageBox.critical(self, "Yazma Hatası",
                                 f"Dosya yazılamadı:\n{hata}")

    def _karsilastirma_ac(self):
        """Orijinal metin ile çeviriyi yan yana gösteren karşılaştırma diyaloğunu açar."""
        if not self.aktif_bolum_id:
            return
        if not hasattr(self, "orijinal_metin_edit") or not hasattr(self, "ceviri_metin_edit"):
            return

        orijinal = self.orijinal_metin_edit.toPlainText()
        ceviri   = self.ceviri_metin_edit.toPlainText()

        diyalog = KarsilastirmaDiyalogu(orijinal, ceviri, parent=self)
        diyalog.exec()

    # =========================================================================
    # SÖZLÜK TARAMA
    # =========================================================================

    def _sozlugu_tara(self):
        """Orijinal metinde sözlük terimlerini tarar ve önizlemeyi günceller."""
        if not self.aktif_bolum_id or not self.seri_id:
            return

        orijinal = self.orijinal_metin_edit.toPlainText()
        bulunanlar = self.db_manager.metinde_sozluk_terimlerini_bul(self.seri_id, orijinal)
        self._sozluk_onizlemesini_guncelle(bulunanlar)

        # Grup kapalıysa aç
        if not self._sozluk_acik:
            self._sozluk_toggle()

    def _sozluk_onizlemesini_guncelle(self, terimler: list):
        """Sözlük önizleme tablosunu bulunan terimlerle doldurur."""
        # Başlık çubuğunu güncelle
        ok = "▼" if self._sozluk_acik else "▶"
        self._sozluk_baslik_bar.setText(
            f"{ok}  Metinde Bulunan Sözlük Terimleri ({len(terimler)} adet)"
        )

        self.sozluk_tablo.setRowCount(0)
        for i, terim in enumerate(terimler):
            self.sozluk_tablo.insertRow(i)

            orijinal_item = QTableWidgetItem(terim.get("orijinal_terim", ""))
            orijinal_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.sozluk_tablo.setItem(i, 0, orijinal_item)

            ceviri_item = QTableWidgetItem(terim.get("cevrilmis_terim", ""))
            ceviri_item.setForeground(QColor("#a0f0b0"))
            self.sozluk_tablo.setItem(i, 1, ceviri_item)

            kat_kodu   = terim.get("kategori", "diger")
            kat_gorunum = KATEGORI_GORUNUM.get(kat_kodu, kat_kodu)
            kat_item   = QTableWidgetItem(kat_gorunum)
            kat_item.setForeground(QColor("#6b5a7a"))
            self.sozluk_tablo.setItem(i, 2, kat_item)

    def _sozluk_toggle(self):
        """Sözlük önizleme panelini açar veya kapatır."""
        self._sozluk_acik = not self._sozluk_acik
        self._sozluk_icerik.setVisible(self._sozluk_acik)
        ok = "▼" if self._sozluk_acik else "▶"
        baslik = self._sozluk_baslik_bar.text()
        # Ok ikonunu güncelle
        if baslik.startswith("▶") or baslik.startswith("▼"):
            baslik = ok + baslik[1:]
        self._sozluk_baslik_bar.setText(baslik)

    def _sozluk_panelini_goster_gizle(self, acik: bool):
        """Geriye dönük uyumluluk için korunmuş — _sozluk_toggle kullanılır."""
        if acik != self._sozluk_acik:
            self._sozluk_toggle()

    # =========================================================================
    # DEĞİŞİKLİK TAKİBİ VE YARDIMCILAR
    # =========================================================================

    def _degisiklik_isaretlendir(self):
        """Metin veya başlık değiştiğinde kaydedilmemiş değişiklik bayrağını koyar."""
        self._kaydedilmemis = True
        if hasattr(self, "degisiklik_label"):
            self.degisiklik_label.setText("● Kaydedilmemiş değişiklikler")

    def _karakter_sayaci_guncelle(self):
        """Orijinal metin kutusunun karakter ve satır sayacını günceller."""
        if not hasattr(self, "orijinal_metin_edit"):
            return
        metin  = self.orijinal_metin_edit.toPlainText()
        karakt = len(metin)
        satir  = metin.count("\n") + 1 if metin else 0
        self.orijinal_sayac.setText(f"{karakt} karakter | {satir} satır")

    def _karakter_sayaci_guncelle_ceviri(self):
        """Çeviri metin kutusunun karakter ve satır sayacını günceller."""
        if not hasattr(self, "ceviri_metin_edit"):
            return
        metin  = self.ceviri_metin_edit.toPlainText()
        karakt = len(metin)
        satir  = metin.count("\n") + 1 if metin else 0
        self.ceviri_sayac.setText(f"{karakt} karakter | {satir} satır")

    def _gecici_durum_goster(self, mesaj: str, renk: str, sure_ms: int):
        """
        Belirtilen renkte bir durum mesajı gösterir;
        sure_ms milisaniye sonra otomatik temizler.
        """
        if hasattr(self, "durum_label"):
            self.durum_label.setText(mesaj)
            self.durum_label.setStyleSheet(f"color: {renk}; font-size: 12px;")
            self._durum_timer.start(sure_ms)

    def _durum_mesajini_temizle(self):
        if hasattr(self, "durum_label"):
            self.durum_label.setText("")

    def _arama_degisti(self, metin: str):
        """Arama kutusuna yazıldığında bölüm listesini filtreler."""
        self._arama_metni = metin.strip()
        self.bolum_listesini_yukle()

    def _otomatik_kaydet(self):
        """
        30 saniyede bir çalışır; kaydedilmemiş değişiklik varsa sessizce kaydeder.
        Hata olursa kullanıcıyı rahatsız etmez — yalnızca konsola yazar.
        """
        if not self._kaydedilmemis or not self.aktif_bolum_id:
            return
        if not hasattr(self, "orijinal_metin_edit"):
            return
        try:
            baslik    = self.baslik_input.text().strip() or None
            orijinal  = self.orijinal_metin_edit.toPlainText()
            cevrilmis = self.ceviri_metin_edit.toPlainText()
            durum     = self.durum_combo.currentData()
            basari = self.db_manager.bolum_guncelle(
                bolum_id=self.aktif_bolum_id,
                bolum_baslik=baslik,
                orijinal_metin=orijinal,
                cevrilmis_metin=cevrilmis,
                durum=durum,
            )
            if basari:
                self._kaydedilmemis = False
                if hasattr(self, "degisiklik_label"):
                    self.degisiklik_label.setText("")
                self._gecici_durum_goster("Otomatik kaydedildi.", "#6b8a6b", 1500)
        except Exception as exc:
            print(f"[Otomatik Kaydet] Hata: {exc}")

    def _sag_paneli_temizle(self):
        """Sağ içerik alanındaki tüm widget'ları kaldırır."""
        while self.sag_layout.count():
            oge = self.sag_layout.takeAt(0)
            if oge.widget():
                oge.widget().deleteLater()

    def _ayirici(self) -> QFrame:
        """1px yatay ayırıcı çizgi oluşturur."""
        cizgi = QFrame()
        cizgi.setFrameShape(QFrame.Shape.HLine)
        cizgi.setFixedHeight(1)
        cizgi.setStyleSheet("background-color: #1a1225; max-height: 1px;")
        return cizgi

    def _diyalog_stili_uygula(self, widget):
        """Diyaloglara tutarlı koyu tema stilini uygular."""
        # Global tema QApplication seviyesinde uygulandığından
        # ekstra override gerekmez; yalnızca özel durumlar için yer tutucu.
        pass

    def _grup_kutusu_stili(self) -> str:
        return """
            QGroupBox {
                background-color: #0f0a1a;
                border: 1px solid #1a1225;
                border-radius: 8px;
                margin-top: 12px;
                padding: 8px 4px 4px 4px;
                font-weight: 600;
                color: #9b59d0;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px; top: -1px;
                padding: 0 6px;
                color: #9b59d0;
                background-color: #0f0a1a;
            }
        """

    def _metin_edit_stili(self) -> str:
        return """
            QTextEdit {
                background-color: #130c20;
                color: #e8e0f0;
                border: none;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #9b59d0;
                selection-color: #0f0a1a;
            }
            QTextEdit:focus { border: 1px solid #2d1a40; }
            QScrollBar:vertical {
                background: #0f0a1a; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2d1a40; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #3d2d55; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0; background: none;
            }
        """

    def _ikincil_buton_stili(self) -> str:
        return """
            QPushButton {
                background-color: #1a1225; color: #e8e0f0;
                border: 1px solid #3d2d55; border-radius: 6px;
                padding: 6px 14px; font-size: 12px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #9b59d0; }
            QPushButton:disabled { color: #6b5a7a; border-color: #2d1a40; }
        """

    # =========================================================================
    # STREAMING
    # =========================================================================

    def _streaming_token_al(self, token: str):
        """Streaming modunda her token geldiğinde çeviri kutusuna ekler."""
        if not hasattr(self, "ceviri_metin_edit"):
            return
        self._streaming_birikim.append(token)
        # İmleci sona taşıyarak token ekle
        cursor = self.ceviri_metin_edit.textCursor()
        from PyQt6.QtGui import QTextCursor
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.ceviri_metin_edit.setTextCursor(cursor)
        self.ceviri_metin_edit.insertPlainText(token)

    # =========================================================================
    # ÇEVİRİ GEÇMİŞİ (UNDO)
    # =========================================================================

    def _cevirmeyi_geri_al(self):
        """Önceki çeviriyi (undo) geri yükler."""
        if not self.aktif_bolum_id or not self.db_manager:
            return
        bolum = self.db_manager.bolum_getir(self.aktif_bolum_id)
        if not bolum:
            return
        onceki = bolum.get("onceki_ceviri", "")
        if not onceki or not onceki.strip():
            QMessageBox.information(self, "Geri Al", "Geri alınacak önceki çeviri bulunamadı.")
            return
        # Mevcut çeviriyi yeni undo olarak sakla (ileri-geri döngüsü)
        self.db_manager.onceki_ceviri_kaydet(
            self.aktif_bolum_id,
            self.ceviri_metin_edit.toPlainText()
        )
        self.ceviri_metin_edit.setPlainText(onceki)
        self._gecici_durum_goster("Önceki çeviriye döndü.", "#f0d090", 2500)
        self._kaydedilmemis = True
        self._degisiklik_isaretlendir()

    # =========================================================================
    # KALİTE / UX ARAÇLARI
    # =========================================================================

    def _kisayollari_kur(self):
        """Bölüm paneli kısayollarını kaydeder."""
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._cevirmeyi_baslat)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._cevirmeyi_baslat)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._metin_arama_ac)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._okuma_modu_toggle)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._diff_goster)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, activated=self._sozluk_uyum_kontrol)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._esc_eylemi)

    def _esc_eylemi(self):
        """Esc: çeviriyi iptal et veya okuma modundan çık."""
        if self._worker is not None and self._worker.isRunning():
            self._tek_ceviri_iptal()
            return
        if self._okuma_modu and hasattr(self, "okuma_modu_btn"):
            self.okuma_modu_btn.setChecked(False)

    def _sozluk_uyum_kontrol(self):
        """Çeviride sözlük karşılıklarının kullanılıp kullanılmadığını kontrol eder."""
        if not hasattr(self, "ceviri_metin_edit"):
            return
        ceviri = self.ceviri_metin_edit.toPlainText()
        terimler = getattr(self, "_son_sozluk_terimleri", None)
        if not terimler and self.seri_id and self.db_manager:
            orijinal = self.orijinal_metin_edit.toPlainText() if hasattr(self, "orijinal_metin_edit") else ""
            terimler = self.db_manager.metinde_sozluk_terimlerini_bul(self.seri_id, orijinal)
        sozluk_uyum_goster(self, ceviri, terimler or [])

    def _diff_goster(self):
        """Önceki çeviri ile güncel çeviri arasındaki farkı gösterir."""
        if not self.aktif_bolum_id or not self.db_manager:
            return
        if not hasattr(self, "ceviri_metin_edit"):
            return
        bolum = self.db_manager.bolum_getir(self.aktif_bolum_id)
        onceki = (bolum or {}).get("onceki_ceviri") or ""
        yeni = self.ceviri_metin_edit.toPlainText()
        diff_goster(self, onceki, yeni)

    def _okuma_modu_toggle(self):
        if hasattr(self, "okuma_modu_btn"):
            self.okuma_modu_btn.setChecked(not self.okuma_modu_btn.isChecked())

    def _okuma_modu_degisti(self, acik: bool):
        """Okuma modu: orijinal paneli gizler, çeviriyi salt okunur yapar."""
        self._okuma_modu = acik
        if not hasattr(self, "orijinal_metin_edit") or not hasattr(self, "ceviri_metin_edit"):
            return
        # Orijinal panelin parent GroupBox'ını bul
        orijinal_grup = self.orijinal_metin_edit.parent()
        while orijinal_grup is not None and not isinstance(orijinal_grup, QGroupBox):
            orijinal_grup = orijinal_grup.parent()
        if orijinal_grup is not None:
            orijinal_grup.setVisible(not acik)
        self.ceviri_metin_edit.setReadOnly(acik)
        if hasattr(self, "okuma_modu_btn"):
            self.okuma_modu_btn.setText("  Düzenle" if acik else "  Okuma")
        self._gecici_durum_goster(
            "Okuma modu açık." if acik else "Düzenleme modu.",
            "#c9a8e8", 1800
        )

    def _metin_arama_ac(self):
        """Orijinal + çeviri metinlerinde arama diyaloğu."""
        if not hasattr(self, "orijinal_metin_edit"):
            return
        from PyQt6.QtWidgets import QInputDialog
        sorgu, ok = QInputDialog.getText(self, "Metinde Ara", "Aranacak metin:")
        if not ok or not sorgu.strip():
            return
        self._metin_arama_son_idx = 0
        self._metinde_bul(sorgu.strip())

    def _metinde_bul(self, sorgu: str):
        """Önce çeviride, yoksa orijinalde arar ve seçer."""
        hedefler = []
        if hasattr(self, "ceviri_metin_edit"):
            hedefler.append(self.ceviri_metin_edit)
        if hasattr(self, "orijinal_metin_edit"):
            hedefler.append(self.orijinal_metin_edit)

        for edit in hedefler:
            metin = edit.toPlainText()
            idx = metin_icerisinde_ara(metin, sorgu, self._metin_arama_son_idx)
            if idx is None and self._metin_arama_son_idx > 0:
                idx = metin_icerisinde_ara(metin, sorgu, 0)
            if idx is not None:
                cursor = edit.textCursor()
                cursor.setPosition(idx)
                cursor.setPosition(idx + len(sorgu), QTextCursor.MoveMode.KeepAnchor)
                edit.setTextCursor(cursor)
                edit.setFocus()
                self._metin_arama_son_idx = idx + len(sorgu)
                self._gecici_durum_goster(f"Bulundu: “{sorgu}”", "#a0f0b0", 2000)
                return
        self._metin_arama_son_idx = 0
        self._gecici_durum_goster(f"Bulunamadı: “{sorgu}”", "#f0d090", 2500)

    # =========================================================================
    # DURUM FİLTRESİ
    # =========================================================================

    def _filtre_degisti(self):
        """Filtre combobox değiştiğinde listeyi yeniler."""
        self._filtre_durum = self.filtre_combo.currentData()
        self.bolum_listesini_yukle()

    # =========================================================================
    # TOKEN TAHMİNİ
    # =========================================================================

    def _token_tahminini_guncelle(self):
        """Orijinal metin uzunluğuna göre yaklaşık token ve maliyet tahmini gösterir."""
        if not hasattr(self, "token_label"):
            return
        metin = self.orijinal_metin_edit.toPlainText() if hasattr(self, "orijinal_metin_edit") else ""
        if not metin.strip():
            self.token_label.setText("")
            return
        # Yaklaşık: 1 token ≈ 4 karakter (Türkçe/Japonca için ~3)
        tahmini_token = max(1, len(metin) // 3)
        # GPT-4o fiyatı: ~$5/1M token giriş
        tahmini_maliyet = tahmini_token * 5 / 1_000_000
        if tahmini_maliyet < 0.001:
            maliyet_str = "<$0.001"
        else:
            maliyet_str = f"~${tahmini_maliyet:.3f}"
        self.token_label.setText(f"~{tahmini_token:,} token | {maliyet_str}")

    # =========================================================================
    # SENKRONİZE SCROLL
    # =========================================================================

    def _orijinal_scroll_degisti(self, deger: int):
        """Orijinal panel kaydırılınca çeviri panelini senkronize eder."""
        if not self._sync_scroll_aktif:
            return
        if not hasattr(self, "ceviri_metin_edit"):
            return
        sb = self.ceviri_metin_edit.verticalScrollBar()
        # Oransal konum hesapla
        kaynak_sb = self.orijinal_metin_edit.verticalScrollBar()
        maks = kaynak_sb.maximum()
        if maks > 0:
            oran = deger / maks
            hedef_maks = sb.maximum()
            self._sync_scroll_aktif = False
            sb.setValue(int(oran * hedef_maks))
            self._sync_scroll_aktif = True

    def _ceviri_scroll_degisti(self, deger: int):
        """Çeviri paneli kaydırılınca orijinal paneli senkronize eder."""
        if not self._sync_scroll_aktif:
            return
        if not hasattr(self, "orijinal_metin_edit"):
            return
        sb = self.orijinal_metin_edit.verticalScrollBar()
        kaynak_sb = self.ceviri_metin_edit.verticalScrollBar()
        maks = kaynak_sb.maximum()
        if maks > 0:
            oran = deger / maks
            hedef_maks = sb.maximum()
            self._sync_scroll_aktif = False
            sb.setValue(int(oran * hedef_maks))
            self._sync_scroll_aktif = True

    # =========================================================================
    # TOPLU ÇEVİRİ
    # =========================================================================

    def _toplu_ceviri_baslat(self):
        """Toplu çeviri diyaloğunu açar ve seçili bölümleri sırayla çevirir."""
        if not self.translator:
            QMessageBox.warning(self, "AI Yapılandırılmamış",
                                "Lütfen önce Ayarlar menüsünden bir AI sağlayıcısı ekleyin.")
            return
        if not self.seri_id or not self.db_manager:
            return

        seri = self.db_manager.seri_getir(self.seri_id)
        if not seri:
            return

        bolumler = self.db_manager.serinin_bolumlerini_getir(self.seri_id)
        bekleyenler = [b for b in bolumler if b.get("durum") == "beklemede"
                       and (b.get("orijinal_metin") or "").strip()]

        if not bekleyenler:
            QMessageBox.information(self, "Toplu Çeviri",
                                    "Çevrilecek 'beklemede' durumunda ve orijinal metni olan bölüm yok.")
            return

        onay = QMessageBox(self)
        onay.setWindowTitle("Toplu Çeviri")
        onay.setText(
            f"{len(bekleyenler)} adet 'beklemede' bölüm bulundu.\n"
            "Tümü sırayla çevrilecek. Devam edilsin mi?"
        )
        evet_btn  = onay.addButton("Evet, Başlat", QMessageBox.ButtonRole.AcceptRole)
        hayir_btn = onay.addButton("İptal",        QMessageBox.ButtonRole.RejectRole)
        onay.setDefaultButton(hayir_btn)
        self._diyalog_stili_uygula(onay)
        onay.exec()

        if onay.clickedButton() != evet_btn:
            return

        # Tüm sözlük terimlerini al
        tum_sozluk = self.db_manager.sozluk_terimlerini_getir(self.seri_id)

        ayar = self.db_manager.aktif_ai_ayar_getir()
        saglayici_kodu = ayar.get("saglayici", "") if ayar else ""
        model_kodu     = ayar.get("model_adi", "") if ayar else getattr(self.translator, "model_adi", "")

        self._batch_worker = BatchTranslationWorker(
            translator=self.translator,
            bolumler=bekleyenler,
            seri=seri,
            sozluk_terimleri=tum_sozluk,
            db_manager=self.db_manager,
            saglayici=saglayici_kodu,
            model_adi=model_kodu,
            parent=self,
        )
        self._batch_worker.ilerleme.connect(self._toplu_ceviri_ilerleme)
        self._batch_worker.bolum_bitti.connect(self._toplu_bolum_tamamlandi)
        self._batch_worker.tamamlandi.connect(self._toplu_ceviri_tamamlandi)
        self._batch_worker.duraklatildi.connect(self._toplu_ceviri_duraklatildi)
        self._batch_worker.devam_edildi.connect(self._toplu_ceviri_devam_edildi)

        self.cevir_btn.setEnabled(False)
        self.toplu_cevir_btn.setEnabled(False)
        self.ceviriliyor_label.setVisible(True)
        self.ilerleme_cubugu.setVisible(True)

        # Duraklat/Devam Et + İptal butonlarını göster
        self._toplu_duraklat_btn.setText("  ⏸ Duraklat")
        self._toplu_duraklat_btn.setVisible(True)
        self._toplu_iptal_btn.setVisible(True)

        self._batch_worker.start()

    def _toplu_ceviri_ilerleme(self, tamamlanan: int, toplam: int, baslik: str):
        """Toplu çeviri ilerleme güncellemesi."""
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setText(
                f"Toplu çeviri: {tamamlanan+1}/{toplam} — {baslik[:30]}..."
            )

    def _toplu_bolum_tamamlandi(self, bolum_id: int, cevrilmis_metin: str):
        """Toplu çeviride bir bölüm tamamlandığında DB'ye kaydeder."""
        bolum = self.db_manager.bolum_getir(bolum_id)
        if not bolum:
            return
        self.db_manager.bolum_guncelle(
            bolum_id=bolum_id,
            bolum_baslik=bolum.get("bolum_baslik"),
            orijinal_metin=bolum.get("orijinal_metin"),
            cevrilmis_metin=cevrilmis_metin,
            durum="cevirildi",
        )
        # Aktif bölümse görünümü güncelle
        if bolum_id == self.aktif_bolum_id and hasattr(self, "ceviri_metin_edit"):
            self.ceviri_metin_edit.setPlainText(cevrilmis_metin)

    def _toplu_ceviri_tamamlandi(self, basarili: int, basarisiz: int):
        """Toplu çeviri tamamlandığında UI'ı sıfırlar ve sonucu gösterir."""
        self._batch_worker = None
        if hasattr(self, "cevir_btn"):
            self.cevir_btn.setEnabled(True)
        if hasattr(self, "toplu_cevir_btn"):
            self.toplu_cevir_btn.setEnabled(True)
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setText("Çevriliyor...")
            self.ceviriliyor_label.setVisible(False)
        if hasattr(self, "ilerleme_cubugu"):
            self.ilerleme_cubugu.setVisible(False)
        if hasattr(self, "_toplu_duraklat_btn"):
            self._toplu_duraklat_btn.setVisible(False)
        if hasattr(self, "_toplu_iptal_btn"):
            self._toplu_iptal_btn.setVisible(False)
        self.bolum_listesini_yukle()
        self._aktif_ogeyi_sec()
        QMessageBox.information(
            self, "Toplu Çeviri Tamamlandı",
            f"Toplu çeviri bitti.\n✓ Başarılı: {basarili}\n✗ Başarısız: {basarisiz}"
        )

    def _toplu_ceviri_duraklat_toggle(self):
        """Duraklat/Devam Et butonuna basıldığında durumu değiştirir."""
        if self._batch_worker is None:
            return
        if self._batch_worker._duraklatildi:
            self._batch_worker.devam_et()
        else:
            self._batch_worker.duraklat()

    def _toplu_ceviri_duraklatildi(self):
        """Toplu çeviri duraklatıldığında butonu günceller."""
        if hasattr(self, "_toplu_duraklat_btn"):
            self._toplu_duraklat_btn.setText("  ▶ Devam Et")
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setText("Toplu çeviri duraklatıldı...")

    def _toplu_ceviri_devam_edildi(self):
        """Toplu çeviri devam ettiğinde butonu günceller."""
        if hasattr(self, "_toplu_duraklat_btn"):
            self._toplu_duraklat_btn.setText("  ⏸ Duraklat")
        if hasattr(self, "ceviriliyor_label"):
            self.ceviriliyor_label.setText("Çevriliyor...")

    def _toplu_ceviri_iptal(self):
        """Toplu çeviriyi iptal eder."""
        if self._batch_worker is not None:
            self._batch_worker.dur()
        if hasattr(self, "_toplu_duraklat_btn"):
            self._toplu_duraklat_btn.setVisible(False)
        if hasattr(self, "_toplu_iptal_btn"):
            self._toplu_iptal_btn.setVisible(False)

    # =========================================================================
    # OTOMATİK SÖZLÜK ÖNERİSİ
    # =========================================================================

    def _otomatik_sozluk_onerisi(self, orijinal_metin: str, cevrilmis_metin: str):
        """
        Çeviri tamamlandıktan sonra NER motoru ile orijinal metni analiz eder.
        Yüksek güvenli entity'ler DB'ye öneri olarak eklenir (çeviri kullanıcıdan alınır).
        UI bildirimi gösterir; detay için Sözlük → Öneriler sekmesi açılabilir.
        """
        if not self.seri_id or not self.db_manager:
            return

        try:
            from story_dict import StoryDictionaryEngine
        except ImportError:
            return

        # Mevcut sözlük ile engine'i başlat
        mevcut = self.db_manager.sozluk_terimlerini_getir(self.seri_id, sadece_onaylandi=False)
        engine = StoryDictionaryEngine(mevcut)

        # Bölüm numarasını bul
        bolum_no = 0
        if self.aktif_bolum_id and self.db_manager:
            try:
                b = self.db_manager.bolum_getir(self.aktif_bolum_id)
                if b:
                    bolum_no = b.get("bolum_no", 0) or 0
            except Exception:
                pass

        sonuc = engine.analyze_chapter(orijinal_metin, bolum_no=bolum_no, existing_entries=mevcut)

        adaylar = [
            {
                "phrase":      a["phrase"],
                "entity_type": a["entity_type"],
                "confidence":  a["confidence"],
                "frequency":   a["frequency"],
                "bolum_no":    bolum_no,
            }
            for a in sonuc["auto_save"] + sonuc["suggestions"]
        ]
        eklenen = self.db_manager.oneri_ekle_toplu(self.seri_id, adaylar) if adaylar else 0

        if eklenen:
            self._gecici_durum_goster(
                f"{eklenen} entity önerisi eklendi. Sözlük → Öneriler sekmesinden onaylayın.",
                "#f0d090", 5000
            )


# =============================================================================
# HIZLI TEST — python chapters_widget.py ile çalıştırılabilir
# =============================================================================

if __name__ == "__main__":
    from database import DatabaseManager

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #0f0a1a;
            color: #e8e0f0;
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QMessageBox { background-color: #0f0a1a; color: #e8e0f0; }
        QInputDialog { background-color: #0f0a1a; color: #e8e0f0; }
    """)

    db = DatabaseManager()

    # Test serisi
    seriler = db.tum_serileri_getir()
    if not seriler:
        seri_id = db.seri_olustur("Test Serisi", "Japonca", "Turkce")
    else:
        seri_id = seriler[0]["id"]

    # Test bölümleri
    bolumler = db.serinin_bolumlerini_getir(seri_id)
    if not bolumler:
        db.bolum_olustur(seri_id, 1, "Ilk Bolum",
                         "Bu bir test metnidir. Kirito ve Asuna Aincrad'da.")
        db.bolum_olustur(seri_id, 2, "Ikinci Bolum", "Ikinci bolum metni.")

    # Test sozlugu
    if not db.sozluk_terimlerini_getir(seri_id):
        db.sozluk_terimi_ekle(seri_id, "Kirito",  "Kirito",  "karakter", entity_type="PERSON")
        db.sozluk_terimi_ekle(seri_id, "Asuna",   "Asuna",   "karakter", entity_type="PERSON")
        db.sozluk_terimi_ekle(seri_id, "Aincrad", "Aincrad", "mekan",    entity_type="LOCATION")

    widget = ChaptersWidget(seri_id=seri_id, db_manager=db, translator=None)
    widget.setWindowTitle("Bolumler Widget - Test")
    widget.resize(1200, 700)
    widget.show()

    sys.exit(app.exec())