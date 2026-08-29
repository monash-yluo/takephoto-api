# SmartPark - takephoto camera-sim API
# ---------------------------------------------------------------------------
# Lightweight Python image for the simulated car park camera service.
# Only needs fastapi + uvicorn (no ML libraries here).
# ---------------------------------------------------------------------------
FROM python:3.10-slim

# Working directory inside the container
WORKDIR /app

# 1) Install dependencies first (this layer is cached, so code changes don't
#    re-install packages every build).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copy the application code
COPY app ./app

# 3) Copy the dataset images (needed by /api/takephoto).
#    NOTE: images/ is gitignored, so this COPY requires images/ to exist in
#    the build context (i.e. present locally when you run docker build).
COPY images ./images

# Port the app listens on. Cloud Run injects $PORT at runtime and overrides this.
ENV PORT=8000
EXPOSE 8000

# The app reads $PORT from the environment (see app/main.py), so this also
# satisfies Cloud Run's "listen on $PORT" requirement.
CMD ["python", "app/main.py"]
