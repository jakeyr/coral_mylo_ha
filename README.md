# Coral Mylo Home Assistant Integration

Integrate your **Coral MYLO Pool Camera** (also known as SmartPool MYLO) with Home Assistant. The integration exposes the latest pool snapshot as a camera entity and provides several live sensors from the device's StatsD interface.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jakeyr&repository=coral_mylo_ha&category=integration)

## Features
- **Camera** entity displaying the most recent MYLO image
- **Sensors** for key pool and weather values collected by MYLO:
  - Water temperature (`°C`)
  - Water level (`cm`)
  - Wind speed (`km/h`)
  - Air quality PM2.5 (`µg/m³`)

## Requirements
- A running Home Assistant instance (Core or OS)
- Coral MYLO on the same network as Home Assistant
- A computer capable of running **mitmproxy**. The MYLO mobile app hides its authentication tokens, so mitmproxy is needed to intercept them for initial setup.

## Installation

### Via HACS
1. Open [HACS](https://hacs.xyz/) in Home Assistant.
2. Choose **Integrations → + Explore & Download Repositories**.
3. Search for **Coral Mylo Integration** and install.

### Manual
1. Copy the `custom_components/coral_mylo` folder from this repository to `<config>/custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant.

## Obtaining the API Credentials
The MYLO app authenticates via Apple ID and never exposes the required tokens. To allow Home Assistant to fetch images you must capture the **API Key** and **Refresh Token** once using mitmproxy.

1. Install mitmproxy:
   ```bash
   brew install mitmproxy
   ```
2. Run mitmproxy (default port `8080`):
   ```bash
   mitmproxy
   ```
3. On your phone, set the Wi-Fi proxy to the IP of the computer running mitmproxy, port `8080`.
4. Open `http://mitm.it` on the phone and install the certificate as instructed.
5. Launch the MYLO mobile app and log in. Requests will appear in mitmproxy.
6. Look for a request to `securetoken.googleapis.com/v1/token?key=...` and copy the value of `key=` (this is your **API Key**).
7. The POST body of the same request contains a `refresh_token` field. Copy this string as your **Refresh Token**.

These two values will be entered when adding the integration.

## Adding the Integration
1. In Home Assistant, navigate to **Settings → Devices & Services → Add Integration**.
2. Select **Coral Mylo**.
3. Provide:
   - **IP Address** of your MYLO (for example `192.168.1.42`)
   - **API Key** captured from mitmproxy
   - **Refresh Token** captured from mitmproxy
4. Submit the form. The integration queries the MYLO's StatsD service to discover the device ID and then creates the camera and sensor entities.

## Entities Created
- `camera.mylo_camera_<id>` – shows the most recent snapshot taken by the MYLO.
- `sensor.mylo_water_temperature` – pool water temperature.
- `sensor.mylo_water_level` – measured distance from camera to water surface.
- `sensor.mylo_wind_speed` – outdoor wind speed near the pool.
- `sensor.mylo_air_quality_pm2_5` – particulate matter reading (PM2.5).

The device ID becomes part of each entity's unique ID, ensuring separate MYLO units are differentiated if you add more than one.

## How It Works
1. The integration connects to the MYLO's StatsD admin port (`8126`) to read gauge values. This also reveals the internal device ID used to construct camera and sensor entity IDs.
2. When a camera image is requested, the integration refreshes the short‑lived JWT using your refresh token and API key via Google's SecureToken service.
3. With the JWT, it queries Firebase for a one‑time download token associated with `images/coral_<device_id>_last.jpg`.
4. The final URL containing this token returns the latest snapshot, which Home Assistant exposes as the camera image.

Sensor updates are fetched from StatsD on demand; each update polls MYLO for the latest gauges and extracts the relevant metrics.

## Troubleshooting
- **Camera unavailable** – ensure the API key is correct and the refresh token is still valid.
- **No sensors** – check that port `8126` on the MYLO is reachable from Home Assistant and that both are on the same network.
- Review the log under **Settings → System → Logs** and filter for `custom_components.coral_mylo` for details.

## Security
- The API key and refresh token are stored in Home Assistant's `.storage/core.config_entries` file rather than in plain YAML.
- Anyone with direct file-system access to Home Assistant can read these tokens, so restrict access to your installation.

## Development
Pull requests and issues are very welcome! To run the unit tests:

1. Install the test requirements:
   ```bash
   pip install -r requirements-test.txt
   ```
2. Run the tests from the repository root:
   ```bash
   pytest -q
   ```

## Disclaimer
This is an **unofficial** integration not endorsed by Coral Smart Pool. Use at your own risk.
