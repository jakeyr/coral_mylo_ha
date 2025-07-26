import os
import sys
import types
import importlib.util
from unittest.mock import patch

# Provide dummy aiohttp module before loading utils
sys.modules['aiohttp'] = types.ModuleType('aiohttp')
sys.modules['aiohttp'].ClientSession = None

# Ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load utils without requiring Home Assistant
utils_path = os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'coral_mylo', 'utils.py')
spec = importlib.util.spec_from_file_location('utils', utils_path)
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)

class FakeSocket:
    def __init__(self, responses):
        self._responses = list(responses)
        self.sent = []
    def sendall(self, data):
        self.sent.append(data)
    def recv(self, bufsize):
        return self._responses.pop(0) if self._responses else b''
    def close(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass

def test_discover_device_id_from_statsd():
    gauges = {'coral.42.water.temperature': 24.0}
    with patch.object(utils, 'read_gauges_from_statsd', return_value=gauges):
        assert utils.discover_device_id_from_statsd('1.2.3.4') == '42'
    with patch.object(utils, 'read_gauges_from_statsd', return_value={}):
        assert utils.discover_device_id_from_statsd('1.2.3.4') is None

def test_read_gauges_from_statsd_success():
    responses = [b"{'coral.1.metric': 1}\nEND"]
    fake_socket = FakeSocket(responses)
    with patch('socket.create_connection', return_value=fake_socket):
        gauges = utils.read_gauges_from_statsd('1.2.3.4')
    assert gauges == {'coral.1.metric': 1}
    assert fake_socket.sent == [b'gauges\n']

def test_read_gauges_from_statsd_error():
    with patch('socket.create_connection', side_effect=OSError):
        gauges = utils.read_gauges_from_statsd('1.2.3.4')
    assert gauges == {}

def test_get_statsd_gauge_value(monkeypatch):
    monkeypatch.setattr(utils, 'read_gauges_from_statsd', lambda ip: {'key': 3})
    assert utils.get_statsd_gauge_value('1.2.3.4', 'key') == 3
    assert utils.get_statsd_gauge_value('1.2.3.4', 'missing') is None
