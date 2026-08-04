# Changelog

Tüm önemli değişiklikler bu dosyada belgelenir.

---

## [Unreleased]

### Düzeltmeler
- `_islem_butonlari_ekle`: CSS `{}` parantezlerinin `.format()` ile çakışması düzeltildi (KeyError)
- `_otomatik_sozluk_onerisi`: `_secili_bolum_id` → `aktif_bolum_id` attribute hatası düzeltildi
- `settings_widget`: yanlış DB metod adları düzeltildi (`tum_ai_ayarlarini_getir`, `ai_ayar_getir`)

---

## [0.5.0] - 2025-07-17

### Yeni Özellikler

#### Story Consistency Dictionary (Hikaye Tutarlılık Sözlüğü)
- **`story_dict.py`** — NER tabanlı entity engine eklendi
  - `EntityType`: PERSON, LOCATION, ORGANIZATION, TITLE, SKILL, ABILITY, ITEM, RACE, MONSTER, REALM
  - `_normalize_key()`: fuzzy matching (`Ye Chen` / `Ye-Chen` / `YeChen` → aynı anahtar)
  - Stop-word listesi: 150+ İngilizce + Türkçe yaygın kelime ve generic fantasy terimi
  - Entity pattern sınıflandırıcı: Realm, Örgüt, Mekan, Beceri, Eşya, Irk kalıpları
  - `StoryDictionaryEngine`: O(1) hash tabanlı arama, greedy match, kilit koruması
  - `analyze_chapter()`: güven skoru eşiklerine göre auto_save / suggestions ayrımı
  - `build_translation_instructions()`: kilitli terimler önce, prompt'a eklenecek sözlük talimatı

#### Sözlük Widget Yenileme (`glossary_widget.py`)
- Tablo 6 → 9 sütuna genişledi: kilit (🔒), entity türü rozeti, geçiş sayısı, güven skoru
- Yeni **Öneriler sekmesi**: satır satır onayla / reddet, "Tümünü Onayla / Reddet"
- Kilit toggle butonu: kilitli girişler altın renkte gösterilir
- AI kilitli girişleri asla değiştiremez
- Otomatik tarama artık NER motoru kullanıyor (eski regex tabanlı tarama kaldırıldı)
- CSV dışa aktarma genişletildi: entity_type, confidence, occurrences, locked alanları eklendi
- Inline düzenleme → otomatik kilit

#### Chapters Widget (`chapters_widget.py`)
- `_otomatik_sozluk_onerisi` yeniden yazıldı: 350 satır regex → 40 satır NER çağrısı
- Çeviri sonrası öneriler sessizce DB'ye yazılıyor, bildirim ile yönlendirme yapılıyor

### İyileştirmeler
- **API anahtarı güvenliği** (`secure_store.py`): Windows DPAPI şifreleme, otomatik migrasyon
- **Worker yaşam döngüsü**: iptal butonu, `requestInterruption`, sinyal disconnect
- **Uzun bölüm desteği** (`text_utils.py`): paragraf/cümle bazlı parçalama (~5500 karakter)
- **Performans**: sözlük taramasında greedy match, bölüm listesinde `setUpdatesEnabled`
- **UX kısayolları**: Ctrl+Enter, Ctrl+F, Ctrl+R, Ctrl+D, Ctrl+Shift+G, F1
- **Paketleme**: `novel_cevirmen.spec` + `build_exe.bat` ile tek tık EXE

---

## [0.4.0] - 2025-07-10

### Yeni Özellikler
- Çeviri kalitesi araçları (`quality_tools.py`): diff görünümü, sözlük uyum kontrolü
- Toplu çeviri worker iptali desteği
- DB alias temizliği: standart API metod adları

### Düzeltmeler
- `settings_widget` açılırken çökme sorunu giderildi
- `SUTUN_KATEGORI` → `SUTUN_ENTITY` geçişi

---

## [0.3.0] - 2025-07-01

### Yeni Özellikler
- OpenRouter sağlayıcı desteği
- Çeviri önbellekleme (SQLite)
- Seri yedekleme / geri yükleme
- Streaming çeviri desteği

---

## [0.2.0] - 2025-06-15

### Yeni Özellikler
- Google Gemini ve Grok desteği
- Bölüm sıralama ve toplu çeviri
- CSV içe / dışa aktarma
- Koyu tema (mor aksan)

---

## [0.1.0] - 2025-06-01

### İlk Sürüm
- PyQt6 tabanlı masaüstü arayüzü
- OpenAI ve Anthropic desteği
- SQLite veritabanı
- Temel sözlük yönetimi
- Seri ve bölüm CRUD işlemleri