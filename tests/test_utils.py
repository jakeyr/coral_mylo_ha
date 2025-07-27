import importlib.util
from pathlib import Path
import sys
import types

# Provide dummy aiohttp module so utils imports succeed
sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))

utils_path = Path("custom_components/coral_mylo/utils.py")
spec = importlib.util.spec_from_file_location("coral_mylo.utils", utils_path)
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)


def test_discover_device_id_from_statsd(monkeypatch):
    sample_gauges = {
        "coral.abc123.water.temperature": 25,
        "other.metric": 5,
    }

    monkeypatch.setattr(utils, "read_gauges_from_statsd", lambda ip: sample_gauges)

    device_id = utils.discover_device_id_from_statsd("1.2.3.4")
    assert device_id == "abc123"
