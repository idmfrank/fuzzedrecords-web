import time, json, asyncio, os, binascii, base64, re
from io import BytesIO
import qrcode
from flask import request, jsonify
from nacl.exceptions import CryptoError

# These imports create circular dependencies when this module is imported
# during testing. Import them lazily inside the functions that require them.
from flask import current_app

relay_manager = None
error_response = None
logger = None
limiter = None
wallet_priv_hex = None
from nostr_client import (
    EncryptedDirectMessage,
    EventKind,
    Event,
    nip44_decrypt,
    build_nip47_response,
)


def _load_app_dependencies():
    """Lazy import objects from app to avoid circular imports during testing."""
    global relay_manager, error_response, logger, limiter, wallet_priv_hex
    if relay_manager is None:
        from app import (
            relay_manager as rm,
            error_response as er,
            logger as lg,
            limiter as lm,
            WALLET_PRIVKEY_HEX as wph,
        )
        relay_manager = rm
        error_response = er
        logger = lg
        limiter = lm
        wallet_priv_hex = wph

def generate_ticket(event_name: str, user_pubkey: str, timestamp: int = None):
    ts = timestamp if timestamp is not None else int(time.time())
    payload = {"event": event_name, "pubkey": user_pubkey, "timestamp": ts}
    payload_str = json.dumps(payload)
    qr_img = qrcode.make(payload_str)
    img_io = BytesIO()
    qr_img.save(img_io, 'PNG')
    img_io.seek(0)
    return payload_str, img_io

async def send_ticket_as_dm(event_name: str, recipient_pubkey_hex: str,
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
    async with relay_manager() as mgr:
        await mgr.publish_event(ev)
    return ev.id

async def publish_signed_ticket_dm(event_data: dict) -> str:
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
    async with relay_manager() as mgr:
        await mgr.publish_event(ev)
    return ev.id

def register_ticket_routes(app):
    _load_app_dependencies()
    @app.route("/send_ticket", methods=["POST"])
    @limiter.limit("10 per minute")
    def send_ticket_endpoint():
        data = request.json or {}

        req_id = data.get("id")
        sender_pub = data.get("pubkey")
        cipher = data.get("content")
        if not (req_id and sender_pub and cipher):
            return error_response("Missing event fields", 400)

        wallet_priv = wallet_priv_hex
        if not wallet_priv:
            return error_response("Server wallet not configured", 500)

        if not re.fullmatch(r"[0-9a-fA-F]{64}", sender_pub):
            return error_response("Invalid pubkey", 400)

        try:
            base64.b64decode(cipher, validate=True)
        except (ValueError, binascii.Error):
            return error_response("Invalid encrypted payload", 400)

        try:
            plain = nip44_decrypt(wallet_priv, sender_pub, cipher)
            payload = json.loads(plain)
            method = payload.get("method")
            params = payload.get("params", {})
            resp_id = payload.get("id") or req_id

            if method != "ticket.create":
                return error_response("Unsupported method", 400)

            event_name = params.get("event_name")
            timestamp = params.get("timestamp")
            recipient_pub = params.get("pubkey") or sender_pub

            if not event_name:
                return error_response("Missing event_name", 400)

            asyncio.run(send_ticket_as_dm(event_name, recipient_pub, wallet_priv, timestamp))

            resp_payload = {"result": "ok", "id": resp_id}
            resp_event = build_nip47_response(wallet_priv, sender_pub, resp_payload)
            resp_event.tags.append(["e", req_id])

            async def publish_response():
                async with relay_manager() as mgr:
                    await mgr.publish_event(resp_event)

            asyncio.run(publish_response())

            return jsonify({"status": "sent", "event_id": resp_event.id})
        except (ValueError, binascii.Error, CryptoError) as e:
            logger.warning(
                "Invalid encrypted payload: id=%s pubkey=%s ip=%s error=%s",
                req_id,
                sender_pub,
                request.remote_addr,
                e,
            )
            return error_response("Invalid encrypted payload", 400)
        except Exception as e:
            logger.error(f"Error in send_ticket_endpoint: {e}")
            return error_response(str(e), 500)
