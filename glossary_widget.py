"""
Novel Çevirmen - Story Consistency Dictionary Widget
Her seriye ait hikaye tutarlılık sözlüğünü yöneten arayüz bileşeni.
NER tabanlı entity yönetimi, kilit, güven skoru ve öneri sistemi içerir.
"""

import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QComboBox, QMessageBox, QFileDialog,
    QAbstractItemView, QFrame, QTabWidget, QScrollArea, QCheckBox,
    QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from icons import set_icon
from story_dict import EntityType, StoryDictionaryEngine


# =============================================================================
# KATEGORİ SABİTLERİ
# =============================================================================

# Veritabanında saklanan kategori kod adları (eski uyumluluk)
KATEGORI_KODLAR = ["karakter", "mekan", "beceri", "esya", "sistem", "diger"]

# Kategori kodu → EntityType eşlemesi
# SozlukGirdisiDialog'dan kayıt geldiğinde entity_type alanını doldurmak için kullanılır.
KATEGORI_TO_ENTITY_TYPE = {
    "karakter": "PERSON",
    "mekan":    "LOCATION",
    "beceri":   "SKILL",
    "esya":     "ITEM",
    "sistem":   "ORGANIZATION",
    "diger":    "PERSON",
}

# Kullanıcıya gösterilen Türkçe karşılıkları
KATEGORI_GORUNUM = {
    "karakter": "Karakter",
    "mekan":    "Mekan",
    "beceri":   "Beceri",
    "esya":     "Eşya",
    "sistem":   "Sistem",
    "diger":    "Diğer",
}

# Entity type → kullanıcı dostu ad
ENTITY_GORUNUM = {
    EntityType.PERSON:       "Karakter",
    EntityType.LOCATION:     "Mekan",
    EntityType.ORGANIZATION: "Örgüt",
    EntityType.TITLE:        "Unvan",
    EntityType.SKILL:        "Beceri",
    EntityType.ABILITY:      "Yetenek",
    EntityType.ITEM:         "Eşya",
    EntityType.RACE:         "Irk",
    EntityType.MONSTER:      "Canavar",
    EntityType.REALM:        "Realm",
}

# Entity type → rozet rengi
ENTITY_RENKLER = {
    EntityType.PERSON:       "#9b59d0",   # mor
    EntityType.LOCATION:     "#a0f0b0",   # yeşil
    EntityType.ORGANIZATION: "#c9a8e8",   # açık mor
    EntityType.TITLE:        "#e8b86a",   # altın
    EntityType.SKILL:        "#f0d090",   # sarı
    EntityType.ABILITY:      "#d0e060",   # lime
    EntityType.ITEM:         "#d8a880",   # turuncu
    EntityType.RACE:         "#80c8f0",   # mavi
    EntityType.MONSTER:      "#f08080",   # kırmızı
    EntityType.REALM:        "#a8d8e8",   # açık mavi
}

# Her kategorinin rozet rengi (eski uyumluluk)
KATEGORI_RENKLER = {
    "karakter": "#9b59d0",
    "mekan":    "#a0f0b0",
    "beceri":   "#f0d090",
    "esya":     "#d8a880",
    "sistem":   "#c9a8e8",
    "diger":    "#6b5a7a",
}

# Tablo sütun indeksleri — ana sözlük
SUTUN_NO        = 0
SUTUN_KILIT     = 1
SUTUN_ORIJINAL  = 2
SUTUN_CEVRILMIS = 3
SUTUN_ENTITY    = 4
SUTUN_GECIS     = 5
SUTUN_GUVEN     = 6
SUTUN_NOTLAR    = 7
SUTUN_ISLEMLER  = 8


# =============================================================================
# YARDIMCI — KATEGORİ ROZET ETİKETİ
# =============================================================================

def kategori_rozet_olustur(kategori_kodu: str) -> QLabel:
    """Eski kategori kodu için renkli rozet (geriye uyumluluk)."""
    gorunum = KATEGORI_GORUNUM.get(kategori_kodu, kategori_kodu.capitalize())
    renk    = KATEGORI_RENKLER.get(kategori_kodu, "#6b5a7a")
    return _rozet_olustur(gorunum, renk)


def entity_rozet_olustur(entity_type: str) -> QLabel:
    """Entity türü için renkli rozet etiketi döndürür."""
    gorunum = ENTITY_GORUNUM.get(entity_type, entity_type)
    renk    = ENTITY_RENKLER.get(entity_type, "#6b5a7a")
    return _rozet_olustur(gorunum, renk)


def _rozet_olustur(gorunum: str, renk: str) -> QLabel:
    etiket = QLabel(gorunum)
    etiket.setAlignment(Qt.AlignmentFlag.AlignCenter)
    etiket.setFixedHeight(22)
    etiket.setStyleSheet(f"""
        QLabel {{
            background-color: {renk}22;
            color: {renk};
            border: 1px solid {renk}66;
            border-radius: 4px;
            padding: 1px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
    """)
    return etiket


def _kilit_ikonu(kilitli: bool) -> QLabel:
    """Kilit durumu etiketi."""
    lbl = QLabel("🔒" if kilitli else "")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setToolTip("Kilitli — AI bu çeviriyi değiştiremez" if kilitli else "Kilitsiz")
    lbl.setStyleSheet("background: transparent; font-size: 14px;")
    return lbl


# =============================================================================
# SÖZLÜK GİRDİSİ DİYALOĞU
# =============================================================================

class SozlukGirdisiDialog(QDialog):
    """
    Yeni terim ekleme ve mevcut terimi düzenleme için ortak diyalog.
    mevcut_girdi verilmişse düzenleme modunda açılır.
    """

    def __init__(self, parent=None, mevcut_girdi: dict = None):
        super().__init__(parent)
        self.mevcut_girdi = mevcut_girdi
        self.duzenle_modu = mevcut_girdi is not None

        self.setWindowTitle("Terimi Düzenle" if self.duzenle_modu else "Yeni Terim Ekle")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._arayuz_olustur()

        if self.duzenle_modu:
            self._alanlari_doldur()

    def _arayuz_olustur(self):
        ana_layout = QVBoxLayout(self)
        ana_layout.setSpacing(14)
        ana_layout.setContentsMargins(24, 24, 24, 20)

        # ── Başlık ────────────────────────────────────────────────────────
        baslik = QLabel("Terimi Düzenle" if self.duzenle_modu else "Yeni Terim Ekle")
        baslik.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #9b59d0;")
        ana_layout.addWidget(baslik)

        # ── Form alanları ─────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Orijinal terim
        self.orijinal_input = QLineEdit()
        self.orijinal_input.setPlaceholderText("Kaynaktaki terimin tam yazılışı...")
        form.addRow("Orijinal Terim *", self.orijinal_input)

        # Çevrilmiş terim
        self.cevrilmis_input = QLineEdit()
        self.cevrilmis_input.setPlaceholderText("Her zaman kullanılacak Türkçe karşılık...")
        form.addRow("Çevrilmiş Terim *", self.cevrilmis_input)

        # Kategori ComboBox
        self.kategori_combo = QComboBox()
        for kod in KATEGORI_KODLAR:
            self.kategori_combo.addItem(
                KATEGORI_GORUNUM[kod],   # görünen metin
                userData=kod             # gizli veri: kod
            )
        form.addRow("Kategori", self.kategori_combo)

        # Notlar
        self.notlar_input = QLineEdit()
        self.notlar_input.setPlaceholderText("İsteğe bağlı — çevirmen notu...")
        form.addRow("Notlar", self.notlar_input)

        ana_layout.addLayout(form)

        # ── İpucu metni ───────────────────────────────────────────────────
        ipucu = QLabel(
            "Ipucu: Orijinal terimi tam olarak göründüğü gibi girin. "
            "Büyük/küçük harf duyarsız arama yapılır."
        )
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet(
            "color: #6b5a7a; font-size: 11px; "
            "background: #1a1225; border-radius: 4px; padding: 6px 8px;"
        )
        ana_layout.addWidget(ipucu)

        # ── Hata etiketi ──────────────────────────────────────────────────
        self.hata_label = QLabel("")
        self.hata_label.setStyleSheet("color: #f0a0b0; font-size: 12px;")
        self.hata_label.setVisible(False)
        ana_layout.addWidget(self.hata_label)

        # ── Butonlar ──────────────────────────────────────────────────────
        buton_layout = QHBoxLayout()
        buton_layout.addStretch()

        self.iptal_btn = QPushButton("İptal")
        self.iptal_btn.setObjectName("ikincilButon")
        self.iptal_btn.setFixedWidth(90)
        self.iptal_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d1a40;
                color: #e8e0f0;
                border: none;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #3d2d55; }
        """)
        self.iptal_btn.clicked.connect(self.reject)

        self.kaydet_btn = QPushButton("Kaydet")
        self.kaydet_btn.setFixedWidth(100)
        self.kaydet_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59d0;
                color: #0f0a1a;
                border: none;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #b06ad9; }
        """)
        self.kaydet_btn.clicked.connect(self._kaydet)
        self.kaydet_btn.setDefault(True)

        buton_layout.addWidget(self.iptal_btn)
        buton_layout.addSpacing(8)
        buton_layout.addWidget(self.kaydet_btn)
        ana_layout.addLayout(buton_layout)

    def _alanlari_doldur(self):
        """Düzenleme modunda mevcut terim verilerini alanlara yazar."""
        g = self.mevcut_girdi
        self.orijinal_input.setText(g.get("orijinal_terim", ""))
        self.cevrilmis_input.setText(g.get("cevrilmis_terim", ""))
        self.notlar_input.setText(g.get("notlar", "") or "")

        # Kategori seçimini eşleştir
        kod = g.get("kategori", "diger")
        idx = self.kategori_combo.findData(kod)
        if idx >= 0:
            self.kategori_combo.setCurrentIndex(idx)

    def _kaydet(self):
        """Formu doğrular; geçerliyse sonuçları alanlara yazar ve kapatır."""
        orijinal  = self.orijinal_input.text().strip()
        cevrilmis = self.cevrilmis_input.text().strip()

        if not orijinal or not cevrilmis:
            self.hata_label.setText(
                "Orijinal Terim ve Çevrilmiş Terim alanları zorunludur."
            )
            self.hata_label.setVisible(True)
            return

        self.hata_label.setVisible(False)

        # Sonuçları dışarıdan okunabilecek niteliklere ata
        self.sonuc_orijinal  = orijinal
        self.sonuc_cevrilmis = cevrilmis
        self.sonuc_kategori  = self.kategori_combo.currentData()
        self.sonuc_notlar    = self.notlar_input.text().strip() or None

        self.accept()


# =============================================================================
# ANA SÖZLÜK WIDGET'I
# =============================================================================

class GlossaryWidget(QWidget):
    """
    Bir seriye ait sözlük terimlerini listeleyen, ekleyen, düzenleyen,
    silen ve CSV ile içe/dışa aktaran ana bileşen.
    """

    def __init__(self, seri_id=None, db_manager=None, parent=None):
        super().__init__(parent)
        self.seri_id    = seri_id
        self.db_manager = db_manager

        # Tabloda gösterilen terim kayıtları (dict listesi)
        self._terimler: list[dict] = []

        self._arayuz_olustur()

        # Seri verilmişse hemen yükle
        if self.seri_id and self.db_manager:
            self.sozlugu_yukle()

    # =========================================================================
    # ARAYÜZ KURULUMU
    # =========================================================================

    def _arayuz_olustur(self):
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(16, 14, 16, 14)
        ana_layout.setSpacing(10)

        # ── Üst araç çubuğu ───────────────────────────────────────────────
        ana_layout.addLayout(self._arac_cubugu_olustur())

        # ── Tab widget: Sözlük | Öneriler ─────────────────────────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; background: #0f0a1a; }
            QTabBar::tab {
                background: #130c20; color: #6b5a7a;
                border: none; border-radius: 4px 4px 0 0;
                padding: 6px 18px; margin-right: 2px; font-size: 12px;
            }
            QTabBar::tab:selected { background: #1a1225; color: #9b59d0; font-weight: 600; }
            QTabBar::tab:hover { background: #1a1225; }
        """)

        # — Sözlük sekmesi —
        sozluk_tab = QWidget()
        sozluk_layout = QVBoxLayout(sozluk_tab)
        sozluk_layout.setContentsMargins(0, 8, 0, 0)
        sozluk_layout.setSpacing(0)

        self.tablo = self._tablo_olustur()
        sozluk_layout.addWidget(self.tablo, stretch=1)

        self.bos_durum_label = QLabel(
            "Bu seri için henüz sözlük girdisi yok.\n"
            "'Terim Ekle' butonuna tıklayarak başlayın."
        )
        self.bos_durum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bos_durum_label.setStyleSheet("color: #6b5a7a; font-size: 14px; padding: 40px;")
        self.bos_durum_label.setVisible(False)
        sozluk_layout.addWidget(self.bos_durum_label, stretch=1)

        self.tab_widget.addTab(sozluk_tab, "Sözlük")

        # — Öneriler sekmesi —
        self.oneri_tab_widget = self._oneri_sekmesi_olustur()
        self.tab_widget.addTab(self.oneri_tab_widget, "Öneriler (0)")

        ana_layout.addWidget(self.tab_widget, stretch=1)

    def _arac_cubugu_olustur(self) -> QHBoxLayout:
        """Arama, ekle, içe aktar, dışa aktar ve sayaç satırı."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Arama kutusu
        self.arama_input = QLineEdit()
        self.arama_input.setPlaceholderText("Terim ara...")
        self.arama_input.setFixedHeight(34)
        self.arama_input.setMinimumWidth(220)
        self.arama_input.textChanged.connect(self._arama_filtrele)
        layout.addWidget(self.arama_input)

        layout.addStretch()

        # Terim Ekle
        self.ekle_btn = QPushButton("  Terim Ekle")
        self.ekle_btn.setFixedHeight(34)
        self.ekle_btn.setStyleSheet(self._birincil_buton_stili())
        self.ekle_btn.clicked.connect(self._terim_ekle)
        set_icon(self.ekle_btn, "add", size=16)
        layout.addWidget(self.ekle_btn)

        # Otomatik Tara
        self.otomatik_tara_btn = QPushButton("  Otomatik Tara")
        self.otomatik_tara_btn.setFixedHeight(34)
        self.otomatik_tara_btn.setStyleSheet(self._ikincil_buton_stili())
        self.otomatik_tara_btn.clicked.connect(self._tum_bolumlerden_tara)
        set_icon(self.otomatik_tara_btn, "search", size=16)
        layout.addWidget(self.otomatik_tara_btn)

        # CSV İçe Aktar
        self.iceaktar_btn = QPushButton("  CSV İçe Aktar")
        self.iceaktar_btn.setFixedHeight(34)
        self.iceaktar_btn.setStyleSheet(self._ikincil_buton_stili())
        self.iceaktar_btn.clicked.connect(self._csv_ice_aktar)
        set_icon(self.iceaktar_btn, "import", size=16)
        layout.addWidget(self.iceaktar_btn)

        # CSV Dışa Aktar
        self.disaaktar_btn = QPushButton("  CSV Dışa Aktar")
        self.disaaktar_btn.setFixedHeight(34)
        self.disaaktar_btn.setStyleSheet(self._ikincil_buton_stili())
        self.disaaktar_btn.clicked.connect(self._csv_disa_aktar)
        set_icon(self.disaaktar_btn, "export", size=16)
        layout.addWidget(self.disaaktar_btn)

        layout.addSpacing(12)

        # Terim sayacı
        self.sayac_label = QLabel("Toplam: 0 terim")
        self.sayac_label.setStyleSheet(
            "color: #6b5a7a; font-size: 12px; min-width: 90px;"
        )
        layout.addWidget(self.sayac_label)

        return layout

    def _oneri_sekmesi_olustur(self) -> QWidget:
        """Öneriler sekmesi widget'ını oluşturur."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # Açıklama
        aciklama = QLabel(
            "AI'ın bölüm analizinde tespit ettiği olası entity'ler.\n"
            "Türkçe karşılıklarını girerek onaylayabilir veya reddedebilirsiniz."
        )
        aciklama.setStyleSheet("color: #6b5a7a; font-size: 11px; padding: 0 4px;")
        aciklama.setWordWrap(True)
        layout.addWidget(aciklama)

        # Scroll alan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self._oneri_icerik = QWidget()
        self._oneri_icerik.setStyleSheet("background: transparent;")
        self._oneri_layout = QVBoxLayout(self._oneri_icerik)
        self._oneri_layout.setSpacing(6)
        self._oneri_layout.setContentsMargins(0, 0, 0, 0)
        self._oneri_layout.addStretch()
        scroll.setWidget(self._oneri_icerik)
        layout.addWidget(scroll, stretch=1)

        # Buton çubuğu
        btn_layout = QHBoxLayout()
        tumunu_onayla_btn = QPushButton("Tümünü Onayla")
        tumunu_onayla_btn.setStyleSheet(self._birincil_buton_stili())
        tumunu_onayla_btn.clicked.connect(self._tum_onerileri_onayla)
        tumunu_reddet_btn = QPushButton("Tümünü Reddet")
        tumunu_reddet_btn.setStyleSheet(self._ikincil_buton_stili())
        tumunu_reddet_btn.clicked.connect(self._tum_onerileri_reddet)
        btn_layout.addWidget(tumunu_onayla_btn)
        btn_layout.addWidget(tumunu_reddet_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return w

    def _tablo_olustur(self) -> QTableWidget:
        """Sözlük terimlerini gösteren ana tabloyu yapılandırır."""
        tablo = QTableWidget()
        tablo.setColumnCount(9)
        tablo.setHorizontalHeaderLabels([
            "No", "🔒", "Orijinal Terim", "Çevrilmiş Terim",
            "Tür", "×", "Güven", "Notlar", "İşlemler"
        ])

        # Sütun genişlikleri
        tablo.setColumnWidth(SUTUN_NO,        38)
        tablo.setColumnWidth(SUTUN_KILIT,     32)
        tablo.setColumnWidth(SUTUN_ORIJINAL,  170)
        tablo.setColumnWidth(SUTUN_CEVRILMIS, 170)
        tablo.setColumnWidth(SUTUN_ENTITY,    100)
        tablo.setColumnWidth(SUTUN_GECIS,     40)
        tablo.setColumnWidth(SUTUN_GUVEN,     55)
        tablo.setColumnWidth(SUTUN_NOTLAR,    140)
        tablo.setColumnWidth(SUTUN_ISLEMLER,  110)

        # Notlar esnesin
        tablo.horizontalHeader().setSectionResizeMode(
            SUTUN_NOTLAR, QHeaderView.ResizeMode.Stretch
        )

        # Genel tablo ayarları
        tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        # Çift tıklamayla inline düzenleme (İşlemler sütunu hariç)
        tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        tablo.itemChanged.connect(self._inline_duzenleme_kaydedildi)
        tablo.setAlternatingRowColors(True)
        tablo.verticalHeader().setVisible(False)
        tablo.horizontalHeader().setHighlightSections(False)
        tablo.setSortingEnabled(True)
        tablo.setShowGrid(False)
        tablo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tablo.verticalHeader().setDefaultSectionSize(38)

        # Tema stilleri
        tablo.setStyleSheet("""
            QTableWidget {
                background-color: #0f0a1a;
                alternate-background-color: #130c20;
                color: #e8e0f0;
                border: none;
                border-radius: 0px;
                gridline-color: transparent;
                outline: none;
                selection-background-color: #1a1225;
            }
            QTableWidget::item {
                padding: 4px 10px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #1a1225;
                color: #9b59d0;
            }
            QHeaderView::section {
                background-color: #0a0612;
                color: #9b59d0;
                border: none;
                border-bottom: 2px solid #1a1225;
                padding: 6px 10px;
                font-weight: 600;
                font-size: 12px;
            }
            QHeaderView::section:hover {
                background-color: #130c20;
            }
            QScrollBar:vertical {
                background: #0f0a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2d1a40;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #3d2d55; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; background: none; }
        """)

        return tablo

    # =========================================================================
    # VERİ YÜKLEME
    # =========================================================================

    def set_seri(self, seri_id: int):
        """
        Aktif seriyi değiştirir ve sözlüğü yeniden yükler.
        main_window.py tarafından seri değiştiğinde çağrılır.
        """
        self.seri_id = seri_id
        self.sozlugu_yukle()

    # Geriye dönük uyumluluk için alias (main_window'da seri_yukle() çağrılıyor)
    def seri_yukle(self, seri_id: int):
        self.set_seri(seri_id)

    def sozlugu_yukle(self):
        """
        Veritabanından serinin sözlük terimlerini çeker ve tabloyu doldurur.
        Her ekleme/düzenleme/silme/içe aktarma sonrasında çağrılır.
        """
        if not self.seri_id or not self.db_manager:
            self._terimler = []
            self._tabloyu_temizle()
            self._bos_durumu_guncelle()
            return

        self._terimler = self.db_manager.sozluk_terimlerini_getir(self.seri_id)
        self._tabloyu_doldur(self._terimler)
        self._sayaci_guncelle(len(self._terimler))
        self._bos_durumu_guncelle()
        self._onerileri_yukle()

        # Mevcut arama filtresini koru
        if self.arama_input.text():
            self._arama_filtrele(self.arama_input.text())

    def _tabloyu_temizle(self):
        """Tablodaki tüm satırları kaldırır."""
        self.tablo.setSortingEnabled(False)
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(0)
        self.tablo.blockSignals(False)
        self.tablo.setSortingEnabled(True)

    def _tabloyu_doldur(self, terimler: list[dict]):
        """Verilen terim listesiyle tabloyu satır satır doldurur."""
        self.tablo.setSortingEnabled(False)
        # Programatik setItem() çağrıları _inline_duzenleme_kaydedildi'yi
        # tetiklemesini önlemek için sinyali geçici olarak kapat.
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(0)

        for sira, terim in enumerate(terimler):
            self.tablo.insertRow(sira)

            # No — terim ID'si UserRole'a yazılır
            no_item = QTableWidgetItem(str(sira + 1))
            no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            no_item.setForeground(QColor("#6b5a7a"))
            no_item.setFlags(no_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            no_item.setData(Qt.ItemDataRole.UserRole, terim["id"])
            self.tablo.setItem(sira, SUTUN_NO, no_item)

            # Kilit ikonu
            kilitli = bool(terim.get("locked", False))
            kilit_w = QWidget()
            kilit_w.setStyleSheet("background: transparent;")
            kilit_l = QHBoxLayout(kilit_w)
            kilit_l.setContentsMargins(2, 0, 2, 0)
            kilit_l.addWidget(_kilit_ikonu(kilitli))
            self.tablo.setCellWidget(sira, SUTUN_KILIT, kilit_w)

            # Orijinal terim
            orijinal_item = QTableWidgetItem(terim.get("orijinal_terim", ""))
            orijinal_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            if kilitli:
                orijinal_item.setForeground(QColor("#e8b86a"))
            self.tablo.setItem(sira, SUTUN_ORIJINAL, orijinal_item)

            # Çevrilmiş terim
            cevrilmis_item = QTableWidgetItem(terim.get("cevrilmis_terim", ""))
            cevrilmis_item.setForeground(QColor("#a0f0b0"))
            self.tablo.setItem(sira, SUTUN_CEVRILMIS, cevrilmis_item)

            # Entity rozeti
            etype = terim.get("entity_type") or EntityType.PERSON
            rozet = entity_rozet_olustur(etype)
            rozet_w = QWidget()
            rozet_w.setStyleSheet("background: transparent;")
            rozet_l = QHBoxLayout(rozet_w)
            rozet_l.setContentsMargins(4, 2, 4, 2)
            rozet_l.addWidget(rozet)
            rozet_l.addStretch()
            self.tablo.setCellWidget(sira, SUTUN_ENTITY, rozet_w)

            # Geçiş sayısı
            gecis_item = QTableWidgetItem(str(terim.get("occurrences", 1)))
            gecis_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            gecis_item.setForeground(QColor("#6b5a7a"))
            gecis_item.setFlags(gecis_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tablo.setItem(sira, SUTUN_GECIS, gecis_item)

            # Güven skoru — None ise 1.0 kullan; 0.0 geçerli bir değerdir
            _conf_raw = terim.get("confidence")
            guven = 1.0 if _conf_raw is None else _conf_raw
            guven_item = QTableWidgetItem(f"{guven:.0%}")
            guven_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if guven >= 0.80:
                guven_item.setForeground(QColor("#a0f0b0"))
            elif guven >= 0.50:
                guven_item.setForeground(QColor("#f0d090"))
            else:
                guven_item.setForeground(QColor("#f08080"))
            guven_item.setFlags(guven_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tablo.setItem(sira, SUTUN_GUVEN, guven_item)

            # Notlar
            notlar_item = QTableWidgetItem(terim.get("notlar", "") or "")
            notlar_item.setForeground(QColor("#6b5a7a"))
            notlar_item.setFont(QFont("Segoe UI", 11))
            self.tablo.setItem(sira, SUTUN_NOTLAR, notlar_item)

            # İşlem butonları
            self._islem_butonlari_ekle(sira, terim)

        self.tablo.blockSignals(False)
        self.tablo.setSortingEnabled(True)

    def _islem_butonlari_ekle(self, satir: int, terim: dict):
        """Tablо satırına 'Kilit', 'Düzenle' ve 'Sil' butonlarını ekler."""
        kapsayici = QWidget()
        kapsayici.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(kapsayici)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        _btn_stili = (
            "QPushButton {{"
            "background-color: #1a1225; color: {renk};"
            "border: 1px solid #2d1a40; border-radius: 5px; font-size: 12px;}}"
            "QPushButton:hover {{background-color: #2d1a40; border-color: {renk};}}"
        )

        kilitli = bool(terim.get("locked", False))

        # Kilit toggle butonu
        kilit_btn = QPushButton("🔒" if kilitli else "🔓")
        kilit_btn.setToolTip("Kilidi Aç" if kilitli else "Kilitle (AI değiştiremez)")
        kilit_btn.setFixedSize(30, 28)
        kilit_btn.setStyleSheet(_btn_stili.format(renk="#e8b86a"))
        kilit_btn.clicked.connect(
            lambda checked, t=terim: self._kilit_toggle(t)
        )

        # Düzenle butonu
        duzenle_btn = QPushButton("")
        duzenle_btn.setToolTip("Düzenle")
        duzenle_btn.setFixedSize(28, 28)
        duzenle_btn.setStyleSheet(_btn_stili.format(renk="#9b59d0"))
        set_icon(duzenle_btn, "edit", size=13)
        duzenle_btn.clicked.connect(
            lambda checked, t=terim: self._terim_duzenle(t)
        )

        # Sil butonu
        sil_btn = QPushButton("")
        sil_btn.setToolTip("Sil")
        sil_btn.setFixedSize(28, 28)
        sil_btn.setStyleSheet(_btn_stili.format(renk="#f0a0b0"))
        set_icon(sil_btn, "delete", size=13)
        sil_btn.clicked.connect(
            lambda checked, t=terim: self._terim_sil(t)
        )

        layout.addWidget(kilit_btn)
        layout.addWidget(duzenle_btn)
        layout.addWidget(sil_btn)
        layout.addStretch()

        self.tablo.setCellWidget(satir, SUTUN_ISLEMLER, kapsayici)

    # =========================================================================
    # ARAMA FİLTRELEME
    # =========================================================================

    def _arama_filtrele(self, aranan: str):
        """
        Kullanıcının arama kutusuna yazdığı metne göre tablo satırlarını
        anlık filtreler. Büyük/küçük harf duyarsız; Orijinal Terim,
        Çevrilmiş Terim ve Notlar sütunlarında arar.
        """
        aranan = aranan.strip().lower()

        gorunen_sayisi = 0
        for satir in range(self.tablo.rowCount()):
            esles = False

            if not aranan:
                # Arama kutusu boşsa tüm satırları göster
                esles = True
            else:
                # Aranacak sütunlar: orijinal, çevrilmiş, notlar
                for sutun in (SUTUN_ORIJINAL, SUTUN_CEVRILMIS, SUTUN_NOTLAR):
                    item = self.tablo.item(satir, sutun)
                    if item and aranan in item.text().lower():
                        esles = True
                        break

            self.tablo.setRowHidden(satir, not esles)
            if esles:
                gorunen_sayisi += 1

        # Arama sırasında sayacı filtre sonucuna güncelle
        if aranan:
            self.sayac_label.setText(f"Sonuç: {gorunen_sayisi} terim")
        else:
            self._sayaci_guncelle(len(self._terimler))

    # =========================================================================
    # OTOMATİK TARAMA
    # =========================================================================

    def _kilit_toggle(self, terim: dict):
        """Bir terimin kilit durumunu değiştirir."""
        girdi_id = terim["id"]
        mevcut_kilit = bool(terim.get("locked", False))
        yeni_kilit = not mevcut_kilit
        self.db_manager.sozluk_terimi_kilitle(girdi_id, yeni_kilit)
        self.sozlugu_yukle()

    def _onerileri_yukle(self):
        """Öneriler sekmesini DB'den yeniler."""
        if not self.seri_id or not self.db_manager:
            return
        oneriler = self.db_manager.onerileri_getir(self.seri_id)
        # Sekme başlığını güncelle
        idx = self.tab_widget.indexOf(self.oneri_tab_widget)
        self.tab_widget.setTabText(idx, f"Öneriler ({len(oneriler)})")

        # Eski widget'ları temizle (stretch hariç)
        while self._oneri_layout.count() > 1:
            item = self._oneri_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not oneriler:
            bos = QLabel("Bekleyen öneri yok.")
            bos.setStyleSheet("color: #6b5a7a; font-size: 13px; padding: 20px;")
            bos.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._oneri_layout.insertWidget(0, bos)
            return

        self._oneri_satirlari = []
        for oneri in oneriler:
            satir_w = self._oneri_satiri_olustur(oneri)
            self._oneri_layout.insertWidget(self._oneri_layout.count() - 1, satir_w)

    def _oneri_satiri_olustur(self, oneri: dict) -> QWidget:
        """Tek bir öneri için onay satırı widget'ı oluşturur."""
        w = QWidget()
        w.setStyleSheet("background: #130c20; border-radius: 6px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Entity rozeti
        rozet = entity_rozet_olustur(oneri.get("entity_type", EntityType.PERSON))
        layout.addWidget(rozet)

        # Orijinal terim
        orig_lbl = QLabel(oneri.get("orijinal_terim", ""))
        orig_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        orig_lbl.setMinimumWidth(160)
        layout.addWidget(orig_lbl)

        # Güven + geçiş
        conf = oneri.get("confidence", 0.65)
        meta_lbl = QLabel(f"×{oneri.get('occurrences', 1)}  {conf:.0%}")
        meta_lbl.setStyleSheet("color: #6b5a7a; font-size: 11px;")
        layout.addWidget(meta_lbl)

        # Çeviri giriş kutusu
        cev_edit = QLineEdit()
        cev_edit.setPlaceholderText("Türkçe karşılık...")
        cev_edit.setFixedHeight(28)
        cev_edit.setMinimumWidth(150)
        cev_edit.setStyleSheet(
            "background: #1a1225; color: #a0f0b0; border: 1px solid #2d1a40;"
            "border-radius: 4px; padding: 2px 6px;"
        )
        layout.addWidget(cev_edit, stretch=1)

        # Onayla
        onayla_btn = QPushButton("✓ Onayla")
        onayla_btn.setFixedHeight(28)
        onayla_btn.setStyleSheet("""
            QPushButton { background: #2a4a2a; color: #a0f0b0; border: 1px solid #4a8a4a;
                          border-radius: 4px; padding: 2px 10px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #3a6a3a; }
        """)
        oneri_id = oneri["id"]
        onayla_btn.clicked.connect(lambda _, oid=oneri_id, e=cev_edit: self._oneri_onayla(oid, e))
        layout.addWidget(onayla_btn)

        # Reddet
        reddet_btn = QPushButton("✗")
        reddet_btn.setFixedSize(28, 28)
        reddet_btn.setToolTip("Reddet")
        reddet_btn.setStyleSheet("""
            QPushButton { background: #2a1a1a; color: #f0a0b0; border: 1px solid #6a3a3a;
                          border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background: #3a2020; }
        """)
        reddet_btn.clicked.connect(lambda _, oid=oneri_id: self._oneri_reddet(oid))
        layout.addWidget(reddet_btn)

        self._oneri_satirlari.append((oneri, cev_edit))
        return w

    def _oneri_onayla(self, oneri_id: int, cev_edit: QLineEdit):
        """Tek öneriyi onaylar."""
        ceviri = cev_edit.text().strip()
        if not ceviri:
            cev_edit.setPlaceholderText("⚠ Çeviri gerekli!")
            cev_edit.setStyleSheet(
                "background: #1a1225; color: #f0a0b0; border: 1px solid #f0a0b0;"
                "border-radius: 4px; padding: 2px 6px;"
            )
            return
        self.db_manager.oneri_onayla(oneri_id, ceviri, locked=False)
        self.sozlugu_yukle()
        self._onerileri_yukle()

    def _oneri_reddet(self, oneri_id: int):
        """Tek öneriyi reddeder."""
        self.db_manager.oneri_reddet(oneri_id)
        self._onerileri_yukle()

    def _tum_onerileri_onayla(self):
        """Türkçe karşılığı girilmiş tüm önerileri onaylar."""
        if not hasattr(self, "_oneri_satirlari"):
            return
        onaylanan = 0
        for oneri, cev_edit in self._oneri_satirlari:
            ceviri = cev_edit.text().strip()
            if ceviri:
                self.db_manager.oneri_onayla(oneri["id"], ceviri)
                onaylanan += 1
        if onaylanan:
            self.sozlugu_yukle()
            self._onerileri_yukle()

    def _tum_onerileri_reddet(self):
        """Tüm bekleyen önerileri reddeder."""
        if not self.seri_id or not self.db_manager:
            return
        oneriler = self.db_manager.onerileri_getir(self.seri_id)
        for o in oneriler:
            self.db_manager.oneri_reddet(o["id"])
        self._onerileri_yukle()

    def _tum_bolumlerden_tara(self):
        """NER motoru ile serinin tüm bölümlerini tarar ve önerilere ekler."""
        if not self.seri_id or not self.db_manager:
            QMessageBox.warning(self, "Seri Seçilmedi",
                                "Lütfen önce sol panelden bir seri seçin.")
            return

        bolumler = self.db_manager.serinin_bolumlerini_getir(self.seri_id)
        if not bolumler:
            QMessageBox.information(self, "Bölüm Yok",
                                    "Bu seride taranacak bölüm bulunamadı.")
            return

        # NER motoru ile tara
        mevcut_terimler = self.db_manager.sozluk_terimlerini_getir(self.seri_id, sadece_onaylandi=False)
        engine = StoryDictionaryEngine(mevcut_terimler)

        toplam_auto = 0
        toplam_oneri = 0

        for bolum in bolumler:
            orijinal = bolum.get("orijinal_metin") or ""
            if not orijinal.strip():
                continue
            bolum_no = bolum.get("bolum_no", 0) or 0
            sonuc = engine.analyze_chapter(orijinal, bolum_no=bolum_no, existing_entries=mevcut_terimler)

            # Güven >= 0.80 → öneri olarak ekle (kullanıcı çeviriyi girer)
            for aday in sonuc["auto_save"]:
                self.db_manager.oneri_ekle(
                    seri_id=self.seri_id,
                    orijinal_terim=aday["phrase"],
                    entity_type=aday["entity_type"],
                    confidence=aday["confidence"],
                    occurrences=aday["frequency"],
                    bolum_no=bolum_no,
                )
                toplam_auto += 1

            # Güven 0.50-0.79 → öneri
            for aday in sonuc["suggestions"]:
                self.db_manager.oneri_ekle(
                    seri_id=self.seri_id,
                    orijinal_terim=aday["phrase"],
                    entity_type=aday["entity_type"],
                    confidence=aday["confidence"],
                    occurrences=aday["frequency"],
                    bolum_no=bolum_no,
                )
                toplam_oneri += 1

        if toplam_auto + toplam_oneri == 0:
            QMessageBox.information(self, "Tamamlandı",
                                    "Sözlükte olmayan yeni entity adayı bulunamadı.")
            return

        self._onerileri_yukle()
        # Öneriler sekmesine geç
        self.tab_widget.setCurrentWidget(self.oneri_tab_widget)
        QMessageBox.information(
            self, "Tarama Tamamlandı",
            f"{len(bolumler)} bölüm tarandı.\n"
            f"Yüksek güven: {toplam_auto} öneri\n"
            f"Düşük güven: {toplam_oneri} öneri\n\n"
            "Öneriler sekmesinden onaylayabilir veya reddedebilirsiniz."
        )

    # =========================================================================
    # TERIM EKLE / DÜZENLE / SİL
    # =========================================================================

    def _terim_ekle(self):
        """Yeni terim ekleme diyaloğunu açar."""
        if not self.seri_id:
            QMessageBox.warning(
                self, "Seri Seçilmedi",
                "Lütfen önce sol panelden bir seri seçin."
            )
            return

        diyalog = SozlukGirdisiDialog(parent=self)
        self._diyalog_stili_uygula(diyalog)

        if diyalog.exec() == QDialog.DialogCode.Accepted:
            self.db_manager.sozluk_terimi_ekle(
                seri_id=self.seri_id,
                orijinal_terim=diyalog.sonuc_orijinal,
                cevrilmis_terim=diyalog.sonuc_cevrilmis,
                kategori=diyalog.sonuc_kategori,
                entity_type=KATEGORI_TO_ENTITY_TYPE.get(diyalog.sonuc_kategori, "PERSON"),
                notlar=diyalog.sonuc_notlar,
            )
            self.sozlugu_yukle()

    def _terim_duzenle(self, terim: dict):
        """Mevcut terim düzenleme diyaloğunu açar."""
        diyalog = SozlukGirdisiDialog(parent=self, mevcut_girdi=terim)
        self._diyalog_stili_uygula(diyalog)

        if diyalog.exec() == QDialog.DialogCode.Accepted:
            self.db_manager.sozluk_terimi_guncelle(
                girdi_id=terim["id"],
                orijinal_terim=diyalog.sonuc_orijinal,
                cevrilmis_terim=diyalog.sonuc_cevrilmis,
                kategori=diyalog.sonuc_kategori,
                entity_type=KATEGORI_TO_ENTITY_TYPE.get(diyalog.sonuc_kategori, "PERSON"),
                notlar=diyalog.sonuc_notlar,
            )
            self.sozlugu_yukle()

    def _terim_sil(self, terim: dict):
        """Silme onayı alır, onaylanırsa terimi siler."""
        orijinal = terim.get("orijinal_terim", "")

        onay = QMessageBox(self)
        onay.setWindowTitle("Terimi Sil")
        onay.setIcon(QMessageBox.Icon.Question)
        onay.setText(
            f"'{orijinal}' terimi silinecek. Devam etmek istiyor musunuz?"
        )
        evet_btn = onay.addButton("Evet", QMessageBox.ButtonRole.DestructiveRole)
        hayir_btn = onay.addButton("Hayır", QMessageBox.ButtonRole.RejectRole)
        onay.setDefaultButton(hayir_btn)
        self._diyalog_stili_uygula(onay)

        onay.exec()

        if onay.clickedButton() == evet_btn:
            self.db_manager.sozluk_terimi_sil(terim["id"])
            self.sozlugu_yukle()

    # =========================================================================
    # CSV İÇE / DIŞA AKTARMA
    # =========================================================================

    def _csv_ice_aktar(self):
        """
        CSV dosyasından terim listesini içe aktarır.
        Beklenen sütun sırası (başlık satırı atlanır):
          orijinal_terim, cevrilmis_terim, kategori, notlar
        """
        if not self.seri_id:
            QMessageBox.warning(
                self, "Seri Seçilmedi",
                "Lütfen önce sol panelden bir seri seçin."
            )
            return

        dosya_yolu, _ = QFileDialog.getOpenFileName(
            self,
            "CSV Dosyası Seç",
            "",
            "CSV Dosyaları (*.csv);;Tüm Dosyalar (*)"
        )
        if not dosya_yolu:
            return  # Kullanıcı iptal etti

        basarili = 0
        atlanan  = 0

        # Desteklenen encoding'ler sırayla denenir (Türkçe için cp1254 öncelikli)
        satirlar = None
        for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
            try:
                with open(dosya_yolu, newline="", encoding=enc) as f:
                    satirlar = list(csv.reader(f))
                break   # başarılıysa döngüden çık
            except UnicodeDecodeError:
                continue
            except Exception as hata:
                QMessageBox.critical(
                    self, "Okuma Hatası",
                    f"CSV dosyası açılamadı:\n{hata}"
                )
                return

        if satirlar is None:
            QMessageBox.critical(
                self, "Encoding Hatası",
                "CSV dosyası desteklenen hiçbir karakter kodlamasıyla açılamadı.\n"
                "Lütfen dosyayı UTF-8 formatında kaydedin."
            )
            return

        if not satirlar:
            QMessageBox.warning(self, "Boş Dosya", "CSV dosyası boş.")
            return

        # Başlık satırı kontrolü: ilk satırda "orijinal" veya "orijinal_terim" varsa atla
        baslangic = 0
        ilk_satir = [s.strip().lower() for s in satirlar[0]]
        if "orijinal_terim" in ilk_satir or "orijinal" in ilk_satir:
            baslangic = 1

        try:
            for satir in satirlar[baslangic:]:
                # Yeterli sütun yok
                if len(satir) < 2:
                    atlanan += 1
                    continue

                orijinal  = satir[0].strip()
                cevrilmis = satir[1].strip()

                if not orijinal or not cevrilmis:
                    atlanan += 1
                    continue

                # Kategori ve notlar isteğe bağlı
                kategori = satir[2].strip().lower() if len(satir) > 2 else "diger"
                notlar   = satir[3].strip() or None  if len(satir) > 3 else None

                if kategori not in KATEGORI_KODLAR:
                    kategori = "diger"

                # sozluk_terimi_ekle duplicate kontrolü içeriyor
                sonuc = self.db_manager.sozluk_terimi_ekle(
                    seri_id=self.seri_id,
                    orijinal_terim=orijinal,
                    cevrilmis_terim=cevrilmis,
                    kategori=kategori,
                    notlar=notlar,
                )
                if sonuc:
                    basarili += 1
                else:
                    atlanan += 1

        except Exception as hata:
            QMessageBox.critical(
                self, "İşlem Hatası",
                f"CSV içe aktarma sırasında hata oluştu:\n{hata}"
            )
            return

        self.sozlugu_yukle()

        QMessageBox.information(
            self,
            "İçe Aktarma Tamamlandı",
            f"Başarıyla içe aktarılan: {basarili} terim\n"
            f"Atlanan: {atlanan} satır"
        )

    def _csv_disa_aktar(self):
        """Serinin tüm sözlüğünü CSV dosyasına yazar."""
        if not self.seri_id:
            QMessageBox.warning(
                self, "Seri Seçilmedi",
                "Lütfen önce sol panelden bir seri seçin."
            )
            return

        if not self._terimler:
            QMessageBox.information(
                self, "Boş Sözlük",
                "Dışa aktarılacak terim bulunamadı."
            )
            return

        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self,
            "CSV Olarak Kaydet",
            "sozluk_disa_aktar.csv",
            "CSV Dosyaları (*.csv);;Tüm Dosyalar (*)"
        )
        if not dosya_yolu:
            return  # Kullanıcı iptal etti

        try:
            with open(dosya_yolu, "w", newline="", encoding="utf-8-sig") as f:
                yazar = csv.writer(f)
                # Başlık satırı — genişletilmiş story-consistency formatı
                yazar.writerow([
                    "orijinal_terim", "cevrilmis_terim", "kategori",
                    "entity_type", "confidence", "occurrences",
                    "locked", "notlar"
                ])
                for terim in self._terimler:
                    yazar.writerow([
                        terim.get("orijinal_terim",  ""),
                        terim.get("cevrilmis_terim", ""),
                        terim.get("kategori",        "diger"),
                        terim.get("entity_type",     "PERSON"),
                        f"{terim.get('confidence', 1.0) or 1.0:.2f}",
                        terim.get("occurrences",     1),
                        "1" if terim.get("locked") else "0",
                        terim.get("notlar",          "") or "",
                    ])

            QMessageBox.information(
                self,
                "Dışa Aktarma Tamamlandı",
                f"Dışa aktarma tamamlandı: {len(self._terimler)} terim kaydedildi.\n"
                f"Konum: {dosya_yolu}"
            )

        except Exception as hata:
            QMessageBox.critical(
                self, "Yazma Hatası",
                f"CSV dosyası yazılamadı:\n{hata}"
            )

    # =========================================================================
    # INLINE DÜZENLEME
    # =========================================================================

    def _inline_duzenleme_kaydedildi(self, item):
        """
        Tablo hücresine çift tıklanıp düzenlendiğinde çağrılır.
        Değişikliği veritabanına kaydeder.
        İşlemler sütunu (5) ve No sütunu (0) düzenlenemez.
        """
        satir = item.row()
        sutun = item.column()

        # Düzenlenemez sütunlar
        if sutun in (SUTUN_NO, SUTUN_ISLEMLER):
            return

        # Terimin ID'sini bul
        no_item = self.tablo.item(satir, SUTUN_NO)
        if not no_item:
            return
        try:
            terim_id = int(no_item.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            return

        # Mevcut satır verilerini oku
        def _metin(s):
            it = self.tablo.item(satir, s)
            return it.text().strip() if it else ""

        orijinal  = _metin(SUTUN_ORIJINAL)
        cevrilmis = _metin(SUTUN_CEVRILMIS)
        notlar    = _metin(SUTUN_NOTLAR) or None

        # Kategori ve entity_type: hücrede sadece rozet widget'ı var, metin item'ı yok.
        # Mevcut değerleri _terimler listesinden terim_id ile bul.
        kategori    = "diger"
        entity_type = None
        for t in self._terimler:
            if t.get("id") == terim_id:
                kategori    = t.get("kategori", "diger")
                entity_type = t.get("entity_type")
                break
        if kategori not in KATEGORI_KODLAR:
            kategori = "diger"

        if not orijinal or not cevrilmis:
            return

        # Sinyali geçici olarak kapat; DB kaydı sırasında yeniden tetikleme önlenir
        self.tablo.blockSignals(True)
        try:
            # Kullanıcı inline düzenleme → kilitli olarak kaydet
            self.db_manager.sozluk_girisi_guncelle(
                girdi_id=terim_id,
                orijinal_terim=orijinal,
                cevrilmis_terim=cevrilmis,
                kategori=kategori,
                entity_type=entity_type,
                notlar=notlar,
            )
        finally:
            self.tablo.blockSignals(False)

    # =========================================================================
    # YARDIMCI METODLAR
    # =========================================================================

    def _sayaci_guncelle(self, sayi: int):
        """Alt sağdaki terim sayacı etiketini günceller."""
        self.sayac_label.setText(f"Toplam: {sayi} terim")

    def _bos_durumu_guncelle(self):
        """
        Terim varsa tabloyu, yoksa boş durum etiketini gösterir.
        """
        bos = len(self._terimler) == 0
        self.tablo.setVisible(not bos)
        self.bos_durum_label.setVisible(bos)

    def _diyalog_stili_uygula(self, diyalog: QDialog):
        """Tüm diyaloglara tutarlı koyu tema stilini uygular."""
        # Global tema QApplication seviyesinde uygulandığından
        # ekstra override gerekmez; yalnızca özel durumlar için yer tutucu.
        pass

    def _birincil_buton_stili(self) -> str:
        return """
            QPushButton {
                background-color: #9b59d0;
                color: #0f0a1a;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #b06ad9; }
            QPushButton:disabled { background-color: #2d1a40; color: #6b5a7a; }
        """

    def _ikincil_buton_stili(self) -> str:
        return """
            QPushButton {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #9b59d0; }
            QPushButton:disabled { color: #6b5a7a; border-color: #2d1a40; }
        """


# =============================================================================
# HIZLI TEST — python glossary_widget.py ile çalıştırılabilir
# =============================================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from database import DatabaseManager

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #0f0a1a;
            color: #e8e0f0;
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }
    """)

    db = DatabaseManager()

    # Test verisi: seri yoksa oluştur
    seriler = db.tum_serileri_getir()
    if not seriler:
        seri_id = db.seri_olustur(
            baslik="Test Serisi",
            kaynak_dil="Japonca",
            hedef_dil="Turkce",
        )
    else:
        seri_id = seriler[0]["id"]

    # Örnek terimler ekle (henüz yoksa)
    mevcut = db.sozluk_terimlerini_getir(seri_id)
    if not mevcut:
        db.sozluk_terimi_ekle(seri_id, "Kirito",    "Kirito",   "karakter", "Ana karakter")
        db.sozluk_terimi_ekle(seri_id, "Asuna",     "Asuna",    "karakter", "Yan karakter")
        db.sozluk_terimi_ekle(seri_id, "Aincrad",   "Aincrad",  "mekan",    "Kayan kale")
        db.sozluk_terimi_ekle(seri_id, "Sistemli",  "Sistemli", "sistem",   "Oyun sistemi")
        db.sozluk_terimi_ekle(seri_id, "Kilic Bec", "Kilic",    "beceri",   "Kilic becerisi")

    widget = GlossaryWidget(seri_id=seri_id, db_manager=db)
    widget.setWindowTitle("Sozluk Widget - Test")
    widget.resize(900, 550)
    widget.show()

    sys.exit(app.exec())