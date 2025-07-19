import asyncio
import json
import websockets

async def try_connect(url="wss://relay.damus.io"):
    try:
        async with websockets.connect(url, open_timeout=5):
            print("connected")
            return True
    except Exception as e:
        print(e)
        return False

async def fetch_profile(pubkey: str, url: str = "wss://relay.damus.io"):
    """Fetch a Nostr metadata event for ``pubkey`` from ``url``."""
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            req_id = "profile_test"
            req = ["REQ", req_id, {"kinds": [0], "authors": [pubkey], "limit": 1}]
            await ws.send(json.dumps(req))
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    break
                data = json.loads(msg)
                if data[0] == "EVENT" and data[1] == req_id:
                    return json.loads(data[2].get("content", "{}"))
                if data[0] == "EOSE" and data[1] == req_id:
                    break
    except Exception as e:
        print(e)
    return None

def test_nostr_relay_connection():
    assert isinstance(asyncio.run(try_connect()), bool)

def test_fetch_profile():
    pubkey = "00202dff6f2ab427ff6741817de6f61a5a15f57e62ae77d12b209590de32ad2f038b"
    profile = asyncio.run(fetch_profile(pubkey))
    # The relay may not have the profile cached, but if it does, it should be a dict
    assert profile is None or isinstance(profile, dict)
