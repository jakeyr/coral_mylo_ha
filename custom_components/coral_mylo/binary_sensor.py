"""Binary sensors for MYLO."""

import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_call_later
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

        person = MyloLogBinarySensor(
            hass, device_id, "Person Detected in Pool", "person detected in your pool"
        )
        near = MyloLogBinarySensor(
            hass, device_id, "Someone Detected Near Pool", "detected near the pool"
        )
        entities.extend([person, near])

        handler = MyloLogHandler(hass, [person, near])
        log_path = f"/pooldevices/{device_id}/log"
        ws.register_sensor(log_path, handler.handle_log)
        _LOGGER.debug("Registered log watcher for %s", log_path)

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


class MyloLogBinarySensor(BinarySensorEntity):
    """Binary sensor that stays on briefly when a matching log entry appears."""

    def __init__(self, hass, device_id, name, match):
        self._hass = hass
        self._device_id = device_id
        self._match = match.lower()
        self._state = False
        self._turn_off_handle = None
        self._attr_name = f"Mylo {name}"
        uid = f"{device_id}_{name.lower().replace(' ', '_')}"
        self._attr_unique_id = f"mylo_{uid}"
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    def process_entry(self, entry):
        """Update state if the log entry matches our trigger."""
        msg = entry.get("message", "").lower()
        if self._match in msg:
            self._state = True
            if self._turn_off_handle:
                self._turn_off_handle()
            self._turn_off_handle = async_call_later(self._hass, 120, self._turn_off)
            self.async_write_ha_state()

    async def _turn_off(self, _now):
        self._state = False
        self._turn_off_handle = None
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._state


class MyloLogHandler:
    """Handle realtime log updates and dispatch events."""

    def __init__(self, hass, sensors: list[MyloLogBinarySensor]):
        self._hass = hass
        self._sensors = sensors
        self._last_ts = ""

    async def handle_log(self, value):
        """Process incoming log updates from websocket."""
        if isinstance(value, list):
            entries = value
        elif isinstance(value, dict):
            # Firebase may send dict of index to entry
            if all(isinstance(v, dict) for v in value.values()):
                entries = list(value.values())
            else:
                entries = [value]
        else:
            return
        entries.sort(key=lambda e: e.get("timestamp", ""))
        for entry in entries:
            ts = entry.get("timestamp")
            if ts and ts <= self._last_ts:
                continue
            if ts:
                self._last_ts = ts
            self._hass.bus.async_fire(
                "coral_mylo_log",
                {
                    "message": entry.get("message"),
                    "timestamp": entry.get("timestamp"),
                    "has_image": entry.get("has_image"),
                    "state": entry.get("state"),
                    "severity": entry.get("severity"),
                    "privacy_mode": entry.get("privacy_mode"),
                },
            )
            for sensor in self._sensors:
                sensor.process_entry(entry)
