# Deployment Guide

Installation, configuration, and deployment instructions for the ASAN Appeal AI system.

## Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8GB | 16GB |
| GPU | NVIDIA 4GB VRAM | RTX 4050 (6GB VRAM) |
| Storage | 10GB | 20GB |

**Note:** The system can run on CPU-only, but inference will be 5-10x slower.

### Software

| Software | Version |
|----------|---------|
| Python | 3.11+ |
| FFmpeg | 4.0+ |
| CUDA (optional) | 11.8+ |
| cuDNN (optional) | 8.6+ |

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/Wkrotik/Asan-Eleda.git
cd Asan-Eleda
```

### 2. Set Up Python Environment

Using pyenv (recommended):

```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

Create virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

Core dependencies:

```bash
pip install -r requirements.txt
```

ML dependencies (required for actual inference):

```bash
pip install -r requirements-ml.txt
```

### 4. Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

### 5. Pre-Download Models (Recommended)

Download model weights before first use:

```bash
python scripts/warmup_all.py
```

This downloads ~1.5GB of model files to `data/model-cache/`.

---

## Running the Server

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

**Note:** With GPU, use `--workers 1` to avoid GPU memory conflicts.

### Verify Installation

```bash
# Health check
curl http://localhost:8000/healthz

# Open demo UI
open http://localhost:8000/demo
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PIPELINE_CONFIG` | Pipeline config path | `config/pipeline.yaml` |
| `CATEGORIES_CONFIG` | Categories config path | `config/categories.yaml` |
| `MAX_CONCURRENT_INFERENCE` | Concurrent ML ops | `2` |
| `CUDA_VISIBLE_DEVICES` | GPU selection | `0` |

### Config Files

| File | Purpose |
|------|---------|
| `config/pipeline.yaml` | Engine selection, paths |
| `config/categories.yaml` | Category taxonomy |
| `config/priority_rules.yaml` | Priority rules |
| `config/thresholds.yaml` | Verification thresholds |

### GPU Configuration

Enable GPU for OCR (in `config/pipeline.yaml`):

```yaml
ocr:
  languages: [az, en]
  gpu: true  # Set to false for CPU-only
```

---

## Docker Deployment

This repository includes Dockerfiles for both CPU and GPU deployments.

### Quick Start

```bash
# CPU-only
docker build -t asan-appeal-ai:cpu -f Dockerfile.cpu .
docker run --rm -p 8000:8000 \
  -v "$PWD/data:/app/data" \
  asan-appeal-ai:cpu

# With GPU
docker build -t asan-appeal-ai:gpu -f Dockerfile.gpu .
docker run --rm --gpus all -p 8000:8000 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v "$PWD/data:/app/data" \
  asan-appeal-ai:gpu
```

### Docker Compose

```yaml
version: '3.8'
services:
  api:
    image: asan-appeal-ai:gpu
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Building Docker Images

```bash
# CPU image
docker build -t asan-appeal-ai:cpu -f Dockerfile.cpu .

# GPU image
docker build -t asan-appeal-ai:gpu -f Dockerfile.gpu .
```

---

## Production Checklist

### Before Deployment

- [ ] Run all tests: `pytest`
- [ ] Pre-download models: `python scripts/warmup_all.py`
- [ ] Configure storage paths in `config/pipeline.yaml`
- [ ] Set appropriate upload limits
- [ ] Configure cleanup schedule

### Security

- [ ] Run behind reverse proxy (nginx/traefik)
- [ ] Enable HTTPS
- [ ] Set firewall rules
- [ ] Configure log rotation

### Monitoring

- [ ] Set up health check monitoring (`/healthz`)
- [ ] Configure log aggregation
- [ ] Set up alerting for errors

---

## Storage Management

### Directory Structure

```
data/
├── uploads/          # Uploaded files (temporary)
├── artifacts/        # Processing artifacts
└── model-cache/      # Downloaded models (persistent)
```

### Cleanup

Set up automatic cleanup for uploaded files:

```bash
# Cron job: clean files older than 7 days
0 2 * * * /path/to/venv/bin/python /path/to/scripts/cleanup_storage.py --ttl-hours 168
```

Manual cleanup:

```bash
# Dry run first
python scripts/cleanup_storage.py --ttl-hours 168 --dry-run

# Execute
python scripts/cleanup_storage.py --ttl-hours 168
```

---

## Performance Tuning

### GPU Memory

If encountering OOM errors:

1. Reduce concurrent inference:
   ```bash
   MAX_CONCURRENT_INFERENCE=1 uvicorn app.main:app
   ```

2. Disable GPU for OCR:
   ```yaml
   # config/pipeline.yaml
   ocr:
     gpu: false
   ```

### CPU Performance

For CPU-only deployment:

1. Use more workers:
   ```bash
   uvicorn app.main:app --workers 4
   ```

2. Increase concurrent inference:
   ```bash
   MAX_CONCURRENT_INFERENCE=4 uvicorn app.main:app
   ```

### Video Processing

Reduce video processing time:

```yaml
# config/pipeline.yaml
media:
  max_video_frames: 4    # Fewer frames
  video_fps: 0.25        # Less frequent sampling
```

---

## Troubleshooting

### Common Issues

**Models not loading:**
```bash
# Re-download models
rm -rf data/model-cache
python scripts/warmup_all.py
```

**CUDA out of memory:**
```bash
# Reduce concurrency
MAX_CONCURRENT_INFERENCE=1 uvicorn app.main:app
```

**FFmpeg not found:**
```bash
# Verify installation
ffmpeg -version

# Check PATH
which ffmpeg
```

**Slow inference:**
- Verify GPU is being used: check logs for "Using CUDA"
- Reduce video frame count
- Pre-download models

### Logs

Enable debug logging:

```bash
LOG_LEVEL=DEBUG uvicorn app.main:app
```

Check logs for:
- Model loading times
- Inference durations
- Memory usage warnings

---

## Offline Installation

For air-gapped environments:

### 1. On Internet-Connected Machine

```bash
# Download Python packages
pip download -r requirements.txt -r requirements-ml.txt -d ./packages

# Download models
python scripts/warmup_all.py
tar -czf models.tar.gz data/model-cache
```

### 2. Transfer Files

Copy to air-gapped machine:
- Repository code
- `packages/` directory
- `models.tar.gz`

### 3. Install on Air-Gapped Machine

```bash
# Install packages
pip install --no-index --find-links=./packages -r requirements.txt -r requirements-ml.txt

# Extract models
tar -xzf models.tar.gz
```

---

## Support

For issues or questions:
- Check logs for error details
- Run tests to verify installation: `pytest`
- Check hardware requirements are met
