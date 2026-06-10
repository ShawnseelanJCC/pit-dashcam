#!/usr/bin/env python3
"""JRT PitCam — GPS tracker.

Receives GPS fixes from the car phone (e.g. GPSLogger app) and tracks
start/finish line crossings to count laps.

Endpoint:
  GET /gps?lat=<lat>&lon=<lon>  -> records a fix, returns current state
  GET /gps                      -> returns current state (for dashboard polling)
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# EDIT THESE — start/finish line as two (lat, lon) points spanning the track width.
# Calibrate by driving across the line and checking GET /gps for your live coordinates.
SF_LINE = ((2.760516, 101.738582), (2.760840, 101.738308))

# Minimum seconds between counted crossings — prevents double-counting GPS jitter.
CROSS_COOLDOWN = 10

state = {"lat": None, "lon": None, "ts": None, "lap_count": 0, "last_cross": 0}
prev = {"lat": None, "lon": None}


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d):
    return _ccw(a, c, d) != _ccw(b, c, d) and _ccw(a, b, c) != _ccw(a, b, d)


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != '/gps':
            self._send_json({"error": "not found"}, 404)
            return

        qs = parse_qs(parsed.query)
        if 'lat' in qs and 'lon' in qs:
            try:
                lat, lon = float(qs['lat'][0]), float(qs['lon'][0])
            except ValueError:
                self._send_json({"error": "bad lat/lon"}, 400)
                return

            now = time.time()
            if prev["lat"] is not None:
                a, b = (prev["lat"], prev["lon"]), (lat, lon)
                if _segments_intersect(a, b, SF_LINE[0], SF_LINE[1]):
                    if now - state["last_cross"] > CROSS_COOLDOWN:
                        state["lap_count"] += 1
                        state["last_cross"] = now

            prev["lat"], prev["lon"] = lat, lon
            state["lat"], state["lon"], state["ts"] = lat, lon, now

        self._send_json(state)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8081), Handler).serve_forever()
