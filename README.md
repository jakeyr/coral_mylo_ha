# Coral Mylo Home Assistant Integration

Bring your **Coral MYLO Pool Camera** (SmartPool MYLO) into Home Assistant with a live camera feed and local sensors.

## Features
- Live camera entity in HA
- Pool and weather sensors from the device’s local StatsD interface

## Requirements
- Home Assistant (core or OS)
- Coral MYLO device on the same LAN
- A computer that can run *mitmproxy*

## Installation
1. Copy the `custom_components/coral_mylo` folder into `<config>/custom_components/`.
2. Restart Home Assistant.

## Setup

### 1. Discover the MYLO’s IP
   Find it in your router or scan your subnet:  

```
nmap -sn 192.168.1.0/24
```

### 2. Capture **API Key** and **Refresh Token** with *mitmproxy*
Why?  Home Assistant needs these two values to fetch a short‑lived JWT that unlocks the image.

1. **Install mitmproxy**  
   ```
   brew install mitmproxy
   ```
2. **Run mitmproxy** (default port `8080`):  
   ```
   mitmproxy
   ```
3. **Set your phone’s Wi‑Fi proxy** to your computer’s IP, port `8080`.
4. **Install the mitmproxy certificate** on the phone.  
   Open `http://mitm.it` → follow your OS instructions.
5. **Launch the MYLO app** and log in.  Traffic will appear in mitmproxy.
6. **Watch for requests**  
   - `securetoken.googleapis.com/v1/token?key=YOUR_API_KEY` → copy the `key=` value.  
   - In the POST body you will see `"refresh_token":"YOUR_REFRESH_TOKEN"` → copy that string.
7. Save both the **API Key** and **Refresh Token**.

### 3. Add the integration in Home Assistant
1. *Settings → Devices & Services → Add Integration*  
2. Choose **Coral Mylo**.  
3. Enter:
   - **IP Address** (e.g. `192.168.1.42`)
   - **API Key**  
   - **Refresh Token**
4. Submit.  HA discovers the device‑ID via StatsD and creates the camera + sensors.

### 4. Finished
- `camera.mylo_camera_<id>` now shows the latest snapshot.  
- Sensors such as water temperature, water level, wind kph, PM2‑5 appear.

## Troubleshooting
- **Camera unavailable** → wrong API key or stale refresh token.  
- **No sensors** → StatsD port `8126` blocked; ensure MYLO and HA are on the same subnet.  
- Check *Settings → System → Logs* for `custom_components.coral_mylo`.

## Security
- API Key and Refresh Token are stored in `.storage/core.config_entries` (not plaintext YAML).  
- Anyone with file‑system access to Home Assistant could read them.

## How It Works
1. TCP StatsD admin (`8126`) returns gauges → extract device‑ID & live metrics.  
2. Refresh Token + API Key → Google SecureToken → 1‑hour JWT.  
3. JWT → Firebase metadata → one‑time `downloadTokens` value.  
4. Final URL `.../images/coral_<id>_last.jpg?token=...` returns the snapshot.

## Disclaimer
This is an **unofficial** integration, not endorsed by Coral Smart Pool.  Use at your own risk.

PRs and issues welcome!

