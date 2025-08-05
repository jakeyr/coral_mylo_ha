"""Tests for MYLO binary sensor log handling."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

# Stub modules required for import
sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))

ha = types.ModuleType("homeassistant")
ha.__path__ = []
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault(
    "homeassistant.helpers", types.ModuleType("homeassistant.helpers")
)

helpers_event = types.ModuleType("homeassistant.helpers.event")
helpers_event.async_call_later = lambda hass, delay, func: None
sys.modules["homeassistant.helpers.event"] = helpers_event

# Minimal storage implementation
helpers_storage = types.ModuleType("homeassistant.helpers.storage")


class Store:
    _data = {}

    def __init__(self, hass, version, key):
        self.key = key

    async def async_load(self):
        return Store._data.get(self.key)

    async def async_save(self, data):
        Store._data[self.key] = data


helpers_storage.Store = Store
sys.modules["homeassistant.helpers.storage"] = helpers_storage

components = types.ModuleType("homeassistant.components")
sys.modules.setdefault("homeassistant.components", components)
bs_comp = types.ModuleType("homeassistant.components.binary_sensor")
bs_comp.BinarySensorEntity = object
sys.modules["homeassistant.components.binary_sensor"] = bs_comp

# Ensure custom_components package is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(Path("custom_components"))]
sys.modules.setdefault("custom_components", custom_components)
coral_pkg = types.ModuleType("custom_components.coral_mylo")
coral_pkg.__path__ = [str(Path("custom_components/coral_mylo"))]
sys.modules.setdefault("custom_components.coral_mylo", coral_pkg)

# Import the module under test
binary_sensor_path = Path("custom_components/coral_mylo/binary_sensor.py")
spec = importlib.util.spec_from_file_location(
    "custom_components.coral_mylo.binary_sensor", binary_sensor_path
)
binary_sensor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binary_sensor)


class DummyBus:
    """Capture events fired on the Home Assistant bus."""

    def __init__(self):
        self.events = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, data))


class DummyHass:
    """Minimal hass object with an event bus."""

    def __init__(self):
        self.bus = DummyBus()


def test_log_handler_sorts_and_filters():
    """Logs are sorted chronologically and older entries ignored."""
    Store._data.clear()
    hass = DummyHass()
    handler = binary_sensor.MyloLogHandler(hass, [], "abc")
    asyncio.run(handler.async_load())

    entries = [
        {"timestamp": "2023-12-31 20:00:00", "message": "earlier"},
        {"timestamp": "2023-12-31T23:30:00+00:00", "message": "later"},
    ]

    asyncio.run(handler.handle_log(entries))

    assert [e[1]["message"] for e in hass.bus.events] == [
        "earlier",
        "later",
    ]

    asyncio.run(
        handler.handle_log({"timestamp": "2023-12-31T19:00:00+00:00", "message": "old"})
    )
    assert [e[1]["message"] for e in hass.bus.events] == [
        "earlier",
        "later",
    ]


def test_log_handler_persists_last_ts():
    """Last timestamp is saved and restored across handler instances."""

    Store._data.clear()
    hass = DummyHass()
    handler = binary_sensor.MyloLogHandler(hass, [], "abc")
    asyncio.run(handler.async_load())
    asyncio.run(
        handler.handle_log({"timestamp": "2024-01-01T00:00:00+00:00", "message": "now"})
    )
    assert [e[1]["message"] for e in hass.bus.events] == ["now"]

    # Create a new handler to simulate restart
    hass2 = DummyHass()
    handler2 = binary_sensor.MyloLogHandler(hass2, [], "abc")
    asyncio.run(handler2.async_load())
    asyncio.run(
        handler2.handle_log(
            {"timestamp": "2023-12-31T23:00:00+00:00", "message": "old"}
        )
    )
    asyncio.run(
        handler2.handle_log(
            {"timestamp": "2024-01-02T00:00:00+00:00", "message": "new"}
        )
    )
    assert [e[1]["message"] for e in hass2.bus.events] == ["new"]
