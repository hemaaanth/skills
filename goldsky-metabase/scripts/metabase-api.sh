#!/usr/bin/env bash
set -euo pipefail

# Metabase API wrapper
# Usage: ./metabase-api.sh METHOD PATH [BODY]
# Flags: -q quiet, -r raw output, -o FILE write to file
#
# Examples:
#   ./metabase-api.sh GET /api/database/
#   ./metabase-api.sh POST /api/dataset/ '{"type":"native","native":{"query":"SELECT 1"},"database":1}'
#   ./metabase-api.sh GET /api/card/42/query/csv -o results.csv

# Auto-source .env from repo root if vars aren't already set
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -z "${METABASE_URL:-}" ] || [ -z "${METABASE_API_KEY:-}" ]; then
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
  fi
fi

METABASE_URL="${METABASE_URL:?Set METABASE_URL or add it to .env at repo root}"
METABASE_API_KEY="${METABASE_API_KEY:?Set METABASE_API_KEY or add it to .env at repo root}"

QUIET=false
RAW=false
OUTPUT_FILE=""

# Parse flags
while [[ "${1:-}" =~ ^- ]]; do
  case "$1" in
    -q) QUIET=true; shift ;;
    -r) RAW=true; shift ;;
    -o) OUTPUT_FILE="$2"; shift 2 ;;
    *)  echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

METHOD="${1:?Usage: metabase-api.sh METHOD PATH [BODY]}"
PATH_ARG="${2:?Usage: metabase-api.sh METHOD PATH [BODY]}"
BODY="${3:-}"

# Build curl args
CURL_ARGS=(
  -s
  -X "$METHOD"
  -H "X-Api-Key: $METABASE_API_KEY"
  -w "\n%{http_code}"
)

if [ -n "$BODY" ]; then
  CURL_ARGS+=(-H "Content-Type: application/json" -d "$BODY")
fi

if [ -n "$OUTPUT_FILE" ]; then
  CURL_ARGS+=(-o "$OUTPUT_FILE")
fi

# Execute request
RESPONSE=$(curl "${CURL_ARGS[@]}" "${METABASE_URL}${PATH_ARG}")

# Split response body and status code
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

# Handle output file case
if [ -n "$OUTPUT_FILE" ]; then
  if [ "$HTTP_CODE" -ge 400 ]; then
    echo "Error: HTTP $HTTP_CODE" >&2
    rm -f "$OUTPUT_FILE"
    exit 1
  fi
  $QUIET || echo "Saved to $OUTPUT_FILE (HTTP $HTTP_CODE)"
  exit 0
fi

# Handle errors
if [ "$HTTP_CODE" -ge 400 ]; then
  if ! $QUIET; then
    echo "Error: HTTP $HTTP_CODE" >&2
    echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY" >&2
  fi
  exit 1
fi

# Output response
if $RAW; then
  echo "$RESPONSE_BODY"
elif $QUIET; then
  : # No output
else
  echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY"
fi
