import logging
from homeassistant.components.button import ButtonEntity

from .const import CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY
from .utils import (
    download_latest_snapshot,
    discover_device_id_from_statsd,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data[CONF_IP_ADDRESS]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
    if not device_id:
        _LOGGER.error("Could not discover device ID for button")
        return

    async_add_entities([MyloSnapshotRefreshButton(refresh_token, api_key, device_id)])


class MyloSnapshotRefreshButton(ButtonEntity):
    """Button to manually refresh the MYLO snapshot."""

    def __init__(self, refresh_token, api_key, device_id):
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._attr_name = "Refresh MYLO Snapshot"
        self._attr_unique_id = f"mylo_refresh_snapshot_{device_id}"

    async def async_press(self) -> None:
        await self._refresh_snapshot()

    async def _refresh_snapshot(self):
        await download_latest_snapshot(
            self._device_id, self._refresh_token, self._api_key
        )
