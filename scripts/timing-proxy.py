#!/usr/bin/env python3
"""
JRT PitCam — Live Timing Proxy
Connects to live.timing.asia SignalR feed and exposes lap data as REST JSON.
Runs on port 5001, nginx proxies /timing/* to it.
"""

import json
import re
import time
import threading
import logging
from urllib.parse import quote
from collections import deque

import requests
from flask import Flask, jsonify, request, request
import websocket

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL  = 'https://live.timing.asia'
VENUE     = 'sepang'
HUB_PATH  = '/lt'
TKDM      = '336813'  # fetched dynamically from page; this is the fallback

_state = {
    'connected':    False,
    'laps':         {},        # 'CAR_NR' -> [lap_dict, ...]
    'current':      {},        # 'CAR_NR' -> latest position/gap/lap data
    'session':      {          # session-wide data
        'flag':        None,   # 'GREEN','YELLOW','SC','RED'
        'lap':         None,   # current race lap number
        'total_laps':  None,
        'session_name': None,
        'status':      None,   # 'RUNNING','FINISH','PAUSE' etc
    },
    'raw_msgs':     deque(maxlen=200),
    'last_update':  0,
}
_lock = threading.Lock()

_sync = {
    'raceStarted': False,
    'raceStartTime': None,  # epoch float or None
    'flag': 'GREEN',
    'driverIdx': 0,
    'fuelLitres': 45.0,
    'lapCount': 0,
    'lastLap': None,
    'bestLap': None,
}
_sync_lock = threading.Lock()

_sync = {
    'raceStarted': False,
    'raceStartTime': None,
    'flag': 'GREEN',
    'driverIdx': 0,
    'fuelLitres': 45.0,
    'lapCount': 0,
    'lastLap': None,
    'bestLap': None,
    'eventLog': [],
}
_sync_lock = threading.Lock()

_FLAG_MAP = {
    'green':               'GREEN',
    'chequered':           'GREEN',
    'checkered':           'GREEN',
    'yellow':              'YELLOW',
    'full yellow':         'FCY',
    'full course yellow':  'FCY',
    'fcy':                 'FCY',
    'safety car':          'SC',
    'sc':                  'SC',
    'red':                 'RED',
    'red flag':            'RED',
}

# Map timing system flag strings to our dashboard flag names
_FLAG_MAP = {
    'green':        'GREEN',
    'chequered':    'GREEN',
    'checkered':    'GREEN',
    'yellow':       'YELLOW',
    'full yellow':  'YELLOW',
    'full course yellow': 'YELLOW',
    'fcy':          'YELLOW',
    'safety car':   'SC',
    'sc':           'SC',
    'red':          'RED',
    'red flag':     'RED',
}


# ─── Token + negotiate ────────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

def fetch_token():
    """Get _tk token and _tkdm from LiveTimingApp constructor in page HTML."""
    global TKDM
    try:
        r = _session.get(f'{BASE_URL}/{VENUE}', timeout=10,
                         headers={'Referer': BASE_URL,
                                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

        # LiveTimingApp({"n":"sepang","tid":"<token>","m":[...],"dm":"<dataMark>",...})
        m = re.search(r'LiveTimingApp\((\{[^)]+\})\)', r.text)
        if m:
            try:
                cfg = json.loads(m.group(1))
                tid = cfg.get('tid', '')
                dm  = cfg.get('dm', '')
                if tid:
                    log.info(f'Token from LiveTimingApp: {tid[:8]}… dm={dm}')
                    if dm:
                        TKDM = dm
                    return tid
            except Exception as je:
                log.warning(f'LiveTimingApp JSON parse error: {je}')

        log.warning('Token not found in page — connecting without (expect $_Reload)')
        return ''
    except Exception as e:
        log.error(f'fetch_token: {e}')
        return ''


def negotiate(tk):
    ts  = int(time.time() * 1000)
    url = f'{BASE_URL}{HUB_PATH}/negotiate'
    r   = requests.get(url, params={
        'clientProtocol': '1.5',
        '_tk':   tk,
        '_gr':   'w',
        '_tkdm': TKDM,
        '_':     ts,
    }, timeout=10, headers={'User-Agent': 'Mozilla/5.0', 'Referer': f'{BASE_URL}/{VENUE}'})
    return r.json()


def send_start(tk, conn_token):
    ts = int(time.time() * 1000)
    requests.get(f'{BASE_URL}{HUB_PATH}/start', params={
        'clientProtocol': '1.5',
        'transport':       'webSockets',
        'connectionToken': conn_token,
        '_tk':   tk,
        '_gr':   'w',
        '_tkdm': TKDM,
        '_':     ts,
    }, timeout=10, headers={'User-Agent': 'Mozilla/5.0', 'Referer': f'{BASE_URL}/{VENUE}'})


# ─── Message parsing ──────────────────────────────────────────────────────────

def parse_time_to_secs(t):
    """'2:51.756' -> 171.756"""
    if not t:
        raise ValueError
    s = str(t).strip()
    if ':' in s:
        m, sec = s.split(':', 1)
        return int(m) * 60 + float(sec)
    return float(s)


def parse_flag(val):
    """Normalise a flag string to our dashboard names, or None."""
    if not val:
        return None
    return _FLAG_MAP.get(str(val).lower().strip())


def process_session(data):
    """Extract session-level data: flag, lap number, status."""
    if not isinstance(data, dict):
        return
    with _lock:
        s = _state['session']

        raw_flag = (data.get('flag') or data.get('Flag') or data.get('trackStatus') or
                    data.get('TrackStatus') or data.get('condition') or data.get('Condition'))
        flag = parse_flag(raw_flag)
        if flag:
            if s['flag'] != flag:
                log.info(f'Flag: {flag}')
            s['flag'] = flag

        lap = (data.get('raceLap') or data.get('RaceLap') or data.get('currentLap') or
               data.get('CurrentLap'))
        if lap:
            s['lap'] = int(lap)

        total = (data.get('totalLaps') or data.get('TotalLaps'))
        if total:
            s['total_laps'] = int(total)

        # Session status — normalise to RUNNING / FINISH / PAUSE / UNKNOWN
        raw_status = (data.get('sessionStatus') or data.get('SessionStatus') or
                      data.get('status') or data.get('Status') or data.get('E.T.A.'))
        if raw_status:
            rs = str(raw_status).lower()
            if any(x in rs for x in ['run', 'live', 'active', 'started']):
                s['status'] = 'RUNNING'
            elif any(x in rs for x in ['finish', 'end', 'complete', 'chequered', 'checkered']):
                s['status'] = 'FINISH'
            elif any(x in rs for x in ['pause', 'stop', 'red']):
                s['status'] = 'PAUSE'
            else:
                s['status'] = str(raw_status).upper()

        # Also detect FINISH from E.T.A. field containing "Finished"
        eta_val = data.get('E.T.A.') or data.get('eta') or data.get('ETA') or ''
        if 'finish' in str(eta_val).lower():
            s['status'] = 'FINISH'


def process_entry(entry):
    """Extract and store lap data from a timing entry dict."""
    if not isinstance(entry, dict):
        return

    # Pull out any session-level fields embedded in the same message
    process_session(entry)

    car = (entry.get('NR') or entry.get('nr') or entry.get('carNumber') or
           entry.get('CarNumber') or entry.get('number') or entry.get('Number'))
    if not car:
        return
    car = str(car).upper().strip()

    lap_time = (entry.get('LAST') or entry.get('last') or entry.get('lastLap') or
                entry.get('LastLap') or entry.get('lapTime'))
    best_time = (entry.get('BEST') or entry.get('best') or entry.get('bestLap') or
                 entry.get('BestLap'))
    lap_num   = (entry.get('LAP') or entry.get('lap') or entry.get('lapCount') or
                 entry.get('LapCount'))

    # Extract driver name(s) — try every plausible field name
    driver_raw = (entry.get('DRIVER') or entry.get('driver') or entry.get('Driver') or
                  entry.get('NAME') or entry.get('name') or entry.get('driverName') or
                  entry.get('DriverName') or entry.get('pilot') or entry.get('Pilot'))
    drivers_list_raw = (entry.get('DRIVERS') or entry.get('drivers') or
                        entry.get('Drivers') or entry.get('pilots') or entry.get('Pilots'))

    # Store current race data regardless
    with _lock:
        pos = entry.get('POS') or entry.get('pos')
        _state['current'][car] = {
            'pos':       pos,
            'pos_int':   int(pos) if pos and str(pos).isdigit() else None,
            'gap':       entry.get('GAP') or entry.get('gap'),
            'diff':      entry.get('DIFF') or entry.get('diff'),
            'last':      lap_time,
            'best':      best_time,
            'lap':       lap_num,
            'pit':       entry.get('PIT') or entry.get('pit') or entry.get('pits'),
            'eta':       entry.get('E.T.A.') or entry.get('ETA') or entry.get('eta'),
            'cls':       entry.get('CLS') or entry.get('cls'),
            'cls_pos':   entry.get('PIC') or entry.get('pic') or entry.get('cls_pos'),
            's1':        entry.get('SECT-1') or entry.get('s1'),
            's2':        entry.get('SECT-2') or entry.get('s2'),
            's3':        entry.get('SECT-3') or entry.get('s3'),
            's4':        entry.get('SECT-4') or entry.get('s4'),
        }
        _state['last_update'] = time.time()

        # Accumulate driver names for this car
        existing = _state.setdefault('drivers', {}).setdefault(car, [])
        if drivers_list_raw and isinstance(drivers_list_raw, list):
            for d in drivers_list_raw:
                name = str(d).strip().upper()
                if name and name not in existing:
                    existing.append(name)
                    log.info(f'Car {car} driver from list: {name}')
        elif driver_raw:
            name = str(driver_raw).strip().upper()
            if name and name not in existing:
                existing.append(name)
                log.info(f'Car {car} driver: {name}')

    if not lap_time:
        return

    with _lock:
        laps = _state['laps'].setdefault(car, [])

        # Skip duplicate (same lap time as last recorded)
        if laps and laps[-1].get('time') == lap_time:
            return

        # Delta vs best lap so far
        delta = None
        try:
            lap_secs  = parse_time_to_secs(lap_time)
            best_ref  = best_time or (min((l['_secs'] for l in laps if l.get('_secs')), default=None))
            if best_ref:
                diff  = lap_secs - parse_time_to_secs(best_ref)
                delta = ('+' if diff > 0 else '') + f'{diff:.3f}'
        except Exception:
            pass

        is_best = bool(best_time and lap_time == best_time)

        laps.append({
            'lap':   lap_num if lap_num else len(laps) + 1,
            'time':  lap_time,
            '_secs': (lambda: parse_time_to_secs(lap_time) if lap_time else None)(),
            'best':  is_best,
            'delta': 'BEST' if is_best else (delta or ''),
            's1':    entry.get('SECT-1') or entry.get('s1'),
            's2':    entry.get('SECT-2') or entry.get('s2'),
            's3':    entry.get('SECT-3') or entry.get('s3'),
            's4':    entry.get('SECT-4') or entry.get('s4'),
            'pos':   entry.get('POS') or entry.get('pos'),
            'gap':   entry.get('GAP') or entry.get('gap'),
        })

        log.info(f'Car {car} lap {lap_num}: {lap_time} (delta {delta})')


def dispatch(data):
    """Route parsed data to process_entry. Handles list, dict, and nested shapes."""
    if isinstance(data, list):
        for item in data:
            dispatch(item)
    elif isinstance(data, dict):
        # Nested entry lists
        for key in ('Entries', 'entries', 'Cars', 'cars', 'Results', 'results',
                    'Competitors', 'competitors', 'Drivers', 'Standing', 'standing'):
            if key in data and isinstance(data[key], list):
                log.info(f'Dispatching nested list under "{key}" ({len(data[key])} items)')
                for item in data[key]:
                    process_entry(item)
                process_session(data)
                return
        process_entry(data)


try:
    import lzstring as _lzmod
    _LZ = _lzmod.LZString()
    log.info('lzstring available — LZ decompression enabled')
except ImportError:
    _LZ = None
    log.warning('lzstring not installed — live.timing.asia data will be unreadable. Run: pip install lzstring')


def lz_decode(data):
    """Decode a live.timing.asia LZString-UTF16-compressed data string.
    Returns a Python object (list/dict) or None on failure."""
    if not isinstance(data, str) or not data:
        return None
    # Strip optional ::hexTimestamp suffix
    ti = data.rfind('::')
    if ti != -1:
        data = data[:ti]
    if not _LZ:
        return None
    try:
        decompressed = _LZ.decompressFromUTF16(data)
        if decompressed:
            return json.loads(decompressed)
    except Exception as e:
        log.debug(f'lz_decode error: {e}')
    return None


def dispatch_lz(handle, data):
    """Recursively dispatch a live.timing.asia [handle, data] pair."""
    if handle in ('$_Reload', '$_Reconnect'):
        log.warning(f'Server sent {handle} — auth token likely missing or expired')
        return
    if handle == 's_t' or handle == 's_i':
        return  # server time sync, ignore

    if not isinstance(data, str):
        # Already decoded — treat as a regular data object
        dispatch(data)
        return

    # Data is LZString-compressed
    decoded = lz_decode(data)
    if decoded is None:
        # Not LZ — might be a plain value or "OK<timestamp>"
        if isinstance(data, str) and data.startswith('OK'):
            return
        return

    log.info(f'LZ decoded handle="{handle}" → {len(decoded) if isinstance(decoded, list) else type(decoded).__name__}')

    if isinstance(decoded, list):
        # Array of [handle, value] pairs — process in reverse (like JS while(di--))
        for item in reversed(decoded):
            if isinstance(item, list) and len(item) >= 2:
                dispatch_lz(item[0], item[1])
            elif isinstance(item, dict):
                dispatch(item)
    elif isinstance(decoded, dict):
        dispatch(decoded)


def on_message(ws, raw):
    try:
        msg = json.loads(raw)
    except Exception:
        return

    # Store last 200 raw messages for /timing/debug
    with _lock:
        _state['raw_msgs'].append({'t': time.time(), 'msg': msg})

    # R = response to a hub method invocation
    r_data = msg.get('R')
    if r_data:
        if isinstance(r_data, str):
            dispatch_lz('_', r_data)
        else:
            dispatch(r_data)

    # M = server-push messages (live.timing.asia uses ["handle", lzData] list format)
    messages = msg.get('M', [])
    for m in messages:
        if isinstance(m, list) and len(m) >= 2:
            dispatch_lz(m[0], m[1])
        elif isinstance(m, dict):
            method = m.get('M', '')
            args   = m.get('A', [])
            if method in ('$_Reload', '$_Reconnect'):
                log.warning(f'Server sent {method}')
                continue
            for a in args:
                if isinstance(a, str):
                    dispatch_lz(method, a)
                else:
                    dispatch(a)
        elif isinstance(m, str):
            try:
                dispatch(json.loads(m))
            except Exception:
                pass


# ─── WebSocket connection loop ────────────────────────────────────────────────

def connect_loop():
    while True:
        try:
            _connect()
        except Exception as e:
            log.error(f'connect_loop: {e}')
        with _lock:
            _state['connected'] = False
        log.info('Reconnecting in 20s…')
        time.sleep(20)


def _connect():
    tk    = fetch_token()
    neg   = negotiate(tk)
    token = neg.get('ConnectionToken', '')
    if not token:
        raise RuntimeError('No ConnectionToken')

    ts  = int(time.time() * 1000)
    url = (f'wss://live.timing.asia{HUB_PATH}/connect'
           f'?clientProtocol=1.5&transport=webSockets'
           f'&connectionToken={quote(token, safe="")}'
           f'&_tk={tk}&_gr=w&_tkdm={TKDM}&_={ts}')

    def on_open(ws):
        with _lock:
            _state['connected'] = True
        log.info('WebSocket connected')
        send_start(tk, token)
        # Invoke hub methods to request full current state from server.
        # Try several common method/hub name combinations used by live timing SignalR hubs.
        hub_candidates = [
            {'H': 'lthub',    'M': 'Subscribe',       'A': [], 'I': 1},
            {'H': 'lthub',    'M': 'GetCurrentState',  'A': [], 'I': 2},
            {'H': 'lthub',    'M': 'Start',            'A': [], 'I': 3},
            {'H': 'timinghub','M': 'Subscribe',        'A': [], 'I': 4},
            {'H': 'timinghub','M': 'GetCurrentState',  'A': [], 'I': 5},
            {'H': 'hub',      'M': 'Subscribe',        'A': [], 'I': 6},
        ]
        import threading as _t
        def _send_subscribes():
            import time as _time
            _time.sleep(1)   # wait for start handshake to complete
            for payload in hub_candidates:
                try:
                    ws.send(json.dumps(payload))
                    log.info(f'Sent hub invoke: {payload["H"]}.{payload["M"]}')
                    _time.sleep(0.3)
                except Exception as e:
                    log.warning(f'Hub invoke failed: {e}')
        _t.Thread(target=_send_subscribes, daemon=True).start()

    def on_close(ws, code, msg):
        with _lock:
            _state['connected'] = False
        log.info(f'WebSocket closed: {code}')

    def on_error(ws, err):
        log.error(f'WebSocket error: {err}')

    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error,
        header={'User-Agent': 'Mozilla/5.0', 'Referer': f'{BASE_URL}/{VENUE}'},
    )
    ws.run_forever(ping_interval=25, ping_timeout=10)


# ─── REST API ─────────────────────────────────────────────────────────────────

def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/timing/status')
def api_status():
    with _lock:
        return cors(jsonify({
            'connected':   _state['connected'],
            'cars':        list(_state['laps'].keys()),
            'last_update': _state['last_update'],
        }))


@app.route('/timing/car/<car_number>')
def api_car(car_number):
    car = car_number.upper().strip()
    with _lock:
        laps      = [{k: v for k, v in l.items() if k != '_secs'}
                     for l in _state['laps'].get(car, [])]
        current   = dict(_state['current'].get(car, {}))
        session   = dict(_state['session'])
        connected = _state['connected']
        # Compute gap_behind: find the car at pos+1, their DIFF is the gap between them and us
        my_pos = current.get('pos_int')
        gap_behind = None
        if my_pos:
            for other_car, other_data in _state['current'].items():
                if other_car == car:
                    continue
                other_pos = other_data.get('pos_int')
                if other_pos and other_pos == my_pos + 1:
                    gap_behind = other_data.get('diff')
                    break
        current['gap_behind'] = gap_behind

    with _lock:
        car_drivers = list(_state.get('drivers', {}).get(car, []))

    return cors(jsonify({
        'car':       car,
        'connected': connected,
        'current':   current,
        'session':   session,
        'laps':      laps,
        'drivers':   car_drivers,
    }))


@app.route('/timing/all')
def api_all():
    with _lock:
        result = {}
        for car, laps in _state['laps'].items():
            result[car] = [{k: v for k, v in l.items() if k != '_secs'} for l in laps]
    return cors(jsonify(result))


@app.route('/timing/debug')
def api_debug():
    """Last 20 raw SignalR messages — use this to inspect format during a race."""
    with _lock:
        msgs = list(_state['raw_msgs'])[-20:]
    return cors(jsonify(msgs))


@app.route('/timing/sync', methods=['GET'])
def api_sync_get():
    with _sync_lock:
        return cors(jsonify(dict(_sync)))


@app.route('/timing/sync', methods=['POST'])
def api_sync_post():
    body = request.get_json(silent=True) or {}
    with _sync_lock:
        for k, v in body.items():
            if k in _sync:
                _sync[k] = v
        return cors(jsonify(dict(_sync)))


@app.route('/timing/drivers/<car_number>')
def api_drivers(car_number):
    car = car_number.upper().strip()
    with _lock:
        names = list(_state.get('drivers', {}).get(car, []))
        all_cars = {c: list(v) for c, v in _state.get('drivers', {}).items()}
    return cors(jsonify({'car': car, 'drivers': names, 'all': all_cars}))


@app.route('/timing/reset')
def api_reset():
    with _lock:
        _state['laps'].clear()
        _state['current'].clear()
    return cors(jsonify({'ok': True}))


@app.route('/timing/sync', methods=['GET', 'POST'])
def api_sync():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        with _sync_lock:
            for k in _sync:
                if k in data:
                    _sync[k] = data[k]
    with _sync_lock:
        return cors(jsonify(dict(_sync)))


if __name__ == '__main__':
    threading.Thread(target=connect_loop, daemon=True).start()
    app.run(host='127.0.0.1', port=5001, debug=False)
