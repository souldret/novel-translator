"""
Novel Çevirmen — Örnek Plugin Dosyası
======================================

Bu dosya, kendi özel çevirmen eklentinizi nasıl oluşturacağınızı gösteren
bir şablondur. Gerçek bir API entegrasyonu yazmak için bu dosyayı kopyalayın,
yeniden adlandırın ve aşağıdaki adımları izleyin.

EKLENTI OLUŞTURMA ADIMLARI:
  1. Bu dosyayı kopyalayın:  plugins/benim_eklentim.py
  2. Sınıf adını değiştirin: class BenimCevirmen(BaseTranslator)
  3. GORUNTU_ADI sabitini güncelleyin
  4. translate_bolum() metodunu gerçek API çağrısıyla doldurun
  5. Uygulamayı başlatın — eklenti otomatik yüklenecektir

OTOMATIK YÜKLEME:
  Uygulama başladığında (veya load_plugins() çağrıldığında) bu dizindeki
  tüm .py dosyaları taranır. BaseTranslator'dan türeyen her sınıf otomatik
  olarak TranslatorFactory'ye kaydedilir.

NOT: Bu dosyada gerçek bir sınıf tanımı yoktur (hepsi yorum satırı).
     Kendi eklentinizi yazarken yorumları kaldırın.
"""

# =============================================================================
# ÖRNEK EKLENTI — Yorum satırlarını kaldırarak kullanabilirsiniz
# =============================================================================

# from translator import BaseTranslator, sistem_promptu_olustur, _hata_mesaji_temizle
# from typing import Callable
#
#
# class OrneKCevirmen(BaseTranslator):
#     """
#     Örnek özel çevirmen eklentisi.
#
#     Bu sınıf, herhangi bir HTTP tabanlı çeviri API'sine bağlanmak için
#     şablon görevi görür. Kendi API entegrasyonunuzu buraya yazın.
#
#     Sınıf sabiti:
#         GORUNTU_ADI : TranslatorFactory ve UI'da görünecek ad.
#                       Tanımlanmazsa sınıf adı kullanılır.
#     """
#
#     # UI'da ve sağlayıcı listesinde görünecek ad
#     GORUNTU_ADI = "Örnek Çevirmen"
#
#     def __init__(self, api_anahtari: str, model_adi: str):
#         """
#         Plugin yükleyici bu imzayı bekler:
#             __init__(self, api_anahtari: str, model_adi: str)
#
#         Ekstra parametreler gerekiyorsa varsayılan değerler kullanın.
#         """
#         super().__init__(api_anahtari, model_adi)
#
#         # Kütüphanenizi burada içe aktarın; yüklü değilse açıklayıcı hata verin
#         # try:
#         #     import ornek_kutuphanesi
#         #     self._lib = ornek_kutuphanesi
#         # except ImportError:
#         #     raise ImportError(
#         #         "ornek_kutuphanesi bulunamadı. "
#         #         "Lütfen 'pip install ornek_kutuphanesi' komutuyla yükleyin."
#         #     )
#
#         # API istemcinizi burada başlatın
#         # self._istemci = self._lib.Client(api_key=api_anahtari)
#         pass
#
#     def translate_bolum(
#         self,
#         orijinal_metin: str,
#         kaynak_dil: str,
#         hedef_dil: str,
#         sozluk_terimleri: list
#     ) -> str:
#         """
#         Metni çevirir ve sonucu string olarak döndürür.
#
#         ZORUNLU KURALLAR:
#           - Asla None döndürme; hata durumunda "HATA: ..." ile başlayan
#             string döndür.
#           - Asla exception fırlatma; tüm hataları yakala ve string döndür.
#           - Başarılı durumda yalnızca çevrilmiş metni döndür.
#
#         Döndürür:
#             Çevrilmiş metin veya "HATA: ..." ile başlayan hata mesajı
#         """
#         try:
#             # Sistem promptunu oluştur (sözlük ve çeviri talimatlarını içerir)
#             sistem_promptu = sistem_promptu_olustur(
#                 kaynak_dil, hedef_dil, sozluk_terimleri
#             )
#             kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"
#
#             # ---- BURAYA KENDİ API ÇAĞRINIZI YAZIN ----
#             # Örnek:
#             # yanit = self._istemci.generate(
#             #     system=sistem_promptu,
#             #     prompt=kullanici_mesaji,
#             #     model=self.model_adi,
#             # )
#             # return yanit.text or ""
#             # ------------------------------------------
#
#             # Şimdilik yer tutucu olarak hata döndür
#             return "HATA: OrneKCevirmen henüz uygulanmadı."
#
#         except Exception as hata:
#             return f"HATA: Beklenmeyen sorun - {_hata_mesaji_temizle(str(hata))}"
#
#     # İsteğe bağlı: Streaming desteklemek için bu metodu override edin.
#     # Streaming desteklemiyorsanız bu metodu silmeniz yeterlidir;
#     # BaseTranslator varsayılan implementasyonu translate_bolum'u çağırır.
#     #
#     # def translate_bolum_stream(
#     #     self,
#     #     orijinal_metin: str,
#     #     kaynak_dil: str,
#     #     hedef_dil: str,
#     #     sozluk_terimleri: list,
#     #     on_token: Callable[[str], None],
#     # ) -> str:
#     #     """Token token streaming çeviri."""
#     #     # Her token geldiğinde on_token(token) çağırın
#     #     # Tüm metni birleştirip döndürün
#     #     pass
#
#     # İsteğe bağlı: Streaming destekleniyorsa True döndürün
#     # @property
#     # def streaming_destekli(self) -> bool:
#     #     return True  # Varsayılan False
