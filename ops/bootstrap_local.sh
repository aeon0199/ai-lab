#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e packages/domain -e packages/policy -e services/api -e services/worker -e services/sandbox pytest
cd apps/desktop
npm install
cd ..
echo "Bootstrap complete. Run: docker compose -f infra/docker/docker-compose.yml up --build"
