"""
SmartPark - simulated Car Park "Camera" API (takephoto)

This service simulates the car park operator's cameras. It exposes
GET /api/takephoto which returns a randomly selected image from the
provided dataset, base64-encoded, to simulate a camera snapshot.

It is intentionally a SMALL, separate service (not part of the main
FastAPI platform). The main platform calls it over HTTP to "pull" an
image for each car park when a user asks for parking availability.

Run locally (from the takephoto-api project root):
    pip install -r requirements.txt
    python app/main.py
    # then: http://127.0.0.1:8000/api/takephoto?carpark_id=CBD_001

Dependencies: fastapi, uvicorn
"""

import base64
import logging
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVICE_NAME = "takephoto-api"

# Project root = the parent of this "app" package directory. Resolving against
# the file location (not the current working directory) means the images folder
# is found no matter where you launch the process from — locally or in a
# container.
BASE_DIR = Path(__file__).resolve().parent.parent

# Folder holding the dataset images. Override via env var, default to the
# "images" folder at the project root.
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", BASE_DIR / "images"))

# Image extensions the camera sim understands.
ALLOWED_EXTS = {".jpg", ".jpeg", ".png"}

# Port to listen on. Cloud Run injects $PORT; default 8000 for local use.
PORT = int(os.getenv("PORT", "8000"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Structured-ish logging that captures timestamp, severity, and service name,
# matching the assignment's logging requirement.
def _make_logger() -> logging.Logger:
    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


log = _make_logger()


# ---------------------------------------------------------------------------
# Load the dataset image list once at startup (single source inside this sim)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    image_files: list[Path] = []
    if IMAGES_DIR.is_dir():
        image_files = [
            p
            for p in IMAGES_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in ALLOWED_EXTS
        ]
    else:
        log.warning(
            "Image directory not found: %s. "
            "/api/takephoto will return an error until it exists.",
            IMAGES_DIR,
        )

    # Stash the list on the app so endpoints can read it.
    app.state.image_files = image_files
    log.info("Loaded %s image file(s) from %s", len(image_files), IMAGES_DIR)

    yield


app = FastAPI(title=SERVICE_NAME, version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    """Simple health/landing endpoint."""
    return {"service": SERVICE_NAME, "status": "ok"}


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe."""
    return {"status": "ok"}


@app.get("/api/takephoto")
def takephoto(
    carpark_id: str = Query(default="unknown", description="ID of the car park"),
):
    """
    Simulate a camera snapshot for a car park.

    Returns a randomly selected dataset image, base64-encoded, in JSON.
    The image content itself does not matter for this application; the
    platform only needs a real image to feed into the YOLO model.
    """
    image_files: list[Path] = app.state.image_files

    if not image_files:
        log.error("No images available; cannot take a photo (carpark=%s)", carpark_id)
        return JSONResponse(
            status_code=503,
            content={
                "carpark_id": carpark_id,
                "status": "error",
                "msg": "No images available in dataset.",
            },
        )

    try:
        # Randomly pick an image and base64-encode it.
        chosen = random.choice(image_files)
        raw = chosen.read_bytes()
        encoded = base64.b64encode(raw).decode("utf-8")

        log.info("takephoto ok | carpark=%s | image=%s", carpark_id, chosen.name)
        return {
            "carpark_id": carpark_id,
            "status": "success",
            "msg": "success",
            "image_name": chosen.name,
            "image_base64": encoded,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("takephoto failed | carpark=%s | error=%s", carpark_id, exc)
        return JSONResponse(
            status_code=500,
            content={
                "carpark_id": carpark_id,
                "status": "error",
                "msg": f"Failed to read image: {exc}",
            },
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    log.info("Starting %s on 0.0.0.0:%s", SERVICE_NAME, PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
