#!/bin/sh
# Push the site, editor API and server config to the Oracle box.
# Safe to run again: live data (/var/lib/finndex) and logins are never overwritten.
#
#   ./deploy/deploy.sh
set -eu

HOST=ubuntu@158.178.152.42
KEY="$HOME/Documents/key/ssh-key-2026-02-10.key"
SSH="ssh -i $KEY -o BatchMode=yes"
cd "$(dirname "$0")/.."

# Site files. data.json is excluded: the live copy lives in /var/lib/finndex.
rsync -az --delete --exclude .DS_Store --exclude data.json -e "$SSH" site/ "$HOST:/var/www/travelwillfin/"

# API and config go to a staging folder, then get installed with sudo.
$SSH "$HOST" 'mkdir -p ~/finndex-deploy'
rsync -az -e "$SSH" server/finndex_api.py deploy/finndex-api.service deploy/nginx-travelwillfin.conf "$HOST:finndex-deploy/"

$SSH "$HOST" 'set -eu
cd ~/finndex-deploy

# One-time setup (skipped once done).
id finndex >/dev/null 2>&1 || sudo useradd --system --no-create-home --shell /usr/sbin/nologin finndex
dpkg -s apache2-utils >/dev/null 2>&1 || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apache2-utils >/dev/null
sudo install -d -o finndex -g finndex -m 755 /var/lib/finndex
if [ ! -f /var/lib/finndex/data.json ]; then
  sudo install -o finndex -g finndex -m 644 /var/www/travelwillfin/data.json /var/lib/finndex/data.json
fi
sudo rm -f /var/www/travelwillfin/data.json
[ -f /etc/nginx/finndex-editors ] || sudo install -o root -g www-data -m 640 /dev/null /etc/nginx/finndex-editors

# API + service.
sudo install -d /opt/finndex
sudo install -m 644 finndex_api.py /opt/finndex/finndex_api.py
sudo install -m 644 finndex-api.service /etc/systemd/system/finndex-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now finndex-api >/dev/null 2>&1
sudo systemctl restart finndex-api

# nginx.
sudo install -m 644 nginx-travelwillfin.conf /etc/nginx/sites-available/travelwillfin
sudo nginx -t 2>&1 | tail -1
sudo systemctl reload nginx

echo "api: $(systemctl is-active finndex-api)  nginx: $(systemctl is-active nginx)  editors: $(sudo grep -c . /etc/nginx/finndex-editors || true)"'
