# Coral Mylo Home Assistant Integration

Integrate your **Coral MYLO Pool Camera** with Home Assistant. The integration exposes the latest pool snapshot as a camera entity and provides live sensors sourced from a mix of the device's StatsD service and Firebase WebSocket updates.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jakeyr&repository=coral_mylo_ha&category=integration)

## Features
- **Camera** entity displaying the most recent MYLO image
- **Button** to capture a fresh snapshot via Firebase
- **Sensors** for pool, weather, and system statistics collected from StatsD and real-time WebSocket updates:
  - Water temperature (`°C`)
  - Water level (`cm`)
  - Water pressure (`mbar`)
  - Water cloudiness (`%`)
  - Wind speed (`km/h`)
  - Air quality PM2.5 (`µg/m³`)
  - Air quality PM10 (`µg/m³`)
  - Precipitation (`mm`)
  - Visibility (`km`)
  - Atmospheric pressure (`mbar`)
  - Darkness (`%`)
  - Alert level
  - Pool used count
  - Robot count
  - StatsD timestamp lag (`s`)
  - Cloudiness (`%`)
  - Pool status
  - Battery level
  - System ping
  - CPU temperature (`°C`)
  - GPU temperature (`°C`)
  - Memory usage (`%` used with attributes)
  - Update status
  - Last off notification (date)
- **Binary sensors** for device health and log events (person detected in pool or near the pool)
- **Events**: each device log entry is emitted on the Home Assistant bus as `coral_mylo_log`

## Requirements
- A running Home Assistant instance (Core or OS)
- Coral MYLO on the same network as Home Assistant
- A computer capable of running **mitmproxy**. The MYLO mobile app hides its authentication tokens, so mitmproxy is needed to intercept them for initial setup.

## Installation

### Via HACS (Recommended)
1. Open [HACS](https://hacs.xyz/) in Home Assistant.
2. From the **Integrations** tab, open the overflow menu (**⋮**) and select **Custom repositories**.
3. Enter `https://github.com/jakeyr/coral_mylo_ha` as the repository URL and choose **Integration**.
4. Click **Add**. The repository now appears under integrations.
5. Select **Coral Mylo Integration** and click **Download** to install it.

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

### Via the UI (Recommended)
1. In Home Assistant, navigate to **Settings → Devices & Services → Add Integration**.
2. Select **Coral Mylo**.
3. Provide:
   - **IP Address** of your MYLO (for example `192.168.1.42`)
   - **API Key** captured from mitmproxy
   - **Refresh Token** captured from mitmproxy
4. Submit the form. The integration queries the MYLO's StatsD service to discover the device ID and then creates the camera and sensor entities.

### Manual Addition
Instead of using the Home Assistant config flow, you can define the connection manually in `configuration.yaml`:

```yaml
coral_mylo:
  ip: 192.168.1.42
  api_key: !secret mylo_api_key
  refresh_token: !secret mylo_refresh_token
```

Add your actual credentials to `secrets.yaml` in the same directory:

```yaml
mylo_api_key: YOUR_API_KEY
mylo_refresh_token: YOUR_REFRESH_TOKEN
```

Save both files and restart Home Assistant.

The integration automatically creates `number.mylo_refresh_interval` with a default of 300 seconds. Adjust this value to change how often snapshots refresh.

## Entities Created
- `camera.mylo_camera_<id>` – shows the most recent snapshot taken by the MYLO.
- `button.mylo_refresh_image` – capture a new snapshot on demand.
- `sensor.mylo_water_temperature` – pool water temperature.
- `sensor.mylo_water_level` – measured distance from camera to water surface.
- `sensor.mylo_water_pressure` – water pressure.
- `sensor.mylo_water_cloudiness` – water cloudiness percentage.
- `sensor.mylo_wind_speed` – outdoor wind speed near the pool.
- `sensor.mylo_air_quality_pm2_5` – particulate matter reading (PM2.5).
- `sensor.mylo_air_quality_pm10` – particulate matter reading (PM10).
- `sensor.mylo_precipitation` – recent precipitation.
- `sensor.mylo_visibility` – visibility distance.
- `sensor.mylo_atmospheric_pressure` – atmospheric pressure.
- `sensor.mylo_darkness` – ambient darkness level.
- `sensor.mylo_alert_level` – current alert level.
- `sensor.mylo_pool_used_count` – number of times the pool was used.
- `sensor.mylo_robot_count` – number of robot activations.
- `sensor.mylo_statsd_timestamp_lag` – lag between MYLO and StatsD timestamps.
- `sensor.mylo_cloudiness` – cloudiness percentage.
- `sensor.mylo_pool_status` – current pool status.
- `sensor.mylo_battery` – MYLO battery level.
- `sensor.mylo_system_ping` – last system ping timestamp.
- `sensor.mylo_cpu_temperature` – CPU temperature.
- `sensor.mylo_gpu_temperature` – GPU temperature.
- `sensor.mylo_memory_usage` – percent of memory used with extra attributes.
- `sensor.mylo_update_status` – current update status.
- `sensor.mylo_last_off_notification` – date the device last reported being off.
- `binary_sensor.mylo_health` – overall device health.
- `binary_sensor.mylo_person_detected_in_pool` – turns on briefly when a person is detected in the pool.
- `binary_sensor.mylo_someone_detected_near_pool` – turns on briefly when someone is detected near the pool.
- `number.mylo_refresh_interval` – how often to automatically refresh snapshots (defaults to 300 seconds).

The device ID becomes part of each entity's unique ID, ensuring separate MYLO units are differentiated if you add more than one.

### Testing the Refresh Button
1. In Home Assistant open the **Overview** dashboard.
2. Locate `button.mylo_refresh_image` and press it.
3. The camera entity updates once the device reports the new snapshot is ready.
   It also refreshes periodically based on `number.mylo_refresh_interval`.

## How It Works
1. The integration connects to the MYLO's StatsD admin port (`8126`) to read gauge values. This also reveals the internal device ID used to construct camera and sensor entity IDs.
2. When a camera image is requested, the integration refreshes the short‑lived JWT using your refresh token and API key via Google's SecureToken service.
3. With the JWT, it queries Firebase for a one‑time download token associated with `images/coral_<device_id>_last.jpg`.
4. The final URL containing this token returns the latest snapshot, which Home Assistant exposes as the camera image.

The integration maintains a persistent Firebase WebSocket connection. Image refresh commands, including the periodic updates controlled by `number.mylo_refresh_interval`, and real-time sensor updates flow through this socket. Traditional StatsD polling is still used for metrics not provided over the WebSocket.

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
3. Install the pre-commit hooks so linting runs automatically:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Disclaimer
This is an **unofficial** integration not endorsed by Coral Smart Pool. Use at your own risk.
