#!/usr/bin/env bash
# Send the Ring Playground token from your local .env to the server (it lasts 30 minutes).
# The backend re-reads it on every request, so no restart is needed.
# Usage: make push-token
set -euo pipefail
cd "$(dirname "$0")/.."
HOST="${1:-${DEPLOY_HOST:-100.57.176.133}}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/porchlight.pem}"
TOKEN=$(grep -E '^OAUTH_TOKEN=' .env | head -1 | cut -d= -f2-)
[ -n "$TOKEN" ] || { echo "OAUTH_TOKEN is empty in .env"; exit 1; }
# The token goes over stdin, so it never appears in a process list or shell history.
printf '%s' "$TOKEN" | ssh -i "$KEY" -o ConnectTimeout=15 "ubuntu@$HOST" \
  'TOKEN=$(cat); cd /opt/porchlight && grep -v "^OAUTH_TOKEN=" .env > .env.tmp; echo "OAUTH_TOKEN=$TOKEN" >> .env.tmp; mv .env.tmp .env; chmod 600 .env'
echo "✅ Token sent to $HOST"
