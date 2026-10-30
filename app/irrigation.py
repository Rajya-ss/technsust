# =============================================================
# irrigation.py — Decide whether to irrigate right now
# =============================================================
# This file has one main function:
#   irrigation_advice(crop, reading)
#       → looks at sensor values + crop rules
#       → returns a dictionary with "action" and "reason"
#
# No internet needed.  No AI needed.  Just simple if/else rules
# loaded from crop_rules.json.
# =============================================================

# --- Imports ---
import sys                          # sys.argv lets us read command-line arguments
import json                         # json lets us read .json files
from pathlib import Path            # Path builds file paths that work on any OS

# Find the folder this script lives in (smart-farm/app/)
SCRIPT_DIR = Path(__file__).resolve().parent        # .../smart-farm/app/
PROJECT_DIR = SCRIPT_DIR.parent                      # .../smart-farm/

# Path to the crop rules JSON file
RULES_PATH = PROJECT_DIR / "data" / "crop_rules.json"

# Add the app folder to sys.path so Python can find sensors.py
sys.path.insert(0, str(SCRIPT_DIR))

# Import the get_reading function from sensors.py (same folder)
from sensors import get_reading


# =============================================================
# HELPER — Load crop rules from JSON
# =============================================================

def load_rules():
    """
    Read crop_rules.json and return its contents as a dictionary.

    If the file is missing, print a clear error and stop.
    """

    # Check if the file exists on disk
    if not RULES_PATH.exists():
        print(f"[ERROR] Crop rules file not found: {RULES_PATH}")
        print("Make sure crop_rules.json is inside the data/ folder.")
        sys.exit(1)         # stop the program with error code 1

    # Open the file and load the JSON into a Python dictionary
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)

    return rules


# =============================================================
# MAIN FUNCTION — Irrigation advice
# =============================================================

def irrigation_advice(crop, reading):
    """
    Decide whether the farmer should irrigate right now.

    Parameters:
        crop    (str):  crop name, e.g. "tomato"
        reading (dict): sensor data dictionary with keys:
                        soil_moisture, soil_temp_c, air_temp_c,
                        humidity, rain_last_24h_mm

    Returns:
        A dictionary with two keys:
            "action" — one of: "irrigate_now", "irrigate_soon",
                       "wait", "skip_rain"
            "reason" — one plain English sentence explaining why
    """

    # --- Load the rules from the JSON file ---
    rules = load_rules()

    # --- Look up the rules for this specific crop ---
    # .lower() makes the crop name lowercase so "Tomato" and
    # "tomato" both work
    crop_lower = crop.lower()

    # Check if this crop exists in the rules file
    if crop_lower not in rules:
        # Return a safe default if the crop is unknown
        return {
            "action": "wait",
            "reason": f"No rules found for crop '{crop}'. Add it to crop_rules.json first."
        }

    # Get the rules dictionary for this crop
    # Example: {"soil_moisture_low": 30, "soil_moisture_high": 65, ...}
    crop_rules = rules[crop_lower]

    # --- Pull out the threshold values ---
    # A "threshold" is a boundary number that triggers a decision.
    low = crop_rules["soil_moisture_low"]       # below this → irrigate now
    high = crop_rules["soil_moisture_high"]      # above this → do not irrigate
    max_temp = crop_rules["max_air_temp_c"]      # above this → irrigate sooner

    # --- Pull out the sensor values from the reading ---
    moisture = reading["soil_moisture"]           # current soil moisture %
    air_temp = reading["air_temp_c"]              # current air temperature °C
    rain = reading["rain_last_24h_mm"]            # rain in last 24 hours (mm)

    # ==========================================================
    # DECISION RULES (checked in order — first match wins)
    # ==========================================================

    # RULE 1: If it rained more than 5 mm in the last 24 hours,
    #         skip irrigation — the soil already has water.
    if rain > 5:
        return {
            "action": "skip_rain",
            "reason": f"It rained {rain} mm in the last 24 hours, so irrigation is not needed right now."
        }

    # RULE 2: If soil moisture is BELOW the low threshold,
    #         the soil is too dry — irrigate immediately.
    if moisture < low:
        return {
            "action": "irrigate_now",
            "reason": f"Soil moisture is {moisture}%, which is below the minimum {low}% for {crop_lower}."
        }

    # RULE 3: If soil moisture is ABOVE the high threshold,
    #         the soil has enough water — just wait.
    if moisture > high:
        return {
            "action": "wait",
            "reason": f"Soil moisture is {moisture}%, which is above {high}% — no irrigation needed for {crop_lower}."
        }

    # RULE 4: Moisture is between low and high (the middle zone).
    #         If the air temperature is very high, irrigate soon
    #         because water will evaporate faster.
    if air_temp > max_temp:
        return {
            "action": "irrigate_soon",
            "reason": (
                f"Soil moisture is {moisture}% (OK for now), but air temperature "
                f"is {air_temp}°C which is above {max_temp}°C — plan to irrigate soon."
            )
        }

    # RULE 5: If none of the above triggered, everything is fine.
    return {
        "action": "wait",
        "reason": (
            f"Soil moisture is {moisture}% and air temperature is {air_temp}°C "
            f"— conditions are normal for {crop_lower}, no irrigation needed."
        )
    }


# =============================================================
# MAIN SECTION — Run from the terminal
# =============================================================
# Usage:   python app/irrigation.py tomato
#          python app/irrigation.py potato
#          python app/irrigation.py corn

if __name__ == "__main__":

    # Check if the user typed a crop name
    if len(sys.argv) < 2:
        print("Usage:  python app/irrigation.py <crop>")
        print("Example: python app/irrigation.py tomato")
        sys.exit(1)

    # The crop name is the second word the user typed
    crop = sys.argv[1]

    # --- Get a simulated sensor reading ---
    reading = get_reading(crop)

    # --- Print the sensor reading ---
    print(f"\n===== SENSOR READING ({crop}) =====")
    for key, value in reading.items():
        # :<20 means left-align the key in a 20-character-wide column
        print(f"  {key:<20}: {value}")
    print("=" * 40)

    # --- Get the irrigation advice ---
    advice = irrigation_advice(crop, reading)

    # --- Print the advice ---
    print(f"\n===== IRRIGATION ADVICE =====")
    print(f"  Action : {advice['action']}")
    print(f"  Reason : {advice['reason']}")
    print("=" * 40)
    print()