"""
benchmark_perf.py — Story Dictionary performans ölçümü
Mevcut (before) ve optimize edilmiş (after) karşılaştırması.

Çalıştırma:
    python benchmark_perf.py
"""

import random
import re
import string
import time
import unicodedata
from collections import Counter
from typing import Dict, List


# ---------------------------------------------------------------------------
# Yardımcı: _normalize_key (story_dict'ten kopyalandı)
# ---------------------------------------------------------------------------
def _normalize_key(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    nfkd = nfkd.lower()
    nfkd = re.sub(r"[\s\-_''`]+", "", nfkd)
    nfkd = re.sub(r"[^\w]", "", nfkd, flags=re.UNICODE)
    return nfkd


# ---------------------------------------------------------------------------
# Veri üreteci
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Lin", "Ye", "Chen", "Wang", "Li", "Zhang", "Liu", "Yang", "Wu", "Zhao",
    "Qin", "Han", "Tang", "Song", "Ming", "Feng", "Xiao", "Hao", "Jun", "Kai",
    "Ren", "Jian", "Long", "Xing", "Yue", "Tian", "Bai", "Zhu", "Shen", "Luo",
]
LAST_NAMES = [
    "Feng", "Chen", "Yun", "Xue", "Ling", "Dao", "Zhen", "Huo", "Lei", "Shan",
    "Hai", "Kong", "Yuan", "Jing", "Mo", "Ge", "Wei", "Hu", "Meng", "Lan",
]
PLACES = [
    "Abyss Palace", "Divine Mountain", "Crystal Tower", "Shadow Gate",
    "Heaven Realm", "Crimson Valley", "Azure Peak", "Storm Citadel",
    "Iron Fortress", "Jade Garden", "Thunder Domain", "Void Abyss",
]
SKILLS = [
    "Sky Sword Technique", "Nine Heavens Slash", "Crimson Lotus Art",
    "Thunder Fist Method", "Wind Step Dance", "Iron Body Scripture",
    "Dragon Claw Strike", "Phoenix Rising Form", "Star Blade Stance",
    "Shadow Walk Technique", "Soul Pierce Slash", "Divine Flame Art",
]


def _gen_term(i: int) -> dict:
    """i'nci terim sözlüğünü üretir."""
    if i < len(FIRST_NAMES) * len(LAST_NAMES):
        fn = FIRST_NAMES[i % len(FIRST_NAMES)]
        ln = LAST_NAMES[i % len(LAST_NAMES)]
        phrase = f"{fn} {ln}"
    elif i < len(FIRST_NAMES) * len(LAST_NAMES) + len(PLACES):
        phrase = PLACES[i % len(PLACES)]
    elif i < len(FIRST_NAMES) * len(LAST_NAMES) + len(PLACES) + len(SKILLS):
        phrase = SKILLS[i % len(SKILLS)]
    else:
        # Ek rastgele terimler
        phrase = f"Term{i:04d} Suffix{i % 50}"
    return {
        "id": i + 1,
        "orijinal_terim": phrase,
        "cevrilmis_terim": f"TR_{phrase}",
        "entity_type": "PERSON",
        "confidence": 1.0,
        "occurrences": 1,
        "first_chapter": 0,
        "last_chapter": 0,
        "locked": (i % 10 == 0),
        "normalize_key": "",
    }


def generate_entries(n: int) -> list:
    seen, result = set(), []
    i = 0
    while len(result) < n:
        e = _gen_term(i)
        nk = _normalize_key(e["orijinal_terim"])
        if nk not in seen:
            seen.add(nk)
            result.append(e)
        i += 1
    return result


def generate_chapter_text(entries: list, target_chars: int = 50_000) -> str:
    """
    Sözlükteki terimlerin bir kısmını içeren yapay bölüm metni üretir.
    """
    rng = random.Random(42)
    words_pool = [
        "the", "and", "was", "with", "his", "her", "they", "from",
        "that", "this", "have", "been", "into", "upon", "before", "after",
        "then", "also", "said", "will", "would", "could", "through",
        "power", "energy", "spirit", "realm", "battle", "strike", "move",
    ]
    phrases = [e["orijinal_terim"] for e in entries[:200]]  # ilk 200 terimi metne göm

    parts = []
    total = 0
    while total < target_chars:
        # Cümle üret
        sentence_words = []
        for _ in range(rng.randint(5, 15)):
            if rng.random() < 0.15 and phrases:
                sentence_words.append(rng.choice(phrases))
            else:
                sentence_words.append(rng.choice(words_pool))
        sentence = " ".join(sentence_words).capitalize() + ". "
        parts.append(sentence)
        total += len(sentence)

    return "".join(parts)


# ---------------------------------------------------------------------------
# BEFORE: mevcut lookup_all_in_text implementasyonu
# ---------------------------------------------------------------------------
class BeforeEngine:
    """Mevcut (optimize edilmemiş) implementasyon."""

    def __init__(self, entries: list):
        from story_dict import DictEntry, _normalize_key as nk
        self._table: Dict[str, DictEntry] = {}
        for row in entries:
            key = row.get("normalize_key") or nk(row.get("orijinal_terim", ""))
            if not key:
                continue
            e = DictEntry(
                id=row["id"],
                original=row["orijinal_terim"],
                translation=row["cevrilmis_terim"],
                entity_type=row["entity_type"],
                confidence=row["confidence"] or 1.0,
                occurrences=row["occurrences"] or 1,
                first_chapter=row["first_chapter"] or 0,
                last_chapter=row["last_chapter"] or 0,
                locked=bool(row["locked"]),
                normalize_key=key,
            )
            self._table[key] = e

    def lookup_all_in_text(self, text: str) -> list:
        """Her çağrıda sort + her entry için re.compile + finditer."""
        results = []
        sorted_entries = sorted(
            self._table.values(),
            key=lambda e: len(e.original),
            reverse=True
        )
        used_spans = []
        for entry in sorted_entries:
            pattern = re.compile(
                r'\b' + re.escape(entry.original) + r'\b',
                re.IGNORECASE
            )
            for m in pattern.finditer(text):
                start, end = m.span()
                if any(s <= start < e or s < end <= e for s, e in used_spans):
                    continue
                used_spans.append((start, end))
                results.append((m.group(), entry))
        return results


# ---------------------------------------------------------------------------
# AFTER: optimize edilmiş implementasyon
# ---------------------------------------------------------------------------
class AfterEngine:
    """
    Optimize edilmiş implementasyon:
    1. Pattern'ler __init__'te bir kez derlenir, cache'lenir.
    2. Sıralanmış liste de __init__'te hazırlanır.
    3. Büyük sözlüklerde tek geçişli alternatif (Aho-Corasick benzeri
       birleşik regex) kullanılır.
    """

    # Kaç entry'den itibaren birleşik (alternation) regex kullanılsın
    COMBINED_THRESHOLD = 150

    def __init__(self, entries: list):
        from story_dict import DictEntry, _normalize_key as nk
        self._table: Dict[str, DictEntry] = {}
        for row in entries:
            key = row.get("normalize_key") or nk(row.get("orijinal_terim", ""))
            if not key:
                continue
            e = DictEntry(
                id=row["id"],
                original=row["orijinal_terim"],
                translation=row["cevrilmis_terim"],
                entity_type=row["entity_type"],
                confidence=row["confidence"] or 1.0,
                occurrences=row["occurrences"] or 1,
                first_chapter=row["first_chapter"] or 0,
                last_chapter=row["last_chapter"] or 0,
                locked=bool(row["locked"]),
                normalize_key=key,
            )
            self._table[key] = e

        # Uzunluğa göre sıralanmış entry listesi (bir kez hesaplanır)
        self._sorted_entries = sorted(
            self._table.values(),
            key=lambda e: len(e.original),
            reverse=True
        )
        # Bireysel compiled pattern'ler (her entry için bir kez)
        self._compiled: Dict[str, re.Pattern] = {
            e.normalize_key: re.compile(
                r'\b' + re.escape(e.original) + r'\b',
                re.IGNORECASE
            )
            for e in self._sorted_entries
        }
        # Büyük sözlük: birleşik alternation regex (tek geçiş)
        if len(self._sorted_entries) >= self.COMBINED_THRESHOLD:
            self._combined_pattern = re.compile(
                r'\b(' + '|'.join(
                    re.escape(e.original) for e in self._sorted_entries
                ) + r')\b',
                re.IGNORECASE
            )
            # Lowercase → entry hızlı lookup
            self._phrase_lower_map: Dict[str, object] = {
                e.original.lower(): e for e in self._sorted_entries
            }
        else:
            self._combined_pattern = None
            self._phrase_lower_map = {}

    def lookup_all_in_text(self, text: str) -> list:
        """
        Büyük sözlüklerde tek geçişli birleşik regex;
        küçük sözlüklerde önceden derlenmiş pattern'ler.
        Greedy (uzun eşleşme öncelikli) davranış korunur.
        """
        if self._combined_pattern is not None:
            return self._lookup_combined(text)
        return self._lookup_individual(text)

    def _lookup_combined(self, text: str) -> list:
        """Tek geçişli: birleşik regex ile tüm eşleşmeleri bul, örtüşme filtrele."""
        results = []
        used_spans: list = []
        # Eşleşmeleri bul (regex alternation, uzun terimler önce sıralandı)
        for m in self._combined_pattern.finditer(text):
            start, end = m.span()
            if any(s <= start < e or s < end <= e for s, e in used_spans):
                continue
            phrase_lower = m.group().lower()
            entry = self._phrase_lower_map.get(phrase_lower)
            if entry is None:
                # Büyük/küçük harf farkı — tam eşleşme ara
                for k, v in self._phrase_lower_map.items():
                    if k == phrase_lower:
                        entry = v
                        break
            if entry:
                used_spans.append((start, end))
                results.append((m.group(), entry))
        return results

    def _lookup_individual(self, text: str) -> list:
        """Küçük sözlük: önceden derlenmiş pattern'lerle tek tek ara."""
        results = []
        used_spans: list = []
        for entry in self._sorted_entries:
            pattern = self._compiled[entry.normalize_key]
            for m in pattern.finditer(text):
                start, end = m.span()
                if any(s <= start < e or s < end <= e for s, e in used_spans):
                    continue
                used_spans.append((start, end))
                results.append((m.group(), entry))
        return results


# ---------------------------------------------------------------------------
# Benchmark çalıştırıcı
# ---------------------------------------------------------------------------
def benchmark(label: str, fn, *args, repeat: int = 5) -> float:
    # Isınma
    fn(*args)
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn(*args)
        times.append(time.perf_counter() - t0)
    avg = sum(times) / len(times)
    mn  = min(times)
    print(f"  {label:<45} avg={avg*1000:7.1f}ms  min={mn*1000:7.1f}ms")
    return avg


def run_lookup_benchmark():
    print("\n" + "=" * 65)
    print("BENCHMARK 1 — lookup_all_in_text (farklı sözlük boyutları)")
    print("=" * 65)

    for n_entries, n_chars in [
        (50,   10_000),
        (200,  10_000),
        (500,  20_000),
        (1000, 20_000),
    ]:
        entries = generate_entries(n_entries)
        text    = generate_chapter_text(entries, n_chars)

        before = BeforeEngine(entries)
        after  = AfterEngine(entries)

        print(f"\n  Sözlük: {n_entries:4d} terim | Metin: {n_chars:,} karakter")
        b_avg = benchmark("  BEFORE (per-call sort+compile)", before.lookup_all_in_text, text)
        a_avg = benchmark("  AFTER  (cache+combined regex) ", after.lookup_all_in_text,  text)
        speedup = b_avg / a_avg if a_avg > 0 else float("inf")
        print(f"  {'→ Hızlanma:':45} {speedup:.1f}x")

        # Sonuç tutarlılığı
        b_res = set(m for m, _ in before.lookup_all_in_text(text))
        a_res = set(m for m, _ in after.lookup_all_in_text(text))
        ok = b_res == a_res
        print(f"  {'→ Sonuç tutarlılığı:':45} {'OK' if ok else 'FARK VAR! ' + str(b_res ^ a_res)}")


def run_analyze_chapter_benchmark():
    """_extract_candidates + analyze_chapter benchmark."""
    print("\n" + "=" * 65)
    print("BENCHMARK 2 — analyze_chapter (engine instantiate vs. re-use)")
    print("=" * 65)

    from story_dict import StoryDictionaryEngine

    n_bolum  = 20
    n_chars  = 10_000
    entries  = generate_entries(200)
    bolumler = [generate_chapter_text(entries, n_chars) for _ in range(n_bolum)]

    print(f"\n  {n_bolum} bölüm × {n_chars:,} karakter")

    # BEFORE: her bölümde yeni engine
    def before_analyze():
        for bolum_text in bolumler:
            eng = StoryDictionaryEngine(entries)
            eng.analyze_chapter(bolum_text, bolum_no=1)

    # AFTER: engine bir kez oluşturulur, bölümler arasında re-use
    def after_analyze():
        eng = StoryDictionaryEngine(entries)
        for i, bolum_text in enumerate(bolumler):
            eng.analyze_chapter(bolum_text, bolum_no=i + 1)

    b_avg = benchmark("  BEFORE (her bölümde yeni engine)", before_analyze, repeat=3)
    a_avg = benchmark("  AFTER  (engine re-use)           ", after_analyze,  repeat=3)
    speedup = b_avg / a_avg if a_avg > 0 else float("inf")
    print(f"  {'→ Hızlanma:':45} {speedup:.1f}x")


def run_db_insert_benchmark():
    """Tekli vs. toplu DB insert benchmark."""
    print("\n" + "=" * 65)
    print("BENCHMARK 3 — DB oneri_ekle tekli vs. toplu insert")
    print("=" * 65)

    import sqlite3, os, tempfile
    from story_dict import _normalize_key

    db_path = os.path.join(tempfile.gettempdir(), "bench_test.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE sozluk_oneri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seri_id INTEGER, orijinal_terim TEXT,
            entity_type TEXT, confidence REAL, occurrences INTEGER,
            bolum_no INTEGER, normalize_key TEXT, durum TEXT
        )
    """)
    conn.commit()

    N = 500  # toplam insert sayısı
    rows = [
        (1, f"Term {i}", "PERSON", 0.75, i % 5 + 1, i % 10,
         _normalize_key(f"Term {i}"), "bekliyor")
        for i in range(N)
    ]

    print(f"\n  {N} satır insert")

    # BEFORE: her satır için ayrı execute+commit
    def before_insert():
        conn.execute("DELETE FROM sozluk_oneri")
        conn.commit()
        for r in rows:
            conn.execute(
                "INSERT INTO sozluk_oneri (seri_id,orijinal_terim,entity_type,"
                "confidence,occurrences,bolum_no,normalize_key,durum) VALUES (?,?,?,?,?,?,?,?)",
                r
            )
            conn.commit()

    # AFTER: executemany + tek commit
    def after_insert():
        conn.execute("DELETE FROM sozluk_oneri")
        conn.commit()
        conn.executemany(
            "INSERT INTO sozluk_oneri (seri_id,orijinal_terim,entity_type,"
            "confidence,occurrences,bolum_no,normalize_key,durum) VALUES (?,?,?,?,?,?,?,?)",
            rows
        )
        conn.commit()

    b_avg = benchmark("  BEFORE (tekli execute+commit)  ", before_insert, repeat=3)
    a_avg = benchmark("  AFTER  (executemany+tek commit)", after_insert,  repeat=3)
    speedup = b_avg / a_avg if a_avg > 0 else float("inf")
    print(f"  {'→ Hızlanma:':45} {speedup:.1f}x")

    conn.close()
    os.remove(db_path)


def run_table_render_benchmark():
    """setUpdatesEnabled ile tablo doldurma fark tahmini (headless)."""
    print("\n" + "=" * 65)
    print("BENCHMARK 4 — QTableWidget render maliyeti tahmini")
    print("=" * 65)
    print("  (PyQt6 headless benchmark — setCellWidget maliyeti)")

    try:
        import sys
        from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget, QHBoxLayout, QLabel
        app = QApplication.instance() or QApplication(sys.argv)

        N = 300
        tablo = QTableWidget()
        tablo.setColumnCount(5)

        def fill_without_freeze():
            tablo.setRowCount(0)
            for i in range(N):
                tablo.insertRow(i)
                tablo.setItem(i, 0, QTableWidgetItem(str(i)))
                tablo.setItem(i, 1, QTableWidgetItem(f"Terim {i}"))
                tablo.setItem(i, 2, QTableWidgetItem(f"TR Terim {i}"))
                w = QWidget()
                l = QHBoxLayout(w)
                l.addWidget(QLabel("PERSON"))
                tablo.setCellWidget(i, 3, w)
                tablo.setItem(i, 4, QTableWidgetItem("notlar"))

        def fill_with_freeze():
            tablo.setUpdatesEnabled(False)
            tablo.blockSignals(True)
            tablo.setRowCount(0)
            for i in range(N):
                tablo.insertRow(i)
                tablo.setItem(i, 0, QTableWidgetItem(str(i)))
                tablo.setItem(i, 1, QTableWidgetItem(f"Terim {i}"))
                tablo.setItem(i, 2, QTableWidgetItem(f"TR Terim {i}"))
                w = QWidget()
                l = QHBoxLayout(w)
                l.addWidget(QLabel("PERSON"))
                tablo.setCellWidget(i, 3, w)
                tablo.setItem(i, 4, QTableWidgetItem("notlar"))
            tablo.blockSignals(False)
            tablo.setUpdatesEnabled(True)

        b_avg = benchmark(f"  BEFORE ({N} satır, updates açık)  ", fill_without_freeze, repeat=5)
        a_avg = benchmark(f"  AFTER  ({N} satır, updates kapalı)", fill_with_freeze,    repeat=5)
        speedup = b_avg / a_avg if a_avg > 0 else float("inf")
        print(f"  {'→ Hızlanma:':45} {speedup:.1f}x")

    except Exception as ex:
        print(f"  (Qt headless benchmark atlandı: {ex})")


if __name__ == "__main__":
    print("Novel Translator — Performans Benchmark")
    print("Python sürümü:", __import__("sys").version.split()[0])

    run_lookup_benchmark()
    run_analyze_chapter_benchmark()
    run_db_insert_benchmark()
    run_table_render_benchmark()

    print("\n" + "=" * 65)
    print("Benchmark tamamlandı.")
    print("=" * 65)