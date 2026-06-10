#!/usr/bin/env python3
"""JRT PitCam — RaceChrono telemetry receiver.

Receives live GPS/speed telemetry from RaceChrono Pro's "Live data" UDP
NMEA export and tracks start/finish line crossings to time laps.

RaceChrono Pro setup:
  Settings -> Data sources -> Live data -> Send live data to
    udp://SERVER_IP:10110

Endpoints:
  UDP  :10110     -> receives NMEA sentences (GGA, RMC) from RaceChrono
  GET  /telemetry -> returns current telemetry + lap state (HTTP :8082)
"""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UDP_PORT = 10110
HTTP_PORT = 8082

# EDIT THIS — start/finish line as two (lat, lon) points spanning the track width.
# Calibrate by driving across the line and checking GET /telemetry for live coordinates.
SF_LINE = ((2.760516, 101.738582), (2.760840, 101.738308))

# Minimum seconds between counted crossings — prevents double-counting GPS jitter.
CROSS_COOLDOWN = 10
MAX_LAPS = 50

state = {
    "lat": None, "lon": None, "alt": None, "speed_kmh": None, "heading": None,
    "ts": None, "lap_count": 0, "last_cross": 0, "laps": [],
}
prev = {"lat": None, "lon": None}
lap_start = {"ts": None}
lock = threading.Lock()


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d):
    return _ccw(a, c, d) != _ccw(b, c, d) and _ccw(a, b, c) != _ccw(a, b, d)


def _nmea_to_decimal(value, direction):
    if not value:
        return None
    dot = value.index('.')
    deg_len = dot - 2
    deg = float(value[:deg_len])
    minutes = float(value[deg_len:])
    dec = deg + minutes / 60
    if direction in ('S', 'W'):
        dec = -dec
    return dec


def _handle_gga(fields):
    # $GPGGA,time,lat,N/S,lon,E/W,fix,sats,hdop,alt,M,...
    if len(fields) < 10 or fields[6] == '0':
        return
    lat = _nmea_to_decimal(fields[2], fields[3])
    lon = _nmea_to_decimal(fields[4], fields[5])
    alt = float(fields[9]) if fields[9] else None
    if lat is None or lon is None:
        return
    _update_position(lat, lon, alt=alt)


def _handle_rmc(fields):
    # $GPRMC,time,status,lat,N/S,lon,E/W,speed_knots,course,date,...
    if len(fields) < 9 or fields[2] != 'A':
        return
    lat = _nmea_to_decimal(fields[3], fields[4])
    lon = _nmea_to_decimal(fields[5], fields[6])
    speed_kmh = float(fields[7]) * 1.852 if fields[7] else None
    heading = float(fields[8]) if fields[8] else None
    if lat is None or lon is None:
        return
    _update_position(lat, lon, speed_kmh=speed_kmh, heading=heading)


def _update_position(lat, lon, alt=None, speed_kmh=None, heading=None):
    now = time.time()
    with lock:
        if prev["lat"] is not None:
            a, b = (prev["lat"], prev["lon"]), (lat, lon)
            if _segments_intersect(a, b, SF_LINE[0], SF_LINE[1]):
                if now - state["last_cross"] > CROSS_COOLDOWN:
                    if lap_start["ts"] is not None:
                        duration = now - lap_start["ts"]
                        state["lap_count"] += 1
                        state["laps"].insert(0, {
                            "lap": state["lap_count"],
                            "duration": round(duration, 3),
                        })
                        state["laps"] = state["laps"][:MAX_LAPS]
                    else:
                        state["lap_count"] += 1
                    lap_start["ts"] = now
                    state["last_cross"] = now

        prev["lat"], prev["lon"] = lat, lon
        state["lat"], state["lon"], state["ts"] = lat, lon, now
        if alt is not None:
            state["alt"] = alt
        if speed_kmh is not None:
            state["speed_kmh"] = round(speed_kmh, 1)
        if heading is not None:
            state["heading"] = heading


def _parse_sentence(line):
    line = line.strip()
    if not line.startswith('$'):
        return
    body = line.split('*')[0]
    fields = body.split(',')
    sentence_type = fields[0][3:]  # strip talker ID (GP/GN/GL...)
    if sentence_type == 'GGA':
        _handle_gga(fields)
    elif sentence_type == 'RMC':
        _handle_rmc(fields)


def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    while True:
        data, _ = sock.recvfrom(2048)
        for line in data.decode(errors='ignore').splitlines():
            try:
                _parse_sentence(line)
            except (ValueError, IndexError):
                pass


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
        if self.path != '/telemetry':
            self._send_json({"error": "not found"}, 404)
            return
        with lock:
            self._send_json(dict(state))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    threading.Thread(target=udp_server, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', HTTP_PORT), Handler).serve_forever()
