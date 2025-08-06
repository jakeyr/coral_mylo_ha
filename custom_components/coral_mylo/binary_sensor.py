"""Binary sensor platform for MYLO."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .utils import discover_device_id_from_statsd
from .const import CONF_IP_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MYLO binary sensors for a config entry."""
    _LOGGER.debug("Setting up binary sensors for entry %s", entry.entry_id)
    ip = entry.data[CONF_IP_ADDRESS]
    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        device_id = await hass.async_add_executor_job(
            discover_device_id_from_statsd, ip
        )
        if not device_id:
            _LOGGER.error("Could not discover device ID for binary sensors")
            return

    ws = hass.data.get(DOMAIN, {}).get("ws", {}).get(entry.entry_id)

    entities: list[BinarySensorEntity] = []

    if ws:
        health_path = f"/pooldevices/{device_id}/status/health"
        health = MyloHealthBinarySensor(device_id, health_path)
        entities.append(health)
        ws.register_sensor(health_path, health.update_from_ws)
        _LOGGER.debug("Registered realtime sensor for %s", health_path)

    async_add_entities(entities)


class MyloHealthBinarySensor(BinarySensorEntity):
    """Device health reported via websocket."""

    def __init__(self, device_id, path):
        self._device_id = device_id
        self._path = path
        self._state = False
        self._attr_name = "Mylo Health"
        uid = path.replace("/", "_").strip("_")
        self._attr_unique_id = f"mylo_{uid}"
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    async def update_from_ws(self, value):
        _LOGGER.debug("Health sensor %s received %s", self._path, value)
        cause = hint = None
        level = 0
        if isinstance(value, dict):
            cause = value.get("cause")
            hint = value.get("hint")
            level = value.get("level", 0)
        self._state = level == 0
        self._attr_extra_state_attributes = {
            "cause": cause,
            "hint": hint,
            "level": level,
        }
        if self.hass:
            self.async_write_ha_state()

    @property
    def is_on(self):
        return self._state
