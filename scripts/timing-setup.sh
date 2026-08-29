#!/bin/bash
# JRT PitCam — Timing Proxy Setup
# Run this once on the DigitalOcean server as root.
set -e

echo "=== Installing Python deps ==="
apt-get install -y python3 python3-pip python3-venv

echo "=== Setting up /opt/jrt-timing ==="
mkdir -p /opt/jrt-timing
cp /var/www/pitcam/timing-proxy.py /opt/jrt-timing/timing-proxy.py 2>/dev/null || true

echo "=== Creating virtualenv ==="
python3 -m venv /opt/jrt-timing/venv
/opt/jrt-timing/venv/bin/pip install --upgrade pip
/opt/jrt-timing/venv/bin/pip install flask requests websocket-client

echo "=== Installing systemd service ==="
cp "$(dirname "$0")/timing-proxy.service" /etc/systemd/system/jrt-timing.service
systemctl daemon-reload
systemctl enable jrt-timing
systemctl restart jrt-timing

echo "=== Done ==="
echo "Check status with: systemctl status jrt-timing"
echo "Check logs with:   journalctl -u jrt-timing -f"
echo "Test endpoint:     curl http://localhost:5001/timing/status"
