"""Set up the Coral Mylo integration within Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

import logging

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY
from .utils import discover_device_id_from_statsd, MyloWebsocketClient


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Coral Mylo via YAML (unused)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle creation of entities from a config entry."""

    _LOGGER.debug("Setting up entry %s", entry.entry_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    ip = entry.data[CONF_IP_ADDRESS]
    refresh = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
    if device_id:
        _LOGGER.debug("Discovered device id %s", device_id)
        ws = MyloWebsocketClient(hass, device_id, refresh, api_key)
        hass.data[DOMAIN].setdefault("ws", {})[entry.entry_id] = ws
        hass.data[DOMAIN].setdefault("device_ids", {})[entry.entry_id] = device_id
        await ws.start()
    else:
        device_id = None

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "camera", "button"])
    _LOGGER.debug("Finished setup for entry %s", entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    _LOGGER.debug("Unloading entry %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "camera", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if "cameras" in hass.data[DOMAIN]:
            hass.data[DOMAIN]["cameras"].pop(entry.entry_id, None)
        ws = hass.data[DOMAIN].get("ws", {}).pop(entry.entry_id, None)
        if ws:
            await ws.stop()
        hass.data[DOMAIN].get("device_ids", {}).pop(entry.entry_id, None)
        _LOGGER.debug("Entry %s unloaded", entry.entry_id)
    return unload_ok
