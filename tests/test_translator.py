"""
translator.py birim testleri.
pytest ile çalıştırın: pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from translator import (
    TranslatorError, AuthenticationError, RateLimitError,
    ConnectionError, ContentFilterError, InvalidRequestError,
    TranslatorFactory
)


class TestExceptionHiyerarsisi:
    def test_translator_error_temel_sinif(self):
        assert issubclass(AuthenticationError, TranslatorError)
        assert issubclass(RateLimitError, TranslatorError)
        assert issubclass(ConnectionError, TranslatorError)
        assert issubclass(ContentFilterError, TranslatorError)
        assert issubclass(InvalidRequestError, TranslatorError)

    def test_translator_error_exception_turunde(self):
        assert issubclass(TranslatorError, Exception)

    def test_authentication_error_firlatilab(self):
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Geçersiz API anahtarı")

    def test_rate_limit_error_firlatilabilir(self):
        with pytest.raises(RateLimitError):
            raise RateLimitError("Limit aşıldı")

    def test_connection_error_firlatilabilir(self):
        with pytest.raises(ConnectionError):
            raise ConnectionError("Bağlantı hatası")


class TestTranslatorFactory:
    def test_saglayici_listesi_bos_degil(self):
        saglayicilar = TranslatorFactory.get_tum_saglayicilar()
        assert len(saglayicilar) > 0

    def test_saglayici_listesi_openai_icerir(self):
        saglayicilar = TranslatorFactory.get_tum_saglayicilar()
        assert "openai" in saglayicilar or any("openai" in s.lower() for s in saglayicilar)

    def test_get_saglayici_display_name(self):
        # Her kayıtlı sağlayıcının display adı string olmalı
        saglayicilar = TranslatorFactory.get_tum_saglayicilar()
        for s in saglayicilar:
            ad = TranslatorFactory.get_saglayici_display_name(s)
            assert isinstance(ad, str)
            assert len(ad) > 0

    def test_bilinmeyen_saglayici_none_doner(self):
        # get_translator bilinmeyen sağlayıcı için ValueError fırlatır
        with pytest.raises(ValueError):
            TranslatorFactory.get_translator("bilinmeyen_saglayici_xyz", "api_key", "model")


class TestPluginLoader:
    def test_plugin_loader_import_edilebilir(self):
        try:
            import plugin_loader
            assert hasattr(plugin_loader, 'load_plugins')
            assert hasattr(plugin_loader, 'get_plugin_translator')
        except ImportError:
            pytest.skip("plugin_loader modülü bulunamadı")

    def test_load_plugins_liste_doner(self):
        try:
            import plugin_loader
            sonuc = plugin_loader.load_plugins()
            assert isinstance(sonuc, list)
        except ImportError:
            pytest.skip("plugin_loader modülü bulunamadı")


class TestDatabase:
    def test_database_import(self):
        from database import DatabaseManager
        assert DatabaseManager is not None

    def test_database_olusturulabilir(self):
        import tempfile
        from database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseManager(db_path)
            assert db is not None
            db.kapat() if hasattr(db, 'kapat') else None