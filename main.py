"""
Novel Çevirmen — Uygulama Giriş Noktası
PyQt6 tabanlı Türkçe roman çeviri masaüstü uygulaması.

Kullanım:
    python main.py
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon


# =============================================================================
# LOGGING YAPILANDIRMASI
# Uygulama başlangıcında bir kez çalışır; log dosyası uygulama klasöründe oluşur.
# =============================================================================

def _logging_kur():
    log_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novel_cevirmen.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  —  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_yolu, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("novel_cevirmen").info("Uygulama başlatıldı.")


_logging_kur()


# =============================================================================
# GLOBAL KARANLIK TEMA — Violet Dream
# Modern mor/violet tonlarıyla zarif karanlık tema
# =============================================================================

GLOBAL_TEMA = """

/* ============================================================
   TEMEL WIDGET'LAR
   ============================================================ */

QApplication, QMainWindow, QWidget {
    background-color: #0f0a1a;
    color: #e8e0f0;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", "Arial", sans-serif;
    font-size: 13px;
}

QDialog {
    background-color: #0f0a1a;
    color: #e8e0f0;
}

/* ============================================================
   BUTONLAR
   ============================================================ */

QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9b59d0, stop:1 #7b3cb5);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b06ad9, stop:1 #8f4cc9);
    color: #ffffff;
}

QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b3cb5, stop:1 #6b2ca5);
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #2a2035;
    color: #6b5a7a;
    border: none;
}

QPushButton:flat {
    background-color: transparent;
    border: none;
    color: #c9a8e8;
}

QPushButton:flat:hover {
    background-color: #1f1530;
    color: #dcc0f0;
}

/* ============================================================
   METİN GİRİŞLERİ
   ============================================================ */

QLineEdit {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: #7b3cb5;
    selection-color: #ffffff;
    min-height: 20px;
}

QLineEdit:focus {
    border: 1px solid #9b59d0;
    background-color: #201528;
}

QLineEdit:disabled {
    background-color: #15101f;
    color: #6b5a7a;
    border-color: #2a2035;
}

QLineEdit:read-only {
    background-color: #120d1a;
    color: #6b5a7a;
}

QTextEdit {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #7b3cb5;
    selection-color: #ffffff;
}

QTextEdit:focus {
    border: 1px solid #9b59d0;
    background-color: #201528;
}

QPlainTextEdit {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #7b3cb5;
    selection-color: #ffffff;
}

QPlainTextEdit:focus {
    border: 1px solid #9b59d0;
    background-color: #201528;
}

/* ============================================================
   AÇILIR LİSTE (COMBOBOX)
   ============================================================ */

QComboBox {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 20px;
    min-width: 100px;
}

QComboBox:hover {
    border-color: #9b59d0;
}

QComboBox:focus {
    border: 1px solid #9b59d0;
    background-color: #201528;
}

QComboBox:disabled {
    background-color: #15101f;
    color: #6b5a7a;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #c9a8e8;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 6px;
    outline: none;
    selection-background-color: #2d1a40;
    selection-color: #dcc0f0;
}

QComboBox QAbstractItemView::item {
    padding: 8px 14px;
    border-radius: 6px;
    min-height: 26px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #2d1a40;
    color: #dcc0f0;
}

/* ============================================================
   LİSTE WIDGET'I
   ============================================================ */

QListWidget {
    background-color: #0f0a1a;
    color: #e8e0f0;
    border: none;
    outline: none;
    padding: 4px;
}

QListWidget::item {
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 6px;
}

QListWidget::item:selected {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2d1a40, stop:1 #1f1530);
    color: #e8e0f0;
    border-left: 4px solid #9b59d0;
    padding-left: 8px;
}

QListWidget::item:hover:!selected {
    background-color: #1a1225;
}

/* ============================================================
   TABLO WIDGET'I
   ============================================================ */

QTableWidget, QTableView {
    background-color: #0f0a1a;
    alternate-background-color: #130c20;
    color: #e8e0f0;
    border: 1px solid #2d1a40;
    border-radius: 10px;
    gridline-color: #2d1a40;
    outline: none;
    selection-background-color: #2d1a40;
    selection-color: #e8e0f0;
}

QTableWidget::item, QTableView::item {
    padding: 6px 12px;
    border: none;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #2d1a40;
    color: #e8e0f0;
}

QHeaderView {
    background-color: #0a0612;
    border: none;
}

QHeaderView::section {
    background-color: #0a0612;
    color: #c9a8e8;
    border: none;
    border-bottom: 2px solid #2d1a40;
    border-right: 1px solid #1a1225;
    padding: 8px 12px;
    font-weight: 700;
    font-size: 12px;
}

QHeaderView::section:last {
    border-right: none;
}

QHeaderView::section:hover {
    background-color: #130c20;
}

/* ============================================================
   SEKME WIDGET'I
   ============================================================ */

QTabWidget::pane {
    background-color: #0f0a1a;
    border: none;
    border-top: 2px solid #2d1a40;
}

QTabWidget::tab-bar {
    left: 0px;
    alignment: left;
}

QTabBar {
    background-color: #0a0612;
}

QTabBar::tab {
    background-color: #0a0612;
    color: #6b5a7a;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 12px 24px;
    min-width: 120px;
    font-size: 13px;
    font-weight: 500;
}

QTabBar::tab:selected {
    color: #dcc0f0;
    border-bottom: 2px solid #9b59d0;
    background-color: #0f0a1a;
    font-weight: 700;
}

QTabBar::tab:hover:!selected {
    color: #c9a8e8;
    background-color: #130c20;
    border-bottom: 2px solid #3d2d55;
}



/* ============================================================
   KAYDIRMA ÇUBUKLARI
   ============================================================ */

QScrollBar:vertical {
    background-color: #0f0a1a;
    width: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7b3cb5, stop:1 #9b59d0);
    border-radius: 6px;
    min-height: 30px;
    margin: 3px;
}

QScrollBar::handle:vertical:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8f4cc9, stop:1 #b06ad9);
}

QScrollBar::handle:vertical:pressed {
    background-color: #6b2ca5;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background-color: #0f0a1a;
    height: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7b3cb5, stop:1 #9b59d0);
    border-radius: 6px;
    min-width: 30px;
    margin: 3px;
}

QScrollBar::handle:horizontal:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8f4cc9, stop:1 #b06ad9);
}

QScrollBar::handle:horizontal:pressed {
    background-color: #6b2ca5;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
    border: none;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

/* ============================================================
   İLERLEME ÇUBUĞU
   ============================================================ */

QProgressBar {
    background-color: #2d1a40;
    border: none;
    border-radius: 6px;
    text-align: center;
    color: transparent;
    min-height: 10px;
    max-height: 14px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9b59d0, stop:1 #c9a8e8);
    border-radius: 6px;
}

/* ============================================================
   SAYI GİRİŞİ (SPINBOX)
   ============================================================ */

QSpinBox, QDoubleSpinBox {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #9b59d0;
    background-color: #201528;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: #3d2d55;
    border: none;
    border-top-right-radius: 6px;
    width: 22px;
    image: none;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #3d2d55;
    border: none;
    border-bottom-right-radius: 6px;
    width: 22px;
    image: none;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #9b59d0;
}

QSpinBox::up-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #c9a8e8;
    width: 0; height: 0;
}

QSpinBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #c9a8e8;
    width: 0; height: 0;
}

/* ============================================================
   GRUP KUTUSU
   ============================================================ */

QGroupBox {
    background-color: #130c20;
    border: 1px solid #2d1a40;
    border-radius: 12px;
    margin-top: 18px;
    padding: 14px 10px 12px 10px;
    font-weight: 700;
    font-size: 13px;
    color: #c9a8e8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: -2px;
    padding: 0 10px;
    color: #c9a8e8;
    background-color: #130c20;
    border-radius: 4px;
}

QGroupBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid #3d2d55;
    background-color: #1a1225;
}

QGroupBox::indicator:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9b59d0, stop:1 #7b3cb5);
    border-color: #9b59d0;
}

/* ============================================================
   BÖLÜCÜ
   ============================================================ */

QSplitter {
    background-color: transparent;
}

QSplitter::handle {
    background-color: #2d1a40;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #9b59d0;
}

QSplitterHandle {
    background-color: #2d1a40;
}

/* ============================================================
   MENÜ ÇUBUĞU
   ============================================================ */

QMenuBar {
    background-color: #0a0612;
    color: #e8e0f0;
    border-bottom: 1px solid #2d1a40;
    padding: 4px 8px;
    spacing: 4px;
}

QMenuBar::item {
    background: transparent;
    color: #e8e0f0;
    padding: 6px 14px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #2d1a40;
    color: #dcc0f0;
}

QMenuBar::item:pressed {
    background-color: #3d2d55;
    color: #dcc0f0;
}

/* ============================================================
   MENÜ
   ============================================================ */

QMenu {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 10px;
    padding: 8px 6px;
}

QMenu::item {
    background: transparent;
    color: #e8e0f0;
    padding: 8px 32px 8px 16px;
    border-radius: 6px;
    margin: 2px 6px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #2d1a40;
    color: #dcc0f0;
}

QMenu::item:disabled {
    color: #6b5a7a;
}

QMenu::separator {
    height: 1px;
    background-color: #3d2d55;
    margin: 6px 12px;
}

QMenu::icon {
    padding-left: 10px;
}

/* ============================================================
   MESAJ KUTUSU
   ============================================================ */

QMessageBox {
    background-color: #0f0a1a;
    color: #e8e0f0;
}

QMessageBox QLabel {
    color: #e8e0f0;
    font-size: 13px;
    min-width: 280px;
}

QMessageBox QPushButton {
    min-width: 90px;
    padding: 8px 20px;
}

/* ============================================================
   ONAY KUTUSU
   ============================================================ */

QCheckBox {
    color: #e8e0f0;
    spacing: 10px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid #3d2d55;
    background-color: #1a1225;
}

QCheckBox::indicator:hover {
    border-color: #9b59d0;
}

QCheckBox::indicator:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9b59d0, stop:1 #7b3cb5);
    border-color: #9b59d0;
    image: none;
}

QCheckBox::indicator:checked:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b06ad9, stop:1 #8f4cc9);
}

QCheckBox:disabled {
    color: #6b5a7a;
}

/* ============================================================
   ETİKET
   ============================================================ */

QLabel {
    color: #e8e0f0;
    background: transparent;
}

QLabel:disabled {
    color: #6b5a7a;
}

/* ============================================================
   ARAÇ İPUCU
   ============================================================ */

QToolTip {
    background-color: #1a1225;
    color: #e8e0f0;
    border: 1px solid #3d2d55;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}

/* ============================================================
   KAYDIRMA ALANI
   ============================================================ */

QScrollArea {
    background-color: #0f0a1a;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #0f0a1a;
}

/* ============================================================
   ÇERÇEVE
   ============================================================ */

QFrame {
    background-color: transparent;
}

QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    background-color: #2d1a40;
    border: none;
    max-height: 1px;
    max-width: 1px;
}

/* ============================================================
   DURUM ÇUBUĞU
   ============================================================ */

QStatusBar {
    background-color: #0a0612;
    color: #6b5a7a;
    border-top: 1px solid #2d1a40;
    font-size: 11px;
}

QStatusBar::item {
    border: none;
}

/* ============================================================
   OBJECT NAME İLE ATANAN ÖZEL STİLLER
   ============================================================ */

/* Sol kenar çubuğu */
QWidget#solPanel {
    background-color: #0a0612;
    border-right: 1px solid #2d1a40;
}

/* Ayırıcı çizgi */
QFrame#ayiriciCizgi {
    background-color: #2d1a40;
    max-height: 1px;
    min-height: 1px;
}

/* Başlık / alt başlık etiketleri */
QLabel#baslikLabel {
    color: #dcc0f0;
    font-size: 16px;
    font-weight: 700;
    background: transparent;
}
QLabel#altBaslikLabel {
    color: #6b5a7a;
    font-size: 11px;
    background: transparent;
}
QLabel#bolumBaslikLabel {
    color: #8b7aaa;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    background: transparent;
}
QLabel#placeholderLabel {
    color: #6b5a7a;
    font-size: 14px;
}
QLabel#hataLabel {
    color: #f0a0b0;
    font-size: 12px;
}

/* AI durum etiketi */
QLabel#aiDurumLabel {
    font-size: 11px;
    padding: 6px 10px;
    border-radius: 6px;
    font-weight: 600;
}
QLabel#aiDurumLabel[durum="pasif"] {
    color: #6b5a7a;
    background-color: #130c20;
    border: 1px solid #2d1a40;
}
QLabel#aiDurumLabel[durum="uyari"] {
    color: #f0d090;
    background-color: #1a1505;
    border: 1px solid #3d3520;
}
QLabel#aiDurumLabel[durum="hata"] {
    color: #f0a0b0;
    background-color: #1a0a10;
    border: 1px solid #4a2020;
}
QLabel#aiDurumLabel[durum="basarili"] {
    color: #a0f0b0;
    background-color: #0a1a0f;
    border: 1px solid #204a20;
}

/* Tehlikeli buton */
QPushButton#tehlikeliButon {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d05070, stop:1 #b04060);
    color: #ffffff;
}
QPushButton#tehlikeliButon:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e06080, stop:1 #c05070);
}

/* İkincil buton */
QPushButton#ikincilButon {
    background-color: #2d1a40;
    color: #c9a8e8;
}
QPushButton#ikincilButon:hover {
    background-color: #3d2d55;
    color: #dcc0f0;
}

/* Sözlük bölümü başlık etiketi */
QLabel#sozlukBaslikLabel {
    color: #c9a8e8;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}

"""


# =============================================================================
# GİRİŞ NOKTASI
# =============================================================================

def main():
    """
    Novel Çevirmen uygulamasını başlatır.
    
    Sıra:
    1. QApplication oluştur
    2. Global temayı uygula
    3. Uygulama fontunu ayarla
    4. Simgeyi yükle (varsa)
    5. MainWindow oluştur ve göster
    6. Olay döngüsünü başlat
    """

    # ── 1. QApplication ───────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("Novel Çevirmen")
    app.setApplicationDisplayName("Novel Çevirmen")
    app.setOrganizationName("NovelCevirmen")
    app.setOrganizationDomain("novelcevirmen.local")

    # ── 2. Global tema — MainWindow oluşturulmadan önce uygulanmalı ───────
    app.setStyleSheet(GLOBAL_TEMA)

    # ── 3. Uygulama fontu ────────────────────────────────────────────────
    # Windows için Segoe UI, diğer platformlarda sistem varsayılanına düşer
    if sys.platform == "win32":
        font = QFont("Segoe UI", 10)
    elif sys.platform == "darwin":
        font = QFont("SF Pro Text", 13)
    else:
        # Linux ve diğerleri
        font = QFont("Ubuntu", 10)
        if not font.exactMatch():
            font = QFont()
            font.setPointSize(10)
    app.setFont(font)

    # ── 4. Uygulama simgesi (varsa) ───────────────────────────────────────
    # icon.png dosyası yoksa hata vermeden devam eder
    try:
        simge_yolu = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png"
        )
        if not os.path.exists(simge_yolu):
            # assets/ klasörü yoksa doğrudan uygulama kök dizininde ara
            simge_yolu = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "icon.png"
            )
        if os.path.exists(simge_yolu):
            app.setWindowIcon(QIcon(simge_yolu))
    except Exception as simge_hata:
        # Simge yüklenemezse sessizce devam et
        print(f"[Başlangıç] Simge yüklenemedi: {simge_hata}")

    # ── 5. Ana pencereyi oluştur ─────────────────────────────────────────
    # MainWindow burada import ediliyor; böylece QApplication hazır olmadan
    # PyQt6 widget'ı oluşturulmaz (platform uyarılarını önler).
    from main_window import MainWindow

    pencere = MainWindow()
    pencere.show()

    # ── 6. Olay döngüsünü başlat ─────────────────────────────────────────
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
