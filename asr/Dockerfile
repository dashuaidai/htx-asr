# Task 2e — containerised ASR API (service name: asr-api)
#
# Build (from the asr/ directory):
#   docker build -t asr-api .
# Run:
#   docker run -p 8001:8001 asr-api
#
# The wav2vec2-large-960h weights are downloaded at *build* time and baked
# into the image, so the container starts without needing internet access.

FROM python:3.11-slim

# ffmpeg is required by librosa/audioread to decode mp3 files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first (much smaller than the default CUDA build), then the rest.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model into the image's Hugging Face cache.
RUN python - <<'PY'
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-large-960h")
Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-large-960h")
print("model cached in image")
PY

COPY asr_api.py .

EXPOSE 8001
CMD ["uvicorn", "asr_api:app", "--host", "0.0.0.0", "--port", "8001"]
