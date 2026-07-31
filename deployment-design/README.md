# Task 3 — Proposed deployment architecture

- `design.pdf` — the architecture diagram (deliverable).
- `design.drawio` — the editable draw.io source (open at https://app.diagrams.net).

## Summary

A single EC2 VM (Amazon Linux 2023, Docker + Compose, Elastic IP) hosts three
self-managed containers on one Docker bridge network — **no managed AWS services**:

| Component | Container(s) | Port | Exposed to internet? |
|---|---|---|---|
| Search frontend | `search-ui` (nginx + React Search-UI build) | 3000 | Yes (Security Group: 0.0.0.0/0) |
| Search backend | `es01`, `es02` (Elasticsearch 8.x, 2-node cluster) | 9200/9300 | No — Docker network only |

Key decisions:

1. **ES is never exposed publicly.** The browser-side Search-UI app calls
   `/elasticsearch/*` on port 3000; nginx inside the `search-ui` container
   reverse-proxies those calls to `es01:9200` over the internal Docker network.
2. **Resilience within one VM**: 2 ES nodes with 1 replica per shard tolerate
   the loss of one data node; named volumes (`esdata01/02`) persist data across
   container restarts.
3. **Free tier**: t2.micro (1 GB RAM) works with 256 MB heap per ES node plus a
   4 GB swap file, but t3.medium is recommended for a responsive demo.
4. The ASR pipeline (Task 2) is an **offline batch step** — `asr-api` +
   `cv-decode.py` produce `cv-valid-dev.csv`, which `cv-index.py` bulk-indexes
   into the `cv-transcriptions` index once. The heavyweight wav2vec2 model is
   therefore not part of the always-on hosted stack.
