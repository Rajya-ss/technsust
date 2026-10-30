# =============================================================
# test_api.py - send one photo to the running server
# =============================================================
# Usage:
#   python app/test_api.py <photo> <English|Hindi> <crop> [scenario]
# Example:
#   python app/test_api.py test_photos/tomato_early_blight_1.jpg English tomato
# =============================================================

import sys
import json
from pathlib import Path

import requests

URL = "http://127.0.0.1:8000/analyze"

if len(sys.argv) < 4:
    print("Usage: python app/test_api.py <photo> <English|Hindi> <crop> [scenario]")
    sys.exit(1)

photo_path = Path(sys.argv[1])
language = sys.argv[2]
crop = sys.argv[3]
scenario = sys.argv[4] if len(sys.argv) > 4 else "random"

if not photo_path.exists():
    print(f"Photo not found: {photo_path}")
    sys.exit(1)

try:
    with open(photo_path, "rb") as f:
        reply = requests.post(
            URL,
            files={"photo": (photo_path.name, f)},
            data={"language": language, "crop": crop, "scenario": scenario},
            timeout=300,     # the first request can be slow
        )
except requests.exceptions.ConnectionError:
    print("Could not reach the server. Is 'python app/server.py' running?")
    sys.exit(1)

print("Status:", reply.status_code)
print(json.dumps(reply.json(), indent=2, ensure_ascii=False))