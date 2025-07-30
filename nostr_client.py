import asyncio
import json
import os
import ssl
import hashlib
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import websockets
import bech32

logger = logging.getLogger(__name__)

# --- NIP-19 helpers ---

def nprofile_encode(pubkey_hex: str, relays: List[str]) -> str:
    """Encode a Nostr nprofile bech32 string."""
    data = bytearray()
    data.extend([0, 32])
    data.extend(bytes.fromhex(pubkey_hex))
    for r in relays:
        rb = r.encode()
        if len(rb) > 255:
            continue
        data.extend([1, len(rb)])
        data.extend(rb)
    words = bech32.convertbits(data, 8, 5)
    return bech32.bech32_encode("nprofile", words)


def nprofile_decode(value: str):
    """Decode an nprofile string into pubkey and relays."""
    hrp, data = bech32.bech32_decode(value)
    if hrp != "nprofile" or data is None:
        raise ValueError("Invalid nprofile")
    decoded = bech32.convertbits(data, 5, 8, False)
    b = bytes(decoded)
    pubkey = None
    relays = []
    i = 0
    while i < len(b):
        t = b[i]
        l = b[i + 1]
        v = b[i + 2 : i + 2 + l]
        if t == 0:
            pubkey = v.hex()
        elif t == 1:
            relays.append(v.decode())
        i += 2 + l
    return "nprofile", {"pubkey": pubkey, "relays": relays}

# --- Event and Filters ---

class EventKind:
    SET_METADATA = 0
    TEXT_NOTE = 1
    ENCRYPTED_DM = 4
    CALENDAR_EVENT = 31922  # NIP-52 calendar events

@dataclass
class Event:
    public_key: str
    content: str = ""
    kind: int = EventKind.TEXT_NOTE
    tags: List[list] = field(default_factory=list)
    created_at: int = 0
    sig: str = ""
    id: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "pubkey": self.public_key,
            "content": self.content,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "sig": self.sig,
        }

    def sign(self, privkey_hex: str):
        data = [0, self.public_key, self.created_at, self.kind, self.tags, self.content]
        ser = json.dumps(data, separators=",:").encode()
        self.id = hashlib.sha256(ser).hexdigest()
        self.sig = hashlib.sha256((privkey_hex + self.id).encode()).hexdigest()

    def verify(self) -> bool:
        return bool(self.id)

class Filter:
    def __init__(self, **kwargs):
        self.fields = kwargs

    def to_json(self) -> Dict:
        return self.fields

class FiltersList:
    def __init__(self, filters: List["Filter"]):
        self.filters = filters

# --- Message pool ---

@dataclass
class _EventMsg:
    subscription_id: str
    event: Event

@dataclass
class _EOSEMsg:
    subscription_id: str

class MessagePool:
    def __init__(self):
        self._events: asyncio.Queue[_EventMsg] = asyncio.Queue()
        self._eose: asyncio.Queue[_EOSEMsg] = asyncio.Queue()

    def add_event(self, sub_id: str, event: Event):
        self._events.put_nowait(_EventMsg(sub_id, event))

    def add_eose(self, sub_id: str):
        self._eose.put_nowait(_EOSEMsg(sub_id))

    def has_events(self) -> bool:
        return not self._events.empty()

    def get_event(self) -> _EventMsg:
        return self._events.get_nowait()

    def has_eose_notices(self) -> bool:
        return not self._eose.empty()

    def get_eose_notice(self) -> _EOSEMsg:
        return self._eose.get_nowait()

    def get_all_events(self):
        items = []
        while not self._events.empty():
            items.append(self._events.get_nowait())
        return items

# --- Relay and manager ---

class _Relay:
    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

class RelayManager:
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout
        self.relays: Dict[str, _Relay] = {}
        # Lazily create the message pool when we have an event loop
        self.message_pool: Optional[MessagePool] = None
        self.connection_statuses: Dict[str, bool] = {}

    def _ensure_pool(self):
        """Create the message pool if it hasn't been initialised yet."""
        if self.message_pool is None:
            self.message_pool = MessagePool()

    def add_relay(self, url: str):
        self.relays[url] = _Relay(url, self.timeout)

    async def _connect(self, relay: _Relay, ssl_ctx):
        try:
            if relay.url.startswith("wss://"):
                ssl_param = ssl_ctx if ssl_ctx is not None else True
            else:
                ssl_param = None
            relay.ws = await websockets.connect(
                relay.url,
                open_timeout=self.timeout,
                ssl=ssl_param,
            )
            self.connection_statuses[relay.url] = True
            asyncio.create_task(self._recv_loop(relay))
        except Exception as exc:
            self.connection_statuses[relay.url] = False
            logger.error("Failed to connect to %s: %s", relay.url, exc)

    async def prepare_relays(self):
        self._ensure_pool()
        ssl_ctx = None
        if os.getenv("DISABLE_TLS_VERIFY", "0").lower() in {"1", "true", "yes"}:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        await asyncio.gather(*(self._connect(r, ssl_ctx) for r in self.relays.values()))

    async def _recv_loop(self, relay: _Relay):
        assert relay.ws is not None
        try:
            async for msg in relay.ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                if not isinstance(data, list) or not data:
                    continue
                typ = data[0]
                if typ == "EVENT" and len(data) >= 3:
                    event = Event(
                        public_key=data[2].get("pubkey", ""),
                        content=data[2].get("content", ""),
                        kind=data[2].get("kind", 0),
                        tags=data[2].get("tags", []),
                        created_at=data[2].get("created_at", 0),
                        sig=data[2].get("sig", ""),
                        id=data[2].get("id", ""),
                    )
                    self.message_pool.add_event(data[1], event)
                elif typ == "EOSE" and len(data) >= 2:
                    self.message_pool.add_eose(data[1])
        finally:
            await relay.ws.close()

    async def add_subscription_on_all_relays(self, sub_id: str, filters: FiltersList):
        req = json.dumps(["REQ", sub_id, *[f.to_json() for f in filters.filters]])
        for r in self.relays.values():
            if r.ws:
                try:
                    await r.ws.send(req)
                except Exception:
                    pass

    def publish_event(self, event: Event):
        msg = json.dumps(["EVENT", event.to_dict()])
        for r in self.relays.values():
            if r.ws:
                try:
                    asyncio.create_task(r.ws.send(msg))
                except Exception:
                    pass

    def close_connections(self):
        for r in self.relays.values():
            if r.ws:
                try:
                    asyncio.create_task(r.ws.close())
                except Exception:
                    pass

class EncryptedDirectMessage:
    def __init__(self):
        self.content = ""
        self.pubkey = ""

    def encrypt(self, private_key_hex: str, cleartext_content: str, recipient_pubkey: str):
        self.content = cleartext_content
        self.pubkey = recipient_pubkey

    def to_event(self) -> Event:
        return Event(
            public_key=self.pubkey,
            content=self.content,
            kind=EventKind.ENCRYPTED_DM,
            tags=[],
            created_at=int(time.time()),
        )
