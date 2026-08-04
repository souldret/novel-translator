"""
Novel Çevirmen — Çeviri kalitesi araçları (UI diyalogları).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextBrowser,
    QAbstractItemView, QMessageBox,
)

from text_utils import sozluk_uyum_kontrolu, metin_diff_html


class SozlukUyumDiyalogu(QDialog):
    """Çeviride eksik sözlük karşılıklarını listeler."""

    def __init__(self, ceviri: str, sozluk_terimleri: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sözlük Uyum Kontrolü")
        self.setMinimumSize(560, 420)
        self.setModal(True)

        sonuc = sozluk_uyum_kontrolu(ceviri, sozluk_terimleri)
        self.sonuc = sonuc

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        ozet = QLabel(
            f"Kontrol edilen: {sonuc['toplam']}  ·  "
            f"Uyumlu: {len(sonuc['uyumlu'])}  ·  "
            f"Eksik: {len(sonuc['eksik'])}"
        )
        ozet.setStyleSheet("color:#c9a8e8; font-weight:700; font-size:13px;")
        layout.addWidget(ozet)

        if not sonuc["eksik"]:
            ok = QLabel("Tüm sözlük karşılıkları çeviride bulundu.")
            ok.setStyleSheet("color:#a0f0b0; font-size:13px;")
            layout.addWidget(ok)
        else:
            tablo = QTableWidget(len(sonuc["eksik"]), 3)
            tablo.setHorizontalHeaderLabels(["Orijinal", "Beklenen Çeviri", "Kategori"])
            tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            for i, t in enumerate(sonuc["eksik"]):
                tablo.setItem(i, 0, QTableWidgetItem(t.get("orijinal_terim", "")))
                tablo.setItem(i, 1, QTableWidgetItem(t.get("cevrilmis_terim", "")))
                tablo.setItem(i, 2, QTableWidgetItem(t.get("kategori", "")))
            layout.addWidget(tablo)

        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(kapat)
        layout.addLayout(row)


class DiffDiyalogu(QDialog):
    """Önceki ve yeni çeviri arasındaki farkı gösterir."""

    def __init__(self, onceki: str, yeni: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Çeviri Farkı (Diff)")
        self.setMinimumSize(720, 520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)

        baslik = QLabel("Önceki çeviri ↔ Güncel çeviri")
        baslik.setStyleSheet("color:#c9a8e8; font-weight:700; font-size:13px;")
        layout.addWidget(baslik)

        tarayici = QTextBrowser()
        tarayici.setOpenExternalLinks(False)
        tarayici.setHtml(metin_diff_html(onceki or "", yeni or ""))
        layout.addWidget(tarayici, stretch=1)

        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(kapat)
        layout.addLayout(row)


def sozluk_uyum_goster(parent, ceviri: str, sozluk_terimleri: list) -> dict:
    """Diyaloğu açar ve sonuç dict'ini döndürür."""
    if not sozluk_terimleri:
        QMessageBox.information(
            parent, "Sözlük Uyum",
            "Kontrol edilecek sözlük terimi yok."
        )
        return {"toplam": 0, "uyumlu": [], "eksik": []}
    dlg = SozlukUyumDiyalogu(ceviri, sozluk_terimleri, parent=parent)
    dlg.exec()
    return dlg.sonuc


def diff_goster(parent, onceki: str, yeni: str) -> None:
    if not (onceki or "").strip() and not (yeni or "").strip():
        QMessageBox.information(parent, "Diff", "Karşılaştırılacak metin yok.")
        return
    DiffDiyalogu(onceki, yeni, parent=parent).exec()
