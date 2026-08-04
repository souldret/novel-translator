"""
Novel Çevirmen - Ana Pencere
Uygulamanın tüm arayüz bileşenlerini barındıran ana modül.
"""

import sys
import os
import re
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QLineEdit, QTextEdit, QComboBox, QDialog,
    QFormLayout, QMessageBox, QMenu, QFrame,
    QAbstractItemView, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QAction

# Veritabanı ve çeviri modülleri
from database import DatabaseManager, DB_YOLU
from translator import TranslatorFactory
from icons import pixmap, set_icon

logger = logging.getLogger("novel_cevirmen.main_window")

# Yeni modüller
try:
    from wizards import SeriSihirbazi as _SeriSihirbazi_Dis
    _WIZARDS_MEVCUT = True
except ImportError:
    _WIZARDS_MEVCUT = False

try:
    from importers import txt_bolum_ice_aktar, epub_ice_aktar, txt_disa_aktar, epub_disa_aktar
    _IMPORTERS_MEVCUT = True
except ImportError:
    _IMPORTERS_MEVCUT = False

try:
    import plugin_loader as _plugin_loader
    _PLUGIN_LOADER_MEVCUT = True
except ImportError:
    _PLUGIN_LOADER_MEVCUT = False

# ---------------------------------------------------------------------------
# GERÇEK WIDGET IMPORTLARI
# Her biri try/except ile korunur; dosya henüz yoksa yer tutucu devreye girer.
# ---------------------------------------------------------------------------

try:
    from chapters_widget import ChaptersWidget
except ImportError:
    class ChaptersWidget(QWidget):
        """chapters_widget.py oluşturulana kadar geçici yer tutucu."""
        def __init__(self, db_manager=None, translator=None, seri_id=None, parent=None):
            super().__init__(parent)
            self.db_manager = db_manager
            self.translator = translator
            self._seri_id = seri_id
            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ikon = QLabel()
            ikon.setPixmap(pixmap("book", size=48))
            ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi = QLabel("Bölümler bileşeni henüz yüklenmedi.\n(chapters_widget.py)")
            bilgi.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi.setObjectName("placeholderLabel")
            layout.addWidget(ikon)
            layout.addWidget(bilgi)

        def set_seri(self, seri_id: int):
            self._seri_id = seri_id

        # Geriye dönük uyumluluk için alias
        def seri_yukle(self, seri_id: int):
            self.set_seri(seri_id)

        def set_translator(self, translator):
            self.translator = translator


try:
    from glossary_widget import GlossaryWidget
except ImportError:
    class GlossaryWidget(QWidget):
        """glossary_widget.py oluşturulana kadar geçici yer tutucu."""
        def __init__(self, db_manager=None, seri_id=None, parent=None):
            super().__init__(parent)
            self.db_manager = db_manager
            self._seri_id = seri_id
            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ikon = QLabel()
            ikon.setPixmap(pixmap("books", size=56))
            ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi = QLabel("Sözlük bileşeni henüz yüklenmedi.\n(glossary_widget.py)")
            bilgi.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi.setObjectName("placeholderLabel")
            layout.addWidget(ikon)
            layout.addWidget(bilgi)

        def set_seri(self, seri_id: int):
            self._seri_id = seri_id

        def seri_yukle(self, seri_id: int):
            self.set_seri(seri_id)


try:
    from settings_widget import SettingsWidget
except ImportError:
    class SettingsWidget(QWidget):
        """settings_widget.py oluşturulana kadar geçici yer tutucu."""
        aktif_saglayici_degisti = pyqtSignal(str, str, str, object)

        def __init__(self, db_manager=None, translator_factory_class=None, parent=None):
            super().__init__(parent)
            self.db_manager = db_manager
            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ikon = QLabel()
            ikon.setPixmap(pixmap("settings", size=48))
            ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi = QLabel("Ayarlar bileşeni henüz yüklenmedi.\n(settings_widget.py)")
            bilgi.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bilgi.setObjectName("placeholderLabel")
            layout.addWidget(ikon)
            layout.addWidget(bilgi)


# =============================================================================
# YENİ / DÜZENLE SERİ DİYALOĞU
# =============================================================================

class SeriDiyalogu(QDialog):
    """
    Yeni seri oluşturma ve mevcut seri düzenleme için ortak diyalog.
    duzenle_modu=True ise başlık ve buton metni değişir.
    """

    KAYNAK_DILLER = [
        "Çince (Basitleştirilmiş)",
        "Çince (Geleneksel)",
        "Japonca",
        "Korece",
        "İngilizce",
    ]

    HEDEF_DILLER = [
        "Türkçe",
        "İngilizce",
        "Almanca",
        "Fransızca",
        "İspanyolca",
        "Arapça",
        "Portekizce",
    ]

    def __init__(self, parent=None, mevcut_seri: dict = None):
        super().__init__(parent)
        self.mevcut_seri  = mevcut_seri
        self.duzenle_modu = mevcut_seri is not None

        self.setWindowTitle("Seriyi Düzenle" if self.duzenle_modu else "Yeni Seri Ekle")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._arayuz_olustur()

        if self.duzenle_modu:
            self._alanlari_doldur()

    def _arayuz_olustur(self):
        ana_layout = QVBoxLayout(self)
        ana_layout.setSpacing(16)
        ana_layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        baslik = QLabel("Seriyi Düzenle" if self.duzenle_modu else "Yeni Seri Ekle")
        baslik.setObjectName("baslikLabel")
        ana_layout.addWidget(baslik)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.seri_adi_input = QLineEdit()
        self.seri_adi_input.setPlaceholderText("Örnek: Sword Art Online")
        form.addRow("Seri Adı *", self.seri_adi_input)

        self.kaynak_dil_combo = QComboBox()
        self.kaynak_dil_combo.addItems(self.KAYNAK_DILLER)
        form.addRow("Kaynak Dil", self.kaynak_dil_combo)

        self.hedef_dil_combo = QComboBox()
        self.hedef_dil_combo.addItems(self.HEDEF_DILLER)
        form.addRow("Hedef Dil", self.hedef_dil_combo)

        self.aciklama_input = QTextEdit()
        self.aciklama_input.setPlaceholderText("İsteğe bağlı açıklama...")
        self.aciklama_input.setFixedHeight(80)
        form.addRow("Açıklama", self.aciklama_input)

        ana_layout.addLayout(form)

        # Hata etiketi
        self.hata_label = QLabel("")
        self.hata_label.setObjectName("hataLabel")
        self.hata_label.setVisible(False)
        ana_layout.addWidget(self.hata_label)

        # Butonlar
        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        buton_layout.addStretch()

        self.iptal_btn = QPushButton("İptal")
        self.iptal_btn.setObjectName("ikincilButon")
        self.iptal_btn.setFixedWidth(100)
        self.iptal_btn.clicked.connect(self.reject)

        self.kaydet_btn = QPushButton("Kaydet" if self.duzenle_modu else "Oluştur")
        self.kaydet_btn.setFixedWidth(120)
        self.kaydet_btn.clicked.connect(self._kaydet)
        self.kaydet_btn.setDefault(True)

        buton_layout.addWidget(self.iptal_btn)
        buton_layout.addWidget(self.kaydet_btn)
        ana_layout.addLayout(buton_layout)

    def _alanlari_doldur(self):
        """Düzenleme modunda mevcut seri verilerini alanlara yazar."""
        s = self.mevcut_seri
        self.seri_adi_input.setText(s.get("baslik", ""))

        kaynak = s.get("kaynak_dil", "")
        idx = self.kaynak_dil_combo.findText(kaynak)
        if idx >= 0:
            self.kaynak_dil_combo.setCurrentIndex(idx)

        hedef = s.get("hedef_dil", "")
        idx = self.hedef_dil_combo.findText(hedef)
        if idx >= 0:
            self.hedef_dil_combo.setCurrentIndex(idx)

        self.aciklama_input.setText(s.get("aciklama", "") or "")

    def _kaydet(self):
        """Formu doğrular; geçerliyse veriyi depolar ve diyaloğu kapatır."""
        ad = self.seri_adi_input.text().strip()
        if not ad:
            self.hata_label.setText("Seri adı boş bırakılamaz.")
            self.hata_label.setVisible(True)
            self.seri_adi_input.setFocus()
            return

        self.hata_label.setVisible(False)
        self.sonuc_baslik     = ad
        self.sonuc_kaynak_dil = self.kaynak_dil_combo.currentText()
        self.sonuc_hedef_dil  = self.hedef_dil_combo.currentText()
        self.sonuc_aciklama   = self.aciklama_input.toPlainText().strip() or None
        self.accept()


# =============================================================================
# AYARLAR PENCERESİ
# =============================================================================

class AyarlarPenceresi(QDialog):
    """
    Araçlar → Ayarlar menüsünden açılan ayarlar diyaloğu.
    İçinde SettingsWidget barındırır.

    DÜZELTME: SettingsWidget(db_manager, translator_factory_class, parent)
    imzasına uygun şekilde parent=self olarak açıkça geçirilir.
    """

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.resize(800, 600)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # translator_factory_class=None → SettingsWidget kendi içinde import eder
        # parent=self olarak açıkça geçiriliyor (önceki hatada positional olarak
        # self ana pencere sınıfına gidiyordu)
        self.settings_widget = SettingsWidget(
            db_manager=db_manager,
            translator_factory_class=None,
            parent=self,
        )
        layout.addWidget(self.settings_widget)


# =============================================================================
# SERİ LİSTESİ ÖĞE WİDGET'I
# =============================================================================

class SeriListeOgesi(QWidget):
    """
    Kenar çubuğu seri listesindeki tek bir seriyi gösteren özel widget.
    Üst satır: seri adı (kalın)
    Orta satır: kaynak → hedef dil
    Alt satır: bölüm sayısı
    """

    def __init__(self, seri: dict, bolum_sayisi: int = 0, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 6, 4, 6)

        baslik_label = QLabel(seri.get("baslik", ""))
        baslik_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        baslik_label.setStyleSheet("color: #e8e0f0;")

        kaynak = seri.get("kaynak_dil", "")
        hedef  = seri.get("hedef_dil", "")
        dil_label = QLabel(f"{kaynak}  \u2192  {hedef}")
        dil_label.setStyleSheet("color: #6b5a7a; font-size: 11px;")

        bolum_label = QLabel(f"{bolum_sayisi} bölüm")
        bolum_label.setStyleSheet("color: #5a4a6a; font-size: 10px;")

        layout.addWidget(baslik_label)
        layout.addWidget(dil_label)
        layout.addWidget(bolum_label)


# =============================================================================
# HAKKINDA DİYALOĞU
# =============================================================================

class HakkindaDiyalogu(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novel Çevirmen Hakkında")
        self.setFixedSize(420, 300)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ikon = QLabel()
        ikon.setPixmap(pixmap("book", size=48))
        ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ad_label = QLabel("Novel Çevirmen")
        ad_label.setObjectName("baslikLabel")
        ad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ad_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))

        versiyon_label = QLabel("Versiyon 1.0.0")
        versiyon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        versiyon_label.setStyleSheet("color: #6b5a7a;")

        aciklama_label = QLabel(
            "PyQt6 ve yapay zeka destekli novel çeviri uygulaması."
        )
        aciklama_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        aciklama_label.setWordWrap(True)
        aciklama_label.setStyleSheet("color: #a0f0b0;")

        kutup_label = QLabel(
            "Kullanılan kütüphaneler: PyQt6 · openai · anthropic · google-generativeai"
        )
        kutup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kutup_label.setWordWrap(True)
        kutup_label.setStyleSheet("color: #6b5a7a; font-size: 11px;")

        kapat_btn = QPushButton("Kapat")
        kapat_btn.setFixedWidth(100)
        kapat_btn.clicked.connect(self.accept)

        kapat_layout = QHBoxLayout()
        kapat_layout.addStretch()
        kapat_layout.addWidget(kapat_btn)
        kapat_layout.addStretch()

        layout.addWidget(ikon)
        layout.addWidget(ad_label)
        layout.addWidget(versiyon_label)
        layout.addWidget(aciklama_label)
        layout.addWidget(kutup_label)
        layout.addStretch()
        layout.addLayout(kapat_layout)


# =============================================================================
# ANA PENCERE
# =============================================================================

class MainWindow(QMainWindow):
    """
    Novel Çevirmen uygulamasının ana penceresi.
    Sol kenar çubuğu (seri listesi) + sağ içerik alanı (sekmeler) düzeni.
    """

    def __init__(self):
        super().__init__()
        self.aktif_seri_id:    int | None         = None
        self.aktif_translator                     = None
        self.chapters_widget:  ChaptersWidget | None = None
        self.glossary_widget:  GlossaryWidget | None = None
        self._sekme_widget:    QTabWidget | None  = None
        self.db = DatabaseManager()
        self._ayarlar = QSettings("NovelCevirmen", "NovelCevirmen")
        self._acik_tema_aktif = self._ayarlar.value("tema/acik", False, type=bool)
        self.setWindowTitle("Novel Cevirmen")
        self.setMinimumSize(1280, 800)
        # Global tema main.py'de QApplication'a uygulanmıştır
        self._menubar_olustur()
        self._statusbar_olustur()
        self._merkez_duzen_olustur()
        # Otomatik yedekleme zamanlayıcısı (30 dakikada bir)
        self._yedekleme_timer = QTimer(self)
        self._yedekleme_timer.setInterval(30 * 60 * 1000)  # 30 dakika
        self._yedekleme_timer.timeout.connect(self._otomatik_yedekle)
        self._yedekleme_timer.start()
        self.showMaximized()
        self.statusBar().showMessage("Hazır", 3000)
        QTimer.singleShot(0, self._baslangic_yukle)
        # Tema başlangıçta uygula
        if self._acik_tema_aktif:
            QTimer.singleShot(50, lambda: self._tema_uygula(acik=True))

    # =========================================================================
    # DURUM ÇUBUĞU
    # =========================================================================

    def _statusbar_olustur(self):
        """Pencere altındaki durum çubuğunu yapılandırır."""
        sb = self.statusBar()
        sb.setStyleSheet("font-size: 11px;")

    def _ai_durum_label_ayarla(self, metin: str, durum: str):
        """
        AI durum etiketini günceller. durum: 'pasif' | 'uyari' | 'hata' | 'basarili'.
        Property tabanlı QSS kullandığından style yenilenmelidir.
        """
        self.ai_durum_label.setText(metin)
        self.ai_durum_label.setProperty("durum", durum)
        # Style'ı zorla yenile (property değişikliğini QSS'e bildir)
        stil = self.ai_durum_label.style()
        if stil is not None:
            stil.unpolish(self.ai_durum_label)
            stil.polish(self.ai_durum_label)

    # =========================================================================
    # BAŞLANGIÇ YÜKLEMESİ (ertelenmiş)
    # =========================================================================

    def _baslangic_yukle(self):
        """
        Pencere göründükten sonra çalışır.
        Once AI ayarlarini yukler, ardindan seri listesini doldurur.
        """
        # Eklentileri yükle
        if _PLUGIN_LOADER_MEVCUT:
            try:
                yuklenenler = _plugin_loader.load_plugins()
                if yuklenenler:
                    logger.info(f"Yüklenen eklentiler: {yuklenenler}")
            except Exception as hata:
                logger.warning(f"Eklenti yükleme hatası: {hata}")

        self._ai_ayarlarini_yukle()
        self._serileri_yukle()

        # Son aktif seriyi geri yükle
        son_seri = self._ayarlar.value("son_seri_id", None)
        if son_seri and self.aktif_seri_id is None:
            try:
                son_seri_int = int(son_seri)
                self._seri_sec_by_id(son_seri_int)
            except (ValueError, TypeError):
                pass

    def _otomatik_yedekle(self):
        """30 dakikada bir otomatik veritabanı yedeği alır."""
        try:
            yedek = self.db.yedekle()
            if yedek:
                self.statusBar().showMessage(f"Otomatik yedekleme: {yedek}", 4000)
                logger.info(f"Otomatik yedekleme tamamlandı: {yedek}")
        except Exception as hata:
            logger.error(f"Otomatik yedekleme başarısız: {hata}")

    # =========================================================================
    # MENÜ ÇUBUĞU
    # =========================================================================

    def _menubar_olustur(self):
        menubar = self.menuBar()

        # Dosya
        dosya_menu = menubar.addMenu("Dosya")

        yeni_seri_action = QAction("Yeni Seri", self)
        yeni_seri_action.setShortcut("Ctrl+N")
        yeni_seri_action.triggered.connect(self._yeni_seri_diyalogu_ac)
        dosya_menu.addAction(yeni_seri_action)

        yeni_seri_sihirbaz_action = QAction("Yeni Seri (Sihirbaz)...", self)
        yeni_seri_sihirbaz_action.setShortcut("Ctrl+Shift+N")
        yeni_seri_sihirbaz_action.triggered.connect(self._seri_sihirbazi_ac)
        dosya_menu.addAction(yeni_seri_sihirbaz_action)

        dosya_menu.addSeparator()

        # TXT içe aktar
        txt_aktar_action = QAction("TXT İçe Aktar...", self)
        txt_aktar_action.setShortcut("Ctrl+I")
        txt_aktar_action.triggered.connect(self._txt_ice_aktar)
        dosya_menu.addAction(txt_aktar_action)

        # EPUB içe aktar
        epub_ice_action = QAction("EPUB İçe Aktar...", self)
        epub_ice_action.triggered.connect(self._epub_ice_aktar)
        dosya_menu.addAction(epub_ice_action)

        dosya_menu.addSeparator()

        # EPUB dışa aktar
        epub_disa_action = QAction("EPUB Olarak Dışa Aktar...", self)
        epub_disa_action.setShortcut("Ctrl+E")
        epub_disa_action.triggered.connect(self._epub_disa_aktar)
        dosya_menu.addAction(epub_disa_action)

        # TXT dışa aktar
        txt_disa_action = QAction("TXT Olarak Dışa Aktar...", self)
        txt_disa_action.triggered.connect(self._txt_disa_aktar)
        dosya_menu.addAction(txt_disa_action)

        dosya_menu.addSeparator()

        cikis_action = QAction("Çıkış", self)
        cikis_action.setShortcut("Ctrl+Q")
        cikis_action.triggered.connect(self.close)
        dosya_menu.addAction(cikis_action)

        # Araçlar
        araclar_menu = menubar.addMenu("Araçlar")

        ayarlar_action = QAction("Ayarlar", self)
        ayarlar_action.setShortcut("Ctrl+,")
        ayarlar_action.triggered.connect(self._ayarlar_ac)
        araclar_menu.addAction(ayarlar_action)

        # Tema geçişi
        self._tema_action = QAction("[Tema] Acik Temaya Gec", self)
        self._tema_action.setShortcut("Ctrl+T")
        self._tema_action.triggered.connect(self._tema_degistir)
        araclar_menu.addAction(self._tema_action)

        # Önbelleği temizle
        onbellek_action = QAction("Çeviri Önbelleğini Temizle", self)
        onbellek_action.triggered.connect(self._onbellegi_temizle)
        araclar_menu.addAction(onbellek_action)

        araclar_menu.addSeparator()

        db_konum_action = QAction("Veritabanı Konumu", self)
        db_konum_action.triggered.connect(self._db_konumunu_goster)
        araclar_menu.addAction(db_konum_action)

        araclar_menu.addSeparator()
        eklentiler_action = QAction("Eklentileri Yeniden Yükle", self)
        eklentiler_action.triggered.connect(self._eklentileri_yukle)
        araclar_menu.addAction(eklentiler_action)

        # Yardım
        yardim_menu = menubar.addMenu("Yardım")

        kisayol_action = QAction("Kısayollar", self)
        kisayol_action.setShortcut("F1")
        kisayol_action.triggered.connect(self._kisayollari_goster)
        yardim_menu.addAction(kisayol_action)

        hakkinda_action = QAction("Hakkında", self)
        hakkinda_action.triggered.connect(self._hakkinda_ac)
        yardim_menu.addAction(hakkinda_action)

    # =========================================================================
    # MERKEZ DÜZEN
    # =========================================================================

    def _merkez_duzen_olustur(self):
        self.bolucu = QSplitter(Qt.Orientation.Horizontal)
        self.bolucu.setHandleWidth(1)
        self.setCentralWidget(self.bolucu)

        self.sol_panel = self._sol_panel_olustur()
        self.bolucu.addWidget(self.sol_panel)

        # Sağ alan — QWidget kapsayıcı, içi dinamik
        self.sag_alan = QWidget()
        self.sag_alan_layout = QVBoxLayout(self.sag_alan)
        self.sag_alan_layout.setContentsMargins(0, 0, 0, 0)
        self._bos_durum_goster()
        self.bolucu.addWidget(self.sag_alan)

        self.bolucu.setSizes([280, 1000])
        self.bolucu.setStretchFactor(0, 0)
        self.bolucu.setStretchFactor(1, 1)

    # =========================================================================
    # SOL PANEL
    # =========================================================================

    def _sol_panel_olustur(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("solPanel")
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo / başlık alanı ───────────────────────────────────────────
        logo_alan = QWidget()
        logo_alan.setStyleSheet("background-color: #0a0612;")
        logo_layout = QVBoxLayout(logo_alan)
        logo_layout.setContentsMargins(16, 16, 16, 14)
        logo_layout.setSpacing(3)

        baslik_label = QLabel("Novel Çevirmen")
        baslik_label.setObjectName("baslikLabel")
        baslik_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        baslik_label.setStyleSheet("color: #dcc0f0; background: transparent; font-size: 15px;")

        alt_baslik_label = QLabel("Çeviri Yönetim Sistemi")
        alt_baslik_label.setObjectName("altBaslikLabel")
        alt_baslik_label.setStyleSheet("color: #6b5a7a; font-size: 11px; background: transparent;")

        logo_layout.addWidget(baslik_label)
        logo_layout.addWidget(alt_baslik_label)
        layout.addWidget(logo_alan)

        layout.addWidget(self._ayirici_olustur())

        # ── Yeni seri butonu ──────────────────────────────────────────────
        buton_alan = QWidget()
        buton_alan.setStyleSheet("background-color: #0a0612;")
        buton_layout = QVBoxLayout(buton_alan)
        buton_layout.setContentsMargins(12, 10, 12, 10)

        self.yeni_seri_btn = QPushButton("  Yeni Seri Ekle")
        self.yeni_seri_btn.setFixedHeight(36)
        self.yeni_seri_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9b59d0, stop:1 #7b3cb5);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b06ad9, stop:1 #8f4cc9); }
            QPushButton:pressed { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b3cb5, stop:1 #6b2ca5); }
        """)
        self.yeni_seri_btn.clicked.connect(self._yeni_seri_diyalogu_ac)
        buton_layout.addWidget(self.yeni_seri_btn)
        layout.addWidget(buton_alan)

        layout.addWidget(self._ayirici_olustur())

        # ── "SERİLER" bölüm başlığı ───────────────────────────────────────
        baslik_alan = QWidget()
        baslik_alan.setStyleSheet("background-color: #0a0612;")
        baslik_ic_layout = QHBoxLayout(baslik_alan)
        baslik_ic_layout.setContentsMargins(16, 8, 16, 4)

        seriler_baslik = QLabel("SERİLER")
        seriler_baslik.setObjectName("bolumBaslikLabel")
        seriler_baslik.setStyleSheet(
            "color: #8b7aaa; font-size: 10px; font-weight: 700;"
            " letter-spacing: 1.5px; background: transparent;"
        )
        baslik_ic_layout.addWidget(seriler_baslik)
        baslik_ic_layout.addStretch()
        layout.addWidget(baslik_alan)

        # ── Seri listesi ──────────────────────────────────────────────────
        self.seriler_listesi = QListWidget()
        self.seriler_listesi.setStyleSheet("QListWidget { background-color: #0a0612; }")
        self.seriler_listesi.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.seriler_listesi.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.seriler_listesi.itemClicked.connect(self._seri_secildi)
        self.seriler_listesi.itemDoubleClicked.connect(self._seri_secildi)
        self.seriler_listesi.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.seriler_listesi.customContextMenuRequested.connect(
            self._baglan_menu_goster
        )
        layout.addWidget(self.seriler_listesi, stretch=1)

        # ── Alt AI durum etiketi ──────────────────────────────────────────
        layout.addWidget(self._ayirici_olustur())

        alt_alan = QWidget()
        alt_alan.setStyleSheet("background-color: #0a0612;")
        alt_layout = QVBoxLayout(alt_alan)
        alt_layout.setContentsMargins(10, 8, 10, 10)
        alt_layout.setSpacing(0)

        self.ai_durum_label = QLabel("Yapay Zeka: Yapılandırılmamış")
        self.ai_durum_label.setObjectName("aiDurumLabel")
        self.ai_durum_label.setWordWrap(True)
        self.ai_durum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Başlangıç durumu: pasif (gri)
        self._ai_durum_label_ayarla("Yapay Zeka: Yapılandırılmamış", "pasif")
        alt_layout.addWidget(self.ai_durum_label)
        layout.addWidget(alt_alan)

        return panel

    def _ayirici_olustur(self) -> QFrame:
        cizgi = QFrame()
        cizgi.setObjectName("ayiriciCizgi")
        cizgi.setFrameShape(QFrame.Shape.HLine)
        cizgi.setFixedHeight(1)
        cizgi.setStyleSheet("background-color: #2d1a40;")
        return cizgi

    # =========================================================================
    # SAĞ İÇERİK ALANI
    # =========================================================================

    def _bos_durum_goster(self):
        """Hiçbir seri seçili değilken karşılama ekranını gösterir."""
        self._sag_alani_temizle()

        kapsayici = QWidget()
        ic_layout = QVBoxLayout(kapsayici)
        ic_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_layout.setSpacing(16)

        ikon = QLabel()
        ikon.setPixmap(pixmap("books", size=56))
        ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mesaj = QLabel(
            "<- Başlamak için bir seri seçin\nveya yeni seri oluşturun"
        )
        mesaj.setObjectName("placeholderLabel")
        mesaj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mesaj.setFont(QFont("Segoe UI", 15))

        ic_layout.addWidget(ikon)
        ic_layout.addWidget(mesaj)
        self.sag_alan_layout.addWidget(kapsayici)

    def _seri_icerigi_goster(self, seri: dict):
        """
        Seçilen serinin sekmeli içeriğini sağ alana yükler.
        Widget'lar ilk kez oluşturulur; zaten oluşturulmuşsa seri_id güncellenir.

        DÜZELTME: Aynı seri tekrar seçildiğinde widget'lar yeniden oluşturulmaz,
        sadece set_seri() çağrılarak veriler yenilenir. Bu hem performans hem de
        kaydedilmemiş değişikliklerin korunması açısından önemlidir.
        """
        seri_id = seri["id"]

        # Zaten bu seri açıksa ve widget'lar mevcutsa sadece veriyi yenile
        if (
            self._sekme_widget is not None
            and self.aktif_seri_id == seri_id
            and self.chapters_widget is not None
            and self.glossary_widget is not None
        ):
            # Bölüm listesini ve sözlüğü yenile (seri_bilgisi formu da güncellenir)
            self.chapters_widget.set_seri(seri_id)
            self.glossary_widget.set_seri(seri_id)
            return

        # Farklı seri veya ilk yükleme: eski widget'ları temizle, yenilerini oluştur
        self._sag_alani_temizle()

        self._sekme_widget = QTabWidget()
        self._sekme_widget.setDocumentMode(True)

        # Bölümler sekmesi
        self.chapters_widget = ChaptersWidget(
            db_manager=self.db,
            translator=self.aktif_translator,
            parent=self,
        )
        self.chapters_widget.set_seri(seri_id)
        self._sekme_widget.addTab(self.chapters_widget, "Bölümler")

        # Sözlük sekmesi
        self.glossary_widget = GlossaryWidget(
            db_manager=self.db,
            parent=self,
        )
        self.glossary_widget.set_seri(seri_id)
        self._sekme_widget.addTab(self.glossary_widget, "Sözlük")

        # Seri Bilgisi sekmesi
        seri_bilgi_widget = self._seri_bilgi_widget_olustur(seri)
        self._sekme_widget.addTab(seri_bilgi_widget, "Seri Bilgisi")

        self.sag_alan_layout.addWidget(self._sekme_widget)

    # Dil seçenekleri — SeriDiyalogu ile aynı listeler
    _KAYNAK_DILLER = [
        "Çince (Basitleştirilmiş)",
        "Çince (Geleneksel)",
        "Japonca",
        "Korece",
        "İngilizce",
    ]
    _HEDEF_DILLER = [
        "Türkçe",
        "İngilizce",
        "Almanca",
        "Fransızca",
        "İspanyolca",
        "Arapça",
        "Portekizce",
    ]

    def _seri_bilgi_widget_olustur(self, seri: dict) -> QWidget:
        """Seri bilgilerini düzenlenebilir form olarak gösteren widget."""
        kapsayici = QWidget()
        ana_layout = QVBoxLayout(kapsayici)
        ana_layout.setContentsMargins(40, 28, 40, 28)
        ana_layout.setSpacing(20)
        ana_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Başlık satırı
        baslik = QLabel("Seri Bilgileri")
        baslik.setObjectName("baslikLabel")
        baslik.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        ana_layout.addWidget(baslik)

        # İnce ayırıcı
        ayirici = QFrame()
        ayirici.setObjectName("ayiriciCizgi")
        ayirici.setFrameShape(QFrame.Shape.HLine)
        ayirici.setFixedHeight(1)
        ana_layout.addWidget(ayirici)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        # Seri adı
        self._bilgi_baslik_input = QLineEdit(seri.get("baslik", ""))
        self._bilgi_baslik_input.setPlaceholderText("Seri adını girin...")
        self._bilgi_baslik_input.setFixedHeight(38)
        form.addRow("Seri Adı:", self._bilgi_baslik_input)

        # Kaynak dil — ComboBox
        self._bilgi_kaynak_combo = QComboBox()
        self._bilgi_kaynak_combo.setFixedHeight(38)
        self._bilgi_kaynak_combo.addItems(self._KAYNAK_DILLER)
        kaynak_mevcut = seri.get("kaynak_dil", "")
        k_idx = self._bilgi_kaynak_combo.findText(kaynak_mevcut)
        if k_idx >= 0:
            self._bilgi_kaynak_combo.setCurrentIndex(k_idx)
        elif kaynak_mevcut:
            # Listede olmayan değer: özel girişe izin ver
            self._bilgi_kaynak_combo.addItem(kaynak_mevcut)
            self._bilgi_kaynak_combo.setCurrentIndex(
                self._bilgi_kaynak_combo.count() - 1
            )
        form.addRow("Kaynak Dil:", self._bilgi_kaynak_combo)

        # Hedef dil — ComboBox
        self._bilgi_hedef_combo = QComboBox()
        self._bilgi_hedef_combo.setFixedHeight(38)
        self._bilgi_hedef_combo.addItems(self._HEDEF_DILLER)
        hedef_mevcut = seri.get("hedef_dil", "")
        h_idx = self._bilgi_hedef_combo.findText(hedef_mevcut)
        if h_idx >= 0:
            self._bilgi_hedef_combo.setCurrentIndex(h_idx)
        elif hedef_mevcut:
            self._bilgi_hedef_combo.addItem(hedef_mevcut)
            self._bilgi_hedef_combo.setCurrentIndex(
                self._bilgi_hedef_combo.count() - 1
            )
        form.addRow("Hedef Dil:", self._bilgi_hedef_combo)

        # Açıklama
        self._bilgi_aciklama_input = QTextEdit()
        self._bilgi_aciklama_input.setPlainText(seri.get("aciklama", "") or "")
        self._bilgi_aciklama_input.setFixedHeight(90)
        self._bilgi_aciklama_input.setPlaceholderText("İsteğe bağlı açıklama...")
        form.addRow("Açıklama:", self._bilgi_aciklama_input)

        # Oluşturma tarihi (salt okunur)
        tarih_input = QLineEdit(seri.get("olusturma_tarihi", ""))
        tarih_input.setReadOnly(True)
        tarih_input.setFixedHeight(38)
        form.addRow("Oluşturma Tarihi:", tarih_input)

        ana_layout.addLayout(form)

        # Kaydet butonu
        kaydet_layout = QHBoxLayout()
        kaydet_layout.addStretch()
        kaydet_btn = QPushButton("  Değişiklikleri Kaydet")
        kaydet_btn.setFixedHeight(36)
        kaydet_btn.setMinimumWidth(200)
        set_icon(kaydet_btn, "save", size=16)
        kaydet_btn.clicked.connect(lambda: self._seri_bilgilerini_kaydet(seri["id"]))
        kaydet_layout.addWidget(kaydet_btn)
        ana_layout.addLayout(kaydet_layout)

        # İçeriği yukarı sabitle; satırların dikeyde dağılmasını önler
        ana_layout.addStretch(1)

        return kapsayici

    def _sag_alani_temizle(self):
        """
        Sağ içerik alanındaki tüm widget'ları kaldırır.

        DÜZELTME: Çalışan bir TranslationWorker varsa bağlantıları kesilir.
        Böylece eski widget deleteLater() sonrasında sinyal almaz.
        """
        # Aktif çeviri worker'ını güvenli şekilde iptal et
        if self.chapters_widget is not None:
            iptal = getattr(self.chapters_widget, "_ceviri_worker_iptal", None)
            if callable(iptal):
                iptal()
            else:
                worker = getattr(self.chapters_widget, "_worker", None)
                if worker is not None and worker.isRunning():
                    try:
                        worker.tamamlandi.disconnect()
                        worker.hata.disconnect()
                    except RuntimeError:
                        pass
                    worker.requestInterruption()

        while self.sag_alan_layout.count():
            oge = self.sag_alan_layout.takeAt(0)
            if oge.widget():
                oge.widget().deleteLater()

        self.chapters_widget  = None
        self.glossary_widget  = None
        self._sekme_widget    = None

    # =========================================================================
    # SERİ LİSTESİ YÖNETİMİ
    # =========================================================================

    def _serileri_yukle(self):
        """
        Veritabanından tüm serileri alır ve kenar çubuğu listesini doldurur.

        DÜZELTME: Aktif bir seri mevcutsa liste yenilendikten sonra o seri
        programatik olarak tekrar seçilir; ancak widget'lar YENİDEN oluşturulmaz
        (set_seri zaten çağrılmış olan widget'lar üzerinden veriyi yeniler).
        Liste boşsa boş durum gösterilir.
        """
        onceki_aktif_id = self.aktif_seri_id

        self.seriler_listesi.clear()

        seriler = self.db.tum_serileri_getir()

        if not seriler:
            # Hiç seri yoksa veya hepsi silindiyse boş durum göster
            self.aktif_seri_id = None
            self._bos_durum_goster()
            return

        bolum_sayilari = self.db.seri_bolum_sayilarini_getir()

        for seri in seriler:
            seri_id      = seri["id"]
            bolum_sayisi = bolum_sayilari.get(seri_id, 0)

            oge_widget = SeriListeOgesi(seri, bolum_sayisi)
            oge = QListWidgetItem(self.seriler_listesi)
            oge.setSizeHint(oge_widget.sizeHint())
            oge.setData(Qt.ItemDataRole.UserRole, seri_id)
            self.seriler_listesi.addItem(oge)
            self.seriler_listesi.setItemWidget(oge, oge_widget)

        # Önceki aktif seriyi tekrar seç (widget'ları yeniden oluşturmadan)
        if onceki_aktif_id is not None:
            self._liste_secimini_geri_yukle(onceki_aktif_id)

    def _liste_secimini_geri_yukle(self, seri_id: int):
        """
        Listedeki belirtilen seri ögesini görsel olarak seçer.
        Sağ paneli YENİDEN OLUŞTURMAZ — zaten açık widget varsa
        set_seri() ile günceller.
        """
        for satir in range(self.seriler_listesi.count()):
            oge = self.seriler_listesi.item(satir)
            if oge and oge.data(Qt.ItemDataRole.UserRole) == seri_id:
                self.seriler_listesi.setCurrentItem(oge)
                # Mevcut widget'lar varsa sadece veriyi yenile
                if self.chapters_widget is not None:
                    self.chapters_widget.set_seri(seri_id)
                if self.glossary_widget is not None:
                    self.glossary_widget.set_seri(seri_id)
                return

    def _seri_sec_by_id(self, seri_id: int):
        """
        Verilen seri_id'ye sahip ögeyi listede seçer ve içeriği yükler.
        Yeni seri eklendiğinde veya başka bir seriye geçildiğinde kullanılır.
        """
        for satir in range(self.seriler_listesi.count()):
            oge = self.seriler_listesi.item(satir)
            if oge and oge.data(Qt.ItemDataRole.UserRole) == seri_id:
                self.seriler_listesi.setCurrentItem(oge)
                self._seri_secildi(oge)
                return

    def _seri_secildi(self, oge: QListWidgetItem):
        """
        Listedeki bir seri ögesine tıklandığında tetiklenir.
        Seri içeriği yüklendikten SONRA aktif_seri_id güncellenir;
        böylece _seri_icerigi_goster içindeki "aynı seri mi?" kontrolü
        doğru çalışır.
        """
        seri_id = oge.data(Qt.ItemDataRole.UserRole)
        if seri_id is None:
            return

        try:
            seri = self.db.seri_getir(seri_id)
        except Exception as hata:
            QMessageBox.critical(
                self, "Veritabanı Hatası",
                f"Seri bilgileri alınamadı:\n{hata}"
            )
            return

        if seri:
            # aktif_seri_id'yi _seri_icerigi_goster'DEN ÖNCE güncelleme —
            # aksi hâlde "zaten aynı seri" koşulu yanlış tetiklenir.
            self._seri_icerigi_goster(seri)
            self.aktif_seri_id = seri_id

    # =========================================================================
    # BAĞLAM MENÜSÜ (sağ tık)
    # =========================================================================

    def _baglan_menu_goster(self, konum):
        oge = self.seriler_listesi.itemAt(konum)
        if not oge:
            return

        seri_id = oge.data(Qt.ItemDataRole.UserRole)
        if not seri_id:
            return

        menu = QMenu(self)

        duzenle_action = QAction("Seriyi Düzenle", self)
        duzenle_action.triggered.connect(lambda: self._seri_duzenle(seri_id))

        sil_action = QAction("Seriyi Sil", self)
        sil_action.triggered.connect(lambda: self._seri_sil(seri_id))

        menu.addAction(duzenle_action)
        menu.addSeparator()
        menu.addAction(sil_action)
        menu.exec(self.seriler_listesi.mapToGlobal(konum))

    # =========================================================================
    # SERİ İŞLEMLERİ
    # =========================================================================

    def _yeni_seri_diyalogu_ac(self):
        diyalog = SeriDiyalogu(parent=self)

        if diyalog.exec() == QDialog.DialogCode.Accepted:
            try:
                yeni_id = self.db.seri_olustur(
                    baslik=diyalog.sonuc_baslik,
                    kaynak_dil=diyalog.sonuc_kaynak_dil,
                    hedef_dil=diyalog.sonuc_hedef_dil,
                    aciklama=diyalog.sonuc_aciklama,
                )
            except Exception as hata:
                QMessageBox.critical(
                    self, "Veritabanı Hatası",
                    f"Seri oluşturulamadı:\n{hata}"
                )
                return

            if yeni_id:
                self._serileri_yukle()
                self._seri_sec_by_id(yeni_id)

    def _seri_duzenle(self, seri_id: int):
        try:
            seri = self.db.seri_getir(seri_id)
        except Exception as hata:
            QMessageBox.critical(
                self, "Veritabanı Hatası",
                f"Seri bilgileri alınamadı:\n{hata}"
            )
            return

        if not seri:
            return

        diyalog = SeriDiyalogu(parent=self, mevcut_seri=seri)

        if diyalog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.seri_guncelle(
                    seri_id=seri_id,
                    baslik=diyalog.sonuc_baslik,
                    kaynak_dil=diyalog.sonuc_kaynak_dil,
                    hedef_dil=diyalog.sonuc_hedef_dil,
                    aciklama=diyalog.sonuc_aciklama,
                )
            except Exception as hata:
                QMessageBox.critical(
                    self, "Veritabanı Hatası",
                    f"Seri güncellenemedi:\n{hata}"
                )
                return

            self._serileri_yukle()
            self._seri_sec_by_id(seri_id)

    def _seri_sil(self, seri_id: int):
        try:
            seri = self.db.seri_getir(seri_id)
        except Exception:
            seri = None

        baslik = seri.get("baslik", "Bu seri") if seri else "Bu seri"

        onay = QMessageBox(self)
        onay.setWindowTitle("Seriyi Sil")
        onay.setIcon(QMessageBox.Icon.Warning)
        onay.setText(
            f"'{baslik}' serisi ve tüm bölümleri ile sözlük girdileri silinecek.\n"
            "Bu işlem geri alınamaz. Devam etmek istiyor musunuz?"
        )
        evet_btn  = onay.addButton("Evet, Sil",   QMessageBox.ButtonRole.DestructiveRole)
        hayir_btn = onay.addButton("Hayır, İptal", QMessageBox.ButtonRole.RejectRole)
        evet_btn.setObjectName("tehlikeliButon")
        hayir_btn.setObjectName("ikincilButon")
        onay.setDefaultButton(hayir_btn)
        onay.exec()

        if onay.clickedButton() == evet_btn:
            # Silmeden önce otomatik yedek al
            self.db.yedekle()
            try:
                self.db.seri_sil(seri_id)
            except Exception as hata:
                QMessageBox.critical(
                    self, "Veritabanı Hatası",
                    f"Seri silinemedi:\n{hata}"
                )
                return

            # Silinen seri aktif seriyse sağ paneli temizle
            if seri_id == self.aktif_seri_id:
                self.aktif_seri_id = None
            self._serileri_yukle()

            # Aktif seri silindiyse boş durum göster
            if self.aktif_seri_id is None:
                self._bos_durum_goster()

    def _seri_bilgilerini_kaydet(self, seri_id: int):
        """
        Seri Bilgisi sekmesindeki form verilerini veritabanına kaydeder.

        DÜZELTME: Kaydet sonrasında _serileri_yukle() çağrılır ve aktif seri
        yeniden seçilir. Widget'lar yeniden oluşturulmaz; _liste_secimini_geri_yukle
        mevcut widget'ları set_seri() ile günceller.
        """
        baslik = self._bilgi_baslik_input.text().strip()
        if not baslik:
            QMessageBox.warning(self, "Geçersiz Giriş", "Seri adı boş bırakılamaz.")
            return

        # Dil değerlerini ComboBox'lardan oku
        kaynak_dil = self._bilgi_kaynak_combo.currentText().strip()
        hedef_dil = self._bilgi_hedef_combo.currentText().strip()

        try:
            self.db.seri_guncelle(
                seri_id=seri_id,
                baslik=baslik,
                kaynak_dil=kaynak_dil,
                hedef_dil=hedef_dil,
                aciklama=self._bilgi_aciklama_input.toPlainText().strip() or None,
            )
        except Exception as hata:
            QMessageBox.critical(
                self, "Veritabanı Hatası",
                f"Seri bilgileri güncellenemedi:\n{hata}"
            )
            return

        # Kenar çubuğu listesini güncelle (yeni başlık görünsün)
        self._serileri_yukle()
        self.statusBar().showMessage("Seri bilgileri kaydedildi.", 3000)

    # =========================================================================
    # AI AYARLARI
    # =========================================================================

    def _ai_ayarlarini_yukle(self):
        """
        Aktif AI ayarını veritabanından okur ve translator nesnesini oluşturur.
        Ayar yoksa Türkçe uyarı gösterir; uygulama yine de çalışmaya devam eder.
        """
        try:
            ayar = self.db.aktif_ai_ayar_getir()
        except Exception:
            ayar = None

        if not ayar:
            uyari = QMessageBox(self)
            uyari.setWindowTitle("Yapay Zeka Sağlayıcısı Yapılandırılmamış")
            uyari.setIcon(QMessageBox.Icon.Warning)
            uyari.setText(
                "Yapay zeka sağlayıcısı yapılandırılmamış.\n"
                "Lütfen Araçlar → Ayarlar menüsünden API anahtarı ekleyin."
            )
            uyari.exec()
            self._ai_durum_label_ayarla("AI yapılandırılmamış", "uyari")
            self.aktif_translator = None
            # ChaptersWidget'a da translator olmadığını bildir
            if self.chapters_widget is not None:
                self.chapters_widget.set_translator(None)
            return

        self._cevirmeni_guncelle(
            saglayici=ayar["saglayici"],
            model=ayar["model_adi"],
            api_key=ayar["api_anahtari"],
            ekstra_konfig=ayar.get("ekstra_konfig"),
        )

    def _cevirmeni_guncelle(
        self,
        saglayici: str,
        model: str,
        api_key: str,
        ekstra_konfig: object,
    ):
        """
        Translator nesnesini oluşturur, kenar çubuğu etiketini günceller
        ve açık olan ChaptersWidget'a yeni translator'ı iletir.

        Bu metot hem _ai_ayarlarini_yukle hem de SettingsWidget sinyali
        tarafından çağrılır.

        DÜZELTME: Sağlayıcı görünen adı TranslatorFactory üzerinden alınır;
        Python sınıf adı (İngilizce) kullanıcıya gösterilmez.
        """
        try:
            ekstra = ekstra_konfig if isinstance(ekstra_konfig, dict) else None
            self.aktif_translator = TranslatorFactory.get_translator(
                saglayici=saglayici,
                api_anahtari=api_key,
                model_adi=model,
                ekstra_konfig=ekstra,
            )
            # Türkçe görünen ad TranslatorFactory'den alınıyor
            goruntu_adi = TranslatorFactory.get_saglayici_display_name(saglayici)
            self._ai_durum_label_ayarla(f"● {goruntu_adi} · {model}", "basarili")

            # Açık bölümler widget'ına yeni translator'ı ilet
            if self.chapters_widget is not None:
                self.chapters_widget.set_translator(self.aktif_translator)

        except Exception as hata:
            self.aktif_translator = None
            self._ai_durum_label_ayarla("Bağlantı hatası", "hata")
            # Çevir butonunu devre dışı bırak
            if self.chapters_widget is not None:
                self.chapters_widget.set_translator(None)
            QMessageBox.critical(
                self, "Translator Hatası",
                f"Yapay zeka bağlantısı kurulamadı:\n{hata}"
            )

    # =========================================================================
    # MENÜ EYLEMLERİ
    # =========================================================================

    def _ayarlar_ac(self):
        """
        Ayarlar penceresini açar.

        DÜZELTME: aktif_saglayici_degisti sinyali _cevirmeni_guncelle slotuna
        doğrudan bağlanır. Önceden var olan ama bağlanmamış guncelle_cevirmen
        metodu kaldırıldı.
        """
        pencere = AyarlarPenceresi(db_manager=self.db, parent=self)

        try:
            pencere.settings_widget.aktif_saglayici_degisti.connect(
                self._cevirmeni_guncelle
            )
        except AttributeError:
            # Placeholder widget sinyali tanımlamıyor olabilir; sessizce geç
            pass

        pencere.exec()

    def _db_konumunu_goster(self):
        QMessageBox.information(
            self,
            "Veritabanı Konumu",
            f"Veritabanı dosyası:\n\n{DB_YOLU}",
        )

    def _hakkinda_ac(self):
        diyalog = HakkindaDiyalogu(parent=self)
        diyalog.exec()

    def _kisayollari_goster(self):
        """Uygulama kısayollarını listeler."""
        metin = (
            "<b>Genel</b><br>"
            "Ctrl+N — Yeni seri<br>"
            "Ctrl+Shift+N — Yeni seri sihirbazı<br>"
            "Ctrl+I — TXT içe aktar<br>"
            "Ctrl+E — EPUB dışa aktar<br>"
            "Ctrl+, — Ayarlar<br>"
            "Ctrl+T — Tema değiştir<br>"
            "Ctrl+Q — Çıkış<br>"
            "F1 — Bu yardım<br><br>"
            "<b>Bölüm paneli</b><br>"
            "Ctrl+S — Kaydet<br>"
            "Ctrl+Enter — Çevir<br>"
            "Ctrl+F — Metinde ara<br>"
            "Ctrl+R — Okuma modu<br>"
            "Ctrl+D — Çeviri diff<br>"
            "Ctrl+Shift+G — Sözlük uyum kontrolü<br>"
            "Esc — Çeviriyi iptal et / okuma modundan çık"
        )
        QMessageBox.information(self, "Kısayollar", metin)

    # =========================================================================
    # TEMA GEÇİŞİ
    # =========================================================================

    def _tema_uygula(self, acik: bool):
        """Belirtilen temayı yükler ve uygular."""
        import main as main_mod
        app = QApplication.instance()

        # Tema dosyasını assets/ klasöründen yükle
        _ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

        if acik:
            dosya = os.path.join(_ASSETS, "theme_light.qss")
            try:
                with open(dosya, encoding="utf-8") as f:
                    app.setStyleSheet(f.read())
            except Exception:
                app.setStyleSheet(self._acik_tema_qss())
            self._acik_tema_aktif = True
            self._tema_action.setText("[Tema] Karanlik Temaya Gec")
        else:
            dosya = os.path.join(_ASSETS, "theme_dark.qss")
            try:
                with open(dosya, encoding="utf-8") as f:
                    app.setStyleSheet(f.read())
            except Exception:
                app.setStyleSheet(main_mod.GLOBAL_TEMA)
            self._acik_tema_aktif = False
            self._tema_action.setText("[Tema] Acik Temaya Gec")

        self._ayarlar.setValue("tema/acik", self._acik_tema_aktif)

    def _tema_degistir(self):
        """Karanlık ↔ Açık tema arasında geçiş yapar."""
        self._tema_uygula(not self._acik_tema_aktif)

    @staticmethod
    def _acik_tema_qss() -> str:
        """Açık tema QSS stringi."""
        return """
            QMainWindow, QWidget { background-color: #f5f3fa; color: #1a0d2e; }
            QListWidget { background-color: #ede8f8; border: none; color: #1a0d2e; }
            QListWidget::item:selected { background-color: #c9aff0; color: #1a0d2e; }
            QTextEdit, QLineEdit, QComboBox {
                background-color: #fff; color: #1a0d2e;
                border: 1px solid #c9aff0; border-radius: 6px; padding: 6px;
            }
            QPushButton {
                background-color: #9b59d0; color: #fff;
                border: none; border-radius: 6px; padding: 7px 16px; font-weight: 600;
            }
            QPushButton:hover { background-color: #7d44b0; }
            QPushButton:disabled { background-color: #c9aff0; color: #8877aa; }
            QTabWidget::pane { border: 1px solid #c9aff0; background: #f5f3fa; }
            QTabBar::tab {
                background: #ede8f8; color: #6b5a7a;
                padding: 8px 20px; border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #9b59d0; border-bottom: 2px solid #9b59d0; }
            QHeaderView::section { background-color: #ede8f8; color: #9b59d0; border: none; }
            QTableWidget { background-color: #f5f3fa; alternate-background-color: #ede8f8; color: #1a0d2e; border: none; }
            QTableWidget::item:selected { background-color: #c9aff0; color: #1a0d2e; }
            QMenu { background-color: #f5f3fa; color: #1a0d2e; border: 1px solid #c9aff0; }
            QMenu::item:selected { background-color: #c9aff0; }
            QScrollBar:vertical { background: #ede8f8; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #c9aff0; border-radius: 4px; min-height: 30px; }
            QLabel { color: #1a0d2e; background: transparent; }
            QLabel#baslikLabel { color: #7d44b0; font-size: 16px; font-weight: 700; }
            QSplitter::handle { background-color: #c9aff0; }
        """

    # =========================================================================
    # ÖNBELLEK
    # =========================================================================

    def _onbellegi_temizle(self):
        """Çeviri önbelleğini temizler."""
        onay = QMessageBox.question(
            self, "Önbelleği Temizle",
            "Tüm çeviri önbelleği silinecek. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if onay == QMessageBox.StandardButton.Yes:
            self.db.onbellegi_temizle()
            QMessageBox.information(self, "Önbellek", "Çeviri önbelleği temizlendi.")

    # =========================================================================
    # TXT İÇE AKTARIM
    # =========================================================================

    def _txt_ice_aktar(self):
        """TXT dosyasını okuyup aktif seriye bölüm olarak ekler."""
        if not self.aktif_seri_id:
            QMessageBox.warning(self, "Seri Seçilmedi", "Lütfen önce bir seri seçin.")
            return
        if _IMPORTERS_MEVCUT:
            eklenen = txt_bolum_ice_aktar(self.aktif_seri_id, self.db, self)
            if eklenen:
                self._serileri_yukle()
        else:
            self._txt_ice_aktar_inline()

    def _txt_ice_aktar_inline(self):
        """TXT içe aktarım — importers.py yoksa bu fallback çalışır."""
        dosyalar, _ = QFileDialog.getOpenFileNames(
            self, "TXT Dosyası Seç", "", "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)"
        )
        if not dosyalar:
            return

        mevcut_bolumler = self.db.serinin_bolumlerini_getir(self.aktif_seri_id)
        sonraki_no = max((b.get("bolum_no", 0) for b in mevcut_bolumler), default=0) + 1
        eklenen = 0

        for dosya in sorted(dosyalar):
            icerik = None
            for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
                try:
                    with open(dosya, encoding=enc) as f:
                        icerik = f.read().strip()
                    break
                except UnicodeDecodeError:
                    continue
            if not icerik:
                continue

            baslik = os.path.splitext(os.path.basename(dosya))[0]
            self.db.bolum_olustur(
                seri_id=self.aktif_seri_id,
                bolum_no=sonraki_no,
                bolum_baslik=baslik,
                orijinal_metin=icerik,
            )
            sonraki_no += 1
            eklenen += 1

        if eklenen:
            self._serileri_yukle()
            QMessageBox.information(self, "İçe Aktarım", f"{eklenen} bölüm başarıyla eklendi.")

    # =========================================================================
    # EPUB İÇE AKTARIM
    # =========================================================================

    def _epub_ice_aktar(self):
        """EPUB dosyasını ayrıştırıp bölüm bölüm içe aktarır."""
        if not self.aktif_seri_id:
            QMessageBox.warning(self, "Seri Seçilmedi", "Lütfen önce bir seri seçin.")
            return
        if _IMPORTERS_MEVCUT:
            eklenen = epub_ice_aktar(self.aktif_seri_id, self.db, self)
            if eklenen:
                self._serileri_yukle()
                if self.chapters_widget:
                    self.chapters_widget.set_seri(self.aktif_seri_id)
        else:
            self._epub_ice_aktar_inline()

    def _epub_ice_aktar_inline(self):
        """EPUB içe aktarım — importers.py yoksa bu fallback çalışır."""
        dosya, _ = QFileDialog.getOpenFileName(
            self, "EPUB Dosyası Seç", "", "EPUB Dosyaları (*.epub);;Tüm Dosyalar (*)"
        )
        if not dosya:
            return

        try:
            import zipfile
            from html.parser import HTMLParser

            class HtmlMetinCikartici(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.metin_parcalari = []
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

            def html_den_metin(html_str: str) -> str:
                p = HtmlMetinCikartici()
                p.feed(html_str)
                satirlar = "".join(p.metin_parcalari).splitlines()
                temiz = [s.strip() for s in satirlar if s.strip()]
                return "\n\n".join(temiz)

            eklenen = 0
            mevcut = self.db.serinin_bolumlerini_getir(self.aktif_seri_id)
            sonraki_no = max((b.get("bolum_no", 0) for b in mevcut), default=0) + 1

            with zipfile.ZipFile(dosya, "r") as epub:
                # Dosya adlarını sırala — genellikle bölüm sırası
                icerik_dosyalari = sorted([
                    n for n in epub.namelist()
                    if n.endswith((".html", ".xhtml", ".htm"))
                    and "toc" not in n.lower()
                    and "nav" not in n.lower()
                    and "ncx" not in n.lower()
                ])

                for dosya_adi in icerik_dosyalari:
                    try:
                        html_bytes = epub.read(dosya_adi)
                        html_str   = html_bytes.decode("utf-8", errors="replace")
                        metin      = html_den_metin(html_str)
                        if len(metin.strip()) < 50:
                            continue  # Çok kısa, muhtemelen bölüm değil
                        baslik = os.path.splitext(os.path.basename(dosya_adi))[0]
                        baslik = re.sub(r"[-_]", " ", baslik).title()
                        self.db.bolum_olustur(
                            seri_id=self.aktif_seri_id,
                            bolum_no=sonraki_no,
                            bolum_baslik=baslik,
                            orijinal_metin=metin,
                        )
                        sonraki_no += 1
                        eklenen += 1
                    except Exception:
                        continue

            if eklenen:
                self._serileri_yukle()
                if self.chapters_widget:
                    self.chapters_widget.set_seri(self.aktif_seri_id)
                QMessageBox.information(self, "EPUB İçe Aktarım",
                                        f"{eklenen} bölüm başarıyla içe aktarıldı.")
            else:
                QMessageBox.warning(self, "EPUB İçe Aktarım",
                                    "Bölüm içeriği bulunamadı. Dosya standart EPUB formatında olmayabilir.")

        except Exception as hata:
            QMessageBox.critical(self, "EPUB Hatası",
                                 f"EPUB dosyası işlenirken hata oluştu:\n{hata}")

    # =========================================================================
    # TXT DIŞA AKTARIM
    # =========================================================================

    def _txt_disa_aktar(self):
        """Aktif serinin çevrilmiş bölümlerini TXT olarak dışa aktarır."""
        if not self.aktif_seri_id:
            QMessageBox.warning(self, "Seri Seçilmedi", "Lütfen önce bir seri seçin.")
            return
        if _IMPORTERS_MEVCUT:
            txt_disa_aktar(self.aktif_seri_id, self.db, self)
        else:
            self._txt_disa_aktar_inline()

    def _txt_disa_aktar_inline(self):
        """TXT dışa aktarım — importers.py yoksa bu fallback çalışır."""
        bolumler = self.db.serinin_bolumlerini_getir(self.aktif_seri_id)
        cevirilen = [b for b in bolumler if b.get("cevrilmis_metin", "").strip()]
        if not cevirilen:
            QMessageBox.information(self, "Dışa Aktarım",
                                    "Dışa aktarılacak çevrilmiş bölüm bulunamadı.")
            return

        seri = self.db.seri_getir(self.aktif_seri_id)
        varsayilan_ad = f"{seri.get('baslik','seri')}_ceviri.txt" if seri else "ceviri.txt"
        kayit_yolu, _ = QFileDialog.getSaveFileName(
            self, "TXT Olarak Kaydet", varsayilan_ad,
            "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)"
        )
        if not kayit_yolu:
            return

        try:
            with open(kayit_yolu, "w", encoding="utf-8") as f:
                for bolum in cevirilen:
                    baslik = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no','')}"
                    f.write(f"{'='*60}\n{baslik}\n{'='*60}\n\n")
                    f.write(bolum.get("cevrilmis_metin", "").strip())
                    f.write("\n\n")
            QMessageBox.information(self, "Dışa Aktarım",
                                    f"{len(cevirilen)} bölüm başarıyla kaydedildi:\n{kayit_yolu}")
        except Exception as hata:
            QMessageBox.critical(self, "Yazma Hatası", f"Dosya yazılamadı:\n{hata}")

    # =========================================================================
    # EPUB DIŞA AKTARIM
    # =========================================================================

    def _epub_disa_aktar(self):
        """Aktif serinin çevrilmiş bölümlerini EPUB olarak dışa aktarır."""
        if not self.aktif_seri_id:
            QMessageBox.warning(self, "Seri Seçilmedi", "Lütfen önce bir seri seçin.")
            return
        if _IMPORTERS_MEVCUT:
            epub_disa_aktar(self.aktif_seri_id, self.db, self)
        else:
            self._epub_disa_aktar_inline()

    def _epub_disa_aktar_inline(self):
        """EPUB dışa aktarım — importers.py yoksa bu fallback çalışır."""
        bolumler = self.db.serinin_bolumlerini_getir(self.aktif_seri_id)
        cevirilen = [b for b in bolumler if b.get("cevrilmis_metin", "").strip()]
        if not cevirilen:
            QMessageBox.information(self, "EPUB Dışa Aktarım",
                                    "Dışa aktarılacak çevrilmiş bölüm bulunamadı.")
            return

        seri = self.db.seri_getir(self.aktif_seri_id)
        seri_baslik = seri.get("baslik", "Roman") if seri else "Roman"
        varsayilan_ad = f"{seri_baslik}_ceviri.epub"

        kayit_yolu, _ = QFileDialog.getSaveFileName(
            self, "EPUB Olarak Kaydet", varsayilan_ad,
            "EPUB Dosyaları (*.epub);;Tüm Dosyalar (*)"
        )
        if not kayit_yolu:
            return

        try:
            import zipfile
            import uuid
            from datetime import datetime

            kitap_id = str(uuid.uuid4())
            simdi    = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

            def _html_kacis(metin: str) -> str:
                return (metin.replace("&", "&amp;")
                             .replace("<", "&lt;")
                             .replace(">", "&gt;")
                             .replace('"', "&quot;"))

            def _bolum_html(baslik: str, metin: str) -> str:
                paragraflar = "\n".join(
                    f"<p>{_html_kacis(p.strip())}</p>"
                    for p in metin.split("\n\n") if p.strip()
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
            spine_girisler    = []
            toc_girisler      = []

            with zipfile.ZipFile(kayit_yolu, "w", zipfile.ZIP_DEFLATED) as epub:
                # mimetype (sıkıştırılmadan)
                epub.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")

                # META-INF/container.xml
                epub.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")

                # Bölüm dosyaları
                for i, bolum in enumerate(cevirilen):
                    dosya_id  = f"bolum{i+1}"
                    dosya_adi = f"OEBPS/{dosya_id}.xhtml"
                    baslik    = bolum.get("bolum_baslik") or f"Bölüm {bolum.get('bolum_no', i+1)}"
                    html      = _bolum_html(baslik, bolum.get("cevrilmis_metin", ""))
                    epub.writestr(dosya_adi, html.encode("utf-8"))
                    manifest_girisler.append(
                        f'<item id="{dosya_id}" href="{dosya_id}.xhtml" media-type="application/xhtml+xml"/>'
                    )
                    spine_girisler.append(f'<itemref idref="{dosya_id}"/>')
                    toc_girisler.append(
                        f'<navPoint id="nav{i+1}" playOrder="{i+1}">'
                        f'<navLabel><text>{_html_kacis(baslik)}</text></navLabel>'
                        f'<content src="{dosya_id}.xhtml"/></navPoint>'
                    )

                # content.opf
                opf = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">'
                    f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    f'<dc:title>{_html_kacis(seri_baslik)}</dc:title>'
                    f'<dc:identifier id="bookid">{kitap_id}</dc:identifier>'
                    f'<dc:language>tr</dc:language>'
                    f'<dc:date>{simdi}</dc:date>'
                    '</metadata>'
                    '<manifest>'
                    + "\n".join(manifest_girisler)
                    + '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                    '</manifest>'
                    '<spine toc="ncx">' + "\n".join(spine_girisler) + '</spine>'
                    '</package>'
                )
                epub.writestr("OEBPS/content.opf", opf.encode("utf-8"))

                # toc.ncx
                ncx = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
                    '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
                    '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
                    f'<head><meta name="dtb:uid" content="{kitap_id}"/></head>'
                    f'<docTitle><text>{_html_kacis(seri_baslik)}</text></docTitle>'
                    '<navMap>' + "\n".join(toc_girisler) + '</navMap>'
                    '</ncx>'
                )
                epub.writestr("OEBPS/toc.ncx", ncx.encode("utf-8"))

            QMessageBox.information(self, "EPUB Dışa Aktarım",
                                    f"{len(cevirilen)} bölüm EPUB olarak kaydedildi:\n{kayit_yolu}")

        except Exception as hata:
            QMessageBox.critical(self, "EPUB Hatası", f"EPUB oluşturulamadı:\n{hata}")

    # =========================================================================
    # SERİ OLUŞTURMA SİHİRBAZI
    # =========================================================================

    def _seri_sihirbazi_ac(self):
        """Adım adım seri oluşturma sihirbazını açar."""
        if _WIZARDS_MEVCUT:
            sihirbaz = _SeriSihirbazi_Dis(db=self.db, parent=self)
        else:
            sihirbaz = SeriSihirbazi(db=self.db, parent=self)
        if sihirbaz.exec() == QDialog.DialogCode.Accepted:
            seri_id = sihirbaz.olusturulan_seri_id
            if seri_id:
                self._serileri_yukle()
                self._seri_sec_by_id(seri_id)

    def _eklentileri_yukle(self):
        if not _PLUGIN_LOADER_MEVCUT:
            QMessageBox.information(self, "Eklentiler", "Eklenti sistemi kullanılamıyor.")
            return
        try:
            yuklenenler = _plugin_loader.load_plugins()
            if yuklenenler:
                QMessageBox.information(self, "Eklentiler", f"{len(yuklenenler)} eklenti yüklendi:\n" + "\n".join(yuklenenler))
            else:
                QMessageBox.information(self, "Eklentiler", "plugins/ klasöründe eklenti bulunamadı.")
        except Exception as hata:
            QMessageBox.critical(self, "Eklenti Hatası", str(hata))

    def closeEvent(self, event):
        """Pencere kapanırken durumu kaydeder."""
        # Pencere geometrisini kaydet
        self._ayarlar.setValue("pencere/geometry", self.saveGeometry())
        self._ayarlar.setValue("pencere/state", self.saveState())
        # Aktif seri ID'sini kaydet
        if self.aktif_seri_id:
            self._ayarlar.setValue("son_seri_id", self.aktif_seri_id)
        super().closeEvent(event)


# =============================================================================
# SERİ OLUŞTURMA SİHİRBAZI DİYALOĞU
# =============================================================================

class SeriSihirbazi(QDialog):
    """
    Adım adım seri oluşturma sihirbazı.
    Adım 1: Seri adı ve dil seçimi
    Adım 2: İlk bölüm metnini yapıştır / TXT dosyası seç
    Adım 3: Özet ve oluştur
    """

    _KAYNAK_DILLER = [
        "Japonca", "Çince", "Korece", "İngilizce", "Almanca",
        "Fransızca", "İspanyolca", "Rusça", "Arapça", "Diğer",
    ]
    _HEDEF_DILLER = ["Türkçe", "İngilizce", "Almanca", "Fransızca", "Diğer"]

    def __init__(self, db: "DatabaseManager", parent=None):
        super().__init__(parent)
        self.db = db
        self.olusturulan_seri_id: int | None = None
        self.setWindowTitle("Yeni Seri Sihirbazı")
        self.setMinimumSize(540, 400)
        self.setModal(True)
        self._adim = 0
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        self._ana_layout = QVBoxLayout(self)
        self._ana_layout.setContentsMargins(24, 20, 24, 16)
        self._ana_layout.setSpacing(16)

        # Başlık
        self._baslik_label = QLabel("Adım 1 / 3: Seri Bilgileri")
        self._baslik_label.setStyleSheet(
            "color: #9b59d0; font-size: 15px; font-weight: 700;"
        )
        self._ana_layout.addWidget(self._baslik_label)

        # Adım içerik alanı
        self._icerik_widget = QWidget()
        self._icerik_layout = QVBoxLayout(self._icerik_widget)
        self._icerik_layout.setContentsMargins(0, 0, 0, 0)
        self._ana_layout.addWidget(self._icerik_widget, stretch=1)

        # Alt buton satırı
        alt_layout = QHBoxLayout()
        alt_layout.addStretch()
        self._geri_btn = QPushButton("← Geri")
        self._geri_btn.setEnabled(False)
        self._geri_btn.clicked.connect(self._onceki_adim)
        self._ileri_btn = QPushButton("İleri →")
        self._ileri_btn.clicked.connect(self._sonraki_adim)
        self._iptal_btn = QPushButton("İptal")
        self._iptal_btn.clicked.connect(self.reject)
        for btn in (self._iptal_btn, self._geri_btn, self._ileri_btn):
            btn.setMinimumWidth(90)
            btn.setFixedHeight(36)
        alt_layout.addWidget(self._iptal_btn)
        alt_layout.addWidget(self._geri_btn)
        alt_layout.addWidget(self._ileri_btn)
        self._ana_layout.addLayout(alt_layout)

        self._adimi_goster(0)

    def _adimi_goster(self, adim: int):
        self._adim = adim
        # İçerik alanını temizle
        while self._icerik_layout.count():
            w = self._icerik_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        self._geri_btn.setEnabled(adim > 0)

        if adim == 0:
            self._baslik_label.setText("Adım 1 / 3: Seri Bilgileri")
            self._ileri_btn.setText("İleri →")
            self._adim1_olustur()
        elif adim == 1:
            self._baslik_label.setText("Adım 2 / 3: İlk Bölüm (İsteğe Bağlı)")
            self._ileri_btn.setText("İleri →")
            self._adim2_olustur()
        elif adim == 2:
            self._baslik_label.setText("Adım 3 / 3: Özet ve Oluştur")
            self._ileri_btn.setText("✓ Oluştur")
            self._adim3_olustur()

    def _adim1_olustur(self):
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(16)

        self._ad_input = QLineEdit()
        self._ad_input.setPlaceholderText("Roman veya seri adı...")
        self._ad_input.setFixedHeight(36)
        form.addRow("Seri Adı *:", self._ad_input)

        self._kaynak_combo = QComboBox()
        self._kaynak_combo.addItems(self._KAYNAK_DILLER)
        self._kaynak_combo.setFixedHeight(36)
        form.addRow("Kaynak Dil:", self._kaynak_combo)

        self._hedef_combo = QComboBox()
        self._hedef_combo.addItems(self._HEDEF_DILLER)
        self._hedef_combo.setFixedHeight(36)
        form.addRow("Hedef Dil:", self._hedef_combo)

        self._aciklama_input = QTextEdit()
        self._aciklama_input.setPlaceholderText("İsteğe bağlı açıklama...")
        self._aciklama_input.setFixedHeight(80)
        form.addRow("Açıklama:", self._aciklama_input)

        self._icerik_layout.addLayout(form)
        self._icerik_layout.addStretch()

    def _adim2_olustur(self):
        aciklama = QLabel(
            "İlk bölüm metnini buraya yapıştırabilir ya da TXT dosyası seçebilirsiniz.\n"
            "Bu adım isteğe bağlıdır; daha sonra da bölüm eklenebilir."
        )
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet("color: #6b5a7a; font-size: 11px;")
        self._icerik_layout.addWidget(aciklama)

        btn_layout = QHBoxLayout()
        dosya_btn = QPushButton("TXT Dosyası Seç...")
        dosya_btn.clicked.connect(self._txt_dosyasi_sec)
        btn_layout.addWidget(dosya_btn)
        btn_layout.addStretch()
        self._icerik_layout.addLayout(btn_layout)

        self._bolum_metin = QTextEdit()
        self._bolum_metin.setPlaceholderText("Bölüm metnini buraya yapıştırın...")
        self._icerik_layout.addWidget(self._bolum_metin, stretch=1)

        self._bolum_baslik = QLineEdit()
        self._bolum_baslik.setPlaceholderText("Bölüm başlığı (örn. Bölüm 1)")
        self._bolum_baslik.setText("Bölüm 1")
        self._bolum_baslik.setFixedHeight(34)
        self._icerik_layout.addWidget(self._bolum_baslik)

    def _txt_dosyasi_sec(self):
        dosya, _ = QFileDialog.getOpenFileName(
            self, "TXT Dosyası Seç", "", "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)"
        )
        if not dosya:
            return
        for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
            try:
                with open(dosya, encoding=enc) as f:
                    icerik = f.read()
                self._bolum_metin.setPlainText(icerik)
                baslik = os.path.splitext(os.path.basename(dosya))[0]
                self._bolum_baslik.setText(baslik)
                return
            except UnicodeDecodeError:
                continue

    def _adim3_olustur(self):
        seri_adi   = getattr(self, "_ad_input", None)
        ad         = seri_adi.text().strip() if seri_adi else ""
        kaynak     = getattr(self, "_kaynak_combo", None)
        kaynak_dil = kaynak.currentText() if kaynak else "Japonca"
        hedef      = getattr(self, "_hedef_combo", None)
        hedef_dil  = hedef.currentText() if hedef else "Türkçe"

        ozet = QLabel(
            f"<b>Seri Adı:</b> {ad or '(girilmedi)'}<br>"
            f"<b>Kaynak Dil:</b> {kaynak_dil}<br>"
            f"<b>Hedef Dil:</b> {hedef_dil}<br>"
        )
        ozet.setTextFormat(Qt.TextFormat.RichText)
        ozet.setStyleSheet("color: #e8e0f0; font-size: 13px; line-height: 1.7;")
        ozet.setWordWrap(True)
        self._icerik_layout.addWidget(ozet)

        bolum_metni = getattr(self, "_bolum_metin", None)
        metin = bolum_metni.toPlainText().strip() if bolum_metni else ""
        if metin:
            bolum_info = QLabel(f"İlk bölüm: {len(metin):,} karakter eklendi.")
            bolum_info.setStyleSheet("color: #a0f0b0; font-size: 11px;")
            self._icerik_layout.addWidget(bolum_info)

        self._icerik_layout.addStretch()

    def _sonraki_adim(self):
        if self._adim == 0:
            ad = self._ad_input.text().strip()
            if not ad:
                QMessageBox.warning(self, "Eksik Bilgi", "Lütfen seri adını girin.")
                return
            # Adım 1 widget'ları bir sonraki adımda silineceğinden değerleri sakla
            self._kayit_ad        = ad
            self._kayit_kaynak    = self._kaynak_combo.currentText()
            self._kayit_hedef     = self._hedef_combo.currentText()
            self._kayit_aciklama  = self._aciklama_input.toPlainText().strip()
        if self._adim < 2:
            self._adimi_goster(self._adim + 1)
        else:
            self._olustur()

    def _onceki_adim(self):
        if self._adim > 0:
            self._adimi_goster(self._adim - 1)

    def _olustur(self):
        # Widget'lar _adimi_goster() tarafından silindiğinden kayıtlı değerleri kullan
        ad         = getattr(self, "_kayit_ad",       "")
        kaynak_dil = getattr(self, "_kayit_kaynak",   "Japonca")
        hedef_dil  = getattr(self, "_kayit_hedef",    "Türkçe")
        aciklama   = getattr(self, "_kayit_aciklama", "")

        if not ad:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen seri adını girin.")
            return

        try:
            seri_id = self.db.seri_olustur(
                baslik=ad,
                kaynak_dil=kaynak_dil,
                hedef_dil=hedef_dil,
                aciklama=aciklama,
            )
            # İlk bölüm ekle (varsa)
            bolum_metni = getattr(self, "_bolum_metin", None)
            metin = bolum_metni.toPlainText().strip() if bolum_metni else ""
            bolum_baslik_w = getattr(self, "_bolum_baslik", None)
            bolum_baslik = bolum_baslik_w.text().strip() if bolum_baslik_w else "Bölüm 1"
            if metin:
                self.db.bolum_olustur(
                    seri_id=seri_id,
                    bolum_no=1,
                    bolum_baslik=bolum_baslik or "Bölüm 1",
                    orijinal_metin=metin,
                )
            self.olusturulan_seri_id = seri_id
            self.accept()
        except Exception as hata:
            QMessageBox.critical(self, "Hata", f"Seri oluşturulamadı:\n{hata}")


# =============================================================================
# GİRİŞ NOKTASI (main.py üzerinden çalıştırıldığında burası kullanılmaz)
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Novel Çevirmen")
    app.setOrganizationName("NovelCevirmen")

    pencere = MainWindow()
    pencere.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()