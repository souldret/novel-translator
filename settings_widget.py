"""
Novel Çevirmen - Ayarlar Widget'ı
API anahtarı yönetimi, sağlayıcı seçimi ve uygulama varsayılanlarını
yöneten ayarlar bileşeni.
"""

import sys
import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame,
    QFormLayout, QMessageBox, QApplication,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor
from icons import pixmap, set_icon


# =============================================================================
# BAĞLANTI TEST WORKER
# =============================================================================

class BaglantiTestWorker(QThread):
    """
    Bağlantı testini arka planda çalıştıran QThread.
    UI thread'i bloke etmez.
    """
    basarili  = pyqtSignal(str)   # yanıt metni
    basarisiz = pyqtSignal(str)   # hata mesajı

    def __init__(self, factory, veri: dict, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.veri    = veri

    def run(self):
        try:
            translator = self.factory.get_translator(
                saglayici=self.veri["saglayici"],
                api_anahtari=self.veri["api_key"],
                model_adi=self.veri["model"],
                ekstra_konfig=self.veri["ekstra_konfig"],
            )
            sonuc = translator.translate_bolum(
                orijinal_metin="Merhaba",
                kaynak_dil="Türkçe",
                hedef_dil="İngilizce",
                sozluk_terimleri=[],
            )
            if sonuc and sonuc.startswith("HATA:"):
                self.basarisiz.emit(sonuc)
            else:
                self.basarili.emit(sonuc or "")
        except Exception as hata:
            self.basarisiz.emit(str(hata))


class OpenRouterModelListWorker(QThread):
    """
    OpenRouter API'den guncel model listesini arka planda ceken QThread.

    Sinyaller:
        basarili(list[dict]) : Model listesi basariyla alindi
        basarisiz(str)       : Hata durumunda hata mesaji
    """
    basarili  = pyqtSignal(list)   # model dict listesi
    basarisiz = pyqtSignal(str)

    def __init__(self, factory, api_key: str, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.api_key = api_key

    def run(self):
        try:
            modeller = self.factory.openrouter_modellerini_yukle(self.api_key)
            self.basarili.emit(modeller)
        except Exception as hata:
            self.basarisiz.emit(str(hata))


# Uygulama yapılandırma dosyasının yolu
CONFIG_DOSYASI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app_config.json"
)

# Sağlayıcı kod adı → görünen ad eşlemesi
SAGLAYICI_ADLAR = {
    "openai":      "OpenAI",
    "anthropic":   "Anthropic (Claude)",
    "google":      "Google Gemini",
    "xai":         "xAI (Grok)",
    "openrouter":  "OpenRouter",
}

# Görünen ad → kod adı (ters eşleme)
AD_SAGLAYICI = {v: k for k, v in SAGLAYICI_ADLAR.items()}

# Varsayılan kaynak diller
KAYNAK_DILLER = [
    "Çince (Basitleştirilmiş)",
    "Çince (Geleneksel)",
    "Japonca",
    "Korece",
    "İngilizce",
]

# Varsayılan hedef diller
HEDEF_DILLER = [
    "Türkçe",
    "İngilizce",
    "Almanca",
    "Fransızca",
    "İspanyolca",
    "Arapça",
    "Portekizce",
]

# Model açıklamaları (bilgi etiketi için — modül seviyesinde tanımlı)
MODEL_ACIKLAMALARI = {
    "gpt-4o":                       "OpenAI'nin en yetenekli çok modlu modeli.",
    "gpt-4o-mini":                  "Hızlı ve ekonomik GPT-4o varyantı.",
    "gpt-4-turbo":                  "Yüksek bağlam pencereli GPT-4 Turbo.",
    "gpt-3.5-turbo":                "Hızlı ve ekonomik GPT-3.5 modeli.",
    "claude-opus-4-6":              "Anthropic'in en güçlü Claude modeli.",
    "claude-sonnet-4-6":            "Hız ve yetenek dengesi için Claude Sonnet.",
    "claude-haiku-4-5-20251001":   "En hızlı ve hafif Claude modeli.",
    "gemini-2.0-flash":             "Google'ın en hızlı Gemini modeli.",
    "gemini-1.5-pro":               "Uzun bağlam destekli Gemini Pro modeli.",
    "gemini-1.5-flash":             "Hızlı Gemini Flash modeli.",
    "grok-3":                       "xAI'nin en yetenekli Grok modeli.",
    "grok-3-mini":                  "Hafif ve ekonomik Grok Mini modeli.",
    # OpenRouter popüler modelleri
    "anthropic/claude-3.5-sonnet": "Anthropic'in en dengeli modeli.",
    "anthropic/claude-3.5-haiku":   "Hızlı ve ekonomik Anthropic modeli.",
    "meta-llama/llama-3.3-70b-instruct": "Meta'nın büyük ögretimli modeli.",
    "meta-llama/llama-3.1-8b-instruct":  "Hızlı ve hafif Llama modeli.",
    "google/gemini-2.0-flash":     "Google'un en hızlı modeli.",
    "google/gemini-1.5-pro":      "Uzun bağlam destekli Gemini Pro.",
    "mistralai/mistral-nemo":     "Mistral'in 12B modeli.",
    "mistralai/mixtral-8x7b":     "Uzmanlık alanlı karma uzmanlık modeli.",
    "deepseek/deepseek-chat":     "DeepSeek'in ana sohbet modeli.",
    "qwen/qwen-2.5-72b-instruct": "Alibaba'nın büyük dil modeli.",
    "x-ai/grok-3":               "xAI'nin en güçlü modeli.",
    "perplexity/llama-3.1-sonar-large": "Arama destekli model.",
    "nvidia/llama-3.1-nemotron-70b-instruct": "RLHF ile eğitilmiş model.",
}


# =============================================================================
# AYARLAR WIDGET'I
# =============================================================================

class SettingsWidget(QWidget):
    """
    API anahtarı yönetimi, sağlayıcı aktivasyonu ve uygulama
    varsayılanlarını yöneten tam ayarlar bileşeni.

    Sinyal:
        aktif_saglayici_degisti(saglayici, model_adi, api_anahtari, ekstra_konfig)
        — Aktif AI sağlayıcısı değiştiğinde MainWindow'u bilgilendirir.
    """

    aktif_saglayici_degisti = pyqtSignal(str, str, str, object)

    def __init__(self, db_manager, translator_factory_class=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

        # TranslatorFactory sınıfı — None ise çalışma zamanında import edilir
        if translator_factory_class is None:
            from translator import TranslatorFactory
            self.factory = TranslatorFactory
        else:
            self.factory = translator_factory_class

        self._arayuz_olustur()
        self._baslangic_verilerini_yukle()

    # =========================================================================
    # ARAYÜZ KURULUMU
    # =========================================================================

    def _arayuz_olustur(self):
        """Ana kaydırılabilir düzeni ve tüm bölümleri oluşturur."""
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(0, 0, 0, 0)
        ana_layout.setSpacing(0)

        # ── Kaydırma alanı ────────────────────────────────────────────────
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QFrame.Shape.NoFrame)
        kaydirma.setStyleSheet("""
            QScrollArea { background-color: #0f0a1a; border: none; }
            QScrollBar:vertical {
                background: #0f0a1a; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2d1a40; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #3d2d55; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; background: none; }
        """)

        # İç kapsayıcı widget
        ic_widget = QWidget()
        ic_widget.setStyleSheet("background-color: #0f0a1a;")
        ic_layout = QVBoxLayout(ic_widget)
        ic_layout.setContentsMargins(20, 16, 20, 20)
        ic_layout.setSpacing(16)

        # Sayfa başlığı — ikon ve metin ayrı widget'larda (setText pixmap'i siler)
        baslik_satir = QWidget()
        baslik_satir.setStyleSheet("background: transparent;")
        baslik_satir_layout = QHBoxLayout(baslik_satir)
        baslik_satir_layout.setContentsMargins(0, 0, 0, 0)
        baslik_satir_layout.setSpacing(8)

        baslik_ikon = QLabel()
        baslik_ikon.setPixmap(pixmap("settings", size=24))
        baslik_satir_layout.addWidget(baslik_ikon)

        baslik_metin = QLabel("Ayarlar")
        baslik_metin.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        baslik_metin.setStyleSheet("color: #9b59d0; padding-bottom: 4px; background: transparent;")
        baslik_satir_layout.addWidget(baslik_metin)
        baslik_satir_layout.addStretch()

        ic_layout.addWidget(baslik_satir)

        # ── Bölüm 1: AI Sağlayıcısı Ekle / Güncelle ──────────────────────
        ic_layout.addWidget(self._bolum1_olustur())

        # ── Bölüm 2: Kayıtlı Sağlayıcılar ────────────────────────────────
        ic_layout.addWidget(self._bolum2_olustur())

        # ── Bölüm 3: Çeviri Varsayılanları ───────────────────────────────
        ic_layout.addWidget(self._bolum3_olustur())

        # ── Bölüm 4: Uygulama Hakkında ────────────────────────────────────
        ic_layout.addWidget(self._bolum4_olustur())

        ic_layout.addStretch()
        kaydirma.setWidget(ic_widget)
        ana_layout.addWidget(kaydirma)

    # ─── BÖLÜM 1: AI Sağlayıcısı Ekle / Güncelle ────────────────────────────

    def _bolum1_olustur(self) -> QGroupBox:
        grup = QGroupBox("  AI Sağlayıcısı Ekle / Güncelle")
        grup.setStyleSheet(self._grup_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # ── Sağlayıcı seçimi ─────────────────────────────────────────────
        self.saglayici_combo = QComboBox()
        for kod, ad in SAGLAYICI_ADLAR.items():
            self.saglayici_combo.addItem(ad, userData=kod)
        self.saglayici_combo.setStyleSheet(self._combo_stili())
        self.saglayici_combo.currentIndexChanged.connect(
            self._saglayici_degisti
        )
        form.addRow("Sağlayıcı:", self.saglayici_combo)

        # ── API Anahtarı ──────────────────────────────────────────────────
        api_layout = QHBoxLayout()
        api_layout.setSpacing(6)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API anahtarınızı buraya girin...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setStyleSheet(self._input_stili())

        self.goster_gizle_btn = QPushButton("  Göster")
        self.goster_gizle_btn.setFixedWidth(90)
        self.goster_gizle_btn.setFixedHeight(34)
        self.goster_gizle_btn.setStyleSheet(self._ikincil_buton_stili())
        self.goster_gizle_btn.setCheckable(True)
        self.goster_gizle_btn.toggled.connect(self._api_key_goster_gizle)
        set_icon(self.goster_gizle_btn, "eye", size=14)

        api_layout.addWidget(self.api_key_input, stretch=1)
        api_layout.addWidget(self.goster_gizle_btn)
        form.addRow("API Anahtarı:", api_layout)

        layout.addLayout(form)

        # ── Model seçim alanı (dinamik — sağlayıcıya göre değişir) ───────
        # QStackedWidget: sayfa 0 = ComboBox, sayfa 1 = LineEdit
        self.model_yigin = QStackedWidget()
        self.model_yigin.setFixedHeight(36)

        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet(self._combo_stili())
        self.model_combo.setMinimumContentsLength(0)
        self.model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.model_yigin.addWidget(self.model_combo)   # sayfa 0

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText(
            "orn: meta-llama/llama-3.1-8b-instruct"
        )
        self.model_input.setStyleSheet(self._input_stili())
        self.model_yigin.addWidget(self.model_input)   # sayfa 1

        model_form = QFormLayout()
        model_form.setSpacing(10)
        model_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.model_etiket = QLabel("Model:")
        model_form.addRow(self.model_etiket, self.model_yigin)
        layout.addLayout(model_form)

        # ── OpenRouter model yenileme butonu (OpenRouter secildiginde gorunur) ──
        self.openrouter_yenile_btn = QPushButton("  Listeyi Guncelle")
        self.openrouter_yenile_btn.setFixedHeight(30)
        self.openrouter_yenile_btn.setStyleSheet(self._ikincil_buton_stili())
        self.openrouter_yenile_btn.setVisible(False)
        self.openrouter_yenile_btn.clicked.connect(self._openrouter_modellerini_yukle)
        set_icon(self.openrouter_yenile_btn, "refresh", size=14)
        layout.addWidget(self.openrouter_yenile_btn)

        # ── OpenRouter ek alanları (başlangıçta gizli) ────────────────────
        self.openrouter_widget = self._openrouter_alanlari_olustur()
        self.openrouter_widget.setVisible(False)
        layout.addWidget(self.openrouter_widget)

        # ── Model açıklama etiketi ────────────────────────────────────────
        self.model_aciklama_label = QLabel("")
        self.model_aciklama_label.setStyleSheet(
            "color: #6b5a7a; font-size: 11px; padding: 2px 4px;"
        )
        self.model_aciklama_label.setWordWrap(True)
        layout.addWidget(self.model_aciklama_label)
        self.model_combo.currentTextChanged.connect(self._model_aciklamasi_guncelle)

        # ── Butonlar ──────────────────────────────────────────────────────
        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(8)

        self.kaydet_btn = QPushButton("  Kaydet ve Etkinleştir")
        self.kaydet_btn.setFixedHeight(36)
        self.kaydet_btn.setStyleSheet(self._birincil_buton_stili())
        self.kaydet_btn.clicked.connect(self._kaydet_ve_etkinlestir)
        set_icon(self.kaydet_btn, "save", size=16)

        self.test_btn = QPushButton("  Bağlantıyı Test Et")
        self.test_btn.setFixedHeight(36)
        self.test_btn.setStyleSheet(self._ikincil_buton_stili())
        self.test_btn.clicked.connect(self._baglantyi_test_et)
        set_icon(self.test_btn, "plug", size=16)

        buton_layout.addWidget(self.kaydet_btn)
        buton_layout.addWidget(self.test_btn)
        buton_layout.addStretch()
        layout.addLayout(buton_layout)

        # ── Durum etiketi ─────────────────────────────────────────────────
        self.b1_durum_label = QLabel("")
        self.b1_durum_label.setVisible(False)
        self.b1_durum_label.setWordWrap(True)
        self.b1_durum_label.setStyleSheet("font-size: 12px; padding: 4px 6px;")
        layout.addWidget(self.b1_durum_label)

        # İlk yükleme: sağlayıcıya göre model alanını güncelle
        self._saglayici_degisti()

        return grup

    def _openrouter_alanlari_olustur(self) -> QWidget:
        """OpenRouter'a özgü isteğe bağlı ek alan formu."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.site_url_input = QLineEdit()
        self.site_url_input.setPlaceholderText("https://orneksite.com (opsiyonel)")
        self.site_url_input.setStyleSheet(self._input_stili())
        layout.addRow("Site URL:", self.site_url_input)

        self.app_name_input = QLineEdit()
        self.app_name_input.setPlaceholderText("Novel Çevirmen (opsiyonel)")
        self.app_name_input.setStyleSheet(self._input_stili())
        layout.addRow("Uygulama Adı:", self.app_name_input)

        return widget

    # ─── BÖLÜM 2: Kayıtlı Sağlayıcılar ──────────────────────────────────────

    def _bolum2_olustur(self) -> QGroupBox:
        grup = QGroupBox("  Kayıtlı Sağlayıcılar")
        grup.setStyleSheet(self._grup_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(10)

        # Yenile butonu
        yenile_layout = QHBoxLayout()
        yenile_layout.addStretch()
        self.yenile_btn = QPushButton("  Listeyi Yenile")
        self.yenile_btn.setFixedHeight(30)
        self.yenile_btn.setStyleSheet(self._ikincil_buton_stili())
        self.yenile_btn.clicked.connect(self._kayitli_saglayicilari_yukle)
        yenile_layout.addWidget(self.yenile_btn)
        layout.addLayout(yenile_layout)

        # Sağlayıcı tablosu
        self.saglayici_tablo = QTableWidget()
        self.saglayici_tablo.setColumnCount(4)
        self.saglayici_tablo.setHorizontalHeaderLabels(
            ["Sağlayıcı", "Model", "Durum", "İşlemler"]
        )
        self.saglayici_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.saglayici_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.saglayici_tablo.verticalHeader().setVisible(False)
        self.saglayici_tablo.horizontalHeader().setHighlightSections(False)
        self.saglayici_tablo.setShowGrid(False)
        self.saglayici_tablo.setAlternatingRowColors(True)
        self.saglayici_tablo.verticalHeader().setDefaultSectionSize(44)
        self.saglayici_tablo.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Sütun genişlikleri
        self.saglayici_tablo.setColumnWidth(0, 180)
        self.saglayici_tablo.setColumnWidth(1, 220)
        self.saglayici_tablo.setColumnWidth(2, 100)
        self.saglayici_tablo.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

        self.saglayici_tablo.setStyleSheet("""
            QTableWidget {
                background-color: #0f0a1a;
                alternate-background-color: #130c20;
                color: #e8e0f0;
                border: 1px solid #1a1225;
                border-radius: 6px;
                outline: none;
                gridline-color: transparent;
            }
            QTableWidget::item { padding: 4px 10px; }
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
        """)
        layout.addWidget(self.saglayici_tablo)

        return grup

    # ─── BÖLÜM 3: Çeviri Varsayılanları ──────────────────────────────────────

    def _bolum3_olustur(self) -> QGroupBox:
        grup = QGroupBox("  Çeviri Varsayılanları")
        grup.setStyleSheet(self._grup_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Varsayılan kaynak dil
        self.varsayilan_kaynak_combo = QComboBox()
        self.varsayilan_kaynak_combo.addItems(KAYNAK_DILLER)
        self.varsayilan_kaynak_combo.setStyleSheet(self._combo_stili())
        form.addRow("Varsayılan Kaynak Dil:", self.varsayilan_kaynak_combo)

        # Varsayılan hedef dil
        self.varsayilan_hedef_combo = QComboBox()
        self.varsayilan_hedef_combo.addItems(HEDEF_DILLER)
        self.varsayilan_hedef_combo.setStyleSheet(self._combo_stili())
        form.addRow("Varsayılan Hedef Dil:", self.varsayilan_hedef_combo)

        layout.addLayout(form)

        # Kaydet butonu
        kaydet_layout = QHBoxLayout()
        self.varsayilan_kaydet_btn = QPushButton("  Varsayılanları Kaydet")
        self.varsayilan_kaydet_btn.setFixedHeight(34)
        self.varsayilan_kaydet_btn.setStyleSheet(self._birincil_buton_stili())
        self.varsayilan_kaydet_btn.clicked.connect(self._varsayilanlari_kaydet)
        kaydet_layout.addWidget(self.varsayilan_kaydet_btn)
        kaydet_layout.addStretch()
        layout.addLayout(kaydet_layout)

        # Durum etiketi
        self.b3_durum_label = QLabel("")
        self.b3_durum_label.setVisible(False)
        self.b3_durum_label.setStyleSheet("font-size: 12px; padding: 2px 4px;")
        layout.addWidget(self.b3_durum_label)

        return grup

    # ─── BÖLÜM 4: Uygulama Hakkında ──────────────────────────────────────────

    def _bolum4_olustur(self) -> QGroupBox:
        grup = QGroupBox("  Uygulama Hakkında")
        grup.setStyleSheet(self._grup_stili())
        layout = QVBoxLayout(grup)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        ad = QLabel("Novel Çevirmen")
        ad.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        ad.setStyleSheet("color: #9b59d0;")

        surum = QLabel("Sürüm 1.0.0")
        surum.setStyleSheet("color: #6b5a7a; font-size: 12px;")

        aciklama = QLabel(
            "PyQt6 ve yapay zeka API'leri kullanılarak geliştirilmiştir."
        )
        aciklama.setStyleSheet("color: #e8e0f0; font-size: 13px;")
        aciklama.setWordWrap(True)

        saglayicilar = QLabel(
            "Desteklenen sağlayıcılar: OpenAI · Anthropic · "
            "Google Gemini · xAI (Grok) · OpenRouter"
        )
        saglayicilar.setStyleSheet("color: #6b5a7a; font-size: 12px;")
        saglayicilar.setWordWrap(True)

        for w in (ad, surum, aciklama, saglayicilar):
            layout.addWidget(w)

        return grup

    # =========================================================================
    # VERİ YÜKLEME
    # =========================================================================

    def _baslangic_verilerini_yukle(self):
        """
        Widget ilk oluşturulduğunda:
        1. Bölüm 3 için app_config.json'dan varsayılanları yükler
        2. Bölüm 2 tablosunu doldurur
        3. Aktif sağlayıcıyı Bölüm 1 formuna yükler
        """
        self._varsayilanlari_yukle()
        self._kayitli_saglayicilari_yukle()
        self._aktif_saglayiciyi_forma_yukle()

    def _aktif_saglayiciyi_forma_yukle(self):
        """Aktif AI ayarını Bölüm 1 formuna doldurur."""
        aktif = self.db_manager.aktif_ai_ayar_getir()
        if not aktif:
            return

        # Sağlayıcıyı seç
        saglayici = aktif.get("saglayici", "openai")
        idx = self.saglayici_combo.findData(saglayici)
        if idx >= 0:
            self.saglayici_combo.setCurrentIndex(idx)

        # API anahtarını yükle
        self.api_key_input.setText(aktif.get("api_anahtari", ""))

        # Model seç — Tüm sağlayıcılar artık ComboBox kullanıyor
        model = aktif.get("model_adi", "")
        if saglayici == "openrouter":
            m_idx = self.model_combo.findData(model)
            if m_idx >= 0:
                self.model_combo.setCurrentIndex(m_idx)
            elif model:
                # Listede yoksa sona ekle
                self.model_combo.addItem(model, userData=model)
                self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
            # OpenRouter ekstra konfig
            ekstra = aktif.get("ekstra_konfig")
            if isinstance(ekstra, dict):
                self.site_url_input.setText(ekstra.get("site_url", ""))
                self.app_name_input.setText(ekstra.get("app_name", ""))
        else:
            m_idx = self.model_combo.findText(model)
            if m_idx >= 0:
                self.model_combo.setCurrentIndex(m_idx)

    def _kayitli_saglayicilari_yukle(self):
        """Veritabanından tüm AI ayarlarını okur ve Bölüm 2 tablosunu doldurur."""
        ayarlar = self.db_manager.tum_ai_ayarlarini_getir()
        self.saglayici_tablo.setRowCount(0)

        for i, ayar in enumerate(ayarlar):
            self.saglayici_tablo.insertRow(i)

            saglayici_kodu = ayar.get("saglayici", "")
            gorunum_adi    = SAGLAYICI_ADLAR.get(saglayici_kodu, saglayici_kodu)
            model          = ayar.get("model_adi", "")
            aktif          = bool(ayar.get("aktif", 0))

            # Sağlayıcı adı
            ad_item = QTableWidgetItem(gorunum_adi)
            ad_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.saglayici_tablo.setItem(i, 0, ad_item)

            # Model adı
            model_item = QTableWidgetItem(model)
            model_item.setForeground(QColor("#6b5a7a"))
            self.saglayici_tablo.setItem(i, 1, model_item)

            # Durum rozeti
            if aktif:
                durum_item = QTableWidgetItem("Aktif")
                durum_item.setForeground(QColor("#a0f0b0"))
                durum_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            else:
                durum_item = QTableWidgetItem("Pasif")
                durum_item.setForeground(QColor("#6b5a7a"))
            self.saglayici_tablo.setItem(i, 2, durum_item)

            # İşlem butonları
            self._tablo_islem_butonlari_ekle(i, ayar)

    def _tablo_islem_butonlari_ekle(self, satir: int, ayar: dict):
        """Tablonun İşlemler sütununa 'Etkinleştir' ve 'Sil' butonlarını ekler."""
        kapsayici = QWidget()
        kapsayici.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(kapsayici)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        saglayici_kodu = ayar.get("saglayici", "")
        aktif          = bool(ayar.get("aktif", 0))

        # Etkinleştir butonu — zaten aktifse gizle
        etkin_btn = QPushButton("  Etkinleştir")
        etkin_btn.setFixedHeight(28)
        etkin_btn.setVisible(not aktif)
        etkin_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225; color: #9b59d0;
                border: 1px solid #2d1a40; border-radius: 5px;
                padding: 2px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #9b59d0; }
        """)
        etkin_btn.clicked.connect(
            lambda checked, k=saglayici_kodu: self._saglayiciyi_etkinlestir(k)
        )

        # Sil butonu
        sil_btn = QPushButton("")
        sil_btn.setToolTip("Bu sağlayıcıyı sil")
        sil_btn.setFixedSize(30, 28)
        sil_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1225; color: #f0a0b0;
                border: 1px solid #2d1a40; border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #f0a0b0; }
        """)
        sil_btn.clicked.connect(
            lambda checked, k=saglayici_kodu: self._saglayiciyi_sil(k)
        )

        layout.addWidget(etkin_btn)
        layout.addWidget(sil_btn)
        layout.addStretch()

        self.saglayici_tablo.setCellWidget(satir, 3, kapsayici)

    # =========================================================================
    # BÖLÜM 1 — DİNAMİK FORM GÜNCELLEMELERI
    # =========================================================================

    def _saglayici_degisti(self):
        """
        Sağlayıcı combo kutusu değiştiğinde:
        - Model alanını günceller (ComboBox veya LineEdit)
        - OpenRouter ek alanlarını gösterir/gizler
        - Mevcut sağlayıcı ayarlarını forma yükler
        """
        saglayici = self.saglayici_combo.currentData()
        if not saglayici:
            return

        if saglayici == "openrouter":
            # OpenRouter: ComboBox ile popüler modeller + yenile butonu
            self.model_yigin.setCurrentIndex(0)
            self.model_etiket.setText("Model:")

            # Popüler modelleri doldur
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            populer = self.factory.get_openrouter_populer_modeller()
            for m in populer:
                self.model_combo.addItem(m["name"], userData=m["id"])
            self.model_combo.blockSignals(False)

            self.openrouter_widget.setVisible(True)
            self.openrouter_yenile_btn.setVisible(True)
            self._model_aciklamasi_guncelle(self.model_combo.currentText())
        else:
            # Diğerleri: sabit model listesi
            self.model_yigin.setCurrentIndex(0)
            self.model_etiket.setText("Model:")
            self.openrouter_widget.setVisible(False)
            self.openrouter_yenile_btn.setVisible(False)

            # Modelleri doldur
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            modeller = self.factory.get_available_models(saglayici)
            self.model_combo.addItems(modeller)
            self.model_combo.blockSignals(False)
            self._model_aciklamasi_guncelle(self.model_combo.currentText())

        # Veritabanında bu sağlayıcıya ait kayıt varsa forma yükle
        mevcut = self.db_manager.ai_ayar_getir(saglayici)
        if mevcut:
            self.api_key_input.setText(mevcut.get("api_anahtari", ""))
            model = mevcut.get("model_adi", "")
            if saglayici == "openrouter":
                # OpenRouter: ComboBox'ta model_id ile eşleşen öğeyi bul
                m_idx = self.model_combo.findData(model)
                if m_idx >= 0:
                    self.model_combo.setCurrentIndex(m_idx)
                else:
                    # Mevcut model listede yoksa sona ekle
                    self.model_combo.addItem(model, userData=model)
                    self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
                ekstra = mevcut.get("ekstra_konfig")
                if isinstance(ekstra, dict):
                    self.site_url_input.setText(ekstra.get("site_url", ""))
                    self.app_name_input.setText(ekstra.get("app_name", ""))
            else:
                m_idx = self.model_combo.findText(model)
                if m_idx >= 0:
                    self.model_combo.setCurrentIndex(m_idx)
        else:
            # Yeni sağlayıcı — alanları temizle
            self.api_key_input.clear()
            if saglayici == "openrouter":
                self.site_url_input.clear()
                self.app_name_input.clear()

        # Sağlayıcı değiştiğinde API key alanını gizli moda al ve butonu sıfırla
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.goster_gizle_btn.setChecked(False)
        self.goster_gizle_btn.setText("  Göster")

        # Durum etiketini temizle
        self._b1_durum_gizle()

    def _model_aciklamasi_guncelle(self, display_name: str):
        """Seçilen model için açıklama etiketini günceller."""
        if not hasattr(self, "model_aciklama_label"):
            return

        # Once display name ile dene
        aciklama = MODEL_ACIKLAMALARI.get(display_name, "")
        if not aciklama:
            # Yoksa model ID (userData) ile dene
            model_id = self.model_combo.currentData()
            if model_id:
                aciklama = MODEL_ACIKLAMALARI.get(model_id, "")

        self.model_aciklama_label.setText(aciklama)

    def _api_key_goster_gizle(self, goster: bool):
        """API anahtarını göster/gizle butonu."""
        if goster:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.goster_gizle_btn.setText("  Gizle")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.goster_gizle_btn.setText("  Göster")

    # =========================================================================
    # KAYDET VE ETKİNLEŞTİR
    # =========================================================================

    def _form_verilerini_oku(self) -> dict | None:
        """
        Bölüm 1 formundaki verileri okur ve doğrular.
        Geçerli veriler dict olarak döner; geçersizse None döner.
        """
        saglayici = self.saglayici_combo.currentData()
        api_key   = self.api_key_input.text().strip()

        # API anahtarı doğrulaması
        if not api_key:
            self._b1_durum_goster(
                "API anahtarı boş olamaz.", "#f0a0b0"
            )
            self.api_key_input.setFocus()
            return None

        # Model doğrulaması — Tum saglayicilar ComboBox kullaniyor
        model_id = self.model_combo.currentData()
        model_display = self.model_combo.currentText().strip()
        if not model_id and not model_display:
            self._b1_durum_goster(
                "Lütfen model seçin.", "#f0a0b0"
            )
            return None
        # OpenRouter'da userData (model id) tercih edilir; yoksa display kullanilir
        model = model_id if model_id else model_display

        # OpenRouter ekstra konfigürasyon
        ekstra_konfig = {}
        if saglayici == "openrouter":
            site_url = self.site_url_input.text().strip()
            app_name = self.app_name_input.text().strip()
            if site_url:
                ekstra_konfig["site_url"] = site_url
            if app_name:
                ekstra_konfig["app_name"] = app_name

        return {
            "saglayici":    saglayici,
            "api_key":      api_key,
            "model":        model,
            "ekstra_konfig": ekstra_konfig if ekstra_konfig else None,
        }

    def _kaydet_ve_etkinlestir(self):
        """
        Formu okur, doğrular, veritabanına kaydeder ve aktifleştirir.
        Başarıyla tamamlanınca aktif_saglayici_degisti sinyalini yayar.
        """
        veri = self._form_verilerini_oku()
        if not veri:
            return

        saglayici    = veri["saglayici"]
        api_key      = veri["api_key"]
        model        = veri["model"]
        ekstra       = veri["ekstra_konfig"]

        # Kaydet
        self.db_manager.ai_ayar_kaydet(
            saglayici=saglayici,
            model_adi=model,
            api_anahtari=api_key,
            ekstra_konfig=ekstra if ekstra else None,
        )

        # Etkinleştir
        self.db_manager.aktif_saglayici_ayarla(saglayici)

        # Tabloyu yenile
        self._kayitli_saglayicilari_yukle()

        # Sinyali yay — MainWindow translator'ı güncellesin
        self.aktif_saglayici_degisti.emit(saglayici, model, api_key, ekstra)

        self._b1_durum_goster(
            "Ayarlar kaydedildi ve etkinleştirildi.", "#a0f0b0"
        )

    # =========================================================================
    # OPENROUTER MODEL LISTESI
    # =========================================================================

    def _openrouter_modellerini_yukle(self):
        """OpenRouter API'den guncel model listesini arka planda yukler."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self._b1_durum_goster(
                "Once API anahtari girin.", "#f0a0b0"
            )
            self.api_key_input.setFocus()
            return

        if hasattr(self, "_model_worker") and self._model_worker.isRunning():
            return

        self.openrouter_yenile_btn.setEnabled(False)
        self.openrouter_yenile_btn.setText("Yukleniyor...")
        self._b1_durum_goster("Modeller API'den cekiliyor...", "#9b59d0")

        self._model_worker = OpenRouterModelListWorker(self.factory, api_key, parent=self)
        self._model_worker.basarili.connect(self._modeller_yuklendi)
        self._model_worker.basarisiz.connect(self._modeller_yuklenemedi)
        self._model_worker.start()

    def _modeller_yuklendi(self, modeller: list):
        """API'den gelen model listesini ComboBox'a yerlestirir."""
        self.openrouter_yenile_btn.setEnabled(True)
        self.openrouter_yenile_btn.setText("Listeyi Guncelle")

        # Mevcut secili modeli hatirla
        mevcut_id = self.model_combo.currentData()

        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        eklenen = 0
        for m in modeller:
            mid = m.get("id", "")
            ad = m.get("name", mid)
            if mid:
                self.model_combo.addItem(ad, userData=mid)
                eklenen += 1

        # Eski secim korunmaya calisilir
        if mevcut_id:
            idx = self.model_combo.findData(mevcut_id)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

        self.model_combo.blockSignals(False)
        self._model_aciklamasi_guncelle(self.model_combo.currentText())
        self._b1_durum_goster(
            f"{eklenen} model yuklendi.", "#a0f0b0"
        )

    def _modeller_yuklenemedi(self, hata: str):
        """Model listesi alinamadiysa populer listeye geri doner."""
        self.openrouter_yenile_btn.setEnabled(True)
        self.openrouter_yenile_btn.setText("Listeyi Guncelle")
        self._b1_durum_goster(
            f"API'ye erisilemedi, populer liste kullaniliyor. ({hata[:50]})",
            "#f0d090"
        )

    # =========================================================================
    # BAGLANTI TEST
    # =========================================================================

    def _baglantyi_test_et(self):
        """
        Formdaki değerlerle kısa bir çeviri denemesi yapar.
        İşlem BaglantiTestWorker ile arka planda çalışır — UI donmaz.
        """
        veri = self._form_verilerini_oku()
        if not veri:
            return

        # Önceki test hâlâ sürüyorsa yeni başlatma
        if hasattr(self, "_test_worker") and self._test_worker.isRunning():
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Test ediliyor...")
        self._b1_durum_goster("Test bağlantısı kuruluyor...", "#9b59d0")

        self._test_worker = BaglantiTestWorker(self.factory, veri, parent=self)
        self._test_worker.basarili.connect(self._test_basarili)
        self._test_worker.basarisiz.connect(self._test_basarisiz)
        self._test_worker.start()

    def _test_basarili(self, sonuc: str):
        """Bağlantı testi başarılı olduğunda çağrılır."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("  Bağlantıyı Test Et")
        self._b1_durum_goster("Bağlantı testi başarılı.", "#a0f0b0")
        QMessageBox.information(
            self,
            "Bağlantı Başarılı",
            f"Bağlantı testi başarılı!\n\nTest yanıtı: {sonuc}",
        )

    def _test_basarisiz(self, hata_mesaji: str):
        """Bağlantı testi başarısız olduğunda çağrılır."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("  Bağlantıyı Test Et")
        self._b1_durum_goster("Bağlantı testi başarısız.", "#f0a0b0")
        QMessageBox.critical(
            self,
            "Bağlantı Hatası",
            f"Bağlantı testi başarısız:\n\n{hata_mesaji}",
        )

    # =========================================================================
    # TABLO İŞLEMLERİ
    # =========================================================================

    def _saglayiciyi_etkinlestir(self, saglayici_kodu: str):
        """
        Tablodan 'Etkinleştir' butonuna basıldığında çağrılır.
        Sağlayıcıyı aktif yapar ve sinyali yayar.
        """
        self.db_manager.aktif_saglayici_ayarla(saglayici_kodu)
        self._kayitli_saglayicilari_yukle()

        # Aktif ayarı oku ve sinyali yay
        ayar = self.db_manager.ai_ayar_getir(saglayici_kodu)
        if ayar:
            ekstra = ayar.get("ekstra_konfig")
            self.aktif_saglayici_degisti.emit(
                saglayici_kodu,
                ayar.get("model_adi", ""),
                ayar.get("api_anahtari", ""),
                ekstra,
            )

    def _saglayiciyi_sil(self, saglayici_kodu: str):
        """Silme onayı alır; onaylanırsa sağlayıcıyı veritabanından siler."""
        gorunum_adi = SAGLAYICI_ADLAR.get(saglayici_kodu, saglayici_kodu)

        onay = QMessageBox(self)
        onay.setWindowTitle("Sağlayıcıyı Sil")
        onay.setIcon(QMessageBox.Icon.Warning)
        onay.setText(
            f"'{gorunum_adi}' sağlayıcı ayarları silinecek.\n"
            "Devam edilsin mi?"
        )
        evet_btn  = onay.addButton("Evet, Sil",  QMessageBox.ButtonRole.DestructiveRole)
        hayir_btn = onay.addButton("Hayır",       QMessageBox.ButtonRole.RejectRole)
        onay.setDefaultButton(hayir_btn)
        onay.exec()

        if onay.clickedButton() == evet_btn:
            self.db_manager.ai_ayar_sil(saglayici_kodu)
            self._kayitli_saglayicilari_yukle()

    # =========================================================================
    # BÖLÜM 3 — VARSAYILANLAR
    # =========================================================================

    def _varsayilanlari_yukle(self):
        """app_config.json'dan varsayılan dil ayarlarını yükler."""
        try:
            if os.path.exists(CONFIG_DOSYASI):
                with open(CONFIG_DOSYASI, encoding="utf-8") as f:
                    konfig = json.load(f)
                kaynak = konfig.get("varsayilan_kaynak_dil", "Japonca")
                hedef  = konfig.get("varsayilan_hedef_dil",  "Türkçe")

                k_idx = self.varsayilan_kaynak_combo.findText(kaynak)
                if k_idx >= 0:
                    self.varsayilan_kaynak_combo.setCurrentIndex(k_idx)

                h_idx = self.varsayilan_hedef_combo.findText(hedef)
                if h_idx >= 0:
                    self.varsayilan_hedef_combo.setCurrentIndex(h_idx)
        except Exception as hata:
            print(f"[Ayarlar] Konfig yüklenemedi: {hata}")

    def _varsayilanlari_kaydet(self):
        """Seçilen varsayılan dilleri app_config.json'a yazar."""
        try:
            konfig = {
                "varsayilan_kaynak_dil": self.varsayilan_kaynak_combo.currentText(),
                "varsayilan_hedef_dil":  self.varsayilan_hedef_combo.currentText(),
            }
            with open(CONFIG_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(konfig, f, ensure_ascii=False, indent=2)

            self._b3_durum_goster("Varsayılanlar kaydedildi.", "#a0f0b0")
        except Exception as hata:
            self._b3_durum_goster(f"Kaydetme hatası: {hata}", "#f0a0b0")

    # =========================================================================
    # DURUM ETİKETİ YARDIMCILARI
    # =========================================================================

    def _b1_durum_goster(self, mesaj: str, renk: str):
        """Bölüm 1 durum etiketini gösterir."""
        self.b1_durum_label.setText(mesaj)
        self.b1_durum_label.setStyleSheet(
            f"color: {renk}; font-size: 12px; padding: 4px 6px;"
        )
        self.b1_durum_label.setVisible(True)

    def _b1_durum_gizle(self):
        """Bölüm 1 durum etiketini gizler."""
        self.b1_durum_label.setText("")
        self.b1_durum_label.setVisible(False)

    def _b3_durum_goster(self, mesaj: str, renk: str):
        """Bölüm 3 durum etiketini gösterir."""
        self.b3_durum_label.setText(mesaj)
        self.b3_durum_label.setStyleSheet(
            f"color: {renk}; font-size: 12px; padding: 2px 4px;"
        )
        self.b3_durum_label.setVisible(True)

    # =========================================================================
    # STİL YARDIMCILARI
    # =========================================================================

    def _grup_stili(self) -> str:
        return """
            QGroupBox {
                background-color: #130c20;
                border: 1px solid #1a1225;
                border-radius: 8px;
                margin-top: 14px;
                font-weight: 700;
                font-size: 13px;
                color: #9b59d0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px; top: -1px;
                padding: 0 8px;
                color: #9b59d0;
                background-color: #130c20;
            }
        """

    def _input_stili(self) -> str:
        return """
            QLineEdit {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 22px;
            }
            QLineEdit:focus { border-color: #9b59d0; background-color: #201528; }
            QLineEdit:read-only { background-color: #0f0a1a; color: #6b5a7a; }
        """

    def _combo_stili(self) -> str:
        return """
            QComboBox {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 22px;
            }
            QComboBox:focus { border-color: #9b59d0; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #9b59d0;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1225;
                color: #e8e0f0;
                border: 1px solid #3d2d55;
                border-radius: 4px;
                selection-background-color: #2d1a40;
                selection-color: #9b59d0;
                outline: none;
            }
        """

    def _birincil_buton_stili(self) -> str:
        return """
            QPushButton {
                background-color: #9b59d0; color: #0f0a1a;
                border: none; border-radius: 6px;
                padding: 7px 18px; font-weight: 700; font-size: 13px;
            }
            QPushButton:hover { background-color: #b06ad9; }
            QPushButton:disabled { background-color: #2d1a40; color: #6b5a7a; }
        """

    def _ikincil_buton_stili(self) -> str:
        return """
            QPushButton {
                background-color: #1a1225; color: #e8e0f0;
                border: 1px solid #3d2d55; border-radius: 6px;
                padding: 7px 14px; font-size: 12px;
            }
            QPushButton:hover { background-color: #2d1a40; border-color: #9b59d0; }
            QPushButton:disabled { color: #6b5a7a; border-color: #2d1a40; }
        """


# =============================================================================
# HIZLI TEST — python settings_widget.py ile çalıştırılabilir
# =============================================================================

if __name__ == "__main__":
    from database import DatabaseManager
    from translator import TranslatorFactory

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #0f0a1a;
            color: #e8e0f0;
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QScrollArea { background-color: #0f0a1a; }
    """)

    db = DatabaseManager()

    def sinyal_alindi(saglayici, model, api_key, ekstra):
        print(f"[Sinyal] saglayici={saglayici}, model={model}, ekstra={ekstra}")

    widget = SettingsWidget(db_manager=db, translator_factory_class=TranslatorFactory)
    widget.aktif_saglayici_degisti.connect(sinyal_alindi)
    widget.setWindowTitle("Ayarlar - Test")
    widget.resize(860, 720)
    widget.show()

    sys.exit(app.exec())