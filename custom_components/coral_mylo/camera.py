import logging
import aiohttp
from homeassistant.components.camera import Camera
from .utils import refresh_jwt, discover_device_id_from_statsd, fetch_firebase_download_token
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
        bucket = "coralesto.appspot.com"
        image_path = f"images%2Fcoral_{self._device_id}_last.jpg"
        jwt = await refresh_jwt(self._refresh_token, self._api_key)
        if not jwt:
            _LOGGER.error("Failed to refresh JWT")
            return None

        token = await fetch_firebase_download_token(bucket, image_path, jwt)
        if not token:
            _LOGGER.error("Failed to fetch download token")
            return None

        image_url = (
            f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/"
            f"{image_path}?alt=media&token={token}"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        text = await resp.text()
                        _LOGGER.error(f"Failed to fetch image: {resp.status}, Response: {text}")
        except Exception as e:
            _LOGGER.error(f"Exception fetching camera image: {e}")

        return None
