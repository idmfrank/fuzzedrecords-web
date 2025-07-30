import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_client

class DummyWS:
    def __init__(self):
        self.sent = []
    async def send(self, msg):
        self.sent.append(msg)


def test_publish_event_sends_to_all_relays():
    mgr = nostr_client.RelayManager()
    r1 = nostr_client._Relay("wss://a", mgr.timeout)
    r2 = nostr_client._Relay("wss://b", mgr.timeout)
    r1.ws = DummyWS()
    r2.ws = DummyWS()
    mgr.relays = {"a": r1, "b": r2}

    ev = nostr_client.Event(public_key="00" * 32)
    asyncio.run(mgr.publish_event(ev))

    assert len(r1.ws.sent) == 1
    assert len(r2.ws.sent) == 1
