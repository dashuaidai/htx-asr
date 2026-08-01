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

The Search-UI application is deployed on AWS EC2 (ap-southeast-1) and publicly
accessible at:

**http://47.129.227.62:3000**

(Backed by the 2-node Elasticsearch cluster on the same instance, with all
4,076 transcribed cv-valid-dev records indexed in `cv-transcriptions`.
The cluster itself is intentionally not exposed to the internet — see Task 3.)

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

## Task 2 — ASR microservice (`asr/`)

### Run the API directly

```bash
cd asr
uvicorn asr_api:app --host 0.0.0.0 --port 8001
# first start downloads facebook/wav2vec2-large-960h (~1.2 GB) into the HF cache
```

Health check:

```bash
curl http://localhost:8001/ping          # -> pong
```

Transcribe a file:

```bash
curl -F 'file=@/path/to/cv-valid-dev/sample-000000.mp3' http://localhost:8001/asr
# -> {"transcription": "BEFORE HE HAD TIME TO ANSWER ...", "duration": "5.1"}
```

### Run with Docker (service name `asr-api`)

```bash
cd asr
docker compose up --build -d      # or: docker build -t asr-api . && docker run -p 8001:8001 asr-api
curl http://localhost:8001/ping
```

The model weights are baked into the image at build time, so the container
needs no internet access at runtime.

### Batch-transcribe Common Voice `cv-valid-dev` (4,076 files)

Download and unzip the dataset (link in the assignment), then:

```bash
cd asr
python cv-decode.py \
  --csv       /path/to/common_voice/cv-valid-dev.csv \
  --audio-dir /path/to/common_voice \
  --api-url   http://localhost:8001/asr \
  --workers   4
```

This writes the transcriptions into a new `generated_text` column and saves
the updated `cv-valid-dev.csv` back in place. The script is resumable —
re-running it skips rows that already have a transcription.

## Task 4 — Elasticsearch backend (`elastic-backend/`)

Start the 2-node cluster (needs `vm.max_map_count >= 262144` on the host —
`sudo sysctl -w vm.max_map_count=262144`):

```bash
cd elastic-backend
docker compose up -d
curl http://localhost:9200/_cluster/health   # wait for "number_of_nodes":2
```

Index the transcribed CSV into `cv-transcriptions`:

```bash
python cv-index.py --csv /path/to/common_voice/cv-valid-dev.csv
curl 'http://localhost:9200/cv-transcriptions/_count'   # -> 4076
```

`cv-index.py` is idempotent (doc `_id` = filename) — safe to re-run;
use `--recreate` to wipe and rebuild the index.

## Task 5 — Search-UI frontend (`search-ui/`)

Start it after the elastic-backend stack (it joins the same Docker network):

```bash
cd search-ui
docker compose up --build -d
```

Open http://localhost:3000 — full-text search over `generated_text`, with
facet filters for `duration`, `age`, `gender` and `accent`.

The React app (Elastic Search-UI) is served by nginx on port 3000, which also
reverse-proxies `/elasticsearch/*` to `es01:9200` on the internal Docker
network — the cluster is never exposed to the browser directly.

## Task 6 — Cloud deployment (`deploy/`)

The stack is deployed on a single AWS EC2 instance (self-managed Docker
containers only — no managed services), following the Task 3 architecture.
See [`deploy/AWS-DEPLOYMENT-GUIDE.md`](deploy/AWS-DEPLOYMENT-GUIDE.md) for the
full walkthrough; in short:

```bash
# on a fresh Amazon Linux 2023 EC2 instance (ports 22 + 3000 open)
git clone <this-repo-url> && cd <repo>
bash deploy/setup-ec2.sh      # docker + compose, kernel params, swap
bash deploy/deploy.sh         # ES cluster + Search-UI
bash deploy/index-data.sh ~/cv-valid-dev.csv
```

## Assumptions

- Audio input to the ASR API can be any format readable by `librosa`/`ffmpeg`
  (the test data is mp3); everything is resampled to 16 kHz mono before inference,
  as required by the wav2vec2-large-960h model card.
- `duration` returned by the API is the audio length in seconds, serialised as a string
  (per the API spec in the assignment).
