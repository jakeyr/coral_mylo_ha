"""Tests for the MYLO sensor module."""

import importlib.util
from pathlib import Path
import sys
import types
import asyncio
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


# Stub out Home Assistant modules required for importing the integration
sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))

ha = types.ModuleType("homeassistant")
ha.__path__ = []  # Mark as package
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault(
    "homeassistant.helpers", types.ModuleType("homeassistant.helpers")
)

# Minimal dt utilities
ha_util = types.ModuleType("homeassistant.util")
sys.modules.setdefault("homeassistant.util", ha_util)
helpers_dt = types.ModuleType("homeassistant.util.dt")
helpers_dt.UTC = timezone.utc
helpers_dt.DEFAULT_TIME_ZONE = timezone.utc


def set_default_time_zone(tz):
    helpers_dt.DEFAULT_TIME_ZONE = tz


def get_time_zone(name):
    return ZoneInfo(name)


def parse_datetime(val: str):
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return None


def as_local(dt):
    return dt.astimezone(helpers_dt.DEFAULT_TIME_ZONE)


helpers_dt.set_default_time_zone = set_default_time_zone
helpers_dt.get_time_zone = get_time_zone
helpers_dt.parse_datetime = parse_datetime
helpers_dt.as_local = as_local
sys.modules["homeassistant.util.dt"] = helpers_dt

helpers_entity = types.ModuleType("homeassistant.helpers.entity")


class Entity:  # Minimal base class
    pass


helpers_entity.Entity = Entity
sys.modules["homeassistant.helpers.entity"] = helpers_entity

sys.modules.setdefault(
    "homeassistant.components", types.ModuleType("homeassistant.components")
)
sensor_module = types.ModuleType("homeassistant.components.sensor")


class SensorEntity(Entity):
    """Simplified stand-in for Home Assistant's SensorEntity."""

    @property
    def native_unit_of_measurement(self):
        return getattr(self, "_attr_native_unit_of_measurement", None)

    @property
    def native_value(self):
        return getattr(self, "_attr_native_value", None)

    @property
    def device_class(self):
        return getattr(self, "_attr_device_class", None)

    @property
    def extra_state_attributes(self):
        return getattr(self, "_attr_extra_state_attributes", None)


sensor_module.SensorEntity = SensorEntity
sys.modules["homeassistant.components.sensor"] = sensor_module

const_module = types.ModuleType("homeassistant.const")
const_module.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
const_module.UnitOfLength = types.SimpleNamespace(
    CENTIMETERS="cm",
    KILOMETERS="km",
    MILLIMETERS="mm",
)
const_module.UnitOfSpeed = types.SimpleNamespace(KILOMETERS_PER_HOUR="km/h")
const_module.UnitOfPressure = types.SimpleNamespace(MBAR="mbar")
const_module.UnitOfTime = types.SimpleNamespace(SECONDS="s")
const_module.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"
const_module.PERCENTAGE = "%"
const_module.SensorDeviceClass = types.SimpleNamespace(
    TEMPERATURE="temperature",
    DISTANCE="distance",
    WIND_SPEED="wind_speed",
    PM25="pm25",
    PM10="pm10",
    PRESSURE="pressure",
    PRECIPITATION="precipitation",
    DURATION="duration",
    BATTERY="battery",
    DATE="date",
    TIMESTAMP="timestamp",
)
sys.modules["homeassistant.const"] = const_module
sensor_module.SensorDeviceClass = const_module.SensorDeviceClass

# Ensure packages exist without executing integration __init__
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(Path("custom_components"))]
sys.modules.setdefault("custom_components", custom_components)

coral_pkg = types.ModuleType("custom_components.coral_mylo")
coral_pkg.__path__ = [str(Path("custom_components/coral_mylo"))]
sys.modules.setdefault("custom_components.coral_mylo", coral_pkg)

sensor_path = Path("custom_components/coral_mylo/sensor.py")
spec = importlib.util.spec_from_file_location(
    "custom_components.coral_mylo.sensor", sensor_path
)
sensor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sensor)


def test_mylo_sensor_uses_native_units():
    """Ensure MyloSensor exposes native unit attributes."""

    mylo = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "water.temperature",
        "Water Temperature",
        const_module.UnitOfTemperature.CELSIUS,
        const_module.SensorDeviceClass.TEMPERATURE,
    )

    mylo._state = 23

    assert isinstance(mylo, SensorEntity)
    assert mylo.native_unit_of_measurement == "°C"
    assert mylo.native_value == 23


def test_device_classes_assigned():
    """Ensure sensors are created with appropriate device classes."""

    wind = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "weather.wind_kph",
        "Wind Speed",
        const_module.UnitOfSpeed.KILOMETERS_PER_HOUR,
        const_module.SensorDeviceClass.WIND_SPEED,
    )
    assert wind.device_class == const_module.SensorDeviceClass.WIND_SPEED
    assert wind.native_unit_of_measurement == "km/h"

    pressure = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "weather.pressure_mb",
        "Atmospheric Pressure",
        const_module.UnitOfPressure.MBAR,
        const_module.SensorDeviceClass.PRESSURE,
    )
    assert pressure.device_class == const_module.SensorDeviceClass.PRESSURE
    assert pressure.native_unit_of_measurement == "mbar"

    pm10 = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "weather.aq_pm10",
        "Air Quality PM10",
        const_module.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        const_module.SensorDeviceClass.PM10,
    )
    assert pm10.device_class == const_module.SensorDeviceClass.PM10

    precip = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "weather.precip_mm.count",
        "Precipitation",
        const_module.UnitOfLength.MILLIMETERS,
        const_module.SensorDeviceClass.PRECIPITATION,
    )
    assert precip.device_class == const_module.SensorDeviceClass.PRECIPITATION
    assert precip.native_unit_of_measurement == "mm"

    lag = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "statsd.timestamp_lag",
        "StatsD Timestamp Lag",
        const_module.UnitOfTime.SECONDS,
        const_module.SensorDeviceClass.DURATION,
    )
    assert lag.device_class == const_module.SensorDeviceClass.DURATION
    assert lag.native_unit_of_measurement == "s"

    cpu = sensor.MyloRealtimeSensor(
        "dev1",
        "CPU Temperature",
        "/status/temperature/cpu",
        None,
        const_module.UnitOfTemperature.CELSIUS,
        const_module.SensorDeviceClass.TEMPERATURE,
    )
    assert cpu.device_class == const_module.SensorDeviceClass.TEMPERATURE
    assert cpu.native_unit_of_measurement == "°C"

    last_off = sensor.MyloRealtimeSensor(
        "dev1",
        "Last Off Notification",
        "/monitoring/last_off_notification",
        None,
        None,
        const_module.SensorDeviceClass.DATE,
    )
    assert last_off.device_class == const_module.SensorDeviceClass.DATE


def test_last_off_notification_parses_date():
    """Verify websocket provides a date object for date sensors."""

    last_off = sensor.MyloRealtimeSensor(
        "dev1",
        "Last Off Notification",
        "/monitoring/last_off_notification",
        None,
        None,
        const_module.SensorDeviceClass.DATE,
    )

    asyncio.run(last_off.update_from_ws("2025-07-29T14:47:25.817893"))

    assert isinstance(last_off.native_value, date)
    assert last_off.native_value == date(2025, 7, 29)


def test_last_off_notification_respects_timezone():
    """Date strings are assumed UTC and converted to local time zone."""

    last_off = sensor.MyloRealtimeSensor(
        "dev1",
        "Last Off Notification",
        "/monitoring/last_off_notification",
        None,
        None,
        const_module.SensorDeviceClass.DATE,
    )

    dt_util = sensor.dt_util

    dt_util.set_default_time_zone(dt_util.get_time_zone("Asia/Tokyo"))
    asyncio.run(last_off.update_from_ws("2025-07-29T23:30:00+00:00"))
    assert last_off.native_value == date(2025, 7, 30)
    dt_util.set_default_time_zone(dt_util.UTC)


def test_system_ping_respects_timezone():
    """Timestamp strings are assumed UTC and converted to local time zone."""

    ping = sensor.MyloRealtimeSensor(
        "dev1",
        "System Ping",
        "/status/system_ping",
        None,
        None,
        const_module.SensorDeviceClass.TIMESTAMP,
    )

    dt_util = sensor.dt_util

    dt_util.set_default_time_zone(dt_util.get_time_zone("America/New_York"))
    asyncio.run(ping.update_from_ws("2025-07-29T12:00:00"))
    assert ping.native_value == datetime(
        2025, 7, 29, 8, 0, tzinfo=ZoneInfo("America/New_York")
    )
    dt_util.set_default_time_zone(dt_util.UTC)


def test_memory_usage_parses_components():
    """Ensure memory usage string is parsed into sub values."""

    memory = sensor.MyloRealtimeSensor("dev1", "Memory Usage", "/status/memory", None)

    asyncio.run(memory.update_from_ws("used: 78.0%, available: 873MB, swap is at 41%"))

    assert memory.native_value == 78.0
    assert memory.extra_state_attributes == {
        "available_mb": 873,
        "swap_percent": 41.0,
    }


def test_statsd_metric_without_device_prefix(monkeypatch):
    """StatsD metrics should be queried without a device prefix."""

    lag = sensor.MyloSensor(
        "1.2.3.4",
        "dev1",
        "statsd.timestamp_lag",
        "StatsD Timestamp Lag",
        const_module.UnitOfTime.SECONDS,
        const_module.SensorDeviceClass.DURATION,
    )

    class FakeHass:
        async def async_add_executor_job(self, func, *args):
            return func(*args)

    lag.hass = FakeHass()

    monkeypatch.setattr(
        sensor, "read_gauges_from_statsd", lambda ip: {"statsd.timestamp_lag": 12}
    )

    asyncio.run(lag.async_update())

    assert lag.native_value == 12


def test_pool_state_sensor_maps_codes():
    """Pool state codes are translated to human-readable states."""

    ps = sensor.MyloPoolStateSensor("dev1", None)
    asyncio.run(ps.update_from_ws({"state": 1, "timestamp": "2024-01-01"}))
    assert ps.native_value == "empty"
    asyncio.run(ps.update_from_ws({"state": 2}))
    assert ps.native_value == "near_pool"
    asyncio.run(ps.update_from_ws({"state": 3}))
    assert ps.native_value == "in_pool"


def test_pool_state_sensor_handles_list():
    """When receiving a list, the latest entry is used."""

    ps = sensor.MyloPoolStateSensor("dev1", None)
    asyncio.run(
        ps.update_from_ws(
            [
                {"state": 1},
                {"state": 3, "timestamp": "2024-01-02"},
            ]
        )
    )
    assert ps.native_value == "in_pool"
