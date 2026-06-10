# JRT PitCam — Endurance Live Stream

Phone-to-browser live video streaming for the JRT endurance racing pit wall. The car phone streams over 4G → DigitalOcean Singapore relay server → pit wall browser dashboard. ~2–3 second end-to-end latency.

---

## Race Day — 3 Steps

### 1. Car phone (Larix Broadcaster)
- Open **Larix Broadcaster**
- Tap the **record button** → confirm the **red dot** appears
- Stream is now live

### 2. Pit wall browser
- Open **http://104.248.151.105/**
- Click **CONNECT** (URL is pre-filled)
- Video starts playing within 2–3 seconds

### 3. If stream drops
- Wait 10 seconds — hls.js auto-recovers when 4G signal returns
- If still dead: tap CONNECT again in the dashboard

---

## Dashboard Features

| Feature | How to use |
|---|---|
| **Lap logger** | Press LAP button each time the car crosses the line |
| **Flag status** | GREEN / YELLOW / SC / RED — tap to change, one active at a time |
| **Driver** | Click the driver name in the bottom bar to switch — resets stint timer |
| **Fuel** | Auto-decrements per lap. +/- for manual adjust. REFUEL resets to 100%. Red warning at ≤15% |
| **Pit notes** | Free text box — use for tyre notes, comms, strategy |
| **Event log** | Auto-logs all stream, lap, fuel, flag, and driver events with timestamps |

---

## Larix Broadcaster Setup (one-time)

```
App:         Larix Broadcaster (free — iOS & Android)
Connection:  Connections → New Connection → RTMP
URL:         rtmp://104.248.151.105/live/jrt
Resolution:  1280×720
Framerate:   25fps
Bitrate:     1000 kbps (drop to 750 if signal is weak)
Audio:       Disabled
Reconnect:   Enable auto-reconnect, 5s interval
```

---

## RaceChrono Pro Telemetry (live GPS, speed, lap times)

The dashboard sidebar shows a live telemetry table (speed, heading, lat/lon, altitude) and a lap log timed off Sepang's start/finish line — fed by RaceChrono Pro's built-in UDP live data export, sent from the same phone that's running Larix.

### One-time setup on the car phone

1. Open **RaceChrono Pro** → **Settings → Data sources → Live data**
2. Set **Send live data** to:
   ```
   udp://104.248.151.105:10110
   ```
3. Make sure RaceChrono is actively logging a session (start a session before/with the broadcast) — it only sends live data while a session is running.

### Calibration (one-time, do this at Sepang)

The start/finish line used for lap timing is set in `server/racechrono-server.py` (`SF_LINE`). It ships with placeholder coordinates and **must be calibrated**:

1. Drive across the actual start/finish line.
2. Check `http://104.248.151.105/telemetry` for your live `lat`/`lon`.
3. Update `SF_LINE` in `server/racechrono-server.py` with two (lat, lon) points spanning the track width at that line.
4. Redeploy (see Server section below).

### Race day

- Nothing extra to do — once RaceChrono is sending live data, the dashboard's **RaceChrono Telemetry** panel updates automatically (speed, heading, position, fix status) and logs a lap each time the car crosses the start/finish line.

---

## Server

**Already running.** nginx auto-starts on boot. Nothing to do between events.

**Server IP:** `104.248.151.105` (DigitalOcean Singapore SG1)

### First-time setup (already done — for reference)

```bash
# On a fresh Ubuntu 22.04 DigitalOcean droplet, as root:
git clone https://github.com/ShawnseelanJCC/pit-dashcam.git
cd pit-dashcam
sudo bash scripts/server-setup.sh
```

### Health check (run from any machine)

```bash
bash scripts/health-check.sh 104.248.151.105
```

Output will show nginx status and whether a stream is currently live.

### If you need to SSH in

```bash
ssh root@104.248.151.105

# Check nginx status
systemctl status nginx

# Restart nginx
systemctl restart nginx

# Check HLS segments (confirms stream is being received)
ls /tmp/hls/
```

---

## Pit Wall Network Setup

- Use wired ethernet or strong WiFi at the pit wall — not a mobile hotspot
- Open the dashboard in Chrome, Firefox, or Safari
- Use **http://** not https:// — the stream server is HTTP only

## Car Phone Setup

- Dedicated SIM with data plan (Maxis or Celcom recommended at Sepang)
- Disable WiFi on the car phone — prevents fallback to slow paddock WiFi
- Plug into car 12V USB charger before the session
- Set screen timeout to **Never** (Settings → Display → Screen timeout)
- Disable battery optimisation for Larix (Settings → Battery → App battery usage)

---

## Repository Structure

```
pit-dashcam/
├── dashboard/index.html         ← pit wall browser UI (single file)
├── server/
│   ├── nginx.conf                ← nginx + RTMP config deployed on the server
│   ├── racechrono-server.py      ← RaceChrono UDP telemetry receiver + lap timer
│   └── racechrono-server.service ← systemd unit for the telemetry receiver
├── scripts/
│   ├── server-setup.sh       ← one-time server provisioning
│   └── health-check.sh       ← verify server + stream status
└── docs/hardware.md          ← hardware list, mounting guide, wiring
```
