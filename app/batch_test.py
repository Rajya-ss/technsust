# =============================================================
# batch_test.py — Test the disease model on a folder of photos
# =============================================================
# This script loops over every image in the test_photos/ folder,
# predicts the disease using predict_disease(), compares the
# prediction with the true label taken from the file name, and
# saves the results to a CSV file.
# =============================================================

# --- Imports ---
import sys                          # sys.path lets us tell Python where to find our code
import csv                          # csv lets us write .csv files (spreadsheet format)
from pathlib import Path            # Path builds file paths that work on any OS


# =============================================================
# STEP 1 — Set up paths and import predict_disease
# =============================================================

# Find the folder this script lives in (smart-farm/app/)
SCRIPT_DIR = Path(__file__).resolve().parent        # .../smart-farm/app/
PROJECT_DIR = SCRIPT_DIR.parent                      # .../smart-farm/

# The folder with test photos
TEST_PHOTOS_DIR = PROJECT_DIR / "test_photos"

# The CSV file where we will save results
RESULTS_CSV = PROJECT_DIR / "test_results.csv"

# We need to import predict_disease from predict.py, which is
# in the SAME folder (smart-farm/app/).  Sometimes Python can't
# find files in the same folder if you run the script from a
# different directory.  Adding the app folder to sys.path fixes
# this.  sys.path is the list of folders Python searches when
# you write "import".
sys.path.insert(0, str(SCRIPT_DIR))

# Now Python can find predict.py and import from it.
# This also loads the model and labels ONCE (because predict.py
# loads them at the top level when it is first imported).
from predict import predict_disease


# =============================================================
# STEP 2 — Parse the true label from a file name
# =============================================================
# File names follow this pattern:
#     crop_disease_word1_word2_number.jpg
# Example:
#     tomato_early_blight_1.jpg
#         crop    = Tomato
#         disease = Early blight
#         1       = just a serial number, we ignore it
#
# Rule: the FIRST word is the crop, the LAST word is a number,
#       and everything in between is the disease name.

def parse_filename(filename):
    """
    Take a filename like 'tomato_early_blight_1.jpg' and return
    the crop name and disease name as clean strings.

    Returns: (crop, disease)
        crop    = "Tomato"
        disease = "Early blight"
    """

    # Remove the extension (.jpg, .png, etc.)
    # Path(filename).stem gives the name without the extension
    # Example: "tomato_early_blight_1.jpg" → "tomato_early_blight_1"
    name_without_ext = Path(filename).stem

    # Split by underscore into a list of words
    # Example: ["tomato", "early", "blight", "1"]
    parts = name_without_ext.split("_")

    # The first word is the crop
    crop = parts[0]

    # The last word is usually a number (like 1, 2, 3).
    # We check if the last part is a digit and remove it.
    # .isdigit() returns True if every character is 0–9.
    if parts[-1].isdigit():
        # Everything between the first word and the last number
        # is the disease name
        disease_parts = parts[1:-1]     # slice: from index 1 up to (but NOT including) the last
    else:
        # No number at the end — everything after the crop is the disease
        disease_parts = parts[1:]

    # Join the disease words with spaces
    # Example: ["early", "blight"] → "early blight"
    disease = " ".join(disease_parts)

    # If there are no disease parts (e.g. file is just "tomato_1.jpg"),
    # set disease to "unknown"
    if disease == "":
        disease = "unknown"

    # .title() capitalises the first letter of each word
    # "tomato" → "Tomato", "early blight" → "Early Blight"
    crop = crop.title()
    disease = disease.title()

    return crop, disease


# =============================================================
# STEP 3 — Collect all image files from test_photos/
# =============================================================

def get_test_images(folder):
    """
    Return a sorted list of image file paths from the given folder.
    Only includes .jpg, .jpeg, and .png files.
    """

    # Check if the folder exists
    if not folder.exists():
        print(f"[ERROR] Test photos folder not found: {folder}")
        print("Create the folder and put your test images inside it.")
        sys.exit(1)

    # Allowed file extensions (we store them in a set for fast lookup)
    allowed = {".jpg", ".jpeg", ".png"}

    # folder.iterdir() gives us every file and folder inside test_photos/
    # We keep only files whose extension (lowered) is in our allowed set.
    # .suffix gives the extension like ".jpg"
    # .lower() makes it case-insensitive (".JPG" also works)
    images = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in allowed
    ]

    # Sort alphabetically so the output order is consistent
    images.sort()

    # If the folder is empty or has no images, warn the user
    if len(images) == 0:
        print(f"[ERROR] No .jpg, .jpeg, or .png files found in: {folder}")
        sys.exit(1)

    return images


# =============================================================
# STEP 4 — Run predictions and build the results table
# =============================================================

def run_batch_test():
    """
    Loop over all test images, predict each one, compare with
    the true label, print a table, and save to CSV.
    """

    # Get the list of image paths
    images = get_test_images(TEST_PHOTOS_DIR)
    print(f"\nFound {len(images)} test image(s) in: {TEST_PHOTOS_DIR}\n")

    # We will store each row of results in this list
    results = []

    # Counters for correct and total predictions
    correct_count = 0
    total_count = 0

    # --- Loop over every image ---
    for image_path in images:

        # Get the file name (just the name, not the full path)
        filename = image_path.name      # e.g. "tomato_early_blight_1.jpg"

        # Parse the true crop and disease from the file name
        true_crop, true_disease = parse_filename(filename)
        true_label = f"{true_crop} - {true_disease}"

        # Run the model — predict_disease returns a list of 3 dicts
        # We only care about the TOP prediction (index 0)
        try:
            top_3 = predict_disease(str(image_path))
            top = top_3[0]              # the best prediction

            pred_label = f"{top['crop'].replace(' (maize)', '')} - {top['disease']}"
            confidence = top["confidence"]

        except Exception as e:
            # If something goes wrong with one image, don't crash
            # the whole batch — just mark it as an error
            pred_label = "ERROR"
            confidence = 0.0
            print(f"  [WARNING] Could not process {filename}: {e}")

        # Compare true vs predicted (case-insensitive)
        # .lower() converts to lowercase so "Early Blight" matches "early blight"
        is_correct = true_label.lower() == pred_label.lower()

        # If correct, increase the counter
        if is_correct:
            correct_count += 1
        total_count += 1

        # Store the row — we use a dictionary for clarity
        results.append({
            "filename": filename,
            "true_label": true_label,
            "predicted_label": pred_label,
            "confidence": confidence,
            "result": "CORRECT" if is_correct else "WRONG"
        })

    # ==========================================================
    # STEP 4b — Print the results as a table
    # ==========================================================

    # Column widths (adjust if your filenames are very long)
    # ":<30" means left-align and pad to 30 characters wide
    header = (
        f"{'File':<35} "
        f"{'True Label':<30} "
        f"{'Predicted Label':<30} "
        f"{'Conf':>7}  "
        f"{'Result':<7}"
    )

    # Print a line of dashes the same width as the header
    separator = "-" * len(header)

    print(separator)
    print(header)
    print(separator)

    for row in results:
        # Format confidence as a percentage string
        conf_str = f"{row['confidence']:.2%}"   # 0.92 → "92.00%"

        print(
            f"{row['filename']:<35} "
            f"{row['true_label']:<30} "
            f"{row['predicted_label']:<30} "
            f"{conf_str:>7}  "
            f"{row['result']:<7}"
        )

    print(separator)

    # Print the summary line
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
    print(f"\nResult: {correct_count} correct out of {total_count}  "
          f"(accuracy: {accuracy:.1f}%)\n")

    # ==========================================================
    # STEP 5 — Save the table to a CSV file
    # ==========================================================
    # CSV = Comma-Separated Values.  It is a simple text file
    # that Excel and Google Sheets can open.

    # The column headers for the CSV
    csv_columns = ["filename", "true_label", "predicted_label",
                   "confidence", "result"]

    # Open the file for writing ("w").
    # newline="" prevents csv from adding extra blank lines on Windows.
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:

        # csv.DictWriter writes dictionaries as CSV rows
        writer = csv.DictWriter(f, fieldnames=csv_columns)

        # Write the header row (column names)
        writer.writeheader()

        # Write every result row
        for row in results:
            writer.writerow(row)

    print(f"Results saved to: {RESULTS_CSV}")


# =============================================================
# STEP 6 — Run when executed from the terminal
# =============================================================

if __name__ == "__main__":
    run_batch_test()