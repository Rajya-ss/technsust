# =============================================================
# predict.py — Plant Disease Prediction using TFLite
# =============================================================
# This script loads a TFLite image-classification model and
# predicts the disease on a photo of a leaf.
# =============================================================

# --- Imports ---
# "import" brings in code that other people wrote so we can
# use it without writing everything from scratch.

import sys                          # sys.argv lets us read command-line arguments
import json                         # json lets us read .json files
from pathlib import Path            # Path helps build file paths that work on any OS

import numpy as np                  # numpy is used for number arrays (the model needs arrays)
from PIL import Image               # PIL (Pillow) opens and resizes images
import tensorflow as tf             # tensorflow has the TFLite interpreter to run .tflite models


# =============================================================
# STEP 1 — Build paths relative to THIS file's location
# =============================================================
# __file__ is a special variable Python sets automatically.
# It holds the full path of the script that is currently running.
# Path(__file__) turns that string into a Path object.
# .resolve() converts it to an absolute path (no dots or shortcuts).
# .parent gives us the folder the script lives in (the "app" folder).

SCRIPT_DIR = Path(__file__).resolve().parent          # .../smart-farm/app/
PROJECT_DIR = SCRIPT_DIR.parent                        # .../smart-farm/

# The model and labels are inside smart-farm/data/models/
MODEL_PATH = PROJECT_DIR / "data" / "models" / "disease_model.tflite"
LABELS_PATH = PROJECT_DIR / "data" / "models" / "labels.json"

# The size the model expects: 224 pixels wide, 224 pixels tall
IMAGE_SIZE = (224, 224)

# If the top prediction is below this number, we say "uncertain"
CONFIDENCE_THRESHOLD = 0.70


# =============================================================
# STEP 2 — Load the model and labels ONCE
# =============================================================
# We load them once at the top so we don't reload every time
# we call predict_disease(). This saves time.

def load_model(model_path):
    """Load the TFLite model from disk and prepare it to run."""

    # Check if the model file actually exists
    if not model_path.exists():
        # "raise" stops the program and shows an error message
        raise FileNotFoundError(
            f"Model file not found: {model_path}\n"
            f"Make sure disease_model.tflite is inside the data/models/ folder."
        )

    # Create an "interpreter" — this is the TFLite engine that runs the model
    interpreter = tf.lite.Interpreter(model_path=str(model_path))

    # allocate_tensors() reserves memory for the model's input and output
    interpreter.allocate_tensors()

    return interpreter


def load_labels(labels_path):
    """Load the list of class names from labels.json."""

    # Check if the labels file actually exists
    if not labels_path.exists():
        raise FileNotFoundError(
            f"Labels file not found: {labels_path}\n"
            f"Make sure labels.json is inside the data/models/ folder."
        )

    # Open the file in read mode ("r") and load the JSON content
    # "encoding='utf-8'" makes sure special characters are read correctly
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)       # json.load() turns the file into a Python list

    return labels                    # e.g. ["Tomato___Early_blight", "Corn___Rust", ...]


# Actually load them now (runs once when the script starts)
interpreter = load_model(MODEL_PATH)
labels = load_labels(LABELS_PATH)


# =============================================================
# STEP 3 — Helper: split a label like "Tomato___Early_blight"
# =============================================================
# Labels in the dataset use "___" (three underscores) to
# separate the crop name from the disease name, and "_" (one
# underscore) instead of a space.

def split_label(label):
    """
    Turn 'Tomato___Early_blight' into crop='Tomato' and
    disease='Early blight'.
    """

    # "___" separates crop from disease
    if "___" in label:
        # split("___", 1) splits at the FIRST "___" only
        # It returns a list of two pieces, which we unpack
        # into two variables: crop_part and disease_part
        crop_part, disease_part = label.split("___", 1)
    else:
        # Some labels might not have "___" (e.g. "Healthy")
        crop_part = "Unknown"
        disease_part = label

    # Replace remaining underscores with spaces for readability
    crop_name = crop_part.replace("_", " ").strip()
    disease_name = disease_part.replace("_", " ").strip()

    return crop_name, disease_name


# =============================================================
# STEP 4 — The main prediction function
# =============================================================

def predict_disease(image_path):
    """
    Open an image, run the disease model, and return the top 3
    predictions as a list of dictionaries.

    Each dictionary looks like:
        {"disease": "Early blight", "crop": "Tomato", "confidence": 0.92}

    If the top confidence is below 0.70, disease becomes "uncertain".
    """

    # --- 4a. Check if the image file exists ---
    image_path = Path(image_path)   # make sure it is a Path object
    if not image_path.exists():
        raise FileNotFoundError(
            f"Image file not found: {image_path}\n"
            f"Check the file path and try again."
        )

    # --- 4b. Open and prepare the image ---
    # Image.open() reads the image from disk
    img = Image.open(image_path)

    # .convert("RGB") makes sure the image has 3 colour channels
    # (some PNGs have 4 channels — RGBA — and the model needs 3)
    img = img.convert("RGB")

    # .resize() changes the image to 224×224 pixels
    img = img.resize(IMAGE_SIZE)

    # --- 4c. Turn the image into a numpy array ---
    # The model expects numbers, not a picture.
    # np.array() converts the image pixels into a grid of numbers.
    img_array = np.array(img, dtype=np.float32)
    # img_array shape is (224, 224, 3) — height, width, 3 colours

    # The model expects a "batch" — a list of images.
    # Even though we have one image, we wrap it in a batch of size 1.
    # np.expand_dims adds an extra dimension at position 0.
    # New shape: (1, 224, 224, 3)
    img_batch = np.expand_dims(img_array, axis=0)

    # NOTE: We do NOT divide by 255. The rescaling layer is
    # already inside the model, so we pass raw 0–255 values.

    # --- 4d. Run the model ---
    # Get the model's input and output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Feed our image batch into the model's input slot
    # input_details[0]["index"] is the slot number for the input
    interpreter.set_tensor(input_details[0]["index"], img_batch)

    # Tell the interpreter to run the model
    interpreter.invoke()

    # Read the output — a list of confidence scores, one per class
    # output_details[0]["index"] is the slot number for the output
    predictions = interpreter.get_tensor(output_details[0]["index"])
    # predictions shape: (1, 17) — 1 image, 17 classes

    # Grab the first (and only) row — now shape is (17,)
    scores = predictions[0]

    # --- 4e. Find the top 3 predictions ---
    # np.argsort() returns the indices that would sort the array
    # (smallest to largest). We reverse with [::-1] to get
    # largest first, then take the first 3.
    top_3_indices = np.argsort(scores)[::-1][:3]

    # Build a list of result dictionaries
    results = []
    for rank, idx in enumerate(top_3_indices):
        # idx is the position in the labels list
        raw_label = labels[idx]             # e.g. "Tomato___Early_blight"
        confidence = float(scores[idx])     # e.g. 0.92

        # Split into crop and disease
        crop_name, disease_name = split_label(raw_label)

        # If this is the TOP prediction and confidence is too low,
        # mark it as "uncertain"
        if rank == 0 and confidence < CONFIDENCE_THRESHOLD:
            disease_name = "uncertain"

        results.append({
            "disease": disease_name,
            "crop": crop_name,
            "confidence": round(confidence, 4)  # round to 4 decimal places
        })

    return results


# =============================================================
# STEP 5 — Run from the command line
# =============================================================
# "if __name__ == '__main__'" means: only run this part when
# you execute the script directly (not when another file
# imports it).

if __name__ == "__main__":

    # sys.argv is a list of words you typed in the terminal.
    # sys.argv[0] is the script name ("predict.py")
    # sys.argv[1] should be the path to the leaf image
    if len(sys.argv) < 2:
        print("Usage:  python app/predict.py  path/to/leaf.jpg")
        print("Example: python app/predict.py  data/test_images/tomato_leaf.jpg")
        sys.exit(1)     # exit with code 1 = something went wrong

    # The user typed the image path as the second word
    user_image_path = sys.argv[1]

    # Try to predict — if anything goes wrong, show a friendly message
    try:
        top_3 = predict_disease(user_image_path)

        # Print the results in a readable format
        print("\n===== DISEASE PREDICTION =====")
        for i, pred in enumerate(top_3, start=1):
            # i goes 1, 2, 3 (start=1 makes it start from 1)
            print(
                f"  #{i}  {pred['crop']} — {pred['disease']}"
                f"  (confidence: {pred['confidence']:.2%})"
            )
            # :.2% formats 0.92 as "92.00%"
        print("==============================\n")

    except FileNotFoundError as e:
        # "as e" saves the error message in a variable called e
        print(f"\n[ERROR] {e}")
        sys.exit(1)