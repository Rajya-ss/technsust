# -------------------------------------------------------------
# Knowledge‑base helper functions
# -------------------------------------------------------------
# Load the JSON file that contains verified farming facts.
# Returns a dict (empty if the file cannot be read).
def normalise_crop_name(crop):
    """Turn 'Corn (maize)' into 'corn' and 'Tomato' into 'tomato'."""
    lower = crop.lower().strip()
    if "corn" in lower or "maize" in lower:
        return "corn"
    return lower


def load_knowledge() -> dict:
    """Read smart‑farm/data/knowledge_base.json and return its contents.

    If the file does not exist or cannot be parsed we return an empty
    dictionary so the rest of the program can continue.
    """
    import json
    from pathlib import Path

    kb_path = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"
    if not kb_path.exists():
        print(f"[WARNING] Knowledge base not found: {kb_path}")
        return {}
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # any I/O or JSON error
        print(f"[ERROR] Failed to load knowledge base: {e}")
        return {}


# -------------------------------------------------------------
# Lookup a single entry in the knowledge base.
# -------------------------------------------------------------


def get_kb_entry(crop: str, disease: str) -> dict | None:
    """Return the knowledge‑base entry for *crop* and *disease*.

    The key is ``"crop|disease"`` in lower‑case.
    * "Corn (maize)" is normalised to "corn".
    * If the entry is missing or its ``status`` is "empty" we return ``None``.
    * If the entry exists but its status is "draft" we print a warning.
    """

    kb = load_knowledge()
    crop_key = normalise_crop_name(crop)  # e.g. "Corn (maize)" → "corn"
    disease_key = disease.lower().strip()
    entry_key = f"{crop_key}|{disease_key}"

    entry = kb.get(entry_key)
    if entry is None:
        return None
    status = entry.get("status", "empty").lower()
    if status == "empty":
        return None
    if status == "draft":
        print(f"[WARNING] Knowledge‑base entry '{entry_key}' is still a draft.")
    return entry
