"""DatabaseManager API anahtarı şifreleme testleri."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from secure_store import sifreli_mi


class TestApiKeyEncryption:
    def test_kaydet_ve_oku_sifreli(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "t.db"))
            assert db.ai_ayar_kaydet("openai", "gpt-4o", "sk-secret-key", aktif=True)
            ayar = db.aktif_ai_ayar_getir()
            assert ayar is not None
            assert ayar["api_anahtari"] == "sk-secret-key"

            # Ham DB'de şifreli olmalı
            import sqlite3
            conn = sqlite3.connect(db.db_yolu)
            ham = conn.execute("SELECT api_anahtari FROM ai_ayarlar").fetchone()[0]
            conn.close()
            assert sifreli_mi(ham)

    def test_legacy_duz_metin_migrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = os.path.join(tmp, "t.db")
            db = DatabaseManager(yol)
            # Düz metin enjekte et
            import sqlite3
            conn = sqlite3.connect(yol)
            conn.execute(
                "INSERT INTO ai_ayarlar (saglayici, model_adi, api_anahtari, aktif) VALUES (?,?,?,1)",
                ("anthropic", "claude", "plain-key"),
            )
            conn.commit()
            conn.close()

            ayar = db.aktif_ai_ayar_getir()
            assert ayar["api_anahtari"] == "plain-key"

            conn = sqlite3.connect(yol)
            ham = conn.execute(
                "SELECT api_anahtari FROM ai_ayarlar WHERE saglayici='anthropic'"
            ).fetchone()[0]
            conn.close()
            assert sifreli_mi(ham)
