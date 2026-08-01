#!/usr/bin/env bash
# Quickstart: clone-to-working-search-UI in one command.
#   bash quickstart.sh
# Uses the pre-transcribed data/cv-valid-dev.csv shipped with the repo —
# no dataset download, no GPU, no model needed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> [0/5] Checking prerequisites ..."
command -v docker >/dev/null || { echo "ERROR: docker not found — install Docker first"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose v2 not found"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }

# Elasticsearch kernel requirement (Linux only; harmless failure elsewhere)
if [ "$(uname)" = "Linux" ] && [ "$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)" -lt 262144 ]; then
  echo "==> Setting vm.max_map_count=262144 (needs sudo) ..."
  sudo sysctl -w vm.max_map_count=262144
fi

echo "==> [1/5] Python venv with indexing dependencies ..."
if [ ! -d "$REPO_ROOT/.venv-quickstart" ]; then
  python3 -m venv "$REPO_ROOT/.venv-quickstart"
fi
source "$REPO_ROOT/.venv-quickstart/bin/activate"
pip install --quiet pandas "elasticsearch==8.17.0"

echo "==> [2/5] Starting 2-node Elasticsearch cluster ..."
cd "$REPO_ROOT/elastic-backend"
docker compose up -d

echo "==> Waiting for the cluster (up to 3 min) ..."
for i in $(seq 1 36); do
  if curl -s http://localhost:9200/_cluster/health | grep -q '"number_of_nodes":2'; then
    echo "    cluster is up."
    break
  fi
  [ "$i" = 36 ] && { echo "ERROR: cluster did not come up; check 'docker logs es01'"; exit 1; }
  sleep 5
done

echo "==> [3/5] Indexing data/cv-valid-dev.csv (4,076 records) ..."
python cv-index.py --csv "$REPO_ROOT/data/cv-valid-dev.csv"

echo "==> [4/5] Building + starting the search frontend (a few minutes on first run) ..."
cd "$REPO_ROOT/search-ui"
docker compose up --build -d

echo
echo "=================================================="
echo "  [5/5] Done! Open:  http://localhost:3000"
echo "  Stop everything:   bash quickstart.sh stop"
echo "=================================================="
