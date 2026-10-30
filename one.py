# =============================================================
# LESSON 1: Variables and Types
# =============================================================
# A "variable" is a name that stores a value in your program.
# Think of it like a label on a container — the label is the
# variable name, and the container holds the value.
#
# Python has several basic "types" (kinds of data):
#   int   → whole numbers        (e.g. 42)
#   float → decimal numbers      (e.g. 36.5)
#   str   → text, always in quotes (e.g. "wheat")
#   bool  → True or False
# =============================================================


# --- int (integer = a whole number, no decimal point) ---
# How many sensors are installed on the farm?
sensor_count = 5                    # 5 is an int
print(sensor_count)                 # print() shows the value on screen


# --- float (a number WITH a decimal point) ---
# Soil moisture measured by the sensor (percentage)
soil_moisture = 27.4                # 27.4 is a float
print(soil_moisture)


# --- str (string = a piece of text, always inside quotes) ---
# Name of the crop currently planted
crop_name = "wheat"                 # "wheat" is a str
print(crop_name)


# --- bool (boolean = only True or False) ---
# Is the irrigation pump currently running?
pump_on = False                     # False is a bool
print(pump_on)


# --- Checking the type of a variable ---
# type() is a built-in function that tells you what kind of
# data a variable holds.
print(type(sensor_count))           # <class 'int'>
print(type(soil_moisture))          # <class 'float'>
print(type(crop_name))             # <class 'str'>
print(type(pump_on))               # <class 'bool'>


# --- print() with multiple values ---
# You can print several things on one line by separating them
# with commas.
print("Crop:", crop_name, "| Moisture:", soil_moisture)


# --- f-string (formatted string) ---
# An f-string lets you put variables INSIDE a string.
# Start the string with the letter f, then put variable names
# inside curly braces {}.
report = f"Crop: {crop_name}, Soil moisture: {soil_moisture}%"
print(report)


# You can even do small calculations inside the braces.
temperature_c = 38.2
print(f"Temperature: {temperature_c}°C = {temperature_c * 9/5 + 32}°F")


# --- Changing a variable's value ---
# Variables can be updated at any time.
soil_moisture = 45.0                # sensor sends a new reading
print(f"Updated moisture: {soil_moisture}%")


# =============================================================
# FULL EXAMPLE: Print a mini soil-sensor report
# =============================================================
field_name = "Field A"
soil_moisture = 31.2
soil_temperature = 28.5
crop_name = "rice"
is_irrigated = True

print("===== SENSOR REPORT =====")
print(f"Field        : {field_name}")
print(f"Crop         : {crop_name}")
print(f"Moisture     : {soil_moisture}%")
print(f"Temperature  : {soil_temperature}°C")
print(f"Irrigated    : {is_irrigated}")
print("=========================")


# =============================================================
# EXERCISES — Try them yourself!
# =============================================================

# EXERCISE 1
# Create variables for a second field called "Field B" growing
# "maize" with moisture 22.8, temperature 33.1, and the pump
# is OFF (False). Then print a sensor report just like above.
# ----------------------------------------------------------
# TODO: write your code below



# EXERCISE 2
# A farmer wants to know how much water (in litres) is needed.
# Create two variables:
#   area_sqm   = 500    (area of the field in square metres)
#   water_per_sqm = 2.5 (litres of water needed per square metre)
# Calculate the total water needed, store it in a variable
# called total_water, and print it using an f-string like:
#   "Total water needed for 500 sqm: 1250.0 litres"
# ----------------------------------------------------------
# TODO: write your code below