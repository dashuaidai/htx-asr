#!/usr/bin/env bash
# Stop the search stack started by quickstart.sh.
#   bash quickstop.sh            # pause containers (restart fast with quickstart.sh)
#   bash quickstop.sh --down     # remove containers, keep indexed data (volumes)
#   bash quickstop.sh --purge    # remove containers AND data volumes (full reset)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-stop}"

for dir in elastic-backend search-ui asr; do
  compose_file="$REPO_ROOT/$dir/docker-compose.yml"
  [ -f "$compose_file" ] || continue
  case "$MODE" in
    --purge) echo "==> $dir: down -v (containers + volumes)";
             docker compose -f "$compose_file" down -v ;;
    --down)  echo "==> $dir: down (containers only, volumes kept)";
             docker compose -f "$compose_file" down ;;
    *)       echo "==> $dir: stop";
             docker compose -f "$compose_file" stop ;;
  esac
done

echo
case "$MODE" in
  --purge) echo "Everything removed. 'bash quickstart.sh' rebuilds and re-indexes from scratch." ;;
  --down)  echo "Containers removed, data kept. 'bash quickstart.sh' brings it all back quickly." ;;
  *)       echo "Paused. Resume with 'bash quickstart.sh' (or 'docker compose start' in each dir)." ;;
esac
