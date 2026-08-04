# Novel Çevirmen

PyQt6 tabanlı, yapay zeka destekli web novel / light novel çeviri masaüstü uygulaması.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)
![License](https://img.shields.io/badge/license-MIT-purple)

---

## Özellikler

### Çeviri Motoru
- **Çoklu AI sağlayıcı desteği**: OpenAI, Anthropic Claude, Google Gemini, Grok, OpenRouter
- Streaming (gerçek zamanlı) çeviri
- Toplu bölüm çevirisi
- Uzun bölüm desteği: metni akıllıca parçalara böler ve birleştirir
- Çeviri önbellekleme (aynı metin tekrar API çağrısı yapmaz)

### Story Consistency Dictionary (Hikaye Tutarlılık Sözlüğü)
- **NER tabanlı entity tanıma**: PERSON, LOCATION, ORGANIZATION, TITLE, SKILL, ABILITY, ITEM, RACE, MONSTER, REALM
- Stop-word filtresi: "he", "she", "the", "is" gibi kelimeler asla kaydedilmez
- Güven skoru sistemi:
  - `≥ 0.80` → otomatik kayıt adayı
  - `0.50 – 0.79` → kullanıcı onayı gerektiren öneri
- Minimum frekans kuralı: özel isim değilse en az 2 kez geçmeli
- **Fuzzy matching**: `Ye Chen` / `Ye-Chen` / `YeChen` aynı girişle eşleşir
- **Kilit sistemi**: kullanıcı düzenlediği çeviriler kilitlenir, AI bir daha değiştiremez
- Greedy matching: uzun terimler önce eşleşir
- O(1) hash tabanlı arama performansı
- Bölüm analizinden gelen öneriler ayrı sekmede onay bekler

### Arayüz
- Koyu tema (mor aksan)
- Seri listesi yönetimi (ekle, düzenle, sil)
- Bölüm yönetimi (ekle, sırala, toplu çeviri)
- Sözlük tablosu: kilit ikonu, entity türü rozeti, güven skoru, geçiş sayısı
- Öneriler sekmesi: satır satır onayla / reddet
- Diff görünümü (önceki ↔ güncel çeviri)
- Sözlük uyum kontrolü
- Okuma modu
- Otomatik kaydet (30 saniye)

### Güvenlik
- API anahtarları şifreli saklanır (Windows DPAPI / makine anahtarı)
- Eski düz metin anahtarlar ilk çalıştırmada otomatik migrate edilir

### Veri Yönetimi
- SQLite veritabanı
- CSV içe / dışa aktarma (genişletilmiş format: entity_type, confidence, occurrences, locked)
- Proje yedekleme

---

## Kurulum

### Gereksinimler
- Python 3.10 veya üzeri
- PyQt6

```bash
pip install PyQt6 openai anthropic google-generativeai
```

### Çalıştırma

```bash
python main.py
```

### EXE Derleme (Windows)

```bash
build_exe.bat
```

Çıktı: `dist\NovelCevirmen.exe`

---

## Desteklenen AI Sağlayıcılar

| Sağlayıcı | Model Örnekleri |
|---|---|
| OpenAI | gpt-4o, gpt-4-turbo, gpt-3.5-turbo |
| Anthropic | claude-3-5-sonnet, claude-3-opus |
| Google | gemini-1.5-pro, gemini-1.5-flash |
| Grok (xAI) | grok-beta |
| OpenRouter | Her sağlayıcı ve model |

---

## Proje Yapısı

```
novel-translator/
├── main.py                 # Giriş noktası
├── main_window.py          # Ana pencere
├── chapters_widget.py      # Bölüm yönetimi ve çeviri
├── glossary_widget.py      # Story Consistency Dictionary arayüzü
├── settings_widget.py      # AI ayarları
├── database.py             # SQLite yöneticisi
├── translator.py           # AI sağlayıcı adaptörleri
├── story_dict.py           # NER motoru ve entity engine
├── text_utils.py           # Metin parçalama yardımcıları
├── secure_store.py         # API anahtarı şifreleme
├── quality_tools.py        # Diff ve sözlük uyum araçları
├── importers.py            # TXT/EPUB içe aktarma
├── wizards.py              # Seri oluşturma sihirbazı
├── plugin_loader.py        # Eklenti sistemi
├── icons.py                # İkon yardımcıları
└── novel_cevirmen.spec     # PyInstaller yapılandırması
```

---

## Kısayollar

| Kısayol | İşlev |
|---|---|
| Ctrl+Enter | Çevir |
| Ctrl+S | Kaydet |
| Ctrl+F | Metinde ara |
| Ctrl+R | Okuma modu |
| Ctrl+D | Diff (önceki vs güncel) |
| Ctrl+Shift+G | Sözlük uyum kontrolü |
| Esc | İptal / okuma modundan çık |
| F1 | Kısayol listesi |

---

## Lisans

MIT License — dilediğiniz gibi kullanabilir, değiştirebilir ve dağıtabilirsiniz.