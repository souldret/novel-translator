"""
Novel Çevirmen - AI Çeviri Motoru
Tüm AI sağlayıcılarını tek bir arayüz üzerinden yöneten çeviri modülü.

Desteklenen sağlayıcılar:
  - OpenAI       (GPT-4o ve diğer modeller)
  - Anthropic    (Claude serisi)
  - Google       (Gemini serisi)
  - xAI          (Grok — OpenAI uyumlu API)
  - OpenRouter   (Çoklu model yönlendirme)
"""

from abc import ABC, abstractmethod
from typing import Callable
import json as _json_module
import logging

logger = logging.getLogger("novel_cevirmen.translator")


# =============================================================================
# ÖZEL EXCEPTION HİYERARŞİSİ
# =============================================================================

class TranslatorError(Exception):
    """Tüm translator hatalarının temel sınıfı."""
    pass

class AuthenticationError(TranslatorError):
    """API anahtarı geçersiz veya yetkilendirme hatası."""
    pass

class RateLimitError(TranslatorError):
    """API istek limiti aşıldı."""
    pass

class ConnectionError(TranslatorError):
    """API sunucusuna bağlanılamıyor."""
    pass

class ContentFilterError(TranslatorError):
    """İçerik güvenlik filtresi tarafından engellendi."""
    pass

class InvalidRequestError(TranslatorError):
    """Geçersiz istek parametreleri."""
    pass


# =============================================================================
# YARDIMCI — HATA MESAJI TEMİZLEYİCİ
# =============================================================================

def _hata_mesaji_temizle(hata_str: str) -> str:
    """
    API hata yanıtlarında bazen ham JSON veya teknik hata metni döner.
    Bu fonksiyon:
    - Başında/sonunda boşlukları temizler
    - Ham JSON hata nesnesini okunabilir metne dönüştürür
    - Çok uzun hata mesajlarını 200 karaktere kırpar
    """
    hata_str = str(hata_str).strip()

    # JSON nesnesi ise ayrıştırmayı dene
    if hata_str.startswith("{"):
        try:
            obj = _json_module.loads(hata_str)
            # OpenAI / Anthropic / Gemini hata formatları
            if "error" in obj:
                err = obj["error"]
                if isinstance(err, dict):
                    mesaj = err.get("message", err.get("msg", str(err)))
                    return str(mesaj)[:200]
                return str(err)[:200]
            if "message" in obj:
                return str(obj["message"])[:200]
        except (_json_module.JSONDecodeError, Exception):
            pass

    # Çok uzun metni kırp
    if len(hata_str) > 300:
        hata_str = hata_str[:300] + "..."

    return hata_str


# =============================================================================
# BÖLÜM 1 — SOYUT TEMEL SINIF
# =============================================================================

class BaseTranslator(ABC):
    """
    Tüm AI çeviri sağlayıcılarının uygulamak zorunda olduğu soyut temel sınıf.
    Her sağlayıcı kendi translate_bolum() implementasyonunu yazar;
    üst katman (UI, worker) yalnızca bu arayüzü kullanır.
    """

    def __init__(self, api_anahtari: str, model_adi: str):
        """
        Parametreler:
            api_anahtari : Sağlayıcıya ait API anahtarı
            model_adi    : Kullanılacak modelin adı (örn. "gpt-4o")
        """
        self.api_anahtari = api_anahtari
        self.model_adi = model_adi

    @abstractmethod
    def translate_bolum(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list
    ) -> str:
        """
        Verilen metni çevirir.

        Parametreler:
            orijinal_metin   : Çevrilecek kaynak metin
            kaynak_dil       : Metnin dili (örn. "Çince", "Japonca")
            hedef_dil        : Hedef dil (örn. "Türkçe")
            sozluk_terimleri : Sözlük terimi dict listesi.
                               Her dict şu anahtarları içerir:
                                 - orijinal_terim  : Kaynak dildeki terim
                                 - cevrilmis_terim : Türkçe karşılık

        Döndürür:
            Çevrilmiş metin veya hata durumunda "HATA: ..." ile başlayan string.
            Asla None döndürmez, asla exception fırlatmaz.
        """
        ...

    def translate_bolum_stream(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list,
        on_token: Callable[[str], None],
    ) -> str:
        """
        Streaming çeviri — her token geldiğinde on_token(token) callback'ini çağırır.
        Varsayılan implementasyon non-streaming translate_bolum'u çağırır;
        streaming destekleyen alt sınıflar bu metodu override eder.

        Döndürür:
            Tüm çevrilmiş metin (streaming tamamlandığında).
        """
        sonuc = self.translate_bolum(
            orijinal_metin, kaynak_dil, hedef_dil, sozluk_terimleri
        )
        on_token(sonuc)
        return sonuc

    @property
    def streaming_destekli(self) -> bool:
        """Bu sağlayıcı gerçek streaming destekliyor mu?"""
        return False


# =============================================================================
# BÖLÜM 2 — SÖZLÜK TALİMAT OLUŞTURUCU
# =============================================================================

def sozluk_talimati_olustur(sozluk_terimleri: list) -> str:
    """
    Sözlük terimlerinden AI için sabit çeviri talimatı metni oluşturur.

    Kilitli terimler önce listelenir ve [KİLİTLİ] etiketiyle işaretlenir.
    Tüm terimler için hikaye tutarlılığı vurgulanır.

    Parametreler:
        sozluk_terimleri : orijinal_terim, cevrilmis_terim ve locked anahtarlarına
                           sahip dict listesi

    Döndürür:
        Talimat metni (liste boşsa boş string döner)
    """
    if not sozluk_terimleri:
        return ""

    # Kilitli terimler önce
    locked_terms   = [t for t in sozluk_terimleri if t.get("locked", False)]
    unlocked_terms = [t for t in sozluk_terimleri if not t.get("locked", False)]
    ordered = locked_terms + unlocked_terms

    # Başlık satırı
    satirlar = [
        "HİKAYE TUTARLILIK SÖZLÜĞÜ — Aşağıdaki isimler, unvanlar, yerler, "
        "teknikler ve terimleri MUTLAKA belirtilen şekilde çevir. "
        "Bu terimleri asla farklı, değişik veya benzer bir biçimde çevirme:"
    ]

    # Her terim için bir madde eklenir
    for terim in ordered:
        orijinal  = terim.get("orijinal_terim",  "").strip()
        cevrilmis = terim.get("cevrilmis_terim", "").strip()
        if orijinal and cevrilmis:
            lock_tag = " ⟨KİLİTLİ⟩" if terim.get("locked") else ""
            satirlar.append(f"- {orijinal} → {cevrilmis}{lock_tag}")

    # Yalnızca başlık satırı kaldıysa (geçerli terim yoksa) boş dön
    if len(satirlar) == 1:
        return ""

    return "\n".join(satirlar)


# =============================================================================
# BÖLÜM 3 — SİSTEM PROMPTU OLUŞTURUCU
# =============================================================================

def sistem_promptu_olustur(
    kaynak_dil: str,
    hedef_dil: str,
    sozluk_terimleri: list
) -> str:
    """
    AI'a gönderilecek tam sistem promptunu oluşturur.

    Prompt üç bölümden oluşur:
      1. Rol tanımı        — Çevirmenin uzmanlık alanı
      2. Sözlük talimatı  — Sabit çevrilmesi gereken terimler (varsa)
      3. Genel kurallar   — Biçim, ton ve kapsam kuralları

    Parametreler:
        kaynak_dil       : Kaynak dil adı (örn. "Çince")
        hedef_dil        : Hedef dil adı (örn. "Türkçe")
        sozluk_terimleri : Sözlük terimi dict listesi

    Döndürür:
        Tam sistem promptu string'i
    """
    # --- 1. Rol tanımı ---
    rol_tanimi = (
        f"Sen deneyimli bir edebi çevirmensin. {kaynak_dil} dilindeki web novel ve "
        f"light novel metinlerini {hedef_dil} diline çevirme konusunda uzmanlaşmışsın.\n"
        "Görevin yalnızca kelime kelime çeviri yapmak değil; metnin ruhunu, anlatım "
        "akışını ve karakterlerin sesini koruyarak hedef dilde okunması keyifli, "
        "tutarlı ve doğal bir metin üretmektir."
    )

    # --- 2. Sözlük talimatı (varsa) ---
    sozluk_talimati = sozluk_talimati_olustur(sozluk_terimleri)

    # --- 3. Akıcılık ve anlatım kuralları ---
    hedef_dil_goster = hedef_dil if hedef_dil else "hedef dil"
    genel_kurallar = (
        "Çeviri ilkeleri:\n\n"

        "AKICILIK VE ANLATIM:\n"
        f"- Metni bir roman okuyucusunun {hedef_dil_goster}de keyifle okuyacağı şekilde çevir.\n"
        "- Cümleleri bağımsız birimler olarak değil, bir bütünün parçaları olarak ele al; "
        "paragraf ve sahne akışını koru.\n"
        "- Orijinal anlatım tonunu yansıt: gerilimli sahneler gerilimli, komik sahneler "
        "hafif, duygusal sahneler içten olmalı.\n"
        "- Uzun veya karmaşık cümleleri hedef dilde daha doğal okunacak şekilde "
        "yeniden düzenleyebilirsin; ancak anlam kaybı olmadan.\n"
        "- Tekrar eden ifadeler varsa hedef dilde daha doğal bir karşılık kullan.\n\n"

        "DİYALOG VE KARAKTERLER:\n"
        "- Her karakterin konuşma biçimini (resmi/samimi/kibar/kaba) tutarlı biçimde koru.\n"
        "- Diyalog satırlarını doğal konuşma diline uygun çevir; kalıplaşmış, robotik "
        "ifadelerden kaçın.\n"
        "- Ünlemler, duraklamalar ('...'), vurgu ifadeleri ('—') ve ses taklitleri "
        "anlam ve ritme uygun karşılıklarıyla verilmeli.\n\n"

        "YAPI VE BİÇİM:\n"
        "- Paragraf aralarını ve satır yapısını orijinal metindeki gibi koru.\n"
        "- Kalın, italik, tırnak gibi biçimlendirmeleri aynen aktar.\n"
        "- Hiçbir cümleyi, diyaloğu veya paragrafı atlama, ekleme veya özet geçme.\n\n"

        "ÇIKTI:\n"
        "- Yalnızca çevrilmiş metni döndür. Açıklama, dipnot veya yorum ekleme.\n"
        "- Çeviriyi tamamlamadan yarıda kesme."
    )

    # Bölümleri birleştir; sözlük talimatı boşsa araya eklenmez
    bölümler = [rol_tanimi]
    if sozluk_talimati:
        bölümler.append(sozluk_talimati)
    bölümler.append(genel_kurallar)

    return "\n\n".join(bölümler)


# =============================================================================
# BÖLÜM 4 — SAĞLAYICI SINIFLARI
# =============================================================================

class OpenAITranslator(BaseTranslator):
    """
    OpenAI API (GPT serisi) kullanarak çeviri yapan sınıf.
    GrokTranslator ve OpenRouterTranslator bu sınıfı miras alır.
    """

    def __init__(
        self,
        api_anahtari: str,
        model_adi: str,
        base_url: str = None,
        default_headers: dict = None
    ):
        """
        Parametreler:
            api_anahtari    : OpenAI API anahtarı
            model_adi       : Model adı (örn. "gpt-4o")
            base_url        : Özel endpoint URL'si (xAI, OpenRouter için)
            default_headers : Her isteğe eklenecek HTTP başlıkları
        """
        super().__init__(api_anahtari, model_adi)

        # openai kütüphanesini burada içe aktarıyoruz;
        # böylece yüklenmemişse yalnızca bu sınıf kullanıldığında hata verir.
        try:
            import openai
            self._openai = openai
        except ImportError:
            raise ImportError(
                "openai kütüphanesi bulunamadı. "
                "Lütfen 'pip install openai' komutuyla yükleyin."
            )

        # İstemciyi oluştur; base_url ve default_headers opsiyonel
        istemci_kwargs = {"api_key": api_anahtari}
        if base_url:
            istemci_kwargs["base_url"] = base_url
        if default_headers:
            istemci_kwargs["default_headers"] = default_headers

        self._istemci = self._openai.OpenAI(**istemci_kwargs)

    def translate_bolum(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list
    ) -> str:
        """
        OpenAI Chat Completions API ile metin çevirir.

        Döndürür:
            Çevrilmiş metin veya "HATA: ..." ile başlayan hata mesajı
        """
        try:
            sistem_promptu = sistem_promptu_olustur(
                kaynak_dil, hedef_dil, sozluk_terimleri
            )
            kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"

            yanit = self._istemci.chat.completions.create(
                model=self.model_adi,
                messages=[
                    {"role": "system",  "content": sistem_promptu},
                    {"role": "user",    "content": kullanici_mesaji},
                ]
            )
            if not yanit.choices:
                return "HATA: API boş yanıt döndürdü (choices listesi boş)."
            return yanit.choices[0].message.content or ""

        except self._openai.AuthenticationError:
            return "HATA: API anahtari gecersiz veya yetkisiz erisim. Lutfen API anahtarinizi kontrol edin."
        except self._openai.RateLimitError:
            return "HATA: API istek limiti asildi. Lutfen bir sure bekleyip tekrar deneyin."
        except self._openai.APIConnectionError:
            return "HATA: API sunucusuna baglanilamiyor. Internet baglantinizi kontrol edin."
        except self._openai.BadRequestError as hata:
            return f"HATA: Gecersiz istek - {_hata_mesaji_temizle(str(hata))}"
        except Exception as hata:
            return f"HATA: Beklenmeyen bir sorun olustu - {_hata_mesaji_temizle(str(hata))}"

    def translate_bolum_stream(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list,
        on_token: Callable[[str], None],
    ) -> str:
        """
        OpenAI streaming chat completions ile token token çeviri.
        SSE stream hatası (JSON error injected into SSE stream vb.) oluşursa
        streaming iptal edilir ve non-streaming moda otomatik olarak geçilir.
        """
        sistem_promptu   = sistem_promptu_olustur(kaynak_dil, hedef_dil, sozluk_terimleri)
        kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"

        # --- Streaming denemesi ---
        try:
            tum_metin = []
            with self._istemci.chat.completions.create(
                model=self.model_adi,
                messages=[
                    {"role": "system", "content": sistem_promptu},
                    {"role": "user",   "content": kullanici_mesaji},
                ],
                stream=True,
            ) as stream:
                for chunk in stream:
                    try:
                        token = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                    except Exception:
                        token = ""
                    if token:
                        tum_metin.append(token)
                        on_token(token)
            sonuc = "".join(tum_metin)
            if sonuc:
                return sonuc
            # Streaming boş sonuç döndürdüyse non-streaming'e düş
            raise ValueError("Streaming boş yanıt döndürdü")

        except Exception as stream_hata:
            hata_str = str(stream_hata)
            # Yalnızca SSE/JSON/bağlantı geçici hatalarında non-streaming'e geç;
            # kimlik doğrulama veya kota hatalarında direkt hata döndür.
            kalici_hatalar = ("authentication", "api key", "rate limit", "quota", "billing")
            if any(k in hata_str.lower() for k in kalici_hatalar):
                hata_dongu = f"HATA: Streaming başarısız - {_hata_mesaji_temizle(hata_str)}"
                on_token(hata_dongu)
                return hata_dongu

            # Geçici hata: non-streaming fallback
            try:
                yanit = self._istemci.chat.completions.create(
                    model=self.model_adi,
                    messages=[
                        {"role": "system", "content": sistem_promptu},
                        {"role": "user",   "content": kullanici_mesaji},
                    ],
                )
                if not yanit.choices:
                    return "HATA: API boş yanıt döndürdü."
                sonuc = yanit.choices[0].message.content or ""
                if sonuc:
                    on_token(sonuc)
                return sonuc
            except Exception as fallback_hata:
                hata_dongu = f"HATA: Çeviri başarısız - {_hata_mesaji_temizle(str(fallback_hata))}"
                on_token(hata_dongu)
                return hata_dongu

    @property
    def streaming_destekli(self) -> bool:
        return True


# -----------------------------------------------------------------------------

class AnthropicTranslator(BaseTranslator):
    """
    Anthropic Claude API kullanarak çeviri yapan sınıf.
    """

    def __init__(self, api_anahtari: str, model_adi: str):
        super().__init__(api_anahtari, model_adi)

        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "anthropic kütüphanesi bulunamadı. "
                "Lütfen 'pip install anthropic' komutuyla yükleyin."
            )

        self._istemci = anthropic.Anthropic(api_key=api_anahtari)

    def translate_bolum(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list
    ) -> str:
        """
        Anthropic Messages API ile metin çevirir.
        Sistem promptu 'system' parametresiyle ayrı gönderilir.

        Döndürür:
            Çevrilmiş metin veya "HATA: ..." ile başlayan hata mesajı
        """
        try:
            sistem_promptu = sistem_promptu_olustur(
                kaynak_dil, hedef_dil, sozluk_terimleri
            )
            kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"

            yanit = self._istemci.messages.create(
                model=self.model_adi,
                max_tokens=8096,
                system=sistem_promptu,
                messages=[
                    {"role": "user", "content": kullanici_mesaji}
                ]
            )
            # Anthropic yanıtı ContentBlock listesi döndürür; text tipi bloğu al
            for blok in (yanit.content or []):
                if hasattr(blok, "text"):
                    return blok.text
            return ""

        except self._anthropic.AuthenticationError:
            return "HATA: API anahtari gecersiz. Lutfen Anthropic API anahtarinizi kontrol edin."
        except self._anthropic.RateLimitError:
            return "HATA: API istek limiti asildi. Lutfen bir sure bekleyip tekrar deneyin."
        except self._anthropic.APIConnectionError:
            return "HATA: Anthropic API sunucusuna baglanilamiyor. Internet baglantinizi kontrol edin."
        except self._anthropic.BadRequestError as hata:
            return f"HATA: Gecersiz istek - {_hata_mesaji_temizle(str(hata))}"
        except Exception as hata:
            return f"HATA: Beklenmeyen bir sorun olustu - {_hata_mesaji_temizle(str(hata))}"

    def translate_bolum_stream(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list,
        on_token: Callable[[str], None],
    ) -> str:
        """Anthropic streaming messages API ile token token çeviri."""
        try:
            sistem_promptu = sistem_promptu_olustur(kaynak_dil, hedef_dil, sozluk_terimleri)
            kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"
            tum_metin = []
            with self._istemci.messages.stream(
                model=self.model_adi,
                max_tokens=8096,
                system=sistem_promptu,
                messages=[{"role": "user", "content": kullanici_mesaji}],
            ) as stream:
                for token in stream.text_stream:
                    if token:
                        tum_metin.append(token)
                        on_token(token)
            return "".join(tum_metin)
        except Exception as hata:
            hata_str_raw = str(hata)
            # Kalıcı hatalar (kimlik doğrulama, kota) doğrudan döndürülür
            kalici_hatalar = ("authentication", "api key", "rate limit", "quota", "billing")
            if any(k in hata_str_raw.lower() for k in kalici_hatalar):
                hata_dongu = f"HATA: Streaming başarısız - {_hata_mesaji_temizle(hata_str_raw)}"
                on_token(hata_dongu)
                return hata_dongu
            # Geçici hatalar için non-streaming fallback
            try:
                sistem_promptu = sistem_promptu_olustur(kaynak_dil, hedef_dil, sozluk_terimleri)
                kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"
                yanit = self._istemci.messages.create(
                    model=self.model_adi,
                    max_tokens=8096,
                    system=sistem_promptu,
                    messages=[{"role": "user", "content": kullanici_mesaji}],
                )
                for blok in (yanit.content or []):
                    if hasattr(blok, "text"):
                        on_token(blok.text)
                        return blok.text
                return ""
            except Exception as fallback_hata:
                hata_dongu = f"HATA: Çeviri başarısız - {_hata_mesaji_temizle(str(fallback_hata))}"
                on_token(hata_dongu)
                return hata_dongu

    @property
    def streaming_destekli(self) -> bool:
        return True


# -----------------------------------------------------------------------------

class GeminiTranslator(BaseTranslator):
    """
    Google Gemini API kullanarak çeviri yapan sınıf.
    """

    def __init__(self, api_anahtari: str, model_adi: str):
        super().__init__(api_anahtari, model_adi)

        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai kütüphanesi bulunamadı. "
                "Lütfen 'pip install google-generativeai' komutuyla yükleyin."
            )

        # API anahtarını global olarak yapılandır (Gemini SDK gereksinimi)
        genai.configure(api_key=api_anahtari)

    def translate_bolum(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list
    ) -> str:
        """
        Google Gemini API ile metin çevirir.
        Model her çeviri çağrısında sistem talimatıyla yeniden oluşturulur;
        böylece farklı seriler için farklı sözlükler temiz şekilde uygulanır.

        Döndürür:
            Çevrilmiş metin veya "HATA: ..." ile başlayan hata mesajı
        """
        try:
            sistem_promptu = sistem_promptu_olustur(
                kaynak_dil, hedef_dil, sozluk_terimleri
            )
            kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"

            # system_instruction parametresiyle sistem promptunu modele ver
            model = self._genai.GenerativeModel(
                model_name=self.model_adi,
                system_instruction=sistem_promptu
            )

            yanit = model.generate_content(kullanici_mesaji)

            # Güvenlik filtresi veya boş yanıt durumunu ele al
            if not yanit.candidates:
                return "HATA: Gemini boş yanıt döndürdü (aday içerik yok)."

            try:
                return yanit.text or ""
            except ValueError:
                # yanit.text güvenlik bloğu sebebiyle erişilemez
                return "HATA: Metin, Gemini güvenlik filtreleri tarafından engellendi."

        except Exception as hata:
            hata_str = str(hata).lower()
            if "api_key" in hata_str or "api key" in hata_str or "invalid" in hata_str:
                return "HATA: API anahtari gecersiz. Lutfen Google AI Studio'dan yeni bir anahtar alin."
            if "quota" in hata_str or "limit" in hata_str or "resource" in hata_str:
                return "HATA: API kota limiti asildi. Lutfen bir sure bekleyip tekrar deneyin."
            if "network" in hata_str or "connection" in hata_str or "timeout" in hata_str:
                return "HATA: Google API sunucusuna baglanilamiyor. Internet baglantinizi kontrol edin."
            if "blocked" in hata_str or "safety" in hata_str:
                return "HATA: Metin, Gemini guvenlik filtreleri tarafindan engellendi."
            return f"HATA: Beklenmeyen bir sorun olustu - {_hata_mesaji_temizle(str(hata))}"

    def translate_bolum_stream(
        self,
        orijinal_metin: str,
        kaynak_dil: str,
        hedef_dil: str,
        sozluk_terimleri: list,
        on_token: Callable[[str], None],
    ) -> str:
        """Gemini streaming generate_content ile token token çeviri."""
        try:
            sistem_promptu = sistem_promptu_olustur(kaynak_dil, hedef_dil, sozluk_terimleri)
            kullanici_mesaji = f"Aşağıdaki metni çevir:\n\n{orijinal_metin}"
            model = self._genai.GenerativeModel(
                model_name=self.model_adi,
                system_instruction=sistem_promptu,
            )
            tum_metin = []
            for chunk in model.generate_content(kullanici_mesaji, stream=True):
                try:
                    token = chunk.text or ""
                except Exception:
                    token = ""
                if token:
                    tum_metin.append(token)
                    on_token(token)
            return "".join(tum_metin)
        except Exception as hata:
            hata_str = f"HATA: Streaming başarısız - {_hata_mesaji_temizle(str(hata))}"
            on_token(hata_str)
            return hata_str

    @property
    def streaming_destekli(self) -> bool:
        return True


# -----------------------------------------------------------------------------

class GrokTranslator(OpenAITranslator):
    """
    xAI Grok API kullanarak çeviri yapan sınıf.
    Grok, OpenAI ile uyumlu bir API arayüzü sunduğundan
    OpenAITranslator miras alınır; yalnızca base_url farklıdır.

    Desteklenen modeller: grok-3, grok-3-mini
    """

    # xAI'nın OpenAI uyumlu endpoint'i
    GROK_BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_anahtari: str, model_adi: str):
        """
        Parametreler:
            api_anahtari : xAI API anahtarı
            model_adi    : "grok-3" veya "grok-3-mini"
        """
        super().__init__(
            api_anahtari=api_anahtari,
            model_adi=model_adi,
            base_url=self.GROK_BASE_URL
        )


# -----------------------------------------------------------------------------

def get_openrouter_models(api_key: str) -> list[dict]:
    """
    OpenRouter API'sinden kullanilabilir model listesini getirir.

    OpenRouter yuzlerce modeli destekler ve bu liste surekli guncellenir.
    API'ye her seferinde yeniden sorgu yapmak yerine en populer modeller
    icin bir on-yukleme listesi kullanilir; API erisimi basarisiz olursa
    bu liste kullanilir.

    Parametreler:
        api_key : OpenRouter API anahtari

    Dondurur:
        Model bilgileri dict listesi. Her dict sunlari icerir:
          - id         : Model kimligi (orn. "anthropic/claude-3.5-sonnet")
          - name       : Gorunur ad
          - description : Model aciklamasi
          - context_length : Baglam uzunlugu (varsa)
        API erisimi basarisiz olursa bilinen populer modeller listesi doner.
    """
    import urllib.request
    import urllib.error
    import json

    # On-yukleme populer model listesi (API erisilemezse kullanilir)
    POPULER_MODELLER = [
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "description": "Anthropic'in en dengeli modeli."},
        {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "description": "Hizli ve ekonomik Anthropic modeli."},
        {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "description": "Meta'nin buyuk ogretilmis modeli."},
        {"id": "meta-llama/llama-3.1-8b-instruct", "name": "Llama 3.1 8B", "description": "Hizli ve hafif Llama modeli."},
        {"id": "openai/gpt-4o", "name": "GPT-4o", "description": "OpenAI'nin en yetenekli modeli."},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "description": "Hizli ve ekonomik GPT-4o."},
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Google'un en hizli modeli."},
        {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Uzun baglam destekli Gemini Pro."},
        {"id": "mistralai/mistral-nemo", "name": "Mistral Nemo", "description": "Mistral'in 12B modeli."},
        {"id": "mistralai/mixtral-8x7b", "name": "Mixtral 8x7B", "description": "Uzmanlik alanli karisik uzmanlik modeli."},
        {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "description": "DeepSeek'in ana sohbet modeli."},
        {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "description": "Alibaba'nin buyuk dil modeli."},
        {"id": "x-ai/grok-3", "name": "Grok 3", "description": "xAI'nin en guclu modeli."},
        {"id": "perplexity/llama-3.1-sonar-large", "name": "Llama 3.1 Sonar Large", "description": "Perplexity'nin arama destekli modeli."},
        {"id": "nvidia/llama-3.1-nemotron-70b-instruct", "name": "Nemotron 70B", "description": "NVIDIA'nin RLHF ile egitilmis modeli."},
    ]

    try:
        istek = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
        with urllib.request.urlopen(istek, timeout=10) as yanit:
            veri = json.loads(yanit.read().decode("utf-8"))
            modeller = veri.get("data", [])
            # Yalnizca ceviri icin uygun modelleri dondur
            return [
                {
                    "id": m.get("id", ""),
                    "name": m.get("name", m.get("id", "")),
                    "description": m.get("description", ""),
                    "context_length": m.get("context_length"),
                }
                for m in modeller
                if m.get("id") and m.get("id") not in ("", "free")
            ]
    except Exception:
        # API erisilemezse populer modelleri dondur
        return POPULER_MODELLER


class OpenRouterTranslator(OpenAITranslator):
    """
    OpenRouter API kullanarak çeviri yapan sınıf.
    OpenRouter, yüzlerce modeli tek bir OpenAI uyumlu endpoint üzerinden sunar.
    Model adı kullanıcı tarafından serbest metin olarak girilir.

    İsteğe bağlı ekstra_konfig anahtarları:
        site_url : Uygulamanın URL'si (OpenRouter istatistikleri için)
        app_name : Uygulama adı (OpenRouter dashboard'unda görünür)
    """

    # OpenRouter'ın OpenAI uyumlu endpoint'i
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_anahtari: str,
        model_adi: str,
        ekstra_konfig: dict = None
    ):
        """
        Parametreler:
            api_anahtari  : OpenRouter API anahtarı
            model_adi     : Kullanılacak model (örn. "meta-llama/llama-3.1-70b-instruct")
            ekstra_konfig : İsteğe bağlı ek ayarlar dict'i.
                            Anahtarlar: site_url (str), app_name (str)
        """
        # OpenRouter istatistikleri için isteğe bağlı HTTP başlıkları oluştur
        default_headers = {}
        if ekstra_konfig:
            site_url = ekstra_konfig.get("site_url", "")
            app_name = ekstra_konfig.get("app_name", "")
            if site_url:
                default_headers["HTTP-Referer"] = site_url
            if app_name:
                default_headers["X-Title"] = app_name

        super().__init__(
            api_anahtari=api_anahtari,
            model_adi=model_adi,
            base_url=self.OPENROUTER_BASE_URL,
            default_headers=default_headers if default_headers else None
        )


# =============================================================================
# BÖLÜM 5 — FABRIKA SINIFI
# =============================================================================

class TranslatorFactory:
    """
    Doğru translator nesnesini oluşturan fabrika sınıfı.
    UI katmanı yalnızca bu sınıfla konuşur; alt sınıfları doğrudan bilmez.
    """

    # Desteklenen sağlayıcı adları
    _SAGLAYICILAR = ("openai", "anthropic", "google", "xai", "openrouter")

    # Her sağlayıcının sunduğu modeller (OpenRouter hariç — serbest giriş)
    _MODELLER: dict[str, list[str]] = {
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "anthropic": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "google": [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "xai": [
            "grok-3",
            "grok-3-mini",
        ],
        "openrouter": [],  # Model listesi API'den veya populer listeden alinir
    }

    # OpenRouter icin on-tanimli populer model listesi (API erisilemezse kullanilir)
    # Bu liste get_openrouter_models icinden de dondurulur; buradaki liste
    # modül yuklenir yuklenmez hazir olmasini saglar.
    _OPENROUTER_POPULER_MODELLER: list[dict] = [
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
        {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku"},
        {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B"},
        {"id": "meta-llama/llama-3.1-8b-instruct", "name": "Llama 3.1 8B"},
        {"id": "openai/gpt-4o", "name": "GPT-4o"},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini"},
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
        {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
        {"id": "mistralai/mistral-nemo", "name": "Mistral Nemo"},
        {"id": "mistralai/mixtral-8x7b", "name": "Mixtral 8x7B"},
        {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat"},
        {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B"},
        {"id": "x-ai/grok-3", "name": "Grok 3"},
        {"id": "perplexity/llama-3.1-sonar-large", "name": "Llama 3.1 Sonar Large"},
    ]

    # Sağlayıcıların kullanıcıya gösterilecek Türkçe görünen adları
    _GORUNTU_ADLARI: dict[str, str] = {
        "openai":      "OpenAI",
        "anthropic":   "Anthropic (Claude)",
        "google":      "Google Gemini",
        "xai":         "xAI (Grok)",
        "openrouter":  "OpenRouter",
    }

    @staticmethod
    def get_translator(
        saglayici: str,
        api_anahtari: str,
        model_adi: str,
        ekstra_konfig: dict = None
    ) -> "BaseTranslator":
        """
        Sağlayıcı adına göre uygun translator nesnesini oluşturur ve döndürür.

        Parametreler:
            saglayici    : 'openai' | 'anthropic' | 'google' | 'xai' | 'openrouter'
            api_anahtari : Sağlayıcıya ait API anahtarı
            model_adi    : Kullanılacak model adı
            ekstra_konfig: Sağlayıcıya özgü ek ayarlar (şu an yalnızca openrouter kullanır)

        Döndürür:
            İlgili BaseTranslator alt sınıfının örneği

        Fırlatır:
            ValueError — bilinmeyen sağlayıcı adı verilirse
        """
        saglayici = saglayici.lower().strip()

        if saglayici == "openai":
            return OpenAITranslator(
                api_anahtari=api_anahtari,
                model_adi=model_adi
            )

        elif saglayici == "anthropic":
            return AnthropicTranslator(
                api_anahtari=api_anahtari,
                model_adi=model_adi
            )

        elif saglayici == "google":
            return GeminiTranslator(
                api_anahtari=api_anahtari,
                model_adi=model_adi
            )

        elif saglayici == "xai":
            return GrokTranslator(
                api_anahtari=api_anahtari,
                model_adi=model_adi
            )

        elif saglayici == "openrouter":
            return OpenRouterTranslator(
                api_anahtari=api_anahtari,
                model_adi=model_adi,
                ekstra_konfig=ekstra_konfig
            )

        else:
            desteklenenler = ", ".join(TranslatorFactory._SAGLAYICILAR)
            raise ValueError(
                f"Bilinmeyen sağlayıcı: '{saglayici}'. "
                f"Desteklenen sağlayıcılar: {desteklenenler}"
            )

    @staticmethod
    def get_available_models(saglayici: str) -> list[str]:
        """
        Belirtilen sağlayıcı için kullanılabilir model listesini döndürür.

        Parametreler:
            saglayici : Sağlayıcı adı

        Döndürür:
            Model adları listesi.
            OpenRouter için boş liste döner (kullanıcı kendi yazar).
            Bilinmeyen sağlayıcı için de boş liste döner.
        """
        return TranslatorFactory._MODELLER.get(saglayici.lower().strip(), [])

    @staticmethod
    def get_saglayici_display_name(saglayici: str) -> str:
        """
        Sağlayıcının kullanıcıya gösterilecek Türkçe görünen adını döndürür.

        Parametreler:
            saglayici : Sağlayıcı kod adı (örn. 'openai')

        Döndürür:
            Görünen ad (örn. 'OpenAI').
            Bilinmeyen sağlayıcı için sağlayıcı adı büyük harfle döner.
        """
        return TranslatorFactory._GORUNTU_ADLARI.get(
            saglayici.lower().strip(),
            saglayici.upper()
        )

    @staticmethod
    def get_tum_saglayicilar() -> list[str]:
        """
        Desteklenen tüm sağlayıcı kod adlarını döndürür.
        UI'da provider listesi oluştururken kullanılır.
        """
        return list(TranslatorFactory._SAGLAYICILAR)

    @staticmethod
    def get_openrouter_populer_modeller() -> list[dict]:
        """
        OpenRouter için önceden tanımlı popüler model listesini döndürür.
        API erişimi yapılmadan anında kullanılabilir; ilk açılışta
        kullanıcıya model göstermek için idealdir.

        Döndürür:
            Model dict listesi. Her dict şunları içerir:
              - id   : Model kimliği (örn. "anthropic/claude-3.5-sonnet")
              - name : Görünen ad
        """
        return [
            {"id": m["id"], "name": m["name"]}
            for m in TranslatorFactory._OPENROUTER_POPULER_MODELLER
        ]

    @staticmethod
    def openrouter_modellerini_yukle(api_key: str) -> list[dict]:
        """
        OpenRouter API'sinden güncel model listesini çeker.
        Bu metod senkron olarak çalışır; UI thread'ini bloke etmemek
        için settings_widget.py içindeki OpenRouterModelListWorker
        kullanılmalıdır.

        Parametreler:
            api_key : OpenRouter API anahtarı

        Döndürür:
            Model dict listesi
        """
        return get_openrouter_models(api_key)


# =============================================================================
# HIZLI TEST — python translator.py ile doğrudan çalıştırılabilir
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Novel Cevir men — Ceviri Modulu Testi")
    print("=" * 60)

    # --- Sozluk talimatı testi ---
    print("\n[TEST 1] Sozluk talimati olusturma")
    test_sozluk = [
        {"orijinal_terim": "Kirito",  "cevrilmis_terim": "Kirito"},
        {"orijinal_terim": "Aincrad", "cevrilmis_terim": "Aincrad"},
        {"orijinal_terim": "SAO",     "cevrilmis_terim": "SAO"},
    ]
    talimat = sozluk_talimati_olustur(test_sozluk)
    print(talimat)

    print("\n[TEST 2] Bos sozluk talimat")
    bos_talimat = sozluk_talimati_olustur([])
    print(f"  Bos liste sonucu: '{bos_talimat}' (bos olmali)")

    # --- Sistem promptu testi ---
    print("\n[TEST 3] Sistem promptu olusturma")
    prompt = sistem_promptu_olustur("Japonca", "Turkce", test_sozluk)
    # Yalnizca ilk 300 karakteri goster
    print(prompt[:300] + "..." if len(prompt) > 300 else prompt)

    # --- Factory testi ---
    print("\n[TEST 4] TranslatorFactory.get_available_models()")
    for saglayici in TranslatorFactory.get_tum_saglayicilar():
        modeller  = TranslatorFactory.get_available_models(saglayici)
        goruntu   = TranslatorFactory.get_saglayici_display_name(saglayici)
        print(f"  {goruntu:25s} -> {modeller if modeller else '(kullanici girer)'}")

    print("\n[TEST 5] Bilinmeyen saglayici hata kontrolu")
    try:
        TranslatorFactory.get_translator("bilinmeyen", "anahtar", "model")
    except ValueError as hata:
        print(f"  Beklenen hata alindi: {hata}")

    print("\n" + "=" * 60)
    print("Tum testler tamamlandi.")
    print("NOT: Gercek API cagrisi testi icin gecerli bir API")
    print("     anahtari ile TranslatorFactory.get_translator()")
    print("     kullanin ve translate_bolum() cagirin.")
    print("=" * 60)