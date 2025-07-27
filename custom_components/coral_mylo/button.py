"""Button entity to refresh snapshots on the MYLO device."""

import logging
from homeassistant.components.button import ButtonEntity

from .const import CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY, DOMAIN
from .utils import (
    discover_device_id_from_statsd,
    MyloWebsocketClient,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the snapshot refresh button."""

    _LOGGER.debug("Setting up button entry %s", entry.entry_id)
    ip = entry.data[CONF_IP_ADDRESS]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
        if not device_id:
            _LOGGER.error("Could not discover device ID for button")
            return
        _LOGGER.debug("Discovered device id %s for button", device_id)

    ws = hass.data.get(DOMAIN, {}).get("ws", {}).get(entry.entry_id)
    camera = hass.data.get(DOMAIN, {}).get("cameras", {}).get(entry.entry_id)

    async_add_entities([
        MyloSnapshotRefreshButton(refresh_token, api_key, device_id, camera, ws)
    ])


class MyloSnapshotRefreshButton(ButtonEntity):
    """Button to trigger MYLO to capture a new snapshot."""

    def __init__(self, refresh_token, api_key, device_id, camera, ws):
        """Initialize button entity."""

        self._refresh_token = refresh_token
        self._api_key = api_key
        self._device_id = device_id
        self._camera = camera
        self._ws = ws
        self._attr_name = "Refresh MYLO Image"
        self._attr_unique_id = f"mylo_refresh_image_{device_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._refresh_snapshot()

    async def _refresh_snapshot(self):
        """Send request to MYLO to fetch a new image."""
        if not self._ws:
            _LOGGER.error("WebSocket not available for MYLO refresh")
            return

        _LOGGER.debug("Requesting new snapshot from MYLO %s", self._device_id)
        success = await self._ws.send_getimage()
        if not success:
            _LOGGER.error("MYLO did not report new image ready")
            return
        _LOGGER.debug("Snapshot refresh command acknowledged for %s", self._device_id)

