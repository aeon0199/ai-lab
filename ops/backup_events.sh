#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

PG_URL="${DATABASE_URL:-postgresql://ailab:ailab@localhost:5432/ailab}"

pg_dump "$PG_URL" --table=events --file="$OUT_DIR/events-$STAMP.sql"
echo "Backed up events to $OUT_DIR/events-$STAMP.sql"
