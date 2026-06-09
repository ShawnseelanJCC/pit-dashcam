# JRT PitCam — Claude Code Project

**Janes Racing Team | Endurance Racing Live Stream System**

A phone-to-browser live video streaming system for endurance racing. A phone mounted in the race car streams live footage over 4G cellular to a pit wall dashboard viewed in any browser. Built and maintained using Claude Code.

---

## Project Overview

### What This Is
A self-hosted live streaming pipeline where:
- A **broadcaster phone** in the car runs Larix Broadcaster (external app), pushing an RTMP stream over 4G
- A **Linux server** (DigitalOcean Singapore) receives the RTMP stream and converts it to HLS
- A **pit wall browser** opens the dashboard HTML and watches the HLS feed in near real-time

### What This Is Not
- Not dependent on circuit WiFi (runs entirely over 4G cellular)

---

## Repository Structure

```
pitcam/
├── CLAUDE.md
├── server/
│   └── nginx.conf
├── dashboard/
│   └── index.html
├── scripts/
│   ├── server-setup.sh
│   └── health-check.sh
└── docs/
    └── hardware.md
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Broadcaster | Larix Broadcaster (iOS/Android) | External app, no code required |
| Transport | RTMP over 4G cellular | Phone → server |
| Server | Nginx + nginx-rtmp-module | Ubuntu 22.04, DigitalOcean Singapore |
| Playback format | HLS (.m3u8 + .ts segments) | Browser-native, no plugins |
| HLS player | hls.js (CDN) | Handles browsers without native HLS |
| Dashboard | Vanilla HTML/CSS/JS, single file | No build step, no framework |
| Fonts | Google Fonts (Barlow Condensed, Share Tech Mono) | Racing aesthetic |

---

## System Architecture

```
[RACE CAR]
  Broadcaster Phone
  └─ Larix Broadcaster app
     └─ RTMP stream @ 1000kbps, 720p25
        └─ Phone 4G cellular
           │
           ▼ rtmp://SERVER_IP:1935/live/jrt
           │
[SERVER — DigitalOcean Singapore SG1]
  Nginx + nginx-rtmp-module
  ├─ Receives RTMP on port 1935
  ├─ Slices into 0.5s HLS segments → /tmp/hls/
  └─ Serves HLS on port 8080
     │
     ▼ http://SERVER_IP:8080/live/jrt.m3u8
     │
[PIT WALL]
  Browser (Chrome/Firefox/Safari)
  └─ dashboard/index.html
     └─ hls.js polls .m3u8, pulls .ts segments, plays video
```

---

## Latency Characteristics

| Stage | Typical Delay |
|---|---|
| Phone encode (Larix) | ~0.2s |
| 4G upload (car → server) | ~0.3–0.8s |
| Nginx HLS slicing | ~0.5s (= hls_fragment size) |
| HLS playlist poll interval | ~0.5s |
| hls.js buffer | ~1s |
| **Total end-to-end** | **~2–3 seconds** |

---

## Server Configuration

### Target
- **Provider:** DigitalOcean
- **Region:** Singapore (SG1) — closest to Sepang International Circuit
- **Droplet:** Basic, 1 vCPU, 1GB RAM, 25GB SSD
- **OS:** Ubuntu 22.04 LTS
- **Cost:** ~USD $6/month (~RM27/month)

### Required Open Ports
| Port | Protocol | Purpose |
|---|---|---|
| 22 | TCP | SSH access |
| 80 | TCP | HTTP (optional, health check) |
| 1935 | TCP | RTMP — receives stream from phone |
| 8080 | TCP | HTTP — serves HLS to pit wall browser |

### Key nginx.conf Parameters
- `hls_fragment 0.5s` — 0.5-second HLS segments for low latency (~2–3s end-to-end)
- `hls_playlist_length 3s` — 3-second rolling buffer
- `record off` — no disk recording
- `add_header Access-Control-Allow-Origin *` — required for browser HLS.js access

---

## Configuration

| File | Variable | Description |
|---|---|---|
| `server/nginx.conf` | `hls_fragment` | HLS segment length in seconds |
| `dashboard/index.html` | `DEFAULT_STREAM_URL` | Pre-fills stream URL input |
| `dashboard/index.html` | `LAPS_PER_FUEL` | Fuel burn rate (12 = JRT DC5 default) |
| `dashboard/index.html` | `DRIVERS` | Array of driver names |

---

## Larix Broadcaster Setup

```
App:        Larix Broadcaster (free, iOS + Android)
URL:        rtmp://YOUR_SERVER_IP/live/jrt
Resolution: 1280x720
Framerate:  25fps
Bitrate:    1000–1500 kbps
Audio:      Disabled
```

---

## Race Weekend Quick Reference

**Car phone:** Open Larix → tap record → confirm red dot  
**Pit wall:** Open dashboard → enter `http://SERVER_IP:8080/live/jrt.m3u8` → CONNECT  
**If stream drops:** Wait 10s — hls.js auto-recovers. If not, tap CONNECT again.  
**Fuel critical:** Dashboard flashes red at ≤15% — call BOX BOX  
**Driver change:** Click driver name in stint panel — resets stint timer  

---

## Deployment Checklist

```
[ ] DigitalOcean droplet created (Singapore, Ubuntu 22.04)
[ ] server-setup.sh run successfully
[ ] Ports 1935 and 8080 open in UFW and DigitalOcean firewall
[ ] nginx status: active (running)
[ ] Larix RTMP URL configured: rtmp://SERVER_IP/live/jrt
[ ] Test stream — confirm .m3u8 returns 200
[ ] dashboard/index.html opened in pit wall browser
[ ] Stream URL entered and CONNECT pressed
[ ] Video confirmed live end-to-end
[ ] Phone plugged into car charger
[ ] Phone screen timeout set to Never
[ ] Dedicated SIM in phone
```
