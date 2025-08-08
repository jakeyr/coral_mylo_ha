"""MYLO camera entity implementation."""

import logging
from homeassistant.components.camera import Camera
from .utils import (
    discover_device_id_from_statsd,
    download_latest_snapshot,
)
from .const import CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera entity for a config entry."""
    _LOGGER.debug("Setting up camera for entry %s", entry.entry_id)
    ip = entry.data[CONF_IP_ADDRESS]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        try:
            device_id = await hass.async_add_executor_job(
                discover_device_id_from_statsd, ip
            )
            if not device_id:
                _LOGGER.error("Could not discover device ID from StatsD")
                return
            # Cache the discovered device ID
            hass.data.setdefault(DOMAIN, {}).setdefault("device_ids", {})[
                entry.entry_id
            ] = device_id
        except Exception as e:
            _LOGGER.error("Error discovering device ID: %s", e)
            return

    ws = hass.data.get(DOMAIN, {}).get("ws", {}).get(entry.entry_id)

    camera = MyloCamera(ip, refresh_token, api_key, device_id)
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

    def __init__(self, ip, refresh_token, api_key, device_id):
        super().__init__()
        self._ip = ip
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._image = None

        self._attr_name = f"Mylo Camera {device_id}"
        self._attr_unique_id = f"mylo_camera_{device_id}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

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
