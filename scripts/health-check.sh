#!/usr/bin/env bash
set -uo pipefail

# JRT PitCam — health check script
# Usage: ./health-check.sh YOUR_SERVER_IP

SERVER_IP="${1:-YOUR_SERVER_IP}"

if [[ "$SERVER_IP" == "YOUR_SERVER_IP" ]]; then
    echo "Usage: $0 <server-ip>"
    echo "Example: $0 167.99.123.45"
    exit 1
fi

STREAM_URL="http://$SERVER_IP:8080/live/jrt.m3u8"
HEALTH_URL="http://$SERVER_IP:8080/"
TMP_FILE="/tmp/jrt_hls_check.tmp"

echo "=== JRT PitCam Health Check ==="
echo "Server: $SERVER_IP"
echo ""

echo "[1/2] Checking nginx..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$HEALTH_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "000" ]]; then
    echo "  NGINX DOWN — connection refused at $SERVER_IP:8080"
    echo "    Check: systemctl status nginx"
    echo "    Check: ufw status (ports 1935 and 8080 must be open)"
    exit 1
else
    echo "  nginx is UP (HTTP $HTTP_CODE)"
fi

echo "[2/2] Checking HLS stream..."
HTTP_CODE=$(curl -s -o "$TMP_FILE" -w "%{http_code}" --connect-timeout 5 "$STREAM_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "000" ]]; then
    echo "  No response from stream endpoint"
elif [[ "$HTTP_CODE" == "200" ]]; then
    SEGMENT_COUNT=$(grep -c "\.ts" "$TMP_FILE" 2>/dev/null || echo "0")
    echo "  STREAM LIVE — $SEGMENT_COUNT segments in playlist"
elif [[ "$HTTP_CODE" == "404" ]]; then
    echo "  nginx is up but no stream active"
    echo "    Start Larix Broadcaster on the car phone"
    echo "    Confirm RTMP URL: rtmp://$SERVER_IP/live/jrt"
else
    echo "  Unexpected HTTP $HTTP_CODE"
fi

rm -f "$TMP_FILE"

echo ""
echo "============================================"
echo "  Larix RTMP URL:  rtmp://$SERVER_IP/live/jrt"
echo "  Pit wall URL:    http://$SERVER_IP:8080/live/jrt.m3u8"
echo "============================================"
