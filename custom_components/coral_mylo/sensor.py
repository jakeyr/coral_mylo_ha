"""Sensor entities for MYLO."""

from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)

from .utils import (
    discover_device_id_from_statsd,
    read_gauges_from_statsd,
    MyloWebsocketClient,
    parse_memory_usage,
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
        (
            "water.temperature",
            "Water Temperature",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        ),
        (
            "water.level",
            "Water Level",
            UnitOfLength.CENTIMETERS,
            SensorDeviceClass.DISTANCE,
        ),
        (
            "water.pressure_sensor",
            "Water Pressure",
            UnitOfPressure.MBAR,
            SensorDeviceClass.PRESSURE,
        ),
        (
            "water.cloudiness",
            "Water Cloudiness",
            PERCENTAGE,
            None,
        ),
        (
            "weather.wind_kph",
            "Wind Speed",
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            SensorDeviceClass.WIND_SPEED,
        ),
        (
            "weather.aq_pm2_5",
            "Air Quality PM2.5",
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            SensorDeviceClass.PM25,
        ),
        (
            "weather.aq_pm10",
            "Air Quality PM10",
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            SensorDeviceClass.PM10,
        ),
        (
            "weather.precip_mm.count",
            "Precipitation",
            UnitOfLength.MILLIMETERS,
            SensorDeviceClass.PRECIPITATION,
        ),
        (
            "weather.vis_km",
            "Visibility",
            UnitOfLength.KILOMETERS,
            SensorDeviceClass.DISTANCE,
        ),
        (
            "weather.pressure_mb",
            "Atmospheric Pressure",
            UnitOfPressure.MBAR,
            SensorDeviceClass.PRESSURE,
        ),
        (
            "darkness",
            "Darkness",
            PERCENTAGE,
            None,
        ),
        (
            "manager.alert_level",
            "Alert Level",
            None,
            None,
        ),
        (
            "pool.used.count",
            "Pool Used Count",
            None,
            None,
        ),
        (
            "robot.count",
            "Robot Count",
            None,
            None,
        ),
        (
            "statsd.timestamp_lag",
            "StatsD Timestamp Lag",
            UnitOfTime.SECONDS,
            SensorDeviceClass.DURATION,
        ),
    ]

    sensors = [MyloSensor(ip, device_id, m, n, u, dc) for m, n, u, dc in metrics]
    realtime = []
    if ws:
        realtime_specs = [
            ("status/cloudiness", "Cloudiness", PERCENTAGE, None),
            ("status/pool_status", "Pool Status", None, None),
            (
                "status/battery",
                "Battery",
                PERCENTAGE,
                SensorDeviceClass.BATTERY,
            ),
            ("status/system_ping", "System Ping", None, None),
            (
                "status/temperature/cpu",
                "CPU Temperature",
                UnitOfTemperature.CELSIUS,
                SensorDeviceClass.TEMPERATURE,
            ),
            (
                "status/temperature/gpu",
                "GPU Temperature",
                UnitOfTemperature.CELSIUS,
                SensorDeviceClass.TEMPERATURE,
            ),
            ("status/memory", "Memory Usage", None, None),
            ("status/balena_update/status", "Update Status", None, None),
            (
                "monitoring/last_off_notification",
                "Last Off Notification",
                None,
                SensorDeviceClass.DATE,
            ),
        ]
        for path, name, unit, device_class in realtime_specs:
            full_path = f"/pooldevices/{device_id}/{path}"
            ent = MyloRealtimeSensor(device_id, name, full_path, ws, unit, device_class)
            realtime.append(ent)
            ws.register_sensor(full_path, ent.update_from_ws)
            _LOGGER.debug("Registered realtime sensor for %s", full_path)

    async_add_entities(sensors + realtime, update_before_add=True)


class MyloSensor(SensorEntity):
    """Sensor that polls values from the MYLO StatsD service."""

    def __init__(self, ip, device_id, metric, name, unit, device_class=None):
        """Initialize the MYLO sensor."""
        self._ip = ip
        self._device_id = device_id
        self._metric = metric
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
        self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class

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
            _LOGGER.warning("No data found for metric %s", full_key)

    @property
    def native_value(self):
        """Return the current value of the sensor."""
        return self._state


class MyloRealtimeSensor(SensorEntity):
    """Sensor updated from Firebase websocket."""

    def __init__(
        self,
        device_id,
        name,
        path,
        ws: MyloWebsocketClient,
        unit=None,
        device_class=None,
    ):
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
            self._attr_native_unit_of_measurement = unit
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
        if isinstance(value, str) and self._path.endswith("/status/memory"):
            parsed = parse_memory_usage(value)
            if parsed:
                self._state = parsed["used_percent"]
                self._attr_extra_state_attributes = {
                    "available_mb": parsed["available_mb"],
                    "swap_percent": parsed["swap_percent"],
                }
            else:
                self._state = value
        elif isinstance(value, dict):
            if "status" in value:
                self._state = value["status"]
            elif "level" in value:
                self._state = value["level"]
            else:
                self._state = next(iter(value.values()), None)
        else:
            self._state = value

        if isinstance(self._state, str) and self.device_class == SensorDeviceClass.DATE:
            try:
                self._state = datetime.fromisoformat(self._state).date()
            except ValueError:
                _LOGGER.warning(
                    "Invalid date format for %s: %s", self._path, self._state
                )
                self._state = None

        if getattr(self, "hass", None):
            self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the current value of the sensor."""
        return self._state
