import logging
from homeassistant.components.camera import Camera
from .utils import (
    discover_device_id_from_statsd,
    download_latest_snapshot,
)
from .const import CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data[CONF_IP_ADDRESS]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
    if not device_id:
        _LOGGER.error("Could not discover device ID from StatsD")
        return

    async_add_entities([MyloCamera(ip, refresh_token, api_key, device_id)])

class MyloCamera(Camera):
    def __init__(self, ip, refresh_token, api_key, device_id):
        super().__init__()
        self._ip = ip
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._image = None

        self._attr_name = f"Mylo Camera {device_id}"
        self._attr_unique_id = f"mylo_camera_{device_id}"

    async def async_camera_image(self, **kwargs):
        return await download_latest_snapshot(
            self._device_id, self._refresh_token, self._api_key
        )
