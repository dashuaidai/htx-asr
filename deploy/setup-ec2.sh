#!/usr/bin/env bash
# Task 6 — one-time host preparation for a fresh Amazon Linux 2023 EC2 instance.
# Installs Docker + Compose, sets the kernel parameter Elasticsearch needs,
# and adds a swap file so the stack also fits small (free-tier) instances.
#
# Usage (as ec2-user):   bash setup-ec2.sh
set -euo pipefail

echo "==> Installing Docker & git ..."
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

echo "==> Installing Docker Compose v2 plugin ..."
DOCKER_CONFIG=${DOCKER_CONFIG:-/usr/local/lib/docker}
sudo mkdir -p "$DOCKER_CONFIG/cli-plugins"
ARCH=$(uname -m)   # x86_64 or aarch64
sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${ARCH}" \
     -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
sudo chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"

echo "==> Kernel parameter required by Elasticsearch ..."
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-elasticsearch.conf >/dev/null

# 4 GB swap — lets the 2-node ES cluster + search-ui run even on 1 GB RAM
# (t2.micro free tier). Harmless on bigger instances.
if ! swapon --show | grep -q '/swapfile'; then
  echo "==> Creating 4 GB swap file ..."
  sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Done. Log out and back in (or run 'newgrp docker') so the docker"
echo "    group membership takes effect, then run deploy.sh"
