import json, time, asyncio
from flask import request, jsonify
from app import (
    app,
    error_response,
    get_cached_item,
    set_cached_item,
    relay_manager,
    logger,
    REQUIRED_DOMAIN,
    ACTIVE_RELAYS,
    PROFILE_FETCH_TIMEOUT,
)
from nostr_client import (
    nprofile_encode,
    EventKind,
    Filter as Filters,
    FiltersList,
    EncryptedDirectMessage,
)

def require_nip05_verification(required_domain):
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data = request.json or {}
            pubkey = data.get("pubkey")
            if not pubkey:
                return jsonify({"error": "Missing pubkey"}), 400
            valid = asyncio.run(fetch_and_validate_profile(pubkey, required_domain))
            if not valid:
                logger.warning(f"NIP-05 failed for {pubkey}")
                return jsonify({"error": "NIP-05 verification failed"}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator

async def fetch_profile():
    data = request.json or {}
    logger.debug("fetch_profile called with data: %s", data)
    pubkey_hex = data.get('pubkey')
    if not pubkey_hex:
        logger.warning("fetch_profile missing pubkey in request: %s", data)
        return error_response("Missing pubkey", 400)
    cached = get_cached_item(pubkey_hex)
    if cached:
        logger.debug("Returning cached profile for pubkey %s", pubkey_hex)
        return jsonify(cached)

    nprof = None
    try:
        from app import ACTIVE_RELAYS
        nprof = nprofile_encode(pubkey_hex, ACTIVE_RELAYS)
    except Exception as e:
        logger.warning("nprofile encode failed: %s", e)
    async with relay_manager() as mgr:
        logger.debug("Initializing RelayManager for profile fetch of %s", pubkey_hex)
        statuses = getattr(mgr, "connection_statuses", {})
        if statuses and not any(statuses.values()):
            logger.error("Unable to connect to any Nostr relays: %s", statuses)
            return error_response("Unable to connect to Nostr relays", 503)
        filt = FiltersList([Filters(authors=[pubkey_hex], kinds=[EventKind.SET_METADATA], limit=1)])
        sub_id = f"fetch_{pubkey_hex}"
        await mgr.add_subscription_on_all_relays(sub_id, filt)
        logger.debug("Awaiting profile event for pubkey %s", pubkey_hex)

        profile_data = {}
        start = time.time()
        while time.time() - start < PROFILE_FETCH_TIMEOUT:
            if mgr.message_pool.has_events():
                msg = mgr.message_pool.get_event()
                if msg.subscription_id == sub_id:
                    ev = msg.event
                    logger.debug("fetch_profile received event: %s", ev)
                    try:
                        content = json.loads(ev.content)
                    except Exception as e:
                        logger.error("Error parsing event content: %s", e)
                        content = None
                    if content is not None:
                        profile_data = {"id": ev.id, "pubkey": ev.public_key, "content": content}
                        if nprof:
                            profile_data["nprofile"] = nprof
                        logger.info("Profile data parsed for pubkey %s: %s", pubkey_hex, content)
                    break
            if mgr.message_pool.has_eose_notices():
                notice = mgr.message_pool.get_eose_notice()
                if notice.subscription_id == sub_id:
                    # Ignore EOSE and continue waiting
                    continue
            await asyncio.sleep(0.05)
    if profile_data:
        if nprof and "nprofile" not in profile_data:
            profile_data["nprofile"] = nprof
        set_cached_item(pubkey_hex, profile_data)
        logger.debug("Caching profile for %s", pubkey_hex)
        return jsonify(profile_data)
    logger.warning("No profile found for pubkey %s after fetch", pubkey_hex)
    return error_response("Profile not found", 404)

async def fetch_and_validate_profile(pubkey, required_domain):
    cached = get_cached_item(pubkey)
    if cached is not None:
        data = cached.get("content", cached) if isinstance(cached, dict) else {}
        nip05 = data.get("nip05") if isinstance(data, dict) else None
        if not nip05 or "@" not in nip05:
            return False
        domain = nip05.split("@", 1)[1]
        return domain == required_domain

    async with relay_manager() as mgr:
        filt = FiltersList([
            Filters(authors=[pubkey], kinds=[EventKind.SET_METADATA], limit=1)
        ])
        await mgr.add_subscription_on_all_relays(f"val_{pubkey}", filt)
        await asyncio.sleep(1)

        profile_data = {}
        for msg in mgr.message_pool.get_all_events():
            ev = msg.event
            try:
                profile_data = json.loads(ev.content)
            except Exception:
                continue
            break

    if not profile_data:
        return False

    set_cached_item(pubkey, profile_data)

    nip05 = profile_data.get("nip05")
    if not nip05 or "@" not in nip05:
        return False
    domain = nip05.split("@", 1)[1]
    return domain == required_domain

@app.route("/fetch-profile", methods=["POST"])
def _fetch_profile():
    return asyncio.run(fetch_profile())

@app.route('/validate-profile', methods=['POST'])
def _validate_profile():
    data = request.json or {}
    pubkey = data.get('pubkey')
    if not pubkey:
        return jsonify({"error":"Missing pubkey"}), 400
    valid = asyncio.run(fetch_and_validate_profile(pubkey, REQUIRED_DOMAIN))
    if valid:
        return jsonify({"status":"valid"})
    return jsonify({"error":"Profile validation failed"}), 403
 
async def _send_dm_async(to_pubkey: str, content: str, sender_privkey: str):
    dm = EncryptedDirectMessage()
    dm.encrypt(
        private_key_hex=sender_privkey,
        cleartext_content=content,
        recipient_pubkey=to_pubkey,
    )
    ev = dm.to_event()
    ev.sign(sender_privkey)
    async with relay_manager() as mgr:
        await mgr.publish_event(ev)
        await asyncio.sleep(0.5)


@app.route('/send_dm', methods=['POST'])
def _send_dm():
    data = request.json or {}
    required = ['to_pubkey', 'content', 'sender_privkey']
    if not all(k in data for k in required):
        return error_response("Missing DM fields", 400)

    asyncio.run(
        _send_dm_async(
            to_pubkey=data['to_pubkey'],
            content=data['content'],
            sender_privkey=data['sender_privkey'],
        )
    )
    return jsonify({"message": "DM sent successfully"})
