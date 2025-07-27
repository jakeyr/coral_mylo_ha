import os
import sys
import types
import importlib.util
import asyncio

# Provide dummy aiohttp module before loading utils
sys.modules["aiohttp"] = types.ModuleType("aiohttp")
sys.modules["aiohttp"].ClientSession = None

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

utils_path = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "coral_mylo", "utils.py"
)
spec = importlib.util.spec_from_file_location("utils", utils_path)
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)


class FakeResponse:
    def __init__(self, data=b"", status=200):
        self._data = data
        self.status = status

    async def read(self):
        return self._data

    async def text(self):
        return ""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class FakeSession:
    def __init__(self, response):
        self._response = response

    def get(self, *args, **kwargs):
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


def test_download_latest_snapshot(monkeypatch):
    response = FakeResponse(b"image")

    async def fake_refresh(*args, **kwargs):
        return "jwt"

    async def fake_token(*args, **kwargs):
        return "tok"

    monkeypatch.setattr(utils, "refresh_jwt", fake_refresh)
    monkeypatch.setattr(utils, "fetch_firebase_download_token", fake_token)
    monkeypatch.setattr(
        utils,
        "aiohttp",
        types.SimpleNamespace(ClientSession=lambda: FakeSession(response)),
    )
    data = asyncio.run(utils.download_latest_snapshot("id", "r", "k"))
    assert data == b"image"


def test_download_latest_snapshot_failure(monkeypatch):
    async def fake_refresh(*args, **kwargs):
        return None

    monkeypatch.setattr(utils, "refresh_jwt", fake_refresh)
    data = asyncio.run(utils.download_latest_snapshot("id", "r", "k"))
    assert data is None
