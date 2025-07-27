"""Coral Mylo integration for Home Assistant."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_REFRESH_TOKEN, CONF_API_KEY
from .utils import discover_device_id_from_statsd, MyloWebsocketClient

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialize the integration when Home Assistant starts."""
    _LOGGER.debug("Initializing Coral Mylo integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coral Mylo from a config entry."""
    _LOGGER.debug("Setting up entry %s", entry.entry_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    ip = entry.data[CONF_IP_ADDRESS]
    refresh = entry.data[CONF_REFRESH_TOKEN]
    api_key = entry.data[CONF_API_KEY]

    # Discover the unique MYLO device id via the StatsD service
    device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
    _LOGGER.debug("Discovered device id %s", device_id)
    if device_id:
        ws = MyloWebsocketClient(hass, device_id, refresh, api_key)
        hass.data[DOMAIN].setdefault("ws", {})[entry.entry_id] = ws
        hass.data[DOMAIN].setdefault("device_ids", {})[entry.entry_id] = device_id
        _LOGGER.debug("Starting websocket for %s", device_id)
        await ws.start()
    else:
        device_id = None

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "camera", "button", "number"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "camera", "button", "number"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if "cameras" in hass.data[DOMAIN]:
            hass.data[DOMAIN]["cameras"].pop(entry.entry_id, None)
        ws = hass.data[DOMAIN].get("ws", {}).pop(entry.entry_id, None)
        if ws:
            device_id = hass.data[DOMAIN].get("device_ids", {}).get(entry.entry_id)
            _LOGGER.debug("Stopping websocket for %s", device_id)
            await ws.stop()
        hass.data[DOMAIN].get("device_ids", {}).pop(entry.entry_id, None)
    return unload_ok
