#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-http://localhost:8000}"
curl -fsS -X POST "$API_URL/admin/rebuild-projections" | jq .
