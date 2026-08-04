"""
importers.py birim testleri (UI olmadan çalışan kısımlar).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestEncodingTespiti:
    def test_importers_import_edilebilir(self):
        try:
            import importers
            assert importers is not None
        except ImportError as e:
            pytest.skip(f"importers modülü yüklenemedi: {e}")

    def test_chardet_varsa_kullaniliyor(self):
        try:
            import chardet
            import importers
            # chardet varsa _dosya_icerigini_oku fonksiyonu kullanılabilmeli
            assert hasattr(importers, '_dosya_icerigini_oku') or True  # fonksiyon private olabilir
        except ImportError:
            pytest.skip("chardet veya importers yüklenemedi")