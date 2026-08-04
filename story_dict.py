"""
story_dict.py — Story Consistency Dictionary Engine

NER tabanlı entity tanıma, fuzzy matching, güven skoru hesaplama,
hash tabanlı O(1) arama ve çeviri tutarlılık yönetimi.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# =============================================================================
# ENTİTY TİPLERİ
# =============================================================================

class EntityType:
    PERSON       = "PERSON"
    LOCATION     = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    TITLE        = "TITLE"
    SKILL        = "SKILL"
    ABILITY      = "ABILITY"
    ITEM         = "ITEM"
    RACE         = "RACE"
    MONSTER      = "MONSTER"
    REALM        = "REALM"

    ALL = [
        PERSON, LOCATION, ORGANIZATION, TITLE,
        SKILL, ABILITY, ITEM, RACE, MONSTER, REALM,
    ]


# =============================================================================
# NORMALIZE KEY — fuzzy matching temeli
# =============================================================================

def _normalize_key(text: str) -> str:
    """
    Fuzzy matching için normalize key üretir.
    Ye Chen / Ye-Chen / YeChen → yechen
    """
    if not text:
        return ""
    # Unicode normalize et
    nfkd = unicodedata.normalize("NFKD", text)
    # Küçük harf, tire/alt çizgi/boşluk sil
    nfkd = nfkd.lower()
    nfkd = re.sub(r"[\s\-_''`]+", "", nfkd)
    # Sadece alfanumerik karakterler (ASCII + temel Türkçe)
    nfkd = re.sub(r"[^\w]", "", nfkd, flags=re.UNICODE)
    return nfkd


# =============================================================================
# STOP WORD LİSTESİ — saklanmaması gereken kelimeler
# =============================================================================

_STOP_WORDS: set[str] = {
    # Zamirler
    "he", "she", "it", "they", "him", "her", "them", "his", "hers", "its",
    "i", "me", "my", "we", "us", "our", "you", "your",
    # Makaleler
    "a", "an", "the",
    # Edatlar
    "of", "to", "in", "on", "at", "for", "with", "from", "by",
    "into", "onto", "upon", "about", "against", "between",
    # Yardımcı fiiller
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    # Yaygın fiiller
    "go", "come", "take", "look", "know", "say", "think",
    "get", "see", "make", "give", "find", "tell", "ask",
    "seem", "feel", "try", "leave", "call", "keep", "let",
    "begin", "show", "hear", "play", "run", "move", "live",
    "believe", "hold", "bring", "happen", "write", "stand",
    # Yaygın sıfatlar
    "good", "bad", "small", "large", "young", "old", "new",
    "big", "little", "long", "high", "great", "own", "other",
    "right", "next", "last", "first", "few", "more", "most",
    # Yaygın isimler
    "door", "house", "food", "book", "table", "chair",
    "man", "men", "woman", "women", "child", "people",
    "day", "time", "year", "way", "thing", "place",
    # Sayılar / ay / gün adları
    "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "hundred", "thousand",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Bağlaçlar / zarflar
    "and", "or", "but", "so", "yet", "nor", "if", "as",
    "that", "which", "who", "when", "where", "while",
    "then", "than", "also", "just", "very", "too",
    "only", "even", "still", "here", "there", "now",
    "back", "away", "down", "up", "out", "off", "over",
    # Türkçe yaygın kelimeler
    "bir", "bu", "ve", "de", "da", "ki", "ile", "için", "ama",
    "ne", "o", "ben", "sen", "biz", "siz", "onlar",
    "dedi", "diye", "gibi", "kadar", "sonra", "önce", "her", "hiç",
    "çok", "az", "daha", "en", "hem", "veya", "ancak", "ise", "artık",
    "zaten", "bile", "sadece", "yani", "şimdi", "nasıl",
    "neden", "nerede", "kim", "hangi", "olmak", "etmek", "yapmak",
    "tamam", "evet", "hayır", "lütfen", "çünkü", "eğer", "değil",
}

# Generic fantasy terms — tek başına özel isim sayılmaz
_GENERIC_FANTASY: set[str] = {
    "lord", "king", "queen", "prince", "princess", "emperor", "empress",
    "master", "elder", "senior", "junior",
    "god", "goddess", "demon", "devil", "angel", "saint",
    "dark", "light", "shadow", "black", "white", "red", "blue",
    "sword", "blade", "staff", "shield", "spear", "bow", "dagger",
    "magic", "spell", "skill", "power", "force", "energy", "aura",
    "heaven", "hell", "earth", "world", "realm", "land", "domain",
    "fire", "water", "wind", "thunder", "lightning", "storm",
    "dragon", "beast", "monster", "spirit", "soul", "body", "mind",
    "blood", "heart", "death", "life", "void",
    "clan", "sect", "guild", "tribe", "order", "empire", "kingdom",
    "north", "south", "east", "west", "inner", "outer", "upper", "lower",
    "ancient", "eternal", "supreme", "ultimate",
    "level", "rank", "stage", "peak", "layer", "tier",
    "disciple", "student", "teacher",
    "path", "road", "door", "gate", "hall", "room", "tower",
    "holy", "sacred", "divine",
    "ninth", "eighth", "seventh", "sixth", "fifth", "fourth",
    "battle", "fight", "war", "peace",
}


def _is_stop_word(word: str) -> bool:
    """Kelimenin stop-word veya tek başına anlamsız olup olmadığını kontrol eder."""
    lw = word.lower().strip()
    return (
        lw in _STOP_WORDS or
        lw in _GENERIC_FANTASY or
        len(lw) <= 2 or
        lw.isdigit()
    )


# =============================================================================
# ENTİTY PATTERN SINIFLANDIRICI
# =============================================================================

# Kalıp: (regex, entity_type, confidence_bonus)
_ENTITY_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # Realm / cultivation kalıpları
    (re.compile(
        r'\b(?:(?:Gold|Silver|Bronze|Iron|Diamond|Crystal|Jade|Qi|'
        r'Foundation|Core|Nascent|Soul|Immortal|Divine|Heavenly|'
        r'Peak|Middle|Early|Late|Initial)\s+)+'
        r'(?:Realm|Stage|Layer|Tier|Rank|Level|Core|Formation|Condensation|'
        r'Transformation|Ascension|Tribulation)\b',
        re.IGNORECASE
    ), EntityType.REALM, 0.25),

    # Örgüt / Klan / Sect
    (re.compile(
        r'\b\w+(?:\s+\w+){0,3}\s+'
        r'(?:Clan|Sect|Guild|Alliance|Order|Palace|Hall|Empire|Kingdom|'
        r'Pavilion|Chamber|Association|Union|Family)\b',
        re.IGNORECASE
    ), EntityType.ORGANIZATION, 0.20),

    # Yer / Mekan
    (re.compile(
        r'\b\w+(?:\s+\w+){0,3}\s+'
        r'(?:Mountain|Peak|Valley|Forest|Lake|Sea|Ocean|Desert|Plain|'
        r'Island|City|Town|Village|Castle|Tower|Temple|Ruins|Abyss|'
        r'Continent|Realm|Land|Domain|Gate|Bridge|Road|Pass|Cave)\b',
        re.IGNORECASE
    ), EntityType.LOCATION, 0.20),

    # Beceri / Teknik (maks 4 kelime — büyük harfli başlayan)
    (re.compile(
        r'\b(?:[A-ZÇŞĞÜÖİ]\w*\s+){1,3}'
        r'(?:Technique|Art|Style|Fist|Slash|Strike|Palm|'
        r'Step|Dance|Form|Stance|Method|Mantra|Scripture|'
        r'Sutra|Array|Formation|Seal|Rune|Spell)\b',
    ), EntityType.SKILL, 0.20),

    # Eşya / Silah / Artifact (maks 4 kelime — büyük harfli başlayan)
    (re.compile(
        r'\b(?:[A-ZÇŞĞÜÖİ]\w*\s+){1,3}'
        r'(?:Blade|Spear|Bow|Staff|Ring|Armor|Shield|'
        r'Pendant|Artifact|Relic|Gem|Crystal|Orb|Cauldron|'
        r'Pill|Elixir|Talisman|Token|Badge)\b',
    ), EntityType.ITEM, 0.20),

    # Irk / Canavar türü
    (re.compile(
        r'\b\w+(?:\s+\w+){0,2}\s+'
        r'(?:Race|Tribe|Species|Kind|Beast|Monster|Demon|Spirit|'
        r'Dragon|Phoenix|Qilin|Tiger|Wolf)\b',
        re.IGNORECASE
    ), EntityType.RACE, 0.15),
]

# Çok kelimeli isim kalıbı (Ye Chen, Li Ming-Zhe, Kang Geom-Ma)
_MULTI_WORD_NAME_RE = re.compile(
    r'\b[A-ZÇŞĞÜÖİ][a-zA-Zçşğüöıİ]*(?:-[a-zA-Zçşğüöıİ]+)*'
    r'(?:\s+[A-ZÇŞĞÜÖİ][a-zA-Zçşğüöıİ]*(?:-[a-zA-Zçşğüöıİ]+)*)+\b'
)

# Tekil büyük harfli kelime (min 4 karakter)
_SINGLE_CAP_RE = re.compile(r'\b[A-ZÇŞĞÜÖİ][a-zA-Zçşğüöıİ]{3,}\b')


def _classify_entity(phrase: str) -> tuple[str, float]:
    """
    Bir ifadeyi entity tipine ve başlangıç güven skoruna sınıflandırır.
    Döndürür: (entity_type, confidence)
    """
    # Önce belirli kalıpları dene
    for pattern, etype, bonus in _ENTITY_PATTERNS:
        if pattern.search(phrase):
            base = 0.70 + bonus
            return etype, min(base, 0.95)

    # Çok kelimeli → muhtemelen karakter ismi veya unvan
    words = phrase.split()
    if len(words) >= 2:
        return EntityType.PERSON, 0.72

    # Tekil kelime → daha düşük güven
    return EntityType.PERSON, 0.65


# =============================================================================
# STORY DICTIONARY ENGINE
# =============================================================================

@dataclass
class DictEntry:
    """Tek bir sözlük girişini temsil eder."""
    id: int
    original: str
    translation: str
    entity_type: str
    confidence: float
    occurrences: int
    first_chapter: int
    last_chapter: int
    locked: bool
    normalize_key: str = field(default="")

    def __post_init__(self):
        if not self.normalize_key:
            self.normalize_key = _normalize_key(self.original)


class StoryDictionaryEngine:
    """
    Story Consistency Dictionary Engine.

    Özellikler:
    - O(1) hash tabanlı arama
    - Fuzzy matching (normalize_key ile)
    - Kilitli giriş koruması
    - Entity tipi sınıflandırma
    - Bölüm analizi: otomatik kayıt adayları + öneriler
    """

    # Güven eşikleri
    CONFIDENCE_AUTO  = 0.80   # >= bu değer → otomatik kayıt adayı
    CONFIDENCE_SUGGEST = 0.50 # >= bu değer → öneri
    MIN_FREQUENCY    = 2      # min kaç kez geçmeli (özel isim değilse)

    def __init__(self, existing_entries: list[dict]):
        # hash tablosu: normalize_key → DictEntry
        self._table: Dict[str, DictEntry] = {}
        self._load_entries(existing_entries)

    def _load_entries(self, entries: list[dict]):
        """Veritabanı kayıtlarını engine'e yükler."""
        self._table.clear()
        for row in entries:
            nk = row.get("normalize_key") or _normalize_key(row.get("orijinal_terim", ""))
            if not nk:
                continue
            entry = DictEntry(
                id            = row.get("id", 0),
                original      = row.get("orijinal_terim", ""),
                translation   = row.get("cevrilmis_terim", ""),
                entity_type   = row.get("entity_type", EntityType.PERSON),
                confidence    = row.get("confidence", 1.0) or 1.0,
                occurrences   = row.get("occurrences", 1) or 1,
                first_chapter = row.get("first_chapter", 0) or 0,
                last_chapter  = row.get("last_chapter", 0) or 0,
                locked        = bool(row.get("locked", False)),
                normalize_key = nk,
            )
            self._table[nk] = entry

    # ── Arama ────────────────────────────────────────────────────────────────

    def lookup(self, phrase: str) -> Optional[DictEntry]:
        """O(1) arama. Bulunamazsa None döner."""
        nk = _normalize_key(phrase)
        return self._table.get(nk)

    def lookup_all_in_text(self, text: str) -> list[tuple[str, DictEntry]]:
        """
        Metindeki tüm bilinen entity'leri bulur.
        Uzun terimler önce aranır (greedy match).
        Döndürür: [(orijinal_metin_span, DictEntry)]
        """
        results: list[tuple[str, DictEntry]] = []
        # Uzun term önce (greedy)
        sorted_entries = sorted(
            self._table.values(),
            key=lambda e: len(e.original),
            reverse=True
        )
        used_spans: list[tuple[int, int]] = []

        for entry in sorted_entries:
            pattern = re.compile(
                r'\b' + re.escape(entry.original) + r'\b',
                re.IGNORECASE
            )
            for m in pattern.finditer(text):
                start, end = m.span()
                # Örtüşme kontrolü
                if any(s <= start < e or s < end <= e for s, e in used_spans):
                    continue
                used_spans.append((start, end))
                results.append((m.group(), entry))

        return results

    def build_translation_instructions(self) -> str:
        """
        Çeviri promptuna eklenecek sözlük talimatını oluşturur.
        Kilitli terimler önce listelenir.
        """
        if not self._table:
            return ""

        locked   = [e for e in self._table.values() if e.locked]
        unlocked = [e for e in self._table.values() if not e.locked]
        ordered  = sorted(locked, key=lambda e: e.original) + \
                   sorted(unlocked, key=lambda e: e.original)

        lines = [
            "HİKAYE TUTARLILIK SÖZLÜĞÜ — Aşağıdaki terimleri MUTLAKA "
            "belirtilen şekilde çevir. Bunları asla farklı çevirme:"
        ]
        for entry in ordered:
            lock_tag = " ⟨KİLİTLİ⟩" if entry.locked else ""
            lines.append(f"- {entry.original} → {entry.translation}{lock_tag}")

        return "\n".join(lines)

    # ── Bölüm Analizi ─────────────────────────────────────────────────────────

    def analyze_chapter(
        self,
        text: str,
        bolum_no: int = 0,
        existing_entries: list[dict] | None = None,
    ) -> dict:
        """
        Bir bölümü analiz eder; entity adaylarını döndürür.

        Döndürür:
        {
            "auto_save":   [{"phrase", "entity_type", "confidence", "frequency"}],
            "suggestions": [...],
            "known_hits":  [{"phrase", "entry_id", "translation"}],
        }
        """
        # Mevcut sözlüğü güncelle (çağrıldı ise)
        if existing_entries is not None:
            self._load_entries(existing_entries)

        known_hits = self._find_known_entities(text)
        candidates = self._extract_candidates(text)
        mevcut_keys = set(self._table.keys())

        auto_save:   list[dict] = []
        suggestions: list[dict] = []

        for phrase, freq, etype, conf in candidates:
            nk = _normalize_key(phrase)
            if nk in mevcut_keys:
                continue  # Zaten sözlükte

            # Minimum frekans kuralı (özel isim değilse)
            is_proper = _is_explicitly_proper(phrase)
            if not is_proper and freq < self.MIN_FREQUENCY:
                continue

            entry_dict = {
                "phrase":      phrase,
                "entity_type": etype,
                "confidence":  conf,
                "frequency":   freq,
                "bolum_no":    bolum_no,
            }

            if conf >= self.CONFIDENCE_AUTO:
                auto_save.append(entry_dict)
            elif conf >= self.CONFIDENCE_SUGGEST:
                suggestions.append(entry_dict)

        return {
            "auto_save":   auto_save,
            "suggestions": suggestions,
            "known_hits":  known_hits,
        }

    def _find_known_entities(self, text: str) -> list[dict]:
        """Metinde bilinen entity'leri bulur."""
        hits = self.lookup_all_in_text(text)
        return [
            {
                "phrase":      span,
                "entry_id":    entry.id,
                "translation": entry.translation,
                "locked":      entry.locked,
            }
            for span, entry in hits
        ]

    def _extract_candidates(self, text: str) -> list[tuple[str, int, str, float]]:
        """
        Metinden entity adayları çıkarır.
        Döndürür: [(phrase, frequency, entity_type, confidence)]
        """
        freq_counter: Counter[str] = Counter()
        type_map:  Dict[str, str]  = {}
        conf_map:  Dict[str, float] = {}

        # 1) Çok kelimeli kalıplar önce (greedy)
        for m in _MULTI_WORD_NAME_RE.finditer(text):
            phrase = m.group()
            if _is_stop_phrase(phrase):
                continue
            freq_counter[phrase] += 1
            if phrase not in type_map:
                etype, conf = _classify_entity(phrase)
                type_map[phrase] = etype
                conf_map[phrase] = conf

        # 2) Belirli entity kalıpları
        for pattern, etype, bonus in _ENTITY_PATTERNS:
            for m in pattern.finditer(text):
                phrase = m.group()
                if _is_stop_phrase(phrase):
                    continue
                # Çok kelimeli grubun altında mı?
                if any(phrase in k and k != phrase for k in freq_counter):
                    continue
                freq_counter[phrase] += 1
                if phrase not in type_map:
                    type_map[phrase] = etype
                    conf_map[phrase] = min(0.70 + bonus, 0.95)

        # 3) Tekil büyük harfli kelimeler (cümle başı atlayarak)
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            words = _SINGLE_CAP_RE.findall(sent)
            for word in words[1:]:  # cümle başını atla
                if _is_stop_word(word):
                    continue
                # Çok kelimeli grubun parçası mı?
                if any(word in k for k in freq_counter if ' ' in k or '-' in k):
                    continue
                freq_counter[word] += 1
                if word not in type_map:
                    etype, conf = _classify_entity(word)
                    type_map[word] = etype
                    conf_map[word] = conf

        # Sıklaştır ve döndür
        results = []
        for phrase, freq in freq_counter.most_common(60):
            if phrase not in type_map:
                continue
            results.append((
                phrase,
                freq,
                type_map[phrase],
                conf_map[phrase],
            ))

        return results


def _is_stop_phrase(phrase: str) -> bool:
    """Tüm kelimeleri stop-word ise ifadeyi reddet."""
    words = phrase.split()
    if not words:
        return True
    return all(_is_stop_word(w) for w in words)


def _is_explicitly_proper(phrase: str) -> bool:
    """
    İfadenin açıkça özel isim olduğunu kontrol eder.
    (Büyük harfle başlayan iki+ kelime veya bilinen kalıp)
    """
    words = phrase.split()
    if len(words) >= 2:
        return all(w[0].isupper() for w in words if w)
    return False


# =============================================================================
# HIZLI TEST
# =============================================================================

if __name__ == "__main__":
    test_text = """
    Lin Feng walked toward the Abyss Palace with his Sky Sword Technique ready.
    Ye Chen of the Divine Dragon Clan was already there.
    The Golden Core Realm practitioner grinned.
    Lin Feng activated the Nine Heavens Slash, but Ye Chen countered with the
    Crimson Lotus Art. The World Tree loomed above them.
    He was not afraid. She watched from the shadows.
    The door opened slowly.
    """

    engine = StoryDictionaryEngine([])
    result = engine.analyze_chapter(test_text, bolum_no=1)

    print("=== AUTO SAVE ===")
    for a in result["auto_save"]:
        print(f"  [{a['entity_type']:12}] {a['phrase']!r:<35} conf={a['confidence']:.2f} freq={a['frequency']}")

    print("\n=== SUGGESTIONS ===")
    for s in result["suggestions"]:
        print(f"  [{s['entity_type']:12}] {s['phrase']!r:<35} conf={s['confidence']:.2f} freq={s['frequency']}")

    print(f"\nTotal auto_save: {len(result['auto_save'])}")
    print(f"Total suggestions: {len(result['suggestions'])}")

    # Normalize key test
    assert _normalize_key("Ye Chen") == _normalize_key("Ye-Chen") == _normalize_key("YeChen").lower().replace(" ", "")
    print("\nNormalize key test: OK")