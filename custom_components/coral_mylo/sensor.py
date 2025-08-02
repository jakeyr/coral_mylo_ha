"""Sensor entities for MYLO."""

import logging
from homeassistant.helpers.entity import Entity
from .utils import (
    discover_device_id_from_statsd,
    read_gauges_from_statsd,
    MyloWebsocketClient,
)
from .const import CONF_IP_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MYLO sensors for a config entry."""
    _LOGGER.debug("Setting up sensors for entry %s", entry.entry_id)
    ip = entry.data[CONF_IP_ADDRESS]
    # Retrieve cached device id when available
    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        device_id = await hass.async_add_executor_job(
            discover_device_id_from_statsd, ip
        )
        if not device_id:
            _LOGGER.error("Could not discover device ID for sensors")
            return

    ws = hass.data.get(DOMAIN, {}).get("ws", {}).get(entry.entry_id)

    metrics = [
        ("water.temperature", "Water Temperature", "°C"),
        ("water.level", "Water Level", "cm"),
        ("weather.wind_kph", "Wind Speed", "km/h"),
        ("weather.aq_pm2_5", "Air Quality PM2.5", "µg/m³"),
    ]

    sensors = [MyloSensor(ip, device_id, m, n, u) for m, n, u in metrics]
    realtime = []
    if ws:
        realtime_specs = [
            ("status/cloudiness", "Cloudiness", None, None),
            ("status/pool_status", "Pool Status", None, None),
            ("status/battery", "Battery", None, None),
            ("status/system_ping", "System Ping", None, None),
            ("status/temperature/cpu", "CPU Temperature", "°C", None),
            ("status/temperature/gpu", "GPU Temperature", "°C", None),
            ("status/memory", "Memory Usage", None, None),
            ("status/balena_update/status", "Update Status", None, None),
            (
                "monitoring/last_off_notification",
                "Last Off Notification",
                None,
                "timestamp",
            ),
        ]
        for path, name, unit, device_class in realtime_specs:
            full_path = f"/pooldevices/{device_id}/{path}"
            ent = MyloRealtimeSensor(device_id, name, full_path, ws, unit, device_class)
            realtime.append(ent)
            ws.register_sensor(full_path, ent.update_from_ws)
            _LOGGER.debug("Registered realtime sensor for %s", full_path)

    async_add_entities(sensors + realtime, update_before_add=True)


class MyloSensor(Entity):
    """Sensor that polls values from the MYLO StatsD service."""

    def __init__(self, ip, device_id, metric, name, unit):
        self._ip = ip
        self._device_id = device_id
        self._metric = metric
        self._name = name
        self._unit = unit
        self._state = None
        self._attr_name = f"Mylo {name}"
        self._attr_unique_id = f"mylo_{device_id}_{metric.replace('.', '_')}"
        self._attr_should_poll = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    async def async_update(self):
        """Fetch latest value from the MYLO StatsD server."""
        full_key = f"coral.{self._device_id}.{self._metric}"
        _LOGGER.debug("Querying gauge %s on %s", full_key, self._ip)
        gauges = await self.hass.async_add_executor_job(
            read_gauges_from_statsd, self._ip
        )
        value = gauges.get(full_key)
        if value is not None:
            self._state = value
        else:
            _LOGGER.warning(f"No data found for metric {full_key}")

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit


class MyloRealtimeSensor(Entity):
    """Sensor updated from Firebase websocket."""

    def __init__(self, device_id, name, path, ws: MyloWebsocketClient, unit=None, device_class=None):
        self._device_id = device_id
        self._name = name
        self._path = path
        self._state = None
        self._ws = ws
        self._attr_name = f"Mylo {name}"
        uid = path.replace("/", "_").strip("_")
        self._attr_unique_id = f"mylo_{uid}"
        self._attr_should_poll = False
        if unit:
            self._attr_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Coral SmartPool",
            "model": "MYLO",
            "name": f"MYLO {device_id}",
        }

    async def update_from_ws(self, value):
        """Update state from websocket push message."""
        _LOGGER.debug("Realtime sensor %s received %s", self._path, value)
        if isinstance(value, dict):
            if "status" in value:
                self._state = value["status"]
            elif "level" in value:
                self._state = value["level"]
            else:
                self._state = next(iter(value.values()), None)
        else:
            self._state = value
        if self.hass:
            self.async_write_ha_state()

    @property
    def state(self):
        return self._state
