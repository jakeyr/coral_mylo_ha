import logging
import socket
import aiohttp

_LOGGER = logging.getLogger(__name__)
STATS_PORT = 8126

def discover_device_id_from_statsd(ip):
    """Finds the device ID by querying the TCP statsd interface."""
    gauges = read_gauges_from_statsd(ip)
    for key in gauges.keys():
        if key.startswith("coral."):
            return key.split(".")[1]
    return None

def read_gauges_from_statsd(ip):
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
    gauges = read_gauges_from_statsd(ip)
    return gauges.get(key)

async def refresh_jwt(refresh_token, api_key):
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                data = await resp.json()
                return data.get("access_token")
    except Exception as e:
        _LOGGER.error(f"Exception while refreshing JWT: {e}")
    return None

async def fetch_firebase_download_token(bucket, path, jwt):
    url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}"
    headers = {
        "Authorization": f"Firebase {jwt}",
        "Accept": "application/json"
    }
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
                    return await resp.read()
                text = await resp.text()
                _LOGGER.error(
                    "Failed to fetch image: %s, Response: %s",
                    resp.status,
                    text,
                )
    except Exception as e:
        _LOGGER.error("Exception fetching camera image: %s", e)

    return None
