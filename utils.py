import logging
import socket
import aiohttp

_LOGGER = logging.getLogger(__name__)

STATS_PORT = 8126

def discover_device_id_from_statsd(ip):
    try:
        gauges = _read_gauges_from_statsd(ip)
        for key in gauges.keys():
            if key.startswith("coral."):
                return key.split(".")[1]
    except Exception as e:
        _LOGGER.error(f"Device discovery failed: {e}")
    return None

def _read_gauges_from_statsd(ip):
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
    gauges = _read_gauges_from_statsd(ip)
    return gauges.get(key)

async def refresh_jwt(refresh_token, api_key):
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    try:
        _LOGGER.debug("Refreshing JWT via aiohttp")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    _LOGGER.error(f"Failed to refresh JWT: {resp.status} {text}")
    except Exception as e:
        _LOGGER.error(f"Exception while refreshing JWT: {e}")
    return None

