"""
Novel Çevirmen - Seri Oluşturma Sihirbazı
QStackedWidget tabanlı adım adım seri oluşturma diyaloğu.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QComboBox, QFormLayout, QFileDialog, QMessageBox,
    QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt

from database import DatabaseManager


# =============================================================================
# SERİ OLUŞTURMA SİHİRBAZI DİYALOĞU
# =============================================================================

class SeriSihirbazi(QDialog):
    """
    Adım adım seri oluşturma sihirbazı.

    QStackedWidget kullanarak her adım ayrı bir kalıcı widget içinde tutulur;
    adımlar arasında geçiş yapılırken widget referansları kaybolmaz.

    Adım 1: Seri adı ve dil seçimi
    Adım 2: İlk bölüm metnini yapıştır / TXT dosyası seç
    Adım 3: Özet ve oluştur

    Genel kullanım:
        sihirbaz = SeriSihirbazi(db=db_manager, parent=self)
        if sihirbaz.exec() == QDialog.DialogCode.Accepted:
            seri_id = sihirbaz.olusturulan_seri_id
    """

    _KAYNAK_DILLER = [
        "Japonca", "Çince", "Korece", "İngilizce", "Almanca",
        "Fransızca", "İspanyolca", "Rusça", "Arapça", "Diğer",
    ]
    _HEDEF_DILLER = ["Türkçe", "İngilizce", "Almanca", "Fransızca", "Diğer"]

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.olusturulan_seri_id: int | None = None
        self.setWindowTitle("Yeni Seri Sihirbazı")
        self.setMinimumSize(560, 460)
        self.setModal(True)
        self._arayuz_olustur()

    # -------------------------------------------------------------------------
    # ARAYÜZ KURULUMU
    # -------------------------------------------------------------------------

    def _arayuz_olustur(self):
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(24, 20, 24, 16)
        ana_layout.setSpacing(12)

        # ── İlerleme göstergesi ──────────────────────────────────────────────
        ilerleme_widget = QWidget()
        ilerleme_layout = QHBoxLayout(ilerleme_widget)
        ilerleme_layout.setContentsMargins(0, 0, 0, 0)
        ilerleme_layout.setSpacing(8)

        self._adim_label = QLabel("Adım 1 / 3")
        self._adim_label.setStyleSheet(
            "color: #9b59d0; font-size: 13px; font-weight: 700;"
        )

        self._baslik_label = QLabel("Seri Bilgileri")
        self._baslik_label.setStyleSheet(
            "color: #e8e0f0; font-size: 15px; font-weight: 700;"
        )

        ilerleme_layout.addWidget(self._adim_label)
        ilerleme_layout.addWidget(QLabel("—"))
        ilerleme_layout.addWidget(self._baslik_label)
        ilerleme_layout.addStretch()
        ana_layout.addWidget(ilerleme_widget)

        # İnce ayırıcı
        ayirici = QFrame()
        ayirici.setFrameShape(QFrame.Shape.HLine)
        ayirici.setStyleSheet("background-color: #2d1a40;")
        ayirici.setFixedHeight(1)
        ana_layout.addWidget(ayirici)

        # ── QStackedWidget: her adım ayrı bir widget ─────────────────────────
        self._stack = QStackedWidget()
        self._adim1_widget = self._adim1_olustur()
        self._adim2_widget = self._adim2_olustur()
        self._adim3_widget = self._adim3_olustur()
        self._stack.addWidget(self._adim1_widget)  # index 0
        self._stack.addWidget(self._adim2_widget)  # index 1
        self._stack.addWidget(self._adim3_widget)  # index 2
        self._stack.setCurrentIndex(0)
        ana_layout.addWidget(self._stack, stretch=1)

        # ── Alt buton satırı ─────────────────────────────────────────────────
        alt_layout = QHBoxLayout()
        alt_layout.setSpacing(8)
        alt_layout.addStretch()

        self._iptal_btn = QPushButton("İptal")
        self._iptal_btn.setObjectName("ikincilButon")
        self._iptal_btn.clicked.connect(self.reject)

        self._geri_btn = QPushButton("← Geri")
        self._geri_btn.setEnabled(False)
        self._geri_btn.clicked.connect(self._onceki_adim)

        self._ileri_btn = QPushButton("İleri →")
        self._ileri_btn.setDefault(True)
        self._ileri_btn.clicked.connect(self._sonraki_adim)

        for btn in (self._iptal_btn, self._geri_btn, self._ileri_btn):
            btn.setMinimumWidth(90)
            btn.setFixedHeight(36)

        alt_layout.addWidget(self._iptal_btn)
        alt_layout.addWidget(self._geri_btn)
        alt_layout.addWidget(self._ileri_btn)
        ana_layout.addLayout(alt_layout)

    # -------------------------------------------------------------------------
    # ADIM WİDGET'LARI — bir kez oluşturulur, stack içinde kalır
    # -------------------------------------------------------------------------

    def _adim1_olustur(self) -> QWidget:
        """Adım 1: Seri adı, kaynak/hedef dil ve açıklama formu."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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

        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _adim2_olustur(self) -> QWidget:
        """Adım 2: İlk bölüm metni (isteğe bağlı)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        aciklama = QLabel(
            "İlk bölüm metnini buraya yapıştırabilir ya da TXT dosyası seçebilirsiniz.\n"
            "Bu adım isteğe bağlıdır; daha sonra da bölüm eklenebilir."
        )
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet("color: #6b5a7a; font-size: 11px;")
        layout.addWidget(aciklama)

        btn_layout = QHBoxLayout()
        dosya_btn = QPushButton("TXT Dosyası Seç...")
        dosya_btn.clicked.connect(self._txt_dosyasi_sec)
        btn_layout.addWidget(dosya_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._bolum_metin = QTextEdit()
        self._bolum_metin.setPlaceholderText("Bölüm metnini buraya yapıştırın...")
        layout.addWidget(self._bolum_metin, stretch=1)

        self._bolum_baslik = QLineEdit()
        self._bolum_baslik.setPlaceholderText("Bölüm başlığı (örn. Bölüm 1)")
        self._bolum_baslik.setText("Bölüm 1")
        self._bolum_baslik.setFixedHeight(34)
        layout.addWidget(self._bolum_baslik)

        return widget

    def _adim3_olustur(self) -> QWidget:
        """Adım 3: Özet ekranı — gösterim sırasında güncellenir."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # İçerik gösterim alanı — _adim3_guncelle() tarafından doldurulur
        self._ozet_label = QLabel()
        self._ozet_label.setTextFormat(Qt.TextFormat.RichText)
        self._ozet_label.setStyleSheet("color: #e8e0f0; font-size: 13px; line-height: 1.7;")
        self._ozet_label.setWordWrap(True)
        layout.addWidget(self._ozet_label)

        self._bolum_info_label = QLabel()
        self._bolum_info_label.setStyleSheet("color: #a0f0b0; font-size: 11px;")
        self._bolum_info_label.setVisible(False)
        layout.addWidget(self._bolum_info_label)

        layout.addStretch()
        return widget

    def _adim3_guncelle(self):
        """Adım 3 ekranına geçilmeden önce özet içeriğini tazeler."""
        ad = self._ad_input.text().strip()
        kaynak_dil = self._kaynak_combo.currentText()
        hedef_dil = self._hedef_combo.currentText()
        aciklama = self._aciklama_input.toPlainText().strip()

        ozet_html = (
            f"<b>Seri Adı:</b> {ad or '(girilmedi)'}<br>"
            f"<b>Kaynak Dil:</b> {kaynak_dil}<br>"
            f"<b>Hedef Dil:</b> {hedef_dil}<br>"
        )
        if aciklama:
            ozet_html += f"<b>Açıklama:</b> {aciklama}<br>"

        self._ozet_label.setText(ozet_html)

        metin = self._bolum_metin.toPlainText().strip()
        if metin:
            self._bolum_info_label.setText(f"İlk bölüm: {len(metin):,} karakter eklenecek.")
            self._bolum_info_label.setVisible(True)
        else:
            self._bolum_info_label.setVisible(False)

    # -------------------------------------------------------------------------
    # GEZINME
    # -------------------------------------------------------------------------

    def _goster(self, adim: int):
        """Belirtilen adıma geçer; başlık ve buton metnini günceller."""
        self._stack.setCurrentIndex(adim)
        self._geri_btn.setEnabled(adim > 0)

        basliklar = [
            ("Adım 1 / 3", "Seri Bilgileri"),
            ("Adım 2 / 3", "İlk Bölüm (İsteğe Bağlı)"),
            ("Adım 3 / 3", "Özet ve Oluştur"),
        ]
        self._adim_label.setText(basliklar[adim][0])
        self._baslik_label.setText(basliklar[adim][1])

        if adim == 2:
            self._ileri_btn.setText("✓ Oluştur")
            self._adim3_guncelle()
        else:
            self._ileri_btn.setText("İleri →")

    def _sonraki_adim(self):
        adim = self._stack.currentIndex()

        if adim == 0:
            # Adım 1 doğrulaması
            ad = self._ad_input.text().strip()
            if not ad:
                QMessageBox.warning(self, "Eksik Bilgi", "Lütfen seri adını girin.")
                self._ad_input.setFocus()
                return
            self._goster(1)

        elif adim == 1:
            self._goster(2)

        elif adim == 2:
            self._olustur()

    def _onceki_adim(self):
        adim = self._stack.currentIndex()
        if adim > 0:
            self._goster(adim - 1)

    # -------------------------------------------------------------------------
    # TXT DOSYASI SEÇİMİ (Adım 2)
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # SERİ OLUŞTURMA (Adım 3 → "Oluştur")
    # -------------------------------------------------------------------------

    def _olustur(self):
        """Widget referansları stack içinde yaşadığından doğrudan okunur."""
        ad = self._ad_input.text().strip()
        kaynak_dil = self._kaynak_combo.currentText()
        hedef_dil = self._hedef_combo.currentText()
        aciklama = self._aciklama_input.toPlainText().strip() or None

        if not ad:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen seri adını girin.")
            self._goster(0)
            self._ad_input.setFocus()
            return

        try:
            seri_id = self.db.seri_olustur(
                baslik=ad,
                kaynak_dil=kaynak_dil,
                hedef_dil=hedef_dil,
                aciklama=aciklama,
            )

            # İlk bölüm ekle (isteğe bağlı)
            metin = self._bolum_metin.toPlainText().strip()
            if metin:
                bolum_baslik = self._bolum_baslik.text().strip() or "Bölüm 1"
                self.db.bolum_olustur(
                    seri_id=seri_id,
                    bolum_no=1,
                    bolum_baslik=bolum_baslik,
                    orijinal_metin=metin,
                )

            self.olusturulan_seri_id = seri_id
            self.accept()

        except Exception as hata:
            QMessageBox.critical(self, "Hata", f"Seri oluşturulamadı:\n{hata}")