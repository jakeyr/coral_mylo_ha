import logging
from homeassistant.helpers.entity import Entity
from .utils import discover_device_id_from_statsd, read_gauges_from_statsd
from .const import CONF_IP_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data[CONF_IP_ADDRESS]
    device_id = await hass.async_add_executor_job(discover_device_id_from_statsd, ip)
    if not device_id:
        _LOGGER.error("Could not discover device ID for sensors")
        return

    metrics = [
        ("water.temperature", "Water Temperature", "°C"),
        ("water.level", "Water Level", "cm"),
        ("weather.wind_kph", "Wind Speed", "km/h"),
        ("weather.aq_pm2_5", "Air Quality PM2.5", "µg/m³"),
    ]

    sensors = [
        MyloSensor(ip, device_id, m, n, u) for m, n, u in metrics
    ]
    async_add_entities(sensors, update_before_add=True)

class MyloSensor(Entity):
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
        full_key = f"coral.{self._device_id}.{self._metric}"
        gauges = await self.hass.async_add_executor_job(read_gauges_from_statsd, self._ip)
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
