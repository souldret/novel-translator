import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
from database import DatabaseManager
db = DatabaseManager()
from story_dict import EntityType

assert EntityType.goruntu("PERSON") == "Karakter", "goruntu hatasi"
assert EntityType.kategoriden("karakter") == "PERSON", "kategoriden hatasi"
assert EntityType.entity_den_kategori("SKILL") == "beceri", "entity_den_kategori hatasi"
assert EntityType.gecerli_mi("PERSON") is True, "gecerli_mi True hatasi"
assert EntityType.gecerli_mi("FOO") is False, "gecerli_mi False hatasi"
print("EntityType.goruntu('PERSON'):", EntityType.goruntu("PERSON"))
print("EntityType.kategoriden('karakter'):", EntityType.kategoriden("karakter"))
print("EntityType.entity_den_kategori('SKILL'):", EntityType.entity_den_kategori("SKILL"))
print("EntityType.renk('LOCATION'):", EntityType.renk("LOCATION"))
print("Tum EntityType testleri gecti: OK")