#!/usr/bin/env bash
set -euo pipefail

# JRT PitCam — server provisioning script
# Run as root on a fresh Ubuntu 22.04 DigitalOcean Singapore droplet.
# Safe to re-run (idempotent).

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Run as root (sudo ./server-setup.sh)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== JRT PitCam — Server Setup ==="
echo ""

echo "[1/7] Updating system packages..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "[2/7] Installing nginx, rtmp module, ufw, curl..."
apt-get install -y nginx libnginx-mod-rtmp ufw curl

echo "[3/7] Creating /tmp/hls directory..."
mkdir -p /tmp/hls
chown www-data:www-data /tmp/hls
chmod 755 /tmp/hls

echo "[4/8] Deploying nginx.conf and dashboard..."
cp "$SCRIPT_DIR/../server/nginx.conf" /etc/nginx/nginx.conf
nginx -t
mkdir -p /var/www/pitcam
cp "$SCRIPT_DIR/../dashboard/index.html" /var/www/pitcam/index.html

echo "[5/8] Deploying GPS tracker service..."
mkdir -p /opt/pitcam
cp "$SCRIPT_DIR/../server/gps-server.py" /opt/pitcam/gps-server.py
cp "$SCRIPT_DIR/../server/gps-server.service" /etc/systemd/system/gps-server.service
systemctl daemon-reload
systemctl enable gps-server
systemctl restart gps-server

echo "[6/8] Configuring UFW firewall..."
ufw allow 22/tcp    comment 'SSH'
ufw allow 80/tcp    comment 'HTTP'
ufw allow 1935/tcp  comment 'RTMP ingest'
ufw allow 8080/tcp  comment 'HLS HTTP'
ufw --force enable

echo "[7/8] Enabling and starting nginx..."
systemctl enable nginx
systemctl restart nginx

echo "[8/8] Done!"
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "============================================"
echo "  JRT PitCam is ready"
echo "============================================"
echo "  Pit wall dashboard: http://$SERVER_IP/"
echo "  Larix RTMP URL:     rtmp://$SERVER_IP/live/jrt"
echo "  HLS stream URL:     http://$SERVER_IP:8080/live/jrt.m3u8"
echo "  Health check:       http://$SERVER_IP:8080/"
echo "============================================"
echo ""
echo "  Open http://$SERVER_IP/ on the pit wall browser."
echo ""
