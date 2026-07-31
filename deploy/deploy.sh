#!/usr/bin/env bash
# Task 6 — bring up the full search stack (2-node Elasticsearch + Search-UI)
# on the EC2 host. Run from the repository root after setup-ec2.sh:
#
#   git clone <repo-url> && cd <repo> && bash deploy/deploy.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Starting Elasticsearch cluster (elastic-backend) ..."
cd "$REPO_ROOT/elastic-backend"
docker compose up -d

echo "==> Waiting for the cluster to be healthy ..."
for i in $(seq 1 60); do
  if curl -s http://localhost:9200/_cluster/health | grep -qE '"status":"(green|yellow)"'; then
    echo "    cluster is up:"
    curl -s http://localhost:9200/_cluster/health; echo
    break
  fi
  [ "$i" = 60 ] && { echo "ERROR: cluster did not come up in time"; exit 1; }
  sleep 5
done

echo "==> Building + starting Search-UI frontend ..."
cd "$REPO_ROOT/search-ui"
docker compose up --build -d

PUBLIC_IP=$(curl -s --max-time 5 http://169.254.169.254/latest/meta-data/public-ipv4 || echo "<EC2-public-IP>")
echo
echo "=================================================================="
echo "  Deployment complete."
echo "  Search UI:      http://${PUBLIC_IP}:3000"
echo "  Next step:      index the data (see deploy/index-data.sh)"
echo "=================================================================="
