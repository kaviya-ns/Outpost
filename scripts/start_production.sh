#!/bin/sh
# Single-container production: platform mocks on localhost:8080, API on $PORT.
set -e

MOCK_INTERNAL="${MOCK_INTERNAL_URL:-http://127.0.0.1:8080}"
export DISCOURSE_MOCK_URL="${DISCOURSE_MOCK_URL:-$MOCK_INTERNAL}"
export DEVTO_MOCK_URL="${DEVTO_MOCK_URL:-$MOCK_INTERNAL}"
export WEBHOOK_PARTNER_URL="${WEBHOOK_PARTNER_URL:-$MOCK_INTERNAL}"
export LEMMY_BASE_URL="${LEMMY_BASE_URL:-$MOCK_INTERNAL}"
export GHOST_URL="${GHOST_URL:-$MOCK_INTERNAL}"
export MOCK_RULES_PAGE_URL="${MOCK_RULES_PAGE_URL:-$MOCK_INTERNAL/rules/community-guidelines.txt}"

echo "Starting platform mocks on 127.0.0.1:8080 ..."
python -m uvicorn mocks.mock_platforms:app --host 127.0.0.1 --port 8080 &
sleep 2

PORT="${PORT:-8000}"
echo "Starting API on 0.0.0.0:${PORT} ..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
