"""Utility helpers for the Coral Mylo integration."""

import logging
import socket
import asyncio
import time
import json
import aiohttp

_LOGGER = logging.getLogger(__name__)
STATS_PORT = 8126


def discover_device_id_from_statsd(ip):
    """Return the device ID by querying the TCP StatsD interface."""
    _LOGGER.debug("Discovering device id via StatsD on %s", ip)
    gauges = read_gauges_from_statsd(ip)
    for key in gauges.keys():
        if key.startswith("coral."):
            return key.split(".")[1]
    return None


def read_gauges_from_statsd(ip):
    """Read the current StatsD gauges from the MYLO device."""
    _LOGGER.debug("Reading gauges from StatsD on %s", ip)
    try:
        with socket.create_connection((ip, STATS_PORT), timeout=2) as sock:
            sock.sendall(b"gauges\n")
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"END" in chunk:
                    break
            text = response.decode("utf-8").strip().split("\nEND")[0]
            return eval(text.strip())
    except Exception as e:
        _LOGGER.error(f"Error retrieving gauges: {e}")
        return {}


def get_statsd_gauge_value(ip, key):
    """Convenience helper to fetch a single StatsD gauge value."""
    gauges = read_gauges_from_statsd(ip)
    return gauges.get(key)


async def refresh_jwt(refresh_token, api_key):
    """Refresh the Firebase JWT using the provided refresh token."""
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                data = await resp.json()
                token = data.get("access_token")
                _LOGGER.debug("JWT refreshed successfully")
                return token
    except Exception as e:
        _LOGGER.error(f"Exception while refreshing JWT: {e}")
    return None


async def fetch_firebase_download_token(bucket, path, jwt):
    """Retrieve a Firebase download token for the given path."""
    url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}"
    headers = {"Authorization": f"Firebase {jwt}", "Accept": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                return data.get("downloadTokens")
    except Exception as e:
        _LOGGER.error(f"Error fetching download token: {e}")
    return None


async def download_latest_snapshot(device_id, refresh_token, api_key):
    """Return the latest snapshot bytes for the given MYLO device."""
    _LOGGER.debug("Downloading latest snapshot for %s", device_id)
    bucket = "coralesto.appspot.com"
    image_path = f"images%2Fcoral_{device_id}_last.jpg"

    jwt = await refresh_jwt(refresh_token, api_key)
    if not jwt:
        _LOGGER.error("Failed to refresh JWT")
        return None

    token = await fetch_firebase_download_token(bucket, image_path, jwt)
    if not token:
        _LOGGER.error("Failed to fetch download token")
        return None

    image_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/"
        f"{image_path}?alt=media&token={token}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    _LOGGER.debug("Snapshot downloaded from %s", image_url)
                    return data
                text = await resp.text()
                _LOGGER.error(
                    "Failed to fetch image: %s, Response: %s",
                    resp.status,
                    text,
                )
    except Exception as e:
        _LOGGER.error("Exception fetching camera image: %s", e)

    return None


class MyloWebsocketClient:
    """Persistent Firebase WebSocket for a single MYLO device."""

    def __init__(self, hass, device_id, refresh_token, api_key):
        self._hass = hass
        self._device_id = device_id
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._session = None
        self._ws = None
        self._task = None
        self._rid = 0
        self._running = False
        self._img_event = asyncio.Event()
        self._connected = asyncio.Event()
        self._sensor_callbacks = {}

    def register_sensor(self, path, callback):
        """Register callback for updates on a path."""
        self._sensor_callbacks[path] = callback
        _LOGGER.debug("Sensor callback registered for %s", path)

    async def start(self):
        """Start the websocket connection."""
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession()
        _LOGGER.debug("Starting websocket for MYLO %s", self._device_id)
        self._task = self._hass.loop.create_task(self._run())

    async def stop(self):
        """Stop the websocket connection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        _LOGGER.debug("Websocket for MYLO %s stopped", self._device_id)

    async def _send(self, data):
        """Send a JSON message if the socket is open."""
        if not self._ws:
            return
        await self._ws.send_json(data)

    async def _run(self):
        """Main loop for maintaining the Firebase websocket."""
        url = "wss://coralesto.firebaseio.com/.ws?v=5&ns=coralesto"
        while self._running:
            try:
                jwt = await refresh_jwt(self._refresh_token, self._api_key)
                if not jwt:
                    await asyncio.sleep(5)
                    continue
                self._ws = await self._session.ws_connect(url)
                self._rid = 1
                _LOGGER.debug("Websocket connected for MYLO %s", self._device_id)
                await self._send(
                    {"t": "d", "d": {"r": self._rid, "a": "auth", "b": {"cred": jwt}}}
                )
                await asyncio.wait_for(self._ws.receive(), timeout=5)
                self._rid += 1
                # subscribe to sensors and imgready
                for path in list(self._sensor_callbacks.keys()) + [
                    f"/pooldevices/{self._device_id}/imgready"
                ]:
                    await self._send(
                        {"t": "d", "d": {"r": self._rid, "a": "q", "b": {"p": path}}}
                    )
                    self._rid += 1
                self._connected.set()
                async for msg in self._ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue
                    path = data.get("d", {}).get("b", {}).get("p")
                    payload = data.get("d", {}).get("b", {}).get("d")
                    _LOGGER.debug("WS message on %s: %s", path, payload)
                    if path == f"pooldevices/{self._device_id}/imgready":
                        self._img_event.set()
                    elif path in self._sensor_callbacks:
                        cb = self._sensor_callbacks[path]
                        self._hass.async_create_task(cb(payload))
            except Exception as e:
                _LOGGER.error("WebSocket connection error: %s", e)
                _LOGGER.debug("Retrying websocket connection in 5s")
            self._connected.clear()
            if self._ws:
                await self._ws.close()
            await asyncio.sleep(5)

    async def send_getimage(self, mobile_id="ha", timeout=30):
        """Trigger MYLO to capture a new image and wait for readiness."""
        await self._connected.wait()
        self._img_event.clear()
        self._rid += 1
        await self._send(
            {
                "t": "d",
                "d": {
                    "r": self._rid,
                    "a": "m",
                    "b": {
                        "p": f"/pooldevices/{self._device_id}/getimage",
                        "d": {
                            "device": mobile_id,
                            "time": str(int(time.time() * 1000)),
                        },
                    },
                },
            }
        )
        try:
            await asyncio.wait_for(self._img_event.wait(), timeout=timeout)
            _LOGGER.debug("Image ready event received")
            return True
        except asyncio.TimeoutError:
            return False
