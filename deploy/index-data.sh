#!/usr/bin/env bash
# Task 6 — index the transcribed CSV into the running cluster on the EC2 host.
#
# First copy the CSV (produced by Task 2d) to the instance, e.g. from your laptop:
#   scp -i key.pem /path/to/common_voice/cv-valid-dev.csv ec2-user@<EC2-IP>:~/
# Then on the instance, from the repository root:
#   bash deploy/index-data.sh ~/cv-valid-dev.csv
set -euo pipefail

CSV_PATH="${1:?usage: bash deploy/index-data.sh /path/to/cv-valid-dev.csv}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Creating Python venv with indexing dependencies ..."
sudo dnf install -y python3-pip >/dev/null 2>&1 || true
python3 -m venv "$REPO_ROOT/.venv-index"
source "$REPO_ROOT/.venv-index/bin/activate"
pip install --quiet pandas elasticsearch==8.17.0

echo "==> Indexing $CSV_PATH into cv-transcriptions ..."
python "$REPO_ROOT/elastic-backend/cv-index.py" --csv "$CSV_PATH" --es-url http://localhost:9200

echo "==> Verifying ..."
curl -s 'http://localhost:9200/cv-transcriptions/_count'; echo
