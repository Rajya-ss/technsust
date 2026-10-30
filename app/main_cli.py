# =============================================================
# main_cli.py — Command line interface for the whole assistant
# =============================================================
# This script ties together all the pieces you have built:
#   • predict_disease   (model inference)
#   • get_reading       (simulated sensor data)
#   • irrigation_advice (simple rule‑based irrigation decision)
#   • get_advice        (LLM‑based farm advice)
#
# How to run:
#   python app/main_cli.py path/to/leaf.jpg [English|Hindi] [tomato|potato|corn]
#
# The last two arguments are optional:
#   – language defaults to English
#   – crop is optional; if you give it the script will use it for
#     everything.  If the supplied crop differs from what the model
#     thinks the leaf belongs to, the disease result is changed to
#     “uncertain” and you will see a short note.
# =============================================================

# --------------------------- Imports ---------------------------
import sys                     # to modify the import path and exit gracefully
import argparse                # parses command‑line arguments
from pathlib import Path       # works with file paths on any OS

# -------------------------------------------------------------
# Add the *app* folder to sys.path so we can import sibling modules.
# This mirrors what we did in the other scripts.
# -------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent         # .../smart-farm/app/
PROJECT_DIR  = SCRIPT_DIR.parent                       # .../smart-farm/
sys.path.insert(0, str(SCRIPT_DIR))

# Now import the functions we need.
from predict    import predict_disease
from sensors    import get_reading
from irrigation import irrigation_advice
from advisor    import get_advice


# =============================================================
# Helper – normalise a crop name
# -------------------------------------------------------------
#   * lower‑case everything
#   * turn any form of “Corn (maize)” into plain “corn”
# =============================================================
def normalise_crop_name(name: str) -> str:
    """Return a clean, lower‑cased crop name."""
    lower = name.lower().strip()
    if "corn" in lower or "maize" in lower:
        return "corn"
    return lower   # e.g. "tomato", "potato"


# =============================================================
# Main entry point
# =============================================================
def main() -> None:
    # ----------------------- Argument parsing -----------------------
    parser = argparse.ArgumentParser(
        description="Run the offline smart‑farm assistant on a leaf photo."
    )
    parser.add_argument(
        "photo_path",
        help="Path to the leaf photograph (jpg / jpeg / png)."
    )
    parser.add_argument(
        "language",
        nargs="?",
        default="English",
        choices=["English", "Hindi"],
        help="Output language (default: English)."
    )
    parser.add_argument(
        "crop",
        nargs="?",
        choices=["tomato", "potato", "corn"],
        help="Optional: the crop the farmer is growing."
    )

    args = parser.parse_args()

    # ----------------------- Verify the image file -----------------------
    photo = Path(args.photo_path)
    if not photo.exists():
        print(f"[ERROR] Image file not found: {photo}")
        sys.exit(1)

    # ----------------------- 1️⃣ Run the disease classifier -----------------------
    try:
        top3 = predict_disease(str(photo))          # returns a list of 3 dicts
    except Exception as e:                          # any error from the model
        print(f"[ERROR] Failed to run predict_disease: {e}")
        sys.exit(1)

    # Show the full top‑3 list for the user (required by the spec)
    print("\n" + "=" * 60)
    print("DISEASE RESULT (top 3 predictions)")
    print("=" * 60)
    for i, pred in enumerate(top3, start=1):
        print(
            f"  #{i}: Crop = {pred['crop']}, Disease = {pred['disease']}, "
            f"Confidence = {pred['confidence']:.0%}"
        )
    print("-" * 60)

    # The best prediction is the first element
    top_pred = top3[0]
    pred_crop_raw = top_pred["crop"]                 # e.g. "Tomato" or "Corn (maize)"
    pred_crop = normalise_crop_name(pred_crop_raw)   # -> "tomato", "corn", etc.
    pred_disease   = top_pred["disease"]
    pred_confidence = top_pred["confidence"]

    # ----------------------- 2️⃣ Resolve the final crop -----------------------
    # If the farmer supplied a crop we honour it; otherwise we use the model's guess.
    if args.crop:
        farmer_crop = args.crop.lower()
        print(f"Farmer supplied crop: {farmer_crop}")

        # If the supplied crop differs from the model's prediction we
        # mark the disease as uncertain and inform the user.
        if farmer_crop != pred_crop:
            print(
                "[NOTE] The leaf photo looks like it belongs to a different crop "
                f"(model guessed “{pred_crop_raw}”)."
            )
            disease_result = {
                "disease": "uncertain",
                "crop": farmer_crop,
                "confidence": pred_confidence   # keep the original confidence value
            }
        else:
            # crops match – use the model's disease prediction
            disease_result = {
                "disease": pred_disease,
                "crop": farmer_crop,
                "confidence": pred_confidence
            }
        final_crop = farmer_crop
    else:
        # No crop supplied – just use what the model predicted
        disease_result = {
            "disease": pred_disease,
            "crop": pred_crop,
            "confidence": pred_confidence
        }
        final_crop = pred_crop

    # ----------------------- 3️⃣ Simulated sensor reading -----------------------
    try:
        reading = get_reading(final_crop)   # returns a dict with sensor values
    except Exception as e:
        print(f"[ERROR] Failed to get simulated sensor reading: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SENSOR READING")
    print("=" * 60)
    for key, value in reading.items():
        print(f"  {key:<20}: {value}")
    print("-" * 60)

    # ----------------------- 4️⃣ Irrigation decision -----------------------
    try:
        irrigation = irrigation_advice(final_crop, reading)   # dict with action + reason
    except Exception as e:
        print(f"[ERROR] Irrigation decision failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("IRRIGATION DECISION")
    print("=" * 60)
    print(f"  Action : {irrigation['action']}")
    print(f"  Reason : {irrigation['reason']}")
    print("-" * 60)

    # ----------------------- 5️⃣ Get final LLM advice -----------------------
    try:
        final_advice = get_advice(
            disease_result,
            irrigation,
            reading,
            language=args.language
        )
    except Exception as e:
        print(f"[ERROR] get_advice raised an exception: {e}")
        sys.exit(1)

    # ----------------------- 6️⃣ Print the final advice -----------------------
    print("\n" + "=" * 60)
    print("FINAL ADVICE")
    print("=" * 60)
    print(final_advice)
    print("=" * 60 + "\n")


# -------------------------------------------------------------
# Run the script when executed directly
# -------------------------------------------------------------
if __name__ == "__main__":
    main()