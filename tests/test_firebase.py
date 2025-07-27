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
    def __init__(self, data):
        self._data = data

    async def json(self):
        return self._data

    async def read(self):
        return b""

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


def test_fetch_firebase_download_token(monkeypatch):
    response = FakeResponse({"downloadTokens": "dl"})
    monkeypatch.setattr(
        utils,
        "aiohttp",
        types.SimpleNamespace(ClientSession=lambda: FakeSession(response)),
    )
    token = asyncio.run(utils.fetch_firebase_download_token("b", "p", "jwt"))
    assert token == "dl"


def test_fetch_firebase_download_token_error(monkeypatch):
    def failing_session():
        raise Exception("nope")

    monkeypatch.setattr(
        utils, "aiohttp", types.SimpleNamespace(ClientSession=failing_session)
    )
    assert asyncio.run(utils.fetch_firebase_download_token("b", "p", "jwt")) is None
