#!/usr/bin/env bash
# Deploy Porchlight to the EC2 server: build the dashboard, copy the code and .env, restart the service.
# Usage: make deploy   (or: deploy/deploy.sh [host])
set -euo pipefail
cd "$(dirname "$0")/.."

HOST="${1:-${DEPLOY_HOST:-100.57.176.133}}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/porchlight.pem}"
SG="${DEPLOY_SG:-sg-0a09c3e879974b77b}"
DOMAIN="${DEPLOY_DOMAIN:-${HOST//./-}.sslip.io}"   # free HTTPS name that points at the server's IP
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3"

# Home internet IPs change; make sure ours may SSH in (ignore "already exists").
MYIP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MYIP/32,Description=deploy}]" \
  >/dev/null 2>&1 || true

echo "→ Building the dashboard"
(cd dashboard && npm ci --silent && npm run build >/dev/null)

echo "→ Copying code to $HOST"
rsync -az --delete -e "$SSH" \
  --exclude .git --exclude .venv --exclude node_modules --exclude backend/data --exclude .env \
  --exclude __pycache__ --exclude .pytest_cache --exclude /frames --exclude .DS_Store \
  ./ "ubuntu@$HOST:/opt/porchlight/"
scp -q -i "$KEY" .env "ubuntu@$HOST:/opt/porchlight/.env"

echo "→ Installing and restarting"
$SSH "ubuntu@$HOST" DOMAIN="$DOMAIN" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/porchlight
chmod 600 .env
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt
sudo cp deploy/porchlight.service /etc/systemd/system/porchlight.service
printf '%s {\n  encode gzip\n  reverse_proxy 127.0.0.1:8000\n}\n' "$DOMAIN" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now porchlight >/dev/null 2>&1
sudo systemctl restart porchlight
sudo systemctl reload caddy || sudo systemctl restart caddy
REMOTE

for i in $(seq 1 30); do
  curl -sf "https://$DOMAIN/api/status" >/dev/null && break
  sleep 2
done
echo "✅ Live at https://$DOMAIN"
curl -s "https://$DOMAIN/api/status"; echo
