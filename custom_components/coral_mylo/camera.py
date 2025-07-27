"""MYLO camera entity implementation."""

import logging
from homeassistant.components.camera import Camera
from .utils import (
    discover_device_id_from_statsd,
    download_latest_snapshot,
)
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval
from .const import (
    CONF_IP_ADDRESS,
    CONF_REFRESH_TOKEN,
    CONF_API_KEY,
    DOMAIN,
    DEFAULT_REFRESH_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera entity for a config entry."""
    _LOGGER.debug("Setting up camera for entry %s", entry.entry_id)
    ip = entry.data[CONF_IP_ADDRESS]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        device_id = await hass.async_add_executor_job(
            discover_device_id_from_statsd, ip
        )
        if not device_id:
            _LOGGER.error("Could not discover device ID from StatsD")
            return

    ws = hass.data.get(DOMAIN, {}).get("ws", {}).get(entry.entry_id)

    camera = MyloCamera(ip, refresh_token, api_key, device_id, ws)
    async_add_entities([camera])
    _LOGGER.debug("Camera entity created for MYLO %s", device_id)

    hass.data.setdefault(DOMAIN, {}).setdefault("cameras", {})[entry.entry_id] = camera

    if ws:

        async def _update(_):
            """Callback invoked when a new image is ready."""
            _LOGGER.debug("Image ready notification received from MYLO %s", device_id)
            image = await download_latest_snapshot(device_id, refresh_token, api_key)
            camera.update_image(image)

        ws.register_sensor(f"/pooldevices/{device_id}/imgready", _update)


class MyloCamera(Camera):
    """Camera entity that serves the latest snapshot from MYLO."""

    def __init__(self, ip, refresh_token, api_key, device_id, ws):
        super().__init__()
        self._ip = ip
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._ws = ws
        self._refresh_interval = DEFAULT_REFRESH_INTERVAL
        self._unsub = None
        self._image = None

        self._attr_name = f"Mylo Camera {device_id}"
        self._attr_unique_id = f"mylo_camera_{device_id}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    async def async_added_to_hass(self):
        """Handle entity added to hass and start refresh task."""
        await super().async_added_to_hass()
        await self._start_timer()

    async def async_will_remove_from_hass(self):
        """Clean up refresh task when entity is removed."""
        if self._unsub:
            self._unsub()
        await super().async_will_remove_from_hass()

    async def _start_timer(self):
        """(Re)start the periodic refresh timer."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._refresh_interval > 0:
            self._unsub = async_track_time_interval(
                self.hass,
                self._scheduled_refresh,
                timedelta(seconds=self._refresh_interval),
            )

    async def set_refresh_interval(self, interval: int) -> None:
        """Update refresh interval and restart timer."""
        self._refresh_interval = interval
        if self.hass:
            await self._start_timer()

    async def _scheduled_refresh(self, now):
        """Refresh the camera image on a timer."""
        if not self._ws:
            _LOGGER.error("WebSocket not available for MYLO refresh")
            return
        success = await self._ws.send_getimage()
        if not success:
            _LOGGER.error("MYLO did not report new image ready")
            return
        image = await download_latest_snapshot(
            self._device_id, self._refresh_token, self._api_key
        )
        self.update_image(image)

    async def async_camera_image(self, **kwargs):
        """Return image from MYLO, downloading if necessary."""
        if self._image is None:
            _LOGGER.debug("Fetching initial snapshot for MYLO %s", self._device_id)
            self._image = await download_latest_snapshot(
                self._device_id, self._refresh_token, self._api_key
            )
        return self._image

    def update_image(self, image: bytes | None) -> None:
        """Update cached image and notify Home Assistant."""
        if image:
            _LOGGER.debug("Updating cached image for MYLO %s", self._device_id)
            self._image = image
            if self.hass:
                self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"refresh_interval": self._refresh_interval}
