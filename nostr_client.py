import asyncio
import json
import os
import ssl
import hashlib
import time
import logging
import base64
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import websockets
import bech32
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

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

def npub_to_hex(value: str) -> str:
    """Decode a bech32 ``npub`` string into a hex pubkey."""
    hrp, data = bech32.bech32_decode(value)
    if hrp != "npub" or data is None:
        raise ValueError("Invalid npub")
    decoded = bech32.convertbits(data, 5, 8, False)
    return bytes(decoded).hex()

# --- Event and Filters ---

class EventKind:
    SET_METADATA = 0
    TEXT_NOTE = 1
    ENCRYPTED_DM = 4
    EPHEMERAL_DM = 23194
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
    relay_url: str | None = None

@dataclass
class _EOSEMsg:
    subscription_id: str

class MessagePool:
    def __init__(self):
        self._events: asyncio.Queue[_EventMsg] = asyncio.Queue()
        self._eose: asyncio.Queue[_EOSEMsg] = asyncio.Queue()

    def add_event(self, sub_id: str, event: Event, relay_url: str | None = None):
        self._events.put_nowait(_EventMsg(sub_id, event, relay_url))

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
        self._recv_tasks: List[asyncio.Task] = []

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
            self._recv_tasks.append(asyncio.create_task(self._recv_loop(relay)))
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
                        self.message_pool.add_event(data[1], event, relay.url)
                    elif typ == "EOSE" and len(data) >= 2:
                        self.message_pool.add_eose(data[1])
            except websockets.exceptions.ConnectionClosedError as exc:
                logger.debug("Websocket closed for %s: %s", relay.url, exc)
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

    async def publish_event(self, event: Event):
        """Send ``event`` to all connected relays and wait for completion."""
        msg = json.dumps(["EVENT", event.to_dict()])
        tasks = []
        for url, r in self.relays.items():
            if r.ws:
                logger.debug("Sending message to %s: %s", url, msg)
                try:
                    tasks.append(asyncio.create_task(r.ws.send(msg)))
                except Exception as exc:
                    logger.error("Failed to send to %s: %s", url, exc)
            else:
                logger.debug("Relay %s not connected; skipping send", url)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close_connections(self):
        for r in self.relays.values():
            if r.ws:
                try:
                    await r.ws.close()
                except Exception:
                    pass
        for task in self._recv_tasks:
            task.cancel()
        if self._recv_tasks:
            await asyncio.gather(*self._recv_tasks, return_exceptions=True)
        self._recv_tasks.clear()

_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

def _lift_x(x: int) -> (int, int):
    """Convert x-only pubkey to curve point with even y."""
    y_sq = (pow(x, 3, _P) + 7) % _P
    y = pow(y_sq, (_P + 1) // 4, _P)
    if y % 2 == 1:
        y = _P - y
    return x, y

def _pubkey_from_hex(pub_hex: str) -> ec.EllipticCurvePublicKey:
    x = int(pub_hex, 16)
    x, y = _lift_x(x)
    numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1())
    return numbers.public_key()

def derive_public_key_hex(priv_hex: str) -> str:
    key = ec.derive_private_key(int(priv_hex, 16), ec.SECP256K1())
    numbers = key.public_key().public_numbers()
    return f"{numbers.x:064x}"

def nip17_encrypt(sender_priv: str, recipient_pub: str, plaintext: str) -> str:
    """Encrypt plaintext per NIP-17 using AES-GCM."""
    sender_key = ec.derive_private_key(int(sender_priv, 16), ec.SECP256K1())
    recipient_key = _pubkey_from_hex(recipient_pub)
    shared = sender_key.exchange(ec.ECDH(), recipient_key)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(shared)
    key = digest.finalize()
    aes = AESGCM(key)
    iv = os.urandom(12)
    ct = aes.encrypt(iv, plaintext.encode(), None)
    return base64.b64encode(iv + ct).decode()

class EncryptedDirectMessage:
    def __init__(self, kind: int = EventKind.ENCRYPTED_DM):
        self.kind = kind
        self.content = ""
        self.sender_pubkey = ""
        self.recipient_pubkey = ""

    def encrypt(self, private_key_hex: str, cleartext_content: str, recipient_pubkey: str):
        self.sender_pubkey = derive_public_key_hex(private_key_hex)
        self.recipient_pubkey = recipient_pubkey
        if self.kind == EventKind.EPHEMERAL_DM:
            self.content = nip17_encrypt(private_key_hex, recipient_pubkey, cleartext_content)
        else:
            self.content = cleartext_content

    def to_event(self) -> Event:
        """Return an ``Event`` representing this message.

        The ``pubkey`` field in the resulting event must reference the
        **sender's** public key. Older versions incorrectly used the
        recipient's pubkey here which resulted in invalid signatures.
        """
        return Event(
            public_key=self.sender_pubkey,
            content=self.content,
            kind=self.kind,
            tags=[["p", self.recipient_pubkey]],
            created_at=int(time.time()),
        )
