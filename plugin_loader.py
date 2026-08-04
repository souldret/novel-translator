"""
Novel Çevirmen — Plugin Yükleyici
Plugins klasöründeki özel çevirmen eklentilerini dinamik olarak yükler
ve TranslatorFactory'ye kaydeder.

Kullanım:
    from plugin_loader import load_plugins, get_plugin_translator

    # Tüm eklentileri yükle
    yuklenenler = load_plugins()
    print("Yüklenen eklentiler:", yuklenenler)

    # Eklenti ile çeviri yap
    cevirmen = get_plugin_translator("OrneKCevirmen", api_key="...", model="...")
    sonuc = cevirmen.translate_bolum(metin, "Çince", "Türkçe", [])
"""

import importlib
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("novel_cevirmen.plugin_loader")

# Bu modülün bulunduğu dizin (novel-translator kök dizini)
_MODUL_DIZINI = Path(__file__).parent.resolve()
_PLUGIN_DIZINI = _MODUL_DIZINI / "plugins"

# Yüklenen eklenti sınıflarının kaydı: { "PluginAdi": PluginSinifi }
_KAYITLI_EKLENTILER: dict = {}


def _translator_sinifi_mi(sinif) -> bool:
    """
    Verilen nesnenin BaseTranslator'dan türetilmiş somut bir sınıf olup
    olmadığını kontrol eder.

    Soyut sınıfların (ABC) kendisi hariç tutulur; yalnızca gerçekten
    instantiate edilebilir alt sınıflar kabul edilir.
    """
    try:
        from translator import BaseTranslator
        return (
            inspect.isclass(sinif)
            and issubclass(sinif, BaseTranslator)
            and sinif is not BaseTranslator
            and not inspect.isabstract(sinif)
        )
    except Exception:
        return False


def load_plugins() -> list:
    """
    Plugins klasöründeki tüm .py dosyalarını tarar ve içinde
    BaseTranslator'dan türeyen sınıflar varsa TranslatorFactory'ye kaydeder.

    - Plugin dizini yoksa sessizce boş liste döner.
    - Her plugin dosyası try/except ile yüklenir; hatalı bir dosya
      diğerlerinin yüklenmesini engellemez.
    - Aynı isimli eklenti tekrar yüklenirse uyarı verilir ama üzerine yazılır.

    Döndürür:
        Başarıyla yüklenen eklenti sınıf isimlerinin listesi
    """
    global _KAYITLI_EKLENTILER

    if not _PLUGIN_DIZINI.exists():
        logger.debug("Plugin dizini bulunamadı: %s", _PLUGIN_DIZINI)
        return []

    yuklenen_isimler = []

    # plugins/ dizinini sys.path'e ekle (eklentiler kendi modüllerini import edebilsin)
    plugin_dizin_str = str(_PLUGIN_DIZINI)
    if plugin_dizin_str not in sys.path:
        sys.path.insert(0, plugin_dizin_str)

    for dosya in sorted(_PLUGIN_DIZINI.glob("*.py")):
        # __init__.py ve _ ile başlayan dosyaları atla
        if dosya.name.startswith("_"):
            continue

        modul_adi = f"plugins.{dosya.stem}"

        try:
            spec = importlib.util.spec_from_file_location(modul_adi, dosya)
            if spec is None or spec.loader is None:
                logger.warning("Plugin dosyası yüklenemedi (spec hatası): %s", dosya.name)
                continue

            modul = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modul)

            # Modül içindeki tüm nesneleri tara
            bulunan = False
            for ad, nesne in inspect.getmembers(modul, inspect.isclass):
                if _translator_sinifi_mi(nesne):
                    if ad in _KAYITLI_EKLENTILER:
                        logger.warning(
                            "Eklenti '%s' zaten kayıtlı; üzerine yazılıyor (dosya: %s).",
                            ad, dosya.name
                        )
                    _KAYITLI_EKLENTILER[ad] = nesne
                    yuklenen_isimler.append(ad)
                    bulunan = True
                    logger.info("Eklenti yüklendi: %s (%s)", ad, dosya.name)

            if not bulunan:
                logger.debug(
                    "Plugin dosyasında BaseTranslator alt sınıfı bulunamadı: %s",
                    dosya.name
                )

        except Exception as hata:
            logger.error(
                "Plugin yüklenirken hata oluştu (%s): %s",
                dosya.name, hata, exc_info=True
            )

    # Yüklenen eklentileri TranslatorFactory'ye kaydet
    if yuklenen_isimler:
        _factory_e_kaydet()

    return yuklenen_isimler


def _factory_e_kaydet():
    """
    Kayıtlı eklenti sınıflarını TranslatorFactory'nin iç yapılarına ekler.

    - _SAGLAYICILAR tuple'ına eklenti adını ekler
    - _MODELLER sözlüğüne boş liste ile giriş yapar
    - _GORUNTU_ADLARI sözlüğüne görünen adı yazar
    """
    try:
        from translator import TranslatorFactory

        saglayicilar = list(TranslatorFactory._SAGLAYICILAR)

        for ad, sinif in _KAYITLI_EKLENTILER.items():
            anahtar = ad.lower()

            if anahtar not in saglayicilar:
                saglayicilar.append(anahtar)

            if anahtar not in TranslatorFactory._MODELLER:
                TranslatorFactory._MODELLER[anahtar] = []

            if anahtar not in TranslatorFactory._GORUNTU_ADLARI:
                # Görünen ad: sınıf üzerinde tanımlıysa onu kullan,
                # yoksa sınıf adını döndür
                goruntu_adi = getattr(sinif, "GORUNTU_ADI", ad)
                TranslatorFactory._GORUNTU_ADLARI[anahtar] = goruntu_adi

        TranslatorFactory._SAGLAYICILAR = tuple(saglayicilar)
        logger.debug("TranslatorFactory güncellendi. Toplam sağlayıcı: %d", len(saglayicilar))

    except Exception as hata:
        logger.error("TranslatorFactory güncellenirken hata: %s", hata, exc_info=True)


def get_plugin_translator(plugin_adi: str, api_key: str, model: str):
    """
    Adı verilen eklentinin translator nesnesini oluşturur ve döndürür.

    Parametreler:
        plugin_adi : Eklenti sınıfının adı (büyük/küçük harfe duyarlı değil)
        api_key    : API anahtarı
        model      : Model adı

    Döndürür:
        BaseTranslator alt sınıfının örneği

    Fırlatır:
        KeyError  — eklenti adı kayıtlı değilse
        Exception — sınıf instantiate edilemezse
    """
    # Büyük/küçük harf farkı olmaksızın ara
    eslesen = None
    for kayitli_ad, sinif in _KAYITLI_EKLENTILER.items():
        if kayitli_ad.lower() == plugin_adi.lower():
            eslesen = (kayitli_ad, sinif)
            break

    if eslesen is None:
        mevcut = list(_KAYITLI_EKLENTILER.keys())
        raise KeyError(
            f"'{plugin_adi}' adlı eklenti bulunamadı. "
            f"Yüklü eklentiler: {mevcut}. "
            f"Önce load_plugins() çağrıldığından emin olun."
        )

    ad, sinif = eslesen
    try:
        return sinif(api_key, model)
    except TypeError as hata:
        raise TypeError(
            f"'{ad}' eklentisi oluşturulamadı. "
            f"__init__(api_anahtari, model_adi) imzası bekleniyor. Hata: {hata}"
        ) from hata


def get_yuklenen_eklentiler() -> dict:
    """
    Şu an yüklü olan tüm eklenti sınıflarını döndürür.

    Döndürür:
        { "SinifAdi": <sinif nesnesi> } şeklinde sözlük (kopya)
    """
    return dict(_KAYITLI_EKLENTILER)


def plugin_yuklu_mu(plugin_adi: str) -> bool:
    """
    Verilen adda bir eklentinin yüklenmiş olup olmadığını kontrol eder.

    Parametreler:
        plugin_adi : Kontrol edilecek eklenti adı (büyük/küçük harf farkı yok)

    Döndürür:
        True ise eklenti yüklü, False ise değil
    """
    return any(k.lower() == plugin_adi.lower() for k in _KAYITLI_EKLENTILER)


# =============================================================================
# HIZLI TEST — python plugin_loader.py ile doğrudan çalıştırılabilir
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    print("=" * 60)
    print("Novel Çevirmen — Plugin Loader Testi")
    print("=" * 60)

    print(f"\nPlugin dizini: {_PLUGIN_DIZINI}")
    print(f"Dizin mevcut mu: {_PLUGIN_DIZINI.exists()}")

    print("\nPluginler yükleniyor...")
    yuklenenler = load_plugins()

    if yuklenenler:
        print(f"\nYüklenen eklentiler ({len(yuklenenler)}):")
        for isim in yuklenenler:
            print(f"  - {isim}")
    else:
        print("\nHiç eklenti yüklenmedi.")
        print("plugins/ dizinine BaseTranslator'dan türeyen sınıflar ekleyin.")

    print("\n" + "=" * 60)
    print("Test tamamlandı.")
    print("=" * 60)