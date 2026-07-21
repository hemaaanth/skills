#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
helper="$root/scripts/deployment.sh"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

cat > "$temp_dir/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$DOKPLOY_TEST_CURL_ARGS"
printf '{"ok":true}\n'
EOF
chmod +x "$temp_dir/curl"

run() {
  : > "$temp_dir/curl-args"
  PATH="$temp_dir:$PATH" DOKPLOY_URL="https://dokploy.example.test" DOKPLOY_API_KEY="test-key" DOKPLOY_TEST_CURL_ARGS="$temp_dir/curl-args" "$helper" "$@" > /dev/null
}

expect_arg() {
  grep -Fqx -- "$1" "$temp_dir/curl-args"
}

run app app_123
expect_arg 'https://dokploy.example.test/api/deployment.all?applicationId=app_123'

run logs deploy_123 250
expect_arg 'https://dokploy.example.test/api/deployment.readLogs?deploymentId=deploy_123&tail=250'

run type compose_123 compose
expect_arg 'https://dokploy.example.test/api/deployment.allByType?id=compose_123&type=compose'

run kill deploy_123 --confirm
expect_arg 'https://dokploy.example.test/api/deployment.killProcess'
expect_arg '{"deploymentId":"deploy_123"}'

if PATH="$temp_dir:$PATH" DOKPLOY_URL="https://dokploy.example.test" DOKPLOY_API_KEY="test-key" "$helper" remove deploy_123 > /dev/null 2>&1; then
  echo 'remove must require --confirm' >&2
  exit 1
fi

if PATH="$temp_dir:$PATH" DOKPLOY_URL="http://dokploy.example.test" DOKPLOY_API_KEY="test-key" "$helper" all > /dev/null 2>&1; then
  echo 'non-HTTPS URLs must be rejected' >&2
  exit 1
fi

if PATH="$temp_dir:$PATH" DOKPLOY_URL="https://dokploy.example.test/api" DOKPLOY_API_KEY="test-key" "$helper" all > /dev/null 2>&1; then
  echo 'non-origin URLs must be rejected' >&2
  exit 1
fi
