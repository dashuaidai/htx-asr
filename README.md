# HTX xData Technical Test — ASR Microservice & Search

This repository contains my submission for the HTX xData Technical Test (Engineer).
It implements an Automatic Speech Recognition (ASR) microservice using
[`facebook/wav2vec2-large-960h`](https://huggingface.co/facebook/wav2vec2-large-960h),
batch-transcribes the Common Voice `cv-valid-dev` dataset, indexes the results into a
2-node Elasticsearch cluster, and exposes them through an Elastic Search-UI web frontend
deployed on AWS.

## Repository structure

```
.
├── asr/                    # Task 2 — ASR microservice (FastAPI + wav2vec2) & batch decoder
├── deployment-design/      # Task 3 — Proposed AWS deployment architecture (design.pdf)
├── elastic-backend/        # Task 4 — 2-node Elasticsearch cluster + cv-index.py
├── search-ui/              # Task 5 — Search-UI frontend (port 3000)
├── requirements.txt        # Python dependencies
├── essay.pdf               # Task 8 — Model monitoring & drift essay
└── README.md
```

## Deployment URL (Task 7)

> _To be added after cloud deployment (Task 6)._

## Prerequisites

- Python 3.10+ (developed on 3.11)
- Docker & Docker Compose v2
- ~4 GB free RAM for the ASR model; ~4 GB for the 2-node Elasticsearch cluster

## Setup

```bash
# 1. Clone the repository
git clone <this-repo-url>
cd <repo-name>

# 2. Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Setup and run instructions for each component are documented in the sections below
(added task by task) and in each sub-directory.

## Assumptions

- Audio input to the ASR API can be any format readable by `librosa`/`ffmpeg`
  (the test data is mp3); everything is resampled to 16 kHz mono before inference,
  as required by the wav2vec2-large-960h model card.
- `duration` returned by the API is the audio length in seconds, serialised as a string
  (per the API spec in the assignment).
