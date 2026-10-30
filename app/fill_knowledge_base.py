# =============================================================
# fill_knowledge_base.py - puts four DRAFT entries into the knowledge base
# =============================================================
# Run once with:  python app/fill_knowledge_base.py
# Every entry is a draft. Read each source page yourself and check each
# line. An agriculture officer must mark an entry "verified".
# No chemical names and no doses are allowed in this file.
# =============================================================

import json
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
KB_PATH = PROJECT_DIR / "data" / "knowledge_base.json"
BACKUP_PATH = PROJECT_DIR / "data" / "knowledge_base_backup.json"

NEW_ENTRIES = {
    "tomato|early blight": {
        "what_it_is": "A fungal leaf disease that makes dark spots with rings on leaves and fruit.",
        "what_to_do": [
            "Remove and destroy infected plant parts and crop debris from the field.",
            "Avoid wetting the leaves when you water; use furrow or drip irrigation if possible.",
        ],
        "prevention": [
            "Rotate tomato with crops that are not hosts of this disease.",
            "Stake the plants so air can move between them.",
            "Use healthy, disease-free seed and transplants.",
        ],
        "what_to_do_hi": [],
        "sources": [
            "TNAU Agritech Portal, Tomato Early Blight: https://agritech.tnau.ac.in/crop_protection/tomato_diseases_2.html",
            "Connecticut Agricultural Experiment Station, Early Blight of Tomato fact sheet: https://portal.ct.gov/-/media/caes/documents/publications/fact_sheets/plant_pathology_and_ecology/earlyblightoftomato032912pdf.pdf",
        ],
        "status": "draft",
    },
    "tomato|late blight": {
        "what_it_is": "A fast-spreading disease that makes dark, oily-looking patches on leaves and stems and can destroy the whole crop.",
        "what_to_do": [
            "Remove and destroy infected plants as soon as you see the disease.",
            "Remove leftover tomato and potato plants, cull piles and plant debris from the field.",
            "Avoid overhead or sprinkler irrigation if you can.",
            "Do not use too much nitrogen fertiliser.",
        ],
        "prevention": [
            "Plant only healthy transplants that are free of late blight.",
            "Do not grow tomato or potato in the same field for two years.",
            "Ask your Krishi Vigyan Kendra about resistant varieties for your area.",
        ],
        "what_to_do_hi": [],
        "sources": [
            "Utah State University Extension, Late Blight: https://extension.usu.edu/planthealth/ipm/notes_ag/veg-late-blight.php",
            "UC IPM, Tomato Late Blight: https://ipm.ucanr.edu/agriculture/tomato/late-blight/",
            "UC IPM, Tomato Pest Management Guidelines: https://ipm.ucanr.edu/PMG/r783100211.html",
            "UConn, Late Blight of Tomato and Potato: https://homegarden.cahnr.uconn.edu/factsheets/late-blight-of-tomato-and-potato",
        ],
        "status": "draft",
    },
    "potato|late blight": {
        "what_it_is": "A fast-spreading disease that makes dark, greasy-looking patches on leaves and stems and can destroy the whole crop.",
        "what_to_do": [
            "Remove and destroy infected plants as soon as you see the disease.",
            "Remove cull piles, plant debris and leftover potato and tomato plants from the field.",
            "Avoid overhead or sprinkler irrigation if you can.",
            "Do not use too much nitrogen fertiliser.",
        ],
        "prevention": [
            "Use clean, healthy seed potatoes.",
            "Do not grow potato or tomato in the same field for two years.",
            "Ask your Krishi Vigyan Kendra about resistant varieties for your area.",
        ],
        "what_to_do_hi": [],
        "sources": [
            "Utah State University Extension, Late Blight: https://extension.usu.edu/planthealth/ipm/notes_ag/veg-late-blight.php",
            "UConn, Late Blight of Tomato and Potato: https://homegarden.cahnr.uconn.edu/factsheets/late-blight-of-tomato-and-potato",
        ],
        "status": "draft",
    },
    "corn|common rust": {
        "what_it_is": "A fungal disease that makes small, rust-coloured to dark brown pustules on both sides of the leaves.",
        "what_to_do": [
            "Plant resistant maize hybrids in the next planting.",
            "Ask your Krishi Vigyan Kendra which resistant hybrids suit your area.",
        ],
        "prevention": [
            "Choose resistant maize hybrids when you buy seed.",
        ],
        "what_to_do_hi": [],
        "sources": [
            "University of Minnesota Extension, Common rust on corn: https://extension.umn.edu/corn-pest-management/common-rust-corn",
            "Dey et al. 2017, Screening of maize inbred lines and hybrids against common rust, UAS Dharwad: https://www.ojs.pphouse.org/index.php/IJBSM/article/view/1151",
        ],
        "status": "draft",
    },
}

# ----- Make a backup, then read the file -----
if not KB_PATH.exists():
    print(f"[ERROR] File not found: {KB_PATH}")
    raise SystemExit(1)

shutil.copy(KB_PATH, BACKUP_PATH)
print(f"Backup saved: {BACKUP_PATH.name}")

with open(KB_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Some versions keep the entries inside "entries"
entries = data["entries"] if isinstance(data.get("entries"), dict) else data

# ----- Fill the four entries -----
for key, entry in NEW_ENTRIES.items():
    old = entries.get(key)
    if isinstance(old, dict) and old.get("status") == "verified":
        print(f"[SKIPPED] {key} is already verified; not changed.")
        continue
    if old is None:
        print(f"[NOTE] {key} was not in the file; adding it.")
    entries[key] = entry
    print(f"Filled (draft): {key}")

# ----- Save -----
with open(KB_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Done.")