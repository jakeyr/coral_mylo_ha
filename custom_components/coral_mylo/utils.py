"""Utility helpers for communicating with the MYLO device."""

import logging
import socket
import asyncio
import time
import json
import aiohttp

_LOGGER = logging.getLogger(__name__)
STATS_PORT = 8126

def discover_device_id_from_statsd(ip):
    """Find the device ID by querying the TCP statsd interface."""

    _LOGGER.debug("Querying statsd on %s for device id", ip)
    gauges = read_gauges_from_statsd(ip)
    for key in gauges.keys():
        if key.startswith("coral."):
            return key.split(".")[1]
    # Return None if no matching key is found
    return None

def read_gauges_from_statsd(ip):
    """Return all gauges reported by the device's StatsD server."""

    try:
        with socket.create_connection((ip, STATS_PORT), timeout=2) as sock:
            sock.sendall(b"gauges\n")
            _LOGGER.debug("Sent gauges command to %s:%s", ip, STATS_PORT)
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"END" in chunk:
                    break
            text = response.decode("utf-8").strip().split("\nEND")[0]
            gauges = eval(text.strip())
            return gauges
    except Exception as e:
        _LOGGER.error(f"Error retrieving gauges: {e}")
        return {}

def get_statsd_gauge_value(ip, key):
    """Fetch a single gauge value from StatsD."""

    gauges = read_gauges_from_statsd(ip)
    value = gauges.get(key)
    _LOGGER.debug("Gauge %s=%s", key, value)
    return value

async def refresh_jwt(refresh_token, api_key):
    """Exchange a refresh token for a short-lived JWT."""

    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                data = await resp.json()
                token = data.get("access_token")
                _LOGGER.debug("JWT refresh returned %s", bool(token))
                return token
    except Exception as e:
        _LOGGER.error(f"Exception while refreshing JWT: {e}")
    return None

async def fetch_firebase_download_token(bucket, path, jwt):
    """Fetch a one-time Firebase download token."""

    url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}"
    headers = {
        "Authorization": f"Firebase {jwt}",
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                token = data.get("downloadTokens")
                _LOGGER.debug(
                    "Download token request status %s", getattr(resp, "status", "unknown")
                )
                return token
    except Exception as e:
        _LOGGER.error(f"Error fetching download token: {e}")
    return None


async def download_latest_snapshot(device_id, refresh_token, api_key):
    """Return the latest snapshot bytes for the given MYLO device."""
    bucket = "coralesto.appspot.com"
    image_path = f"images%2Fcoral_{device_id}_last.jpg"

    _LOGGER.debug("Downloading snapshot for %s", device_id)

    jwt = await refresh_jwt(refresh_token, api_key)
    if not jwt:
        _LOGGER.error("Failed to refresh JWT")
        return None

    token = await fetch_firebase_download_token(bucket, image_path, jwt)
    if not token:
        _LOGGER.error("Failed to fetch download token")
        return None
    _LOGGER.debug("Download token acquired")

    image_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/"
        f"{image_path}?alt=media&token={token}"
    )
    _LOGGER.debug("Fetching image from %s", image_url)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    _LOGGER.debug("Image fetched successfully")
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

    async def start(self):
        """Start the persistent WebSocket connection."""
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession()
        self._task = self._hass.loop.create_task(self._run())

    async def stop(self):
        """Stop the WebSocket connection."""
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

    async def _send(self, data):
        """Helper to send data over the WebSocket."""
        if not self._ws:
            return
        await self._ws.send_json(data)
        _LOGGER.debug("Sent WS message: %s", data)

    async def _run(self):
        """Main loop handling reconnections and incoming messages."""

        url = "wss://coralesto.firebaseio.com/.ws?v=5&ns=coralesto"
        while self._running:
            try:
                jwt = await refresh_jwt(self._refresh_token, self._api_key)
                if not jwt:
                    await asyncio.sleep(5)
                    continue
                _LOGGER.debug("WebSocket authenticated")
                self._ws = await self._session.ws_connect(url)
                self._rid = 1
                await self._send({"t": "d", "d": {"r": self._rid, "a": "auth", "b": {"cred": jwt}}})
                await asyncio.wait_for(self._ws.receive(), timeout=5)
                self._rid += 1
                # subscribe to sensors and imgready
                for path in list(self._sensor_callbacks.keys()) + [f"/pooldevices/{self._device_id}/imgready"]:
                    await self._send({"t": "d", "d": {"r": self._rid, "a": "q", "b": {"p": path}}})
                    self._rid += 1
                self._connected.set()
                async for msg in self._ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue
                    _LOGGER.debug("Received WS data: %s", data)
                    path = data.get("d", {}).get("b", {}).get("p")
                    payload = data.get("d", {}).get("b", {}).get("d")
                    if path == f"pooldevices/{self._device_id}/imgready":
                        self._img_event.set()
                    elif path in self._sensor_callbacks:
                        cb = self._sensor_callbacks[path]
                        self._hass.async_create_task(cb(payload))
            except Exception as e:
                _LOGGER.error("WebSocket connection error: %s", e)
            self._connected.clear()
            if self._ws:
                await self._ws.close()
            await asyncio.sleep(5)

    async def send_getimage(self, mobile_id="ha", timeout=30):
        """Request a fresh image from the device via the WebSocket."""

        await self._connected.wait()
        self._img_event.clear()
        self._rid += 1
        _LOGGER.debug("Requesting getimage for %s", self._device_id)
        await self._send({
            "t": "d",
            "d": {
                "r": self._rid,
                "a": "m",
                "b": {
                    "p": f"/pooldevices/{self._device_id}/getimage",
                    "d": {"device": mobile_id, "time": str(int(time.time() * 1000))},
                },
            },
        })
        try:
            await asyncio.wait_for(self._img_event.wait(), timeout=timeout)
            _LOGGER.debug("Image ready event received")
            return True
        except asyncio.TimeoutError:
            return False
