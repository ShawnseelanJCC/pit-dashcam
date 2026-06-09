# JRT PitCam — Hardware Guide

In-car dashcam hardware list and setup guide for the JRT #518 endurance racing live stream system.

---

## Bill of Materials

| Item | Spec | Notes |
|---|---|---|
| Broadcaster phone | Any Android/iOS with 4G LTE + camera | Dedicated device recommended |
| Phone mount | RAM Mount or Arkon suction/roll-bar clamp | Must withstand vibration and G-forces |
| USB power cable | USB-C or Lightning, 1m, braided | Cheap cables fail under vibration |
| 12V USB charger | 12V cigarette lighter to USB-A/C, 2A+ | Or hardwire to fuse box |
| Dedicated SIM | Data-only plan, no throttling | Maxis/Celcom/U Mobile work at Sepang |
| Optional: wide lens | Clip-on wide-angle lens | Improves cockpit + forward view coverage |

---

## Mounting Position

**Recommended:** Top-centre of windscreen, behind the roll cage bar for protection.

- Angle slightly downward: capture steering wheel, dash, and forward view
- Secure all cables with cable ties — loose cables are a safety hazard
- Route USB power cable away from steering column and gear lever
- Ensure mount does not block driver sightlines

**Alternative:** Dashboard centre, angled up toward windscreen.

---

## Larix Broadcaster Configuration

```
App:            Larix Broadcaster (free, iOS and Android)
Menu:           Connections > New Connection > RTMP
Stream URL:     rtmp://YOUR_SERVER_IP/live/jrt    <- EDIT THIS
Video codec:    H.264
Resolution:     1280x720 (720p)
Framerate:      25fps
Bitrate:        1000-1500 kbps (use 1000 if signal is weak)
Audio:          Disabled
Reconnect:      Enable auto-reconnect, 5s interval
```

To start streaming: open Larix → tap record button → confirm red dot.

---

## SIM / Network Setup

- Use a **dedicated SIM** — do not share a hotspot with crew
- Disable WiFi entirely — prevents fallback to slow paddock WiFi
- Disable VPN if enabled — adds latency
- At Sepang: Maxis and Celcom have strongest 4G coverage
- Test signal from pit lane before session — confirm 4G not 3G

---

## Power Management

- Plug into car **12V USB charger** before session starts
- Set screen timeout to **Never**
- Disable battery optimisation for Larix
- Ensure phone can breathe — streaming generates heat
- Keep brightness low

---

## Pre-Session Checklist

```
[ ] Server running — health-check.sh returns nginx UP
[ ] Phone mounted securely, cables tied and routed safely
[ ] SIM inserted, showing 4G signal
[ ] WiFi disabled on car phone
[ ] Larix RTMP URL: rtmp://YOUR_SERVER_IP/live/jrt
[ ] USB power connected — phone charging
[ ] Screen timeout set to Never
[ ] Start Larix stream — confirm red dot
[ ] Run health-check.sh — confirm STREAM LIVE
[ ] Pit wall dashboard open — CONNECT — video playing
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Stream not in dashboard | Is Larix red dot showing? Run health-check.sh |
| Video freezes mid-race | 4G dead zone — hls.js auto-recovers in 5–10s |
| Larix disconnects repeatedly | Signal weak — try 750kbps bitrate |
| Phone overheating | Remove from enclosed mount, lower bitrate |
| No 4G at circuit | Check APN settings, try different carrier |
