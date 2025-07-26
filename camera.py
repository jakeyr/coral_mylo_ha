import logging
import aiohttp
from homeassistant.components.camera import Camera
from .utils import refresh_jwt, discover_device_id_from_statsd
from .const import CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    ip = config[CONF_IP_ADDRESS]
    refresh_token = config[CONF_REFRESH_TOKEN]
    api_key = config[CONF_API_KEY]

    device_id = discover_device_id_from_statsd(ip)
    if not device_id:
        _LOGGER.error("Could not discover device ID from StatsD")
        return

    async_add_entities([MyloCamera(ip, refresh_token, api_key, device_id)], update_before_add=True)

class MyloCamera(Camera):
    def __init__(self, ip, refresh_token, api_key, device_id):
        super().__init__()
        self._ip = ip
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._image = None
        self._jwt = None
        self._attr_name = f"Mylo Camera {device_id}"
        self._attr_unique_id = f"mylo_camera_{device_id}"

    async def async_update(self):
        self._jwt = await refresh_jwt(self._refresh_token, self._api_key)
        if not self._jwt:
            _LOGGER.error("Failed to refresh JWT")
            return

        jwt_token = self._jwt["access_token"]
        image_path = f"images/coral_{self._device_id}_last.jpg"
        metadata_url = f"https://firebasestorage.googleapis.com/v0/b/coralesto.appspot.com/o/{image_path.replace('/', '%2F')}"
        headers = {
            "Authorization": f"Firebase {jwt_token}",
            "Accept": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metadata_url, headers=headers) as resp:
                    _LOGGER.debug(f"Metadata fetch response status: {resp.status}")
                    if resp.status != 200:
                        text = await resp.text()
                        _LOGGER.error(f"Failed to fetch metadata: {resp.status}, Response: {text}")
                        return
                    json_data = await resp.json()
                    token = json_data.get("downloadTokens")
                    if not token:
                        _LOGGER.error("No download token found in metadata response")
                        return

                image_url = f"https://firebasestorage.googleapis.com/v0/b/coralesto.appspot.com/o/{image_path.replace('/', '%2F')}?alt=media&token={token}"
                _LOGGER.debug(f"Fetching camera image from URL: {image_url}")

                async with session.get(image_url) as img_resp:
                    _LOGGER.debug(f"Camera image fetch response status: {img_resp.status}")
                    if img_resp.status == 200:
                        self._image = await img_resp.read()
                    else:
                        text = await img_resp.text()
                        _LOGGER.error(f"Failed to fetch image: {img_resp.status}, Response: {text}")

        except Exception as e:
            _LOGGER.error(f"Exception fetching camera image: {e}")

    async def async_camera_image(self):
        return self._image
