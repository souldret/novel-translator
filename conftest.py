"""
pytest konfigürasyonu.
PyQt6 QApplication gerektiren testler için fixture.
"""
import sys
import os
import pytest

# Projeyi Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication fixture."""
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        yield app
    except ImportError:
        pytest.skip("PyQt6 yüklü değil")