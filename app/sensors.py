# =============================================================
# sensors.py — Get sensor readings (simulated or from CSV)
# =============================================================
# This file has two functions:
#   get_reading(crop)      → returns fake (but realistic) sensor
#                            values so you can test without hardware
#   read_from_csv(path)    → reads the LAST row of a real CSV file
#                            so you can plug in actual sensor data later
# =============================================================

# --- Imports ---
import random                       # random lets us generate random numbers
import csv                          # csv lets us read .csv files (spreadsheet format)
from pathlib import Path            # Path builds file paths that work on any OS


# =============================================================
# FUNCTION 1 — Simulated sensor reading
# =============================================================

def get_reading(crop):
    """
    Return a dictionary with realistic fake sensor values.

    Parameters:
        crop (str): the crop name, like "tomato", "potato", "corn".
                    We use it to adjust the ranges slightly so
                    the simulation feels more realistic.

    Returns:
        A dictionary with these keys:
            soil_moisture   – percent (0 to 100)
            soil_temp_c     – soil temperature in Celsius
            air_temp_c      – air temperature in Celsius
            humidity        – relative humidity in percent
            rain_last_24h_mm – millimetres of rain in the last 24 hours
    """

    # --- Set realistic ranges depending on the crop ---
    # Each crop is grown in slightly different conditions.
    # We store the min and max for each value in a dictionary.
    # These are rough ranges just for simulation — not science.

    # "ranges" is a dictionary where:
    #   key   = crop name (lowercase)
    #   value = another dictionary with (min, max) tuples
    ranges = {
        "tomato": {
            "soil_moisture": (15, 80),      # percent
            "soil_temp_c":   (18, 35),      # Celsius
            "air_temp_c":    (20, 42),      # Celsius
            "humidity":      (40, 85),      # percent
        },
        "potato": {
            "soil_moisture": (12, 75),
            "soil_temp_c":   (14, 28),
            "air_temp_c":    (15, 35),
            "humidity":      (50, 90),
        },
        "corn": {
            "soil_moisture": (20, 85),
            "soil_temp_c":   (20, 38),
            "air_temp_c":    (22, 44),
            "humidity":      (35, 80),
        },
    }

    # .lower() converts the crop name to lowercase so "Tomato"
    # and "tomato" both work.
    crop_lower = crop.lower()

    # If the crop is not in our ranges dictionary, use a generic range
    if crop_lower in ranges:
        r = ranges[crop_lower]
    else:
        # Default ranges that work for most crops
        r = {
            "soil_moisture": (15, 80),
            "soil_temp_c":   (16, 35),
            "air_temp_c":    (18, 40),
            "humidity":      (40, 85),
        }

    # --- Generate random values within the ranges ---

    # random.uniform(a, b) returns a random decimal number between a and b
    # round(..., 1) rounds it to 1 decimal place (e.g. 27.4)
    soil_moisture = round(random.uniform(*r["soil_moisture"]), 1)
    # The * unpacks the tuple (15, 80) into two separate arguments:
    #     random.uniform(15, 80)

    soil_temp_c = round(random.uniform(*r["soil_temp_c"]), 1)

    air_temp_c = round(random.uniform(*r["air_temp_c"]), 1)

    humidity = round(random.uniform(*r["humidity"]), 1)

    # Rain: most days have 0 mm rain.  We simulate this by
    # giving a 70% chance of no rain and a 30% chance of some rain.
    # random.random() returns a number between 0.0 and 1.0
    if random.random() < 0.70:
        rain_last_24h_mm = 0.0              # no rain (70% of the time)
    else:
        rain_last_24h_mm = round(random.uniform(0.5, 25.0), 1)  # some rain

    # --- Build the result dictionary ---
    reading = {
        "crop":             crop_lower,
        "soil_moisture":    soil_moisture,
        "soil_temp_c":      soil_temp_c,
        "air_temp_c":       air_temp_c,
        "humidity":         humidity,
        "rain_last_24h_mm": rain_last_24h_mm,
    }

    return reading


# =============================================================
# FUNCTION 2 — Read the last row from a real sensor CSV file
# =============================================================
# When you connect a real sensor, it can append one row to a
# CSV file every few minutes.  This function reads the LAST row
# so you always get the most recent reading.
#
# Expected CSV columns (header row):
#   crop, soil_moisture, soil_temp_c, air_temp_c, humidity, rain_last_24h_mm

def read_from_csv(path):
    """
    Read the last row of a sensor CSV file and return it as a
    dictionary with the same keys as get_reading().

    Parameters:
        path (str or Path): path to the CSV file

    Returns:
        A dictionary with the sensor values, or None if the
        file is empty or missing.
    """

    # Turn the path into a Path object (in case it was a string)
    path = Path(path)

    # Check if the file exists
    if not path.exists():
        print(f"[ERROR] Sensor CSV file not found: {path}")
        return None                 # None means "no value" in Python

    # Open the file and read all rows
    with open(path, "r", encoding="utf-8") as f:

        # csv.DictReader reads each row as a dictionary where
        # the keys come from the header row (the first line)
        reader = csv.DictReader(f)

        # Convert the reader into a list so we can grab the last row.
        # list() reads every row into memory — fine for small files.
        rows = list(reader)

    # If the file is empty (only a header, no data rows)
    if len(rows) == 0:
        print(f"[ERROR] CSV file has no data rows: {path}")
        return None

    # Grab the last row (index -1 means "the last item in a list")
    last_row = rows[-1]

    # csv.DictReader reads everything as strings ("27.4" not 27.4).
    # We need to convert the number columns to float so the rest
    # of our code can do math with them.
    reading = {
        "crop":             last_row["crop"].strip().lower(),
        "soil_moisture":    float(last_row["soil_moisture"]),
        "soil_temp_c":      float(last_row["soil_temp_c"]),
        "air_temp_c":       float(last_row["air_temp_c"]),
        "humidity":         float(last_row["humidity"]),
        "rain_last_24h_mm": float(last_row["rain_last_24h_mm"]),
    }
    # .strip() removes any extra spaces around the text
    # float() converts a string like "27.4" into the number 27.4

    return reading


# =============================================================
# MAIN SECTION — test the functions from the terminal
# =============================================================
# Run:   python app/sensors.py
# Or:    python app/sensors.py potato

import sys      # sys.argv gives us command-line arguments

if __name__ == "__main__":

    # If the user typed a crop name, use it; otherwise default to "tomato"
    if len(sys.argv) >= 2:
        crop = sys.argv[1]
    else:
        crop = "tomato"

    # Generate a simulated reading
    reading = get_reading(crop)

    # Print it nicely
    print(f"\n===== SIMULATED SENSOR READING ({crop}) =====")
    # .items() gives us each key-value pair in the dictionary
    for key, value in reading.items():
        print(f"  {key:<20}: {value}")
    print("=" * 46)
    print()
    
    
    # =============================================================
# FUNCTION - fixed readings for demos
# =============================================================
def get_scenario_reading(crop, scenario):
    """
    Return a fixed, predictable reading for a demo scenario:
    "dry_hot", "normal" or "rainy". Any other name gives a random reading.
    """
    scenarios = {
        "dry_hot": {"soil_moisture": 18.0, "soil_temp_c": 30.0,
                    "air_temp_c": 40.0, "humidity": 35.0, "rain_last_24h_mm": 0.0},
        "normal":  {"soil_moisture": 50.0, "soil_temp_c": 24.0,
                    "air_temp_c": 28.0, "humidity": 60.0, "rain_last_24h_mm": 0.0},
        "rainy":   {"soil_moisture": 60.0, "soil_temp_c": 22.0,
                    "air_temp_c": 25.0, "humidity": 85.0, "rain_last_24h_mm": 12.0},
    }

    if scenario not in scenarios:
        return get_reading(crop)

    reading = dict(scenarios[scenario])     # copy, so the original is not changed
    reading["crop"] = crop.lower()
    return reading