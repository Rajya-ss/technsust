# =============================================================
# server.py - FastAPI web server for the offline smart-farm assistant
# =============================================================
# Run with:  python app/server.py
# Then open: http://127.0.0.1:8000
# =============================================================

import sys
import uuid
import threading
import traceback
from datetime import datetime
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# --------------------- Paths ---------------------
APP_DIR = Path(__file__).resolve().parent          # .../smart-farm/app/
PROJECT_ROOT = APP_DIR.parent                      # .../smart-farm/
sys.path.insert(0, str(APP_DIR))                   # so we can import our own files

MODELS_DIR = PROJECT_ROOT / "data" / "models"
TEMP_DIR = PROJECT_ROOT / "temp_uploads"
INDEX_PATH = PROJECT_ROOT / "web" / "index.html"

# --------------------- Our own code ---------------------
from predict import predict_disease
from sensors import get_reading, get_scenario_reading
from irrigation import irrigation_advice
from advisor import get_advice, MODEL_NAME

# --------------------- Settings ---------------------
ALLOWED_CROPS = {"tomato", "potato", "corn"}
ALLOWED_LANGUAGES = {"English", "Hindi"}
ALLOWED_SCENARIOS = {"random", "dry_hot", "normal", "rainy"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_BYTES = 10 * 1024 * 1024    # 10 MB

app = FastAPI()

# The TFLite model keeps internal state while it runs. If two requests used
# it at the same moment, the answers could get mixed up. This lock makes
# the requests take turns.
model_lock = threading.Lock()


def error_response(message, status_code=400):
    """Return an error in the shape the web page expects: {"error": "..."}"""
    return JSONResponse(status_code=status_code, content={"error": message})


def normalise_crop(name):
    """'Corn (maize)' -> 'corn', 'Tomato' -> 'tomato'"""
    lower = name.lower().strip()
    if "corn" in lower or "maize" in lower:
        return "corn"
    return lower


# =============================================================
# GET /  - the web page
# =============================================================
@app.get("/")
def home():
    if not INDEX_PATH.is_file():
        return error_response("web/index.html was not found.", 404)
    return FileResponse(str(INDEX_PATH))


# =============================================================
# GET /health  - are all the parts in place?
# =============================================================
@app.get("/health")
def health():
    files = {
        "model": (MODELS_DIR / "disease_model.tflite").is_file(),
        "labels": (MODELS_DIR / "labels.json").is_file(),
        "glossary_hi": (PROJECT_ROOT / "data" / "glossary_hi.json").is_file(),
        "crop_rules": (PROJECT_ROOT / "data" / "crop_rules.json").is_file(),
    }

    try:
        reply = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_ok = reply.status_code == 200
        model_ok = MODEL_NAME in reply.text
    except Exception:
        ollama_ok = False
        model_ok = False

    return {
        "files": files,
        "ollama_running": ollama_ok,
        "ollama_has_model": model_ok,
        "model_name": MODEL_NAME,
    }


# =============================================================
# POST /analyze  - the main job
# =============================================================
# This is a normal "def" (not "async def") on purpose: FastAPI runs it in
# its own thread, so the slow model and Ollama calls do not freeze the server.
@app.post("/analyze")
def analyze(
    photo: UploadFile = File(...),
    language: str = Form("English"),
    crop: str = Form(...),
    scenario: str = Form("random"),
):
    # ---------- 1. Check the simple fields ----------
    crop = crop.lower().strip()
    if crop not in ALLOWED_CROPS:
        return error_response("Crop must be tomato, potato or corn.")
    if language not in ALLOWED_LANGUAGES:
        return error_response("Language must be English or Hindi.")
    if scenario not in ALLOWED_SCENARIOS:
        return error_response("Scenario must be random, dry_hot, normal or rainy.")

    # ---------- 2. Check the photo ----------
    suffix = Path(photo.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return error_response("The photo must be a jpg, jpeg or png file.")

    content = photo.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        return error_response("The photo is too large. The limit is 10 MB.")
    if len(content) == 0:
        return error_response("The photo file is empty.")

    # ---------- 3. Save it to a temporary file ----------
    TEMP_DIR.mkdir(exist_ok=True)
    temp_file = TEMP_DIR / f"upload_{uuid.uuid4().hex}{suffix}"

    try:
        with open(temp_file, "wb") as f:
            f.write(content)

        # ---------- 4. Run the whole chain, one request at a time ----------
        with model_lock:
            # a) Disease classifier (top 3)
            top3 = predict_disease(str(temp_file))

            # b) Crop check: the FARMER states the crop
            model_crop = normalise_crop(top3[0]["crop"])
            crop_mismatch = (model_crop != crop)

            if crop_mismatch:
                # The photo may show another crop, so we do not trust the disease
                disease_result = {"disease": "uncertain", "crop": crop, "confidence": 0.0}
            else:
                disease_result = {
                    "disease": top3[0]["disease"],
                    "crop": crop,
                    "confidence": top3[0]["confidence"],   # for developers only
                }

            # c) Sensor reading (simulated)
            if scenario == "random":
                reading = get_reading(crop)
            else:
                reading = get_scenario_reading(crop, scenario)

            # d) Irrigation decision
            irrigation = irrigation_advice(crop, reading)

            # e) Advice from the local LLM (or the fallback text)
            advice = get_advice(disease_result, irrigation, reading, language=language)

        # ---------- 5. Answer ----------
        print(f"[{datetime.now().strftime('%H:%M:%S')}] /analyze "
              f"crop={crop} language={language} scenario={scenario} "
              f"mismatch={crop_mismatch}")

        return {
            "crop": crop,
            "language": language,
            "top3": top3,
            "disease_result": disease_result,
            "crop_mismatch": crop_mismatch,
            "reading": reading,
            "irrigation": irrigation,
            "advice": advice,
        }

    except Exception:
        traceback.print_exc()    # full details go to the terminal
        return error_response(
            "Something went wrong while analysing the photo. Please try again.", 500
        )

    finally:
        # Always delete the temporary photo
        try:
            if temp_file.is_file():
                temp_file.unlink()
        except Exception:
            pass


# =============================================================
# Start the server
# =============================================================
if __name__ == "__main__":
    print("Starting the server at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)