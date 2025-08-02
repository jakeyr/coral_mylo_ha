"""Tests for the MYLO sensor module."""

import importlib.util
from pathlib import Path
import sys
import types


# Stub out Home Assistant modules required for importing the integration
sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))

ha = types.ModuleType("homeassistant")
ha.__path__ = []  # Mark as package
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault(
    "homeassistant.helpers", types.ModuleType("homeassistant.helpers")
)

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


sensor_module.SensorEntity = SensorEntity
sys.modules["homeassistant.components.sensor"] = sensor_module

const_module = types.ModuleType("homeassistant.const")
const_module.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
const_module.UnitOfLength = types.SimpleNamespace(CENTIMETERS="cm")
const_module.UnitOfSpeed = types.SimpleNamespace(KILOMETERS_PER_HOUR="km/h")
const_module.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"
const_module.PERCENTAGE = "%"
const_module.SensorDeviceClass = types.SimpleNamespace(
    TEMPERATURE="temperature",
    DISTANCE="distance",
    WIND_SPEED="wind_speed",
    PM25="pm25",
    BATTERY="battery",
    DATE="date",
)
sys.modules["homeassistant.const"] = const_module

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
