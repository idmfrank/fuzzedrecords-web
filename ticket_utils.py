import time, json, asyncio
from io import BytesIO
import qrcode
from flask import request, jsonify

# These imports create circular dependencies when this module is imported
# during testing. Import them lazily inside the functions that require them.
from flask import current_app

initialize_client = None
error_response = None
logger = None
limiter = None
from nostr_client import EncryptedDirectMessage, EventKind, Event


def _load_app_dependencies():
    """Lazy import objects from app to avoid circular imports during testing."""
    global initialize_client, error_response, logger, limiter
    if initialize_client is None:
        from app import initialize_client as ic, error_response as er, logger as lg, limiter as lm
        initialize_client = ic
        error_response = er
        logger = lg
        limiter = lm

def generate_ticket(event_name: str, user_pubkey: str, timestamp: int = None):
    ts = timestamp if timestamp is not None else int(time.time())
    payload = {"event": event_name, "pubkey": user_pubkey, "timestamp": ts}
    payload_str = json.dumps(payload)
    qr_img = qrcode.make(payload_str)
    img_io = BytesIO()
    qr_img.save(img_io, 'PNG')
    img_io.seek(0)
    return payload_str, img_io

def send_ticket_as_dm(event_name: str, recipient_pubkey_hex: str,
                      sender_privkey_hex: str, timestamp: int = None) -> str:
    # Generate payload (QR image is not needed for DM)
    _load_app_dependencies()
    payload_str, _ = generate_ticket(event_name, recipient_pubkey_hex, timestamp)
    dm = EncryptedDirectMessage(kind=EventKind.EPHEMERAL_DM)
    dm.encrypt(private_key_hex=sender_privkey_hex,
               cleartext_content=payload_str,
               recipient_pubkey=recipient_pubkey_hex)
    ev = dm.to_event()
    ev.sign(sender_privkey_hex)
    mgr = initialize_client()
    asyncio.run(mgr.prepare_relays())
    asyncio.run(mgr.publish_event(ev))
    asyncio.run(mgr.close_connections())
    return ev.id

def publish_signed_ticket_dm(event_data: dict) -> str:
    """Publish a pre-signed ticket DM event to all relays."""
    _load_app_dependencies()
    ev = Event(
        public_key=event_data.get("pubkey", ""),
        content=event_data.get("content", ""),
        kind=event_data.get("kind", EventKind.EPHEMERAL_DM),
        tags=event_data.get("tags", []),
        created_at=event_data.get("created_at", int(time.time())),
        sig=event_data.get("sig", ""),
        id=event_data.get("id", ""),
    )
    mgr = initialize_client()
    asyncio.run(mgr.prepare_relays())
    asyncio.run(mgr.publish_event(ev))
    asyncio.run(mgr.close_connections())
    return ev.id

def register_ticket_routes(app):
    _load_app_dependencies()
    @app.route('/send_ticket', methods=['POST'])
    @limiter.limit("10 per minute")
    async def send_ticket_endpoint():
        data = request.json or {}
        event_name = data.get('event_name')
        recipient = data.get('recipient_pubkey')
        sender = data.get('sender_privkey')
        ts = data.get('timestamp')
        try:
            if event_name and recipient and sender:
                ev_id = send_ticket_as_dm(event_name, recipient, sender, ts)
            elif 'pubkey' in data and 'id' in data:
                ev_id = publish_signed_ticket_dm(data)
            else:
                return error_response(
                    "Missing fields: event_name, recipient_pubkey, sender_privkey", 400)
            return jsonify({"status": "sent", "event_id": ev_id})
        except Exception as e:
            logger.error(f"Error in send_ticket_endpoint: {e}")
            return error_response(str(e), 500)
