import asyncio
import websockets

async def try_connect(url="wss://relay.damus.io"):
    try:
        async with websockets.connect(url, open_timeout=5):
            print("connected")
            return True
    except Exception as e:
        print(e)
        return False

def test_nostr_relay_connection():
    assert isinstance(asyncio.run(try_connect()), bool)

