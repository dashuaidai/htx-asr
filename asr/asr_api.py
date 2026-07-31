"""
Task 2b/2c — ASR inference microservice.

A FastAPI application exposing:
  * GET  /ping -> "pong"           (health check, Task 2b)
  * POST /asr  -> transcription    (hosted inference API, Task 2c)

Model: facebook/wav2vec2-large-960h (pretrained + fine-tuned on LibriSpeech,
16 kHz speech). All incoming audio is therefore resampled to 16 kHz mono
before inference, as required by the model card.

Assumptions (documented per test instructions):
  * The uploaded file is an audio file readable by librosa/ffmpeg (the test
    data is mp3, but any common format works).
  * "duration" is the audio length in seconds, returned as a *string*
    (matching the sample response in the assignment, e.g. "20.7").
  * Task 2e states "Once the file is successfully processed, your code
    should delete the file" — interpreted as: the temporary copy of the
    uploaded audio saved by the service is deleted after it has been
    successfully transcribed (and also on failure, so no files accumulate
    inside the container).

Run locally:
    uvicorn asr_api:app --host 0.0.0.0 --port 8001
"""

import logging
import os
import tempfile

import librosa
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("asr_api")

MODEL_NAME = "facebook/wav2vec2-large-960h"
TARGET_SAMPLE_RATE = 16_000  # wav2vec2-large-960h expects 16 kHz input

app = FastAPI(title="ASR API", description="wav2vec2-large-960h speech-to-text service")

# ---------------------------------------------------------------------------
# Model loading — done once at import time so that every request reuses the
# same weights. Uses GPU when available, otherwise CPU.
# ---------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info("Loading %s on %s ...", MODEL_NAME, DEVICE)
processor = Wav2Vec2Processor.from_pretrained(MODEL_NAME)
model = Wav2Vec2ForCTC.from_pretrained(MODEL_NAME).to(DEVICE)
model.eval()
logger.info("Model loaded.")


@app.get("/ping", response_class=PlainTextResponse)
def ping() -> str:
    """Health check endpoint (Task 2b): GET /ping -> 'pong'."""
    return "pong"


@app.post("/asr")
async def asr(file: UploadFile = File(...)) -> dict:
    """
    Transcribe an uploaded audio file (Task 2c).

    Input   (multipart/form-data): file — the binary of an audio (mp3) file.
    Output  (application/json):    {"transcription": "<TEXT>", "duration": "<seconds>"}
    """
    # Persist the upload to a temporary file so librosa/ffmpeg can decode it.
    suffix = os.path.splitext(file.filename or "audio.mp3")[1] or ".mp3"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(await file.read())

        # Decode + resample to 16 kHz mono (model requirement).
        try:
            speech, _sr = librosa.load(tmp_path, sr=TARGET_SAMPLE_RATE, mono=True)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Could not decode audio file: {exc}"
            ) from exc

        if len(speech) == 0:
            raise HTTPException(status_code=400, detail="Audio file contains no samples.")

        duration_seconds = round(len(speech) / TARGET_SAMPLE_RATE, 1)

        # Run inference (no gradients needed).
        inputs = processor(
            speech, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt", padding=True
        )
        with torch.no_grad():
            logits = model(inputs.input_values.to(DEVICE)).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = processor.batch_decode(predicted_ids)[0]

        return {"transcription": transcription, "duration": str(duration_seconds)}
    finally:
        # Task 2e: delete the file once it has been processed.
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
