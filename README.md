# HTX xData Technical Test — ASR Microservice & Search

This repository contains my submission for the HTX xData Technical Test (Engineer).
It implements an Automatic Speech Recognition (ASR) microservice using
[`facebook/wav2vec2-large-960h`](https://huggingface.co/facebook/wav2vec2-large-960h),
batch-transcribes the Common Voice `cv-valid-dev` dataset, indexes the results into a
2-node Elasticsearch cluster, and exposes them through an Elastic Search-UI web frontend
deployed on AWS.

**Key deliverables:**
[Live demo](http://47.129.227.62:3000) ·
[Model monitoring & drift essay (essay.pdf)](https://github.com/dashuaidai/htx-asr/blob/main/essay.pdf) ·
[Deployment architecture (design.pdf)](https://github.com/dashuaidai/htx-asr/blob/main/deployment-design/design.pdf) ·
[AWS deployment guide](https://github.com/dashuaidai/htx-asr/blob/main/deploy/AWS-DEPLOYMENT-GUIDE.md)

## Repository structure

```
.
├── asr/                    # Task 2 — ASR microservice (FastAPI + wav2vec2) & batch decoder
├── deployment-design/      # Task 3 — Proposed AWS deployment architecture (design.pdf)
├── elastic-backend/        # Task 4 — 2-node Elasticsearch cluster + cv-index.py
├── search-ui/              # Task 5 — Search-UI frontend (port 3000)
├── deploy/                 # Task 6 — EC2 setup / deploy / indexing scripts + AWS guide
├── data/                   # Transcribed cv-valid-dev.csv (for the Quickstart)
├── quickstart.sh           # One-command local reproduction
├── quickstop.sh            # Stop / clean up the stack
├── requirements.txt        # Python dependencies
├── essay.pdf               # Task 8 — Model monitoring & drift essay
└── README.md
```

## Quickstart (one command, ~10 minutes)

No dataset download, no GPU, no model needed — a transcribed copy of the data
ships with the repo at `data/cv-valid-dev.csv`:

```bash
git clone https://github.com/dashuaidai/htx-asr.git && cd htx-asr
bash quickstart.sh
# then open http://localhost:3000  — full-text search + facet filters over 4,076 records
```

Stop / clean up:

```bash
bash quickstop.sh            # pause containers (resume with quickstart.sh)
bash quickstop.sh --down     # remove containers, keep the indexed data
bash quickstop.sh --purge    # remove everything incl. data volumes (full reset)
```

<details>
<summary>Prefer manual steps? Click to expand.</summary>

```bash
# 0. Prerequisites: Docker + Compose v2, Python 3.10+; on Linux:
sudo sysctl -w vm.max_map_count=262144

# 1. Install indexing dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install pandas elasticsearch==8.17.0

# 2. Start the 2-node Elasticsearch cluster
cd elastic-backend && docker compose up -d
# wait until: curl -s localhost:9200/_cluster/health shows "number_of_nodes":2

# 3. Index the pre-transcribed data
python cv-index.py --csv ../data/cv-valid-dev.csv
curl 'http://localhost:9200/cv-transcriptions/_count'   # -> {"count":4076}

# 4. Build and start the search frontend
cd ../search-ui && docker compose up --build -d

# 5. Open http://localhost:3000
```

</details>

To run the full pipeline from raw audio (ASR service, batch transcription,
Docker image with the model baked in), see the task-by-task sections below.

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

### Evaluate transcription quality (WER)

```bash
python compute-wer.py --csv /path/to/common_voice/cv-valid-dev.csv
```

Prints corpus-level Word Error Rate of `generated_text` against the
ground-truth `text` column, plus breakdowns by accent, gender and duration
(text is normalised — lower-cased, punctuation stripped — before scoring).
Stratified reporting ties into the monitoring approach described in
`essay.pdf`: subgroup degradation must not be averaged away.

Measured results on the 4,076 transcribed cv-valid-dev clips:

| Metric | WER |
|---|---|
| **Corpus overall** | **10.83%** |
| Accent: canada / us / england | 4.88% / 8.26% / 9.75% |
| Accent: australia / indian / philippines | 17.16% / 21.77% / 23.19% |
| Gender: female / male | 10.29% / 10.83% |
| Duration: 3–5 s / 5–8 s | 10.66% / 9.52% |
| Duration: 0–3 s / 8 s + | 13.80% / 13.63% |

Interpretation: the model (trained on LibriSpeech — largely North-American
read speech) degrades markedly on accents far from its training distribution
(Indian, Filipino, Australian), while showing no meaningful gender gap; very
short clips lack context and long clips accumulate errors. The overall 10.83%
vs ~2–3% on LibriSpeech quantifies the distribution shift — exactly the kind
of stratified quality signal the monitoring pipeline in `essay.pdf` is
designed to track continuously.

## Task 4 — Elasticsearch backend (`elastic-backend/`)

Start the 2-node cluster (needs `vm.max_map_count >= 262144` on the host —
`sudo sysctl -w vm.max_map_count=262144`):

```bash
cd elastic-backend
docker compose up -d
curl http://localhost:9200/_cluster/health   # wait for "number_of_nodes":2
```

Index the transcribed CSV into `cv-transcriptions`.

> **Shortcut:** a ready-made transcribed copy is committed at
> `data/cv-valid-dev.csv` (generated_text + duration already filled in by
> Task 2d), so you can index immediately without downloading the dataset or
> re-running the ASR batch step:

```bash
cd elastic-backend
python cv-index.py --csv ../data/cv-valid-dev.csv
curl 'http://localhost:9200/cv-transcriptions/_count'   # -> 4076
```

If you transcribed the dataset yourself, point `--csv` at your own copy instead:

```bash
python cv-index.py --csv /path/to/common_voice/cv-valid-dev.csv
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
