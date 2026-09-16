# SmartPark takephoto API

This service simulates a car park camera for SmartPark. It randomly selects an image from the `images/` dataset, encodes the image as Base64, and returns it through an HTTP API for the main platform and its YOLO pipeline.

It is a small, independent FastAPI service. It does not perform object detection or parking-space calculations.

## Features

- `GET /`: basic service status
- `GET /healthz`: Cloud Run health check endpoint
- `GET /api/takephoto`: returns a randomly selected simulated camera image
- Supports `.jpg`, `.jpeg`, and `.png` images
- Scans the image directory once at startup and keeps the available file list in memory
- Uses the `PORT` environment variable required by Cloud Run
- Writes structured-style logs to standard output for Cloud Logging

## Project structure

```text
.
├── app/
│   ├── __init__.py
│   └── main.py
├── images/                  # Camera image dataset
├── .dockerignore
├── .gcloudignore
├── Dockerfile
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10 or later
- Docker, when running or deploying the container locally
- Google Cloud CLI (`gcloud`), when deploying to Cloud Run

## Run locally

Run the following commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app/main.py
```

The service runs at `http://127.0.0.1:8000` by default.

If PowerShell does not allow virtual environment activation, use the virtual environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app\main.py
```

## API usage

### Service status

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

Expected health check response:

```json
{"status":"ok"}
```

The root endpoint also returns the service name:

```json
{"service":"takephoto-api","status":"ok"}
```

### Take a simulated photo

```powershell
$response = Invoke-RestMethod "http://127.0.0.1:8000/api/takephoto?carpark_id=CBD_001"
$response
```

Example success response:

```json
{
  "carpark_id": "CBD_001",
  "status": "success",
  "msg": "success",
  "image_name": "img042.jpg",
  "image_base64": "/9j/4AAQSkZJRgABAQ..."
}
```

`image_base64` contains the complete image encoded as a Base64 string. The caller can decode it and use the image extension to determine the MIME type.

`carpark_id` is echoed in the response and logs. It currently does not affect image selection. If omitted, it defaults to `unknown`.

### HTTP status codes

| Status code | Meaning |
| --- | --- |
| `200` | A random image was returned successfully |
| `503` | The image directory is missing or contains no supported images |
| `500` | An error occurred while reading the selected image |

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8000` | HTTP listening port; Cloud Run injects this value automatically |
| `IMAGES_DIR` | `images/` in the project root | Image dataset directory; can be changed to another path inside the container |

Example:

```powershell
$env:PORT = "8080"
$env:IMAGES_DIR = "C:\data\smartpark-images"
python app\main.py
```

The image list is loaded only at startup. Restart the service after adding, removing, or replacing images.

## Run with Docker

Build the image:

```powershell
docker build -t takephoto-api .
```

Run the container:

```powershell
docker run --rm -p 8000:8000 takephoto-api
```

Test the container:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/healthz"
Invoke-RestMethod "http://127.0.0.1:8000/api/takephoto?carpark_id=CBD_001"
```

The `Dockerfile` copies `images/` into the container. Make sure the directory and its image files exist in the Docker build context before building.

## Deploy to Google Cloud Run

### Configure Google Cloud

Log in and select the target project:

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Enable the required APIs:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

### Deploy from source

Run this command from the project root:

```powershell
gcloud run deploy takephoto-api `
  --source . `
  --region YOUR_REGION `
  --platform managed
```

Choose whether unauthenticated access should be allowed when prompted. If the main platform must call this service through a public URL, use:

```powershell
gcloud run deploy takephoto-api `
  --source . `
  --region YOUR_REGION `
  --platform managed `
  --allow-unauthenticated
```

After deployment, Cloud Run prints the service URL. Test it with:

```powershell
Invoke-RestMethod "https://YOUR_CLOUD_RUN_URL/healthz"
Invoke-RestMethod "https://YOUR_CLOUD_RUN_URL/api/takephoto?carpark_id=CBD_001"
```

Cloud Run injects `PORT` automatically. The application listens on `0.0.0.0:$PORT`, so no manual port configuration is required.

### Important: the image dataset must be present

This service depends on the images in the local `images/` directory. Although `.gitignore` excludes this directory, `.gcloudignore` deliberately does not exclude it. Therefore, when using `gcloud run deploy --source .`, the images are included in the Cloud Build context and copied into the Docker image.

You can verify the number of images before deployment:

```powershell
(Get-ChildItem .\images -File).Count
```

If the build context contains no images, the service may still start successfully, but `/api/takephoto` returns `503`:

```json
{
  "status": "error",
  "msg": "No images available in dataset."
}
```

The current dataset contains approximately 1,010 images and is about 300 MB. This increases the source upload, build time, and container image size.

### Why the images are stored in the container image

Including the images in the container image is intentional for this simulated camera service:

1. This is a simulation, not a production camera storage architecture. Keeping the fixed dataset with the service makes the deployment self-contained and predictable.
2. Storing the images in a Cloud Storage bucket would take substantial space for this dataset and add unnecessary storage and retrieval overhead for a test-only service.
3. During testing, reading images from a bucket would introduce additional network latency. That latency would affect Smart API test results and make it harder to measure the API behavior itself.

For these reasons, the service reads local files from the container filesystem. A production implementation with a large or frequently changing image dataset could use Cloud Storage or another external object store instead.

## View logs

```powershell
gcloud run services logs read takephoto-api `
  --region YOUR_REGION `
  --limit 50
```

Application logs include the service name, log level, car park ID, and selected image filename. Example:

```text
INFO | takephoto-api | takephoto ok | carpark=CBD_001 | image=img042.jpg
```

## Troubleshooting

### `/api/takephoto` returns `503`

Check that `images/` exists and contains `.jpg`, `.jpeg`, or `.png` files. The directory is scanned only at startup, so restart the service or redeploy Cloud Run after adding the files.

### Cloud Run startup or health check failure

Make sure the container listens on `0.0.0.0:$PORT`. This project reads the Cloud Run `PORT` value in `app/main.py`; do not change the listening address to `127.0.0.1`.

### The service works locally but Cloud Run has no images

Check that deployment was run from the project root and that `images/` exists in the build context. Git tracking and Docker/Cloud Build file availability are separate concerns.

## Development checks

Check Python syntax:

```powershell
python -m py_compile app\main.py
```

FastAPI also exposes interactive API documentation after startup:

- Swagger UI: `/docs`
- ReDoc: `/redoc`

For example: `http://127.0.0.1:8000/docs`
