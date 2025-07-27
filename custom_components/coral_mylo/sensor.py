"""Sensor platform for the Coral Mylo integration."""

import logging
from homeassistant.helpers.entity import Entity
from .utils import discover_device_id_from_statsd, read_gauges_from_statsd, MyloWebsocketClient
from .const import CONF_IP_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities from a config entry."""

    _LOGGER.debug("Setting up sensors for entry %s", entry.entry_id)

    ip = entry.data[CONF_IP_ADDRESS]
    device_id = hass.data.get(DOMAIN, {}).get("device_ids", {}).get(entry.entry_id)
    if not device_id:
        device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
        if not device_id:
            _LOGGER.error("Could not discover device ID for sensors")
            return
        _LOGGER.debug("Discovered device id %s for sensors", device_id)

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
        _LOGGER.debug("Registering realtime sensor callbacks")
        realtime_specs = [
            ("cloudiness", "Cloudiness"),
            ("health", "Health"),
            ("pool_status", "Pool Status"),
            ("battery", "Battery"),
            ("system_ping", "System Ping"),
        ]
        for key, name in realtime_specs:
            path = f"/pooldevices/{device_id}/status/{key}"
            ent = MyloRealtimeSensor(device_id, name, path, ws)
            realtime.append(ent)
            ws.register_sensor(path, ent.update_from_ws)
        _LOGGER.debug("Realtime sensors registered")

    async_add_entities(sensors + realtime, update_before_add=True)

class MyloSensor(Entity):
    """Sensor that polls metrics from the MYLO StatsD interface."""

    def __init__(self, ip, device_id, metric, name, unit):
        """Initialize the sensor."""
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
        """Fetch the latest value from the device."""
        full_key = f"coral.{self._device_id}.{self._metric}"
        gauges = await self.hass.async_add_executor_job(read_gauges_from_statsd, self._ip)
        value = gauges.get(full_key)
        if value is not None:
            self._state = value
            _LOGGER.debug("%s = %s", full_key, value)
        else:
            _LOGGER.warning(f"No data found for metric {full_key}")

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit


class MyloRealtimeSensor(Entity):
    """Sensor updated from Firebase WebSocket messages."""

    def __init__(self, device_id, name, path, ws: MyloWebsocketClient):
        """Initialize realtime sensor."""
        self._device_id = device_id
        self._name = name
        self._path = path
        self._state = None
        self._ws = ws
        self._attr_name = f"Mylo {name}"
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
        """Receive an updated value from the WebSocket."""
        self._state = value
        if self.hass:
            self.async_write_ha_state()
        _LOGGER.debug("Realtime update %s = %s", self._path, value)

    @property
    def state(self):
        return self._state
