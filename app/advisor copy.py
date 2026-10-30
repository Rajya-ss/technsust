# =============================================================
# advisor.py - Ask a local LLM (Ollama) for farming advice
# =============================================================
# What this file does:
#   1. Takes the disease result, the irrigation decision and the
#      sensor reading.
#   2. Sends them to a local AI model (Ollama) and gets back short
#      advice for the farmer, in English or Hindi.
#   3. If Ollama is not running, it builds a simple text answer
#      from the same facts (the "fallback").
#   4. If the disease result is uncertain, a fixed warning sentence
#      is added by OUR code (the model never writes it).
#
# The order of checks for the disease part is always:
#   1. UNCERTAIN -> say nothing about any disease
#   2. HEALTHY   -> say that no disease was found
#   3. otherwise -> say which disease was detected
# =============================================================

# --------------------------- Imports ---------------------------
import re  # removes <think>...</think> text
import json
from pathlib import Path
import requests

# -------------------------------------------------------------
# Knowledge‑base helper imports
# -------------------------------------------------------------
from knowledge_helpers import load_knowledge, get_kb_entry

import json  # reads JSON files
import sys  # command-line arguments and paths
from pathlib import Path  # builds file paths that work on any OS
import requests  # sends requests to Ollama


# --------------------------- Constants -------------------------
# The AI model that Ollama will use (change it here only)
MODEL_NAME = "qwen3.5:9b"

# The address where Ollama listens on your computer
OLLAMA_URL = "http://localhost:11434/api/chat"

# How many seconds to wait for Ollama before giving up
TIMEOUT_SECONDS = 120

# Build paths from the location of THIS file
SCRIPT_DIR = Path(__file__).resolve().parent  # .../smart-farm/app/
PROJECT_DIR = SCRIPT_DIR.parent  # .../smart-farm/
GLOSSARY_PATH = PROJECT_DIR / "data" / "glossary_hi.json"


# ---------------- Fixed "uncertain" sentences ----------------
# We write these ourselves so the farmer always sees the same,
# reliable message. (A native Hindi speaker must check the Hindi.)
UNCERTAIN_EN = (
    "The disease detection result is not certain. "
    "Please show the leaf to a local agriculture officer "
    "or your nearest Krishi Vigyan Kendra (KVK) for a proper diagnosis."
)

UNCERTAIN_HI = (
    "रोग की पहचान निश्चित नहीं है। "
    "कृपया पत्ती को अपने नज़दीकी कृषि अधिकारी "
    "या कृषि विज्ञान केंद्र (KVK) को दिखाएँ।"
)


# ---------------- Fixed Hindi irrigation sentences ----------
# Used only by the fallback (when Ollama is not available).
IRRIGATION_HI = {
    "irrigate_now": "तुरंत सिंचाई करें।",
    "irrigate_soon": "जल्दी ही सिंचाई करने की योजना बनाएँ।",
    "wait": "वर्तमान में जल देने की आवश्यकता नहीं है।",
    "skip_rain": "हाल ही में बारिश हुई है, इसलिए सिंचाई की आवश्यकता नहीं है।",
}


# =============================================================
# Helper - load the Hindi glossary
# =============================================================
def load_glossary():
    """
    Read glossary_hi.json and return it as a dictionary.

    We also make lowercase copies of the crop and disease names,
    so "Healthy" and "healthy" are treated as the same word.

    Returns None if the file is missing.
    """
    if not GLOSSARY_PATH.exists():
        print(f"[WARNING] Hindi glossary not found: {GLOSSARY_PATH}")
        print("  Hindi terms will not be used in prompts or fallback.")
        return None

    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Lowercase lookup tables for case-insensitive searching
    raw["crops_lc"] = {k.lower(): v for k, v in raw.get("crops", {}).items()}
    raw["diseases_lc"] = {k.lower(): v for k, v in raw.get("diseases", {}).items()}

    return raw


# =============================================================
# Helper - remove <think>...</think> text from the model reply
# =============================================================
def remove_think_tags(text):
    """Delete everything between <think> and </think> (inclusive)."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


# =============================================================
# Helper - is the disease result uncertain?
# =============================================================
def is_uncertain(disease_result):
    """
    Return True if we cannot trust the disease result.

    Two cases make it uncertain:
      1. The disease name is "uncertain"
      2. The confidence is below 0.70 (70 percent)
    """
    if disease_result["disease"].lower().strip() == "uncertain":
        return True
    if disease_result["confidence"] < 0.70:
        return True
    return False


# =============================================================
# Helper - make the crop name safe for glossary lookup
# =============================================================
def normalise_crop_name(crop):
    """
    Turn any form of "Corn (maize)" into plain "corn".
    Everything else is just made lowercase ("Tomato" -> "tomato").
    """
    lower = crop.lower().strip()
    if "corn" in lower or "maize" in lower:
        return "corn"
    return lower


# =============================================================
# Helper - get the Hindi crop AND disease names
# =============================================================
def get_hindi_terms(crop, disease, glossary):
    """
    Return (crop_hi, disease_hi) from the glossary.

    If a word is missing, we print a warning (so it is never
    silent) and use the English word instead.
    """
    crop_key = normalise_crop_name(crop)
    disease_key = disease.lower().strip()

    crop_hi = glossary["crops_lc"].get(crop_key)
    disease_hi = glossary["diseases_lc"].get(disease_key)

    if crop_hi is None:
        print(f"[WARNING] Hindi term for crop '{crop}' not found in glossary.")
        crop_hi = crop

    if disease_hi is None:
        print(f"[WARNING] Hindi term for disease '{disease}' not found in glossary.")
        disease_hi = disease

    return crop_hi, disease_hi


# =============================================================
# Helper - get ONLY the Hindi crop name
# =============================================================
def get_hindi_crop(crop, glossary):
    """
    Return the Hindi crop name only. We use this when there is no
    disease name to translate (the leaf is healthy, or the result
    is uncertain).

    If the glossary is missing or the crop is not in it, we print
    a warning and return the English name.
    """
    # No glossary file at all -> keep the English word
    if glossary is None:
        return crop

    crop_key = normalise_crop_name(crop)
    crop_hi = glossary["crops_lc"].get(crop_key)

    if crop_hi is None:
        print(f"[WARNING] Hindi term for crop '{crop}' not found in glossary.")
        return crop

    return crop_hi


# =============================================================
# Build the prompt that we send to Ollama
# =============================================================
def build_prompt(disease_result, irrigation_result, reading, language):
    """Create a text prompt that contains all the facts.

    The order of the checks matters:
      1. UNCERTAIN -> we say nothing about any disease at all.
      2. HEALTHY   -> we say that no disease was found.
      3. otherwise -> we give the disease name.
    """
    crop = disease_result["crop"]
    disease = disease_result["disease"]
    confidence = disease_result["confidence"]

    uncertain = is_uncertain(disease_result)
    disease_lower = disease.lower().strip()

    # ----- Part 1: the disease facts (checked in this order) -----
    if uncertain:
        # No disease name and no confidence number for the model.
        # If it saw "Disease: uncertain" it might try to write about it.
        disease_part = ""
    elif disease_lower == "healthy":
        disease_part = "No disease was found.\n"
    else:
        disease_part = f"Possible disease (not confirmed): {disease}\n"
    # ----- Part 2: the full prompt (English facts, always present) -----
    prompt = (
        f"Crop: {crop}\n"
        f"{disease_part}"
        f"\n"
        f"Irrigation action: {irrigation_result['action']}\n"
        f"Irrigation reason: {irrigation_result['reason']}\n"
        f"\n"
        f"Current sensor reading:\n"
        f"  Soil moisture : {reading['soil_moisture']}%\n"
        f"  Soil temp     : {reading['soil_temp_c']}°C\n"
        f"  Air temp      : {reading['air_temp_c']}°C\n"
        f"  Humidity      : {reading['humidity']}%\n"
        f"  Rain (24h)    : {reading['rain_last_24h_mm']} mm\n"
    )

    # ----- Part 3: Hindi terms (only when Hindi is requested) -----
    if language.lower() == "hindi":
        glossary = load_glossary()

        if glossary is not None:
            if uncertain:
                # Only the crop name is needed
                crop_hi = get_hindi_crop(crop, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                )
            elif disease_lower == "healthy":
                crop_hi = get_hindi_crop(crop, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                    "  No disease found: कोई रोग नहीं मिला।\n"
                )
            else:
                crop_hi, disease_hi = get_hindi_terms(crop, disease, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                    f"  Disease in Hindi: {disease_hi}\n"
                )

    # ----- Part 4: add verified facts from the knowledge base -----
    if not uncertain and disease_lower != "healthy":
        entry = get_kb_entry(crop, disease)
        if entry is not None:
            # English section – always added
            prompt += "\nVerified facts you may use:\n"
            prompt += f"What it is: {entry.get('what_it_is', '')}\n"
            # list what_to_do as bullet points
            what_to_do = entry.get("what_to_do", [])
            if what_to_do:
                prompt += "What to do:\n"
                for step in what_to_do:
                    prompt += f"- {step}\n"
            prevention = entry.get("prevention", [])
            if prevention:
                prompt += "Prevention:\n"
                for step in prevention:
                    prompt += f"- {step}\n"
            # Hindi section – only if Hindi list is not empty
            if language.lower() == "hindi":
                what_to_do_hi = entry.get("what_to_do_hi", [])
                if what_to_do_hi:
                    prompt += "\nVerified facts you may use (Hindi):\n"
                    for step in what_to_do_hi:
                        prompt += f"- {step}\n"

    # ----- Part 5: tell the model what NOT to write when uncertain -----
    if uncertain:
        prompt += (
            "\nThe disease result is uncertain. Do NOT mention any disease "
            "name, and do NOT write any sentence about showing the leaf to "
            "an officer or KVK - that part will be added separately. "
            "Write only about the irrigation advice and the current conditions."
        )

    prompt += f"\n\nPlease give your advice in {language}."
    return prompt
    """
    Create a text prompt that contains all the facts.

    The order of the checks matters:
      1. UNCERTAIN -> we say nothing about any disease at all.
                      (The fixed warning is added later by get_advice.)
      2. HEALTHY   -> we say that no disease was found.
      3. otherwise -> we give the disease name.
    """
    crop = disease_result["crop"]
    disease = disease_result["disease"]
    confidence = disease_result["confidence"]

    uncertain = is_uncertain(disease_result)
    disease_lower = disease.lower().strip()

    # ----- Part 1: the disease facts (checked in this order) -----
    if uncertain:
        # No disease name and no confidence number for the model.
        # If it saw "Disease: uncertain" it might try to write about it.
        disease_part = ""
    elif disease_lower == "healthy":
        disease_part = "No disease was found.\n"
    else:
        disease_part = f"Possible disease (not confirmed): {disease}\n"
    # ----- Part 2: the full prompt (English facts, always present) -----
    prompt = (
        f"Crop: {crop}\n"
        f"{disease_part}"
        f"\n"
        f"Irrigation action: {irrigation_result['action']}\n"
        f"Irrigation reason: {irrigation_result['reason']}\n"
        f"\n"
        f"Current sensor reading:\n"
        f"  Soil moisture : {reading['soil_moisture']}%\n"
        f"  Soil temp     : {reading['soil_temp_c']}°C\n"
        f"  Air temp      : {reading['air_temp_c']}°C\n"
        f"  Humidity      : {reading['humidity']}%\n"
        f"  Rain (24h)    : {reading['rain_last_24h_mm']} mm\n"
    )

    # ----- Part 3: Hindi terms (only when Hindi is requested) -----
    if language.lower() == "hindi":
        glossary = load_glossary()

        if glossary is not None:
            if uncertain:
                # Only the crop name is needed
                crop_hi = get_hindi_crop(crop, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                )
            elif disease_lower == "healthy":
                crop_hi = get_hindi_crop(crop, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                    "  No disease found: कोई रोग नहीं मिला।\n"
                )
            else:
                crop_hi, disease_hi = get_hindi_terms(crop, disease, glossary)
                prompt += (
                    "\nHindi terms to use (use exactly these words):\n"
                    f"  Crop in Hindi   : {crop_hi}\n"
                    f"  Disease in Hindi: {disease_hi}\n"
                )

    # ----- Part 4: tell the model what NOT to write when uncertain -----
    if uncertain:
        prompt += (
            "\nThe disease result is uncertain. Do NOT mention any disease "
            "name, and do NOT write any sentence about showing the leaf to "
            "an officer or KVK - that part will be added separately. "
            "Write only about the irrigation advice and the current conditions."
        )

    prompt += f"\n\nPlease give your advice in {language}."
    return prompt


# =============================================================
# Build a fallback message (no AI) - English and Hindi
# =============================================================
def build_fallback(disease_result, irrigation_result, reading, language):
    """
    Create plain-text advice using only the data we already have.
    This is used when Ollama is not running.

    The order of the checks for the disease part:
      1. UNCERTAIN -> write nothing about disease here
                      (get_advice adds the fixed warning later)
      2. HEALTHY   -> say that no disease was found
      3. otherwise -> say which disease was detected
    """
    crop = disease_result["crop"]
    disease = disease_result["disease"]
    confidence = disease_result["confidence"]
    action = irrigation_result["action"]
    reason = irrigation_result["reason"]

    uncertain = is_uncertain(disease_result)
    disease_lower = disease.lower().strip()

    # =========================== HINDI ===========================
    if language.lower() == "hindi":
        glossary = load_glossary()
        lines = []

        # ----- Disease part -----
    if uncertain:
        pass  # nothing here - the fixed warning comes later

    elif disease_lower == "healthy":
        lines.append("No disease was found.")
        # No knowledge‑base entry for healthy case
    else:
        # Try to get a verified entry from the knowledge base
        entry = get_kb_entry(crop, disease)
        if entry is not None:
            # Use the entry's what_it_is as a short description
            lines.append(f"What it is: {entry.get('what_it_is', '')}".strip())
            # Add the English "what_to_do" steps if they exist
            what_to_do = entry.get("what_to_do", [])
            if what_to_do:
                lines.append("What to do:")
                for step in what_to_do:
                    lines.append(f"- {step}")
            # Add the English "prevention" steps if they exist
            prevention = entry.get("prevention", [])
            if prevention:
                lines.append("Prevention:")
                for step in prevention:
                    lines.append(f"- {step}")
        else:
            # Fallback to the original simple sentence
            lines.append(
                f"Disease detected on {crop}: {disease} (confidence: {confidence:.0%})."
            )
            lines.append(
                "Please consult a local agriculture officer for the correct treatment – do not apply any pesticide without expert advice."
            )

    # ----- Irrigation part -----
    if action == "irrigate_now":
        lines.append(f"Irrigation is needed now. {reason}")
    elif action == "irrigate_soon":
        lines.append(f"Plan to irrigate soon. {reason}")
    elif action == "skip_rain":
        lines.append(f"No irrigation needed - it rained recently. {reason}")
    else:
        lines.append(f"No irrigation needed right now. {reason}")

        if uncertain:
            pass  # nothing here - the fixed warning comes later

        elif disease_lower == "healthy":
            crop_hi = get_hindi_crop(crop, glossary)
            lines.append(f"{crop_hi} में कोई रोग नहीं मिला।")

        else:
            if glossary is not None:
                crop_hi, disease_hi = get_hindi_terms(crop, disease, glossary)
            else:
                crop_hi, disease_hi = crop, disease

            lines.append(
                f"{crop_hi} में {disease_hi} पाया गया है (विश्वास: {confidence:.0%})।"
            )
            lines.append(
                "सही उपचार के लिए स्थानीय कृषि अधिकारी से सलाह लें; "
                "बिना विशेषज्ञ की सलाह के कोई कीटनाशक न लगाएँ।"
            )

        # ----- Irrigation part (fixed Hindi sentences) -----
        if action == "irrigate_now":
            lines.append(IRRIGATION_HI["irrigate_now"])
        elif action == "irrigate_soon":
            lines.append(IRRIGATION_HI["irrigate_soon"])
        elif action == "skip_rain":
            lines.append(IRRIGATION_HI["skip_rain"])
        else:  # "wait" or anything else
            lines.append(IRRIGATION_HI["wait"])

        # ----- Sensor summary -----
        lines.append(
            f"वर्तमान स्थितियां: मिट्टी की नमी {reading['soil_moisture']}%, "
            f"हवा का तापमान {reading['air_temp_c']}°C, आर्द्रता {reading['humidity']}%."
        )

        # ----- Note that the AI was not used -----
        lines.append("[ध्यान: AI सहायक उपलब्ध नहीं है; यह केवल उपलब्ध डेटा का सारांश है।]")

        return "\n".join(lines)

    # ========================== ENGLISH ==========================
    lines = []

    # ----- Disease part -----
    if uncertain:
        pass  # nothing here - the fixed warning comes later

    elif disease_lower == "healthy":
        lines.append("No disease was found.")
        # No knowledge‑base entry for healthy case
    else:
        # Try to get a verified entry from the knowledge base
        entry = get_kb_entry(crop, disease)
        if entry is not None:
            # Use the entry's what_it_is as a short description
            lines.append(f"What it is: {entry.get('what_it_is', '')}".strip())
            # Add the English "what_to_do" steps if they exist
            what_to_do = entry.get("what_to_do", [])
            if what_to_do:
                lines.append("What to do:")
                for step in what_to_do:
                    lines.append(f"- {step}")
            # Add the English "prevention" steps if they exist
            prevention = entry.get("prevention", [])
            if prevention:
                lines.append("Prevention:")
                for step in prevention:
                    lines.append(f"- {step}")
        else:
            # Fallback to the original simple sentence
            lines.append(
                f"Disease detected on {crop}: {disease} (confidence: {confidence:.0%})."
            )
            lines.append(
                "Please consult a local agriculture officer for the correct treatment – do not apply any pesticide without expert advice."
            )

    # ----- Irrigation part -----
    if action == "irrigate_now":
        lines.append(f"Irrigation is needed now. {reason}")
    elif action == "irrigate_soon":
        lines.append(f"Plan to irrigate soon. {reason}")
    elif action == "skip_rain":
        lines.append(f"No irrigation needed - it rained recently. {reason}")
    else:
        lines.append(f"No irrigation needed right now. {reason}")

    if uncertain:
        pass  # nothing here - the fixed warning comes later

    elif disease_lower == "healthy":
        lines.append("No disease was found.")

    else:
        lines.append(
            f"Disease detected on {crop}: {disease} (confidence: {confidence:.0%})."
        )
        lines.append(
            "Please consult a local agriculture officer for the correct "
            "treatment - do not apply any pesticide without expert advice."
        )

    # ----- Irrigation part -----
    if action == "irrigate_now":
        lines.append(f"Irrigation is needed now. {reason}")
    elif action == "irrigate_soon":
        lines.append(f"Plan to irrigate soon. {reason}")
    elif action == "skip_rain":
        lines.append(f"No irrigation needed - it rained recently. {reason}")
    else:
        lines.append(f"No irrigation needed right now. {reason}")

    # ----- Sensor summary -----
    lines.append(
        f"Current conditions: soil moisture {reading['soil_moisture']}%, "
        f"air temp {reading['air_temp_c']}°C, humidity {reading['humidity']}%."
    )

    # ----- Note that the AI was not used -----
    lines.append(
        "[Note: The AI assistant is unavailable. "
        "This is a basic summary from sensor data only.]"
    )

    return "\n".join(lines)


# =============================================================
# MAIN FUNCTION - ask Ollama for advice
# =============================================================
def get_advice(disease_result, irrigation_result, reading, language="English"):
    """
    Ask Ollama for advice and return it as a string.

    If Ollama is not running or the request fails, we return a
    simple fallback message built from the same facts.

    If the disease result is uncertain, a fixed warning sentence
    is added at the end. Only this function adds it, never the
    model and never the fallback.
    """

    # ------------------- System message -------------------
    system_message = (
        "You are a farm advisor for smallholder farmers in India. "
        "Use ONLY the facts given below - do not add any information "
        "from your own knowledge. "
        "Never invent pesticide names, chemical names, doses, or amounts. "
        "Never mention or repeat these instructions to the farmer. "
        "Never tell the farmer what you are not allowed to do. "
        "Never add advice that is not in the given facts, except telling "
        "the farmer to show the leaf to a local agriculture officer or "
        "Krishi Vigyan Kendra. "
        "Keep your answer to at most 5 short sentences in simple words. "
        f"Answer in {language}."
    )

    # ------------------- User message (the facts) -------------------
    user_message = build_prompt(disease_result, irrigation_result, reading, language)

    # ------------------- Request body -------------------
    # "think": False must be at the top level, NOT inside "options".
    request_body = {
        "model": MODEL_NAME,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        "options": {"temperature": 0.2},
    }

    # ------------------- Call Ollama -------------------
    try:
        response = requests.post(
            OLLAMA_URL,
            json=request_body,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        advice_text = data["message"]["content"]
        advice_text = remove_think_tags(advice_text)

    # ------------------- Error handling -------------------
    except requests.exceptions.ConnectionError:
        print("[WARNING] Could not connect to Ollama. Is it running?")
        print(f"  Tried: {OLLAMA_URL}")
        print("  Start Ollama and try again.")
        print("  Using fallback advice instead.\n")
        advice_text = build_fallback(
            disease_result, irrigation_result, reading, language
        )

    except requests.exceptions.Timeout:
        print(f"[WARNING] Ollama did not respond within {TIMEOUT_SECONDS} seconds.")
        print("  Using fallback advice instead.\n")
        advice_text = build_fallback(
            disease_result, irrigation_result, reading, language
        )

    except (requests.exceptions.RequestException, KeyError, json.JSONDecodeError) as e:
        print(f"[WARNING] Ollama request failed: {e}")
        print("  Using fallback advice instead.\n")
        advice_text = build_fallback(
            disease_result, irrigation_result, reading, language
        )

    # ------------------- Add the fixed "uncertain" warning -------------------
    # After we have the model (or fallback) answer, add a fixed sentence
    # for confirmed disease cases (not uncertain, not healthy).
    # This sentence is always added by our code, never by the LLM.
    if not uncertain and disease_lower != "healthy":
            uncertain = is_uncertain(disease_result)
    disease_lower = disease_result["disease"].lower().strip()
        # English version (always added)
        advice_text = (
            advice_text.rstrip()
            + "\n\nFor any spray or chemical treatment, ask your local agriculture officer or Krishi Vigyan Kendra for the registered product and the correct dose."
        )
        # Hindi version – only if the user asked for Hindi
        if language.lower() == "hindi":
            # TODO: native speaker must verify the translation
            advice_text = (
                advice_text.rstrip()
                + "\n\nस्प्रे या रसायन उपचार के लिए, स्थानीय कृषि अधिकारी या कृषि विज्ञान केंद्र (KVK) से पंजीकृत उत्पाद और सही मात्रा के बारे में पूछें।"
            )

    if is_uncertain(disease_result):
        if language.lower() == "hindi":
            warning = UNCERTAIN_HI
        else:
            warning = UNCERTAIN_EN
        # .rstrip() removes trailing spaces so we get one clean blank line
        advice_text = advice_text.rstrip() + "\n\n" + warning

    return advice_text


# =============================================================
# TEST SECTION - runs only when you type: python app/advisor.py
# =============================================================
if __name__ == "__main__":
    # ----------------------------------------------------------
    # TEST 1: confident disease + irrigate_now (English)
    # ----------------------------------------------------------
    print("=" * 60)
    print("TEST 1: Confident disease + irrigate_now (English)")
    print("=" * 60)

    disease_1 = {"disease": "Early blight", "crop": "Tomato", "confidence": 0.93}
    irrigation_1 = {
        "action": "irrigate_now",
        "reason": "Soil moisture is 22%, which is below the minimum 30% for tomato.",
    }
    reading_1 = {
        "soil_moisture": 22.0,
        "soil_temp_c": 26.5,
        "air_temp_c": 37.8,
        "humidity": 45.2,
        "rain_last_24h_mm": 0.0,
    }
    print(get_advice(disease_1, irrigation_1, reading_1, language="English"))
    print()

    # ----------------------------------------------------------
    # TEST 2: uncertain disease (English)
    # ----------------------------------------------------------
    print("=" * 60)
    print("TEST 2: Uncertain disease (English)")
    print("=" * 60)

    disease_2 = {"disease": "uncertain", "crop": "Potato", "confidence": 0.45}
    irrigation_2 = {
        "action": "wait",
        "reason": "Soil moisture is 52% and air temperature is 28°C - conditions are normal for potato.",
    }
    reading_2 = {
        "soil_moisture": 52.0,
        "soil_temp_c": 22.1,
        "air_temp_c": 28.0,
        "humidity": 68.3,
        "rain_last_24h_mm": 2.0,
    }
    print(get_advice(disease_2, irrigation_2, reading_2, language="English"))
    print()

    # ----------------------------------------------------------
    # TEST 3: confident disease + irrigate_soon (Hindi)
    # ----------------------------------------------------------
    print("=" * 60)
    print("TEST 3: Confident disease + irrigate_soon (Hindi)")
    print("=" * 60)

    disease_3 = {"disease": "Common rust", "crop": "Corn (maize)", "confidence": 0.88}
    irrigation_3 = {
        "action": "irrigate_soon",
        "reason": "Soil moisture is 40% (OK for now), but air temperature is 41°C which is above 38°C.",
    }
    reading_3 = {
        "soil_moisture": 40.0,
        "soil_temp_c": 32.0,
        "air_temp_c": 41.0,
        "humidity": 38.5,
        "rain_last_24h_mm": 0.0,
    }
    print(get_advice(disease_3, irrigation_3, reading_3, language="Hindi"))
    print()

    # ----------------------------------------------------------
    # TEST 4: healthy leaf (English)
    # ----------------------------------------------------------
    print("=" * 60)
    print("TEST 4: Healthy leaf (English)")
    print("=" * 60)

    disease_4 = {"disease": "healthy", "crop": "Tomato", "confidence": 0.99}
    irrigation_4 = {
        "action": "wait",
        "reason": "Soil moisture is 70% - plenty of water.",
    }
    reading_4 = {
        "soil_moisture": 70.0,
        "soil_temp_c": 25.0,
        "air_temp_c": 30.0,
        "humidity": 55.0,
        "rain_last_24h_mm": 0.0,
    }
    print(get_advice(disease_4, irrigation_4, reading_4, language="English"))
    print()

    # ----------------------------------------------------------
    # TEST 5: healthy leaf (Hindi)
    # ----------------------------------------------------------
    print("=" * 60)
    print("TEST 5: Healthy leaf (Hindi)")
    print("=" * 60)

    disease_5 = {"disease": "healthy", "crop": "Potato", "confidence": 0.98}
    irrigation_5 = {
        "action": "wait",
        "reason": "Soil moisture is 68% - no irrigation needed.",
    }
    reading_5 = {
        "soil_moisture": 68.0,
        "soil_temp_c": 20.0,
        "air_temp_c": 25.0,
        "humidity": 70.0,
        "rain_last_24h_mm": 0.0,
    }
    print(get_advice(disease_5, irrigation_5, reading_5, language="Hindi"))
    print()

    print("=" * 60)
    print("All test cases finished.")
    print("=" * 60)
