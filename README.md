# JRT PitCam — #518 Endurance Live Stream

Phone-to-browser live video streaming for the JRT #518 endurance racing pit wall. The car phone streams over 4G → DigitalOcean Singapore relay server → pit wall browser dashboard. ~2–3 second end-to-end latency.

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
├── dashboard/index.html      ← pit wall browser UI (single file)
├── server/nginx.conf         ← nginx + RTMP config deployed on the server
├── scripts/
│   ├── server-setup.sh       ← one-time server provisioning
│   └── health-check.sh       ← verify server + stream status
└── docs/hardware.md          ← hardware list, mounting guide, wiring
```
