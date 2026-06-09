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
- Secure all cables with cable ties
- Route USB power cable away from steering column and gear lever
- Ensure mount does not block driver sightlines

---

## Larix Broadcaster Configuration

```
App:            Larix Broadcaster (free, iOS and Android)
Menu:           Connections > New Connection > RTMP
Stream URL:     rtmp://YOUR_SERVER_IP/live/jrt    <- EDIT THIS
Video codec:    H.264
Resolution:     1280x720 (720p)
Framerate:      25fps
Bitrate:        1000-1500 kbps
Audio:          Disabled
Reconnect:      Enable auto-reconnect, 5s interval
```

---

## SIM / Network Setup

- Dedicated SIM, not a shared hotspot
- Disable WiFi on the phone entirely
- Maxis and Celcom have strongest 4G coverage at Sepang
- Test signal from pit lane before session — confirm 4G not 3G

---

## Power Management

- Plug into car 12V USB charger before session
- Set screen timeout to Never
- Disable battery optimisation for Larix
- Keep brightness low

---

## Pre-Session Checklist

```
[ ] Server running — health-check.sh returns nginx UP
[ ] Phone mounted, cables tied
[ ] SIM inserted, showing 4G
[ ] WiFi disabled
[ ] Larix RTMP URL set correctly
[ ] USB power connected
[ ] Screen timeout: Never
[ ] Start Larix — confirm red dot
[ ] health-check.sh — STREAM LIVE
[ ] Dashboard open — CONNECT — video playing
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Stream not in dashboard | Larix red dot showing? Run health-check.sh |
| Video freezes mid-race | 4G dead zone — hls.js auto-recovers in 5–10s |
| Larix disconnects | Signal weak — try 750kbps |
| Phone overheating | Lower bitrate, ensure ventilation |
| No 4G | Check APN settings, try different carrier |
