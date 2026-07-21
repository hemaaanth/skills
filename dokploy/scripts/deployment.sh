#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DOKPLOY_URL:-}" || -z "${DOKPLOY_API_KEY:-}" ]]; then
  echo "DOKPLOY_URL and DOKPLOY_API_KEY must be injected by the credential environment." >&2
  exit 2
fi

base_url="${DOKPLOY_URL%/}"

if [[ ! "$base_url" =~ ^https://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?$ ]]; then
  echo "DOKPLOY_URL must be an HTTPS origin without a path, query, or fragment." >&2
  exit 2
fi

usage() {
  echo "Usage: deployment.sh {app|compose|server|all|queue|type|logs|kill|remove} <id> [type|tail|--confirm]" >&2
  exit 2
}

require_id() {
  local value="${1:-}"
  if [[ ! "$value" =~ ^[A-Za-z0-9_-]{1,200}$ ]]; then
    usage
  fi
}

request() {
  curl --connect-timeout 5 --max-time 20 --fail-with-body --silent --show-error \
    -H "x-api-key: $DOKPLOY_API_KEY" \
    -H "Accept: application/json" \
    "$base_url$1"
}

mutation() {
  local endpoint="$1"
  local deployment_id="$2"
  curl --connect-timeout 5 --max-time 20 --fail-with-body --silent --show-error \
    -X POST \
    -H "x-api-key: $DOKPLOY_API_KEY" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    --data "{\"deploymentId\":\"$deployment_id\"}" \
    "$base_url$endpoint"
}

case "${1:-}" in
  app)
    require_id "${2:-}"
    request "/api/deployment.all?applicationId=$2"
    ;;
  compose)
    require_id "${2:-}"
    request "/api/deployment.allByCompose?composeId=$2"
    ;;
  server)
    require_id "${2:-}"
    request "/api/deployment.allByServer?serverId=$2"
    ;;
  all)
    [[ $# -eq 1 ]] || usage
    request "/api/deployment.allCentralized"
    ;;
  queue)
    [[ $# -eq 1 ]] || usage
    request "/api/deployment.queueList"
    ;;
  type)
    require_id "${2:-}"
    case "${3:-}" in
      application|compose|server|schedule|previewDeployment|backup|volumeBackup) ;;
      *) usage ;;
    esac
    request "/api/deployment.allByType?id=$2&type=$3"
    ;;
  logs)
    require_id "${2:-}"
    tail_count="${3:-100}"
    [[ "$tail_count" =~ ^[1-9][0-9]{0,3}$ ]] && (( tail_count <= 10000 )) || usage
    request "/api/deployment.readLogs?deploymentId=$2&tail=$tail_count"
    ;;
  kill)
    require_id "${2:-}"
    [[ "${3:-}" == "--confirm" && $# -eq 3 ]] || usage
    mutation "/api/deployment.killProcess" "$2"
    ;;
  remove)
    require_id "${2:-}"
    [[ "${3:-}" == "--confirm" && $# -eq 3 ]] || usage
    mutation "/api/deployment.removeDeployment" "$2"
    ;;
  *) usage ;;
esac
