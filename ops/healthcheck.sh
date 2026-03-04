#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-http://localhost:8000/health}"

curl -fsS "$API_URL" | jq .
