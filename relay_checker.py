import asyncio
import json
import os
from pathlib import Path
import websockets

PUBKEY = "2dff6f2ab427ff6741817de6f61a5a15f57e62ae77d12b209590de32ad2f038b"
RELAYS_FILE = Path("relays.txt")
GOOD_RELAYS_FILE = Path("good-relays.txt")
STATE_FILE = Path("relay_state.json")

async def query_relay(url: str) -> bool:
    """Return True if a profile event is received from the relay."""
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            req_id = "check"
            req = ["REQ", req_id, {"kinds": [0], "authors": [PUBKEY], "limit": 1}]
            await ws.send(json.dumps(req))
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    break
                data = json.loads(msg)
                if data[0] == "EVENT" and data[1] == req_id:
                    return True
                if data[0] == "EOSE" and data[1] == req_id:
                    break
    except Exception:
        pass
    return False

async def main():
    if RELAYS_FILE.exists():
        relays = [l.strip() for l in RELAYS_FILE.read_text().splitlines() if l.strip()]
    else:
        relays = []

    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}

    if GOOD_RELAYS_FILE.exists():
        good_relays = {l.strip() for l in GOOD_RELAYS_FILE.read_text().splitlines() if l.strip()}
    else:
        good_relays = set()

    updated_relays = set(relays)
    for url in list(relays):
        success = await query_relay(url)
        if success:
            good_relays.add(url)
            state[url] = 0
        else:
            state[url] = state.get(url, 0) + 1
            if state[url] >= 10:
                updated_relays.discard(url)
                good_relays.discard(url)
                state.pop(url, None)

    RELAYS_FILE.write_text("\n".join(sorted(updated_relays)) + ("\n" if updated_relays else ""))
    GOOD_RELAYS_FILE.write_text("\n".join(sorted(good_relays)) + ("\n" if good_relays else ""))
    STATE_FILE.write_text(json.dumps(state, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
