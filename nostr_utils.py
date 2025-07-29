import os, json, time, asyncio, logging
from flask import request, jsonify
from app import (
    app,
    error_response,
    get_cached_item,
    set_cached_item,
    initialize_client,
    logger,
    REQUIRED_DOMAIN,
    ACTIVE_RELAYS,
    PROFILE_FETCH_TIMEOUT,
)
from nostr_client import (
    nprofile_encode,
    Event,
    EventKind,
    Filter as Filters,
    FiltersList,
    EncryptedDirectMessage,
)

def require_nip05_verification(required_domain):
    from functools import wraps
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            data = request.json or {}
            pubkey = data.get('pubkey')
            if not pubkey:
                return jsonify({"error":"Missing pubkey"}), 400
            valid = await fetch_and_validate_profile(pubkey, required_domain)
            if not valid:
                logger.warning(f"NIP-05 failed for {pubkey}")
                return jsonify({"error":"NIP-05 verification failed"}), 403
            return await func(*args, **kwargs)
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
    mgr = initialize_client()
    logger.debug("Initializing RelayManager for profile fetch of %s", pubkey_hex)
    # Asynchronously connect to relays
    try:
        logger.debug("Preparing relay connections via prepare_relays()")
        await mgr.prepare_relays()
        logger.debug("RelayManager connections prepared")
    except Exception as e:
        logger.error("Error preparing relay connections: %s", e)

    statuses = getattr(mgr, "connection_statuses", {})
    if statuses and not any(statuses.values()):
        logger.error("Unable to connect to any Nostr relays: %s", statuses)
        return error_response("Unable to connect to Nostr relays", 503)
    filt = FiltersList([Filters(authors=[pubkey_hex], kinds=[EventKind.SET_METADATA], limit=1)])
    sub_id = f"fetch_{pubkey_hex}"
    await mgr.add_subscription_on_all_relays(sub_id, filt)
    logger.debug("Awaiting profile event for pubkey %s", pubkey_hex)

    async def wait_for_message():
        """Wait until an event or EOSE for this subscription arrives."""
        while True:
            if mgr.message_pool.has_events():
                msg = mgr.message_pool.get_event()
                if msg.subscription_id == sub_id:
                    return ("event", msg)
            if mgr.message_pool.has_eose_notices():
                notice = mgr.message_pool.get_eose_notice()
                if notice.subscription_id == sub_id:
                    return ("eose", None)
            await asyncio.sleep(0.05)

    try:
        msg_type, msg = await asyncio.wait_for(wait_for_message(), timeout=PROFILE_FETCH_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("Timeout waiting for profile event for %s", pubkey_hex)
        mgr.close_connections()
        return error_response("Profile not found", 404)
    profile_data = {}
    if msg_type == "event":
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
    mgr.close_connections()
    if profile_data:
        if nprof and "nprofile" not in profile_data:
            profile_data["nprofile"] = nprof
        set_cached_item(pubkey_hex, profile_data)
        logger.debug("Caching profile for %s", pubkey_hex)
        return jsonify(profile_data)
    logger.warning("No profile found for pubkey %s after fetch", pubkey_hex)
    return error_response("Profile not found", 404)

async def fetch_and_validate_profile(pubkey, required_domain):
    mgr = initialize_client()
    # Establish WebSocket connections before subscribing
    await mgr.prepare_relays()
    filt = FiltersList([
        Filters(authors=[pubkey], kinds=[EventKind.SET_METADATA], limit=1)
    ])
    await mgr.add_subscription_on_all_relays(f"val_{pubkey}", filt)
    await asyncio.sleep(1)
    profile_data = {}
    for msg in mgr.message_pool.get_all_events():
        ev = msg.event
        try: profile_data = json.loads(ev.content)
        except: continue
        break
    mgr.close_connections()
    if not profile_data:
        return False
    nip05 = profile_data.get('nip05')
    if not nip05 or '@' not in nip05:
        return False
    domain = nip05.split('@',1)[1]
    return domain == required_domain

@app.route('/fetch-profile', methods=['POST'])
async def _fetch_profile():
    return await fetch_profile()

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

@app.route('/create_event', methods=['POST'])
@require_nip05_verification(REQUIRED_DOMAIN)
async def _create_event():
    data = request.json or {}
    ev = Event(public_key=data.get('pubkey'), content=data.get('content',''),
               kind=EventKind(data.get('kind',1)), tags=data.get('tags',[]),
               created_at=data.get('created_at', int(time.time())))
    ev.sig = data.get('sig')
    if not ev.verify():
        return error_response("Invalid signature", 403)
    mgr = initialize_client()
    mgr.publish_event(ev)
    mgr.close_connections()
    return jsonify({"message":"Event successfully broadcasted"})

@app.route('/fuzzed_events', methods=['GET'])
async def _get_fuzzed_events():
    mgr = initialize_client()
    filt = FiltersList([Filters(kinds=[52])])
    await mgr.add_subscription_on_all_relays('fuzzed', filt)
    await asyncio.sleep(1)
    results = []
    seen = set()
    for msg in mgr.message_pool.get_all_events():
        ev = msg.event
        if ev.public_key in seen: continue
        seen.add(ev.public_key)
        if await fetch_and_validate_profile(ev.public_key, REQUIRED_DOMAIN):
            results.append({
                'id':ev.id, 'pubkey':ev.public_key,
                'content':ev.content, 'tags':ev.tags,
                'created_at':ev.created_at
            })
    mgr.close_connections()
    return jsonify({'events':results})

@app.route('/send_dm', methods=['POST'])
async def _send_dm():
    data = request.json or {}
    required = ['to_pubkey','content','sender_privkey']
    if not all(k in data for k in required):
        return error_response("Missing DM fields", 400)
    dm = EncryptedDirectMessage()
    dm.encrypt(private_key_hex=data['sender_privkey'],
               cleartext_content=data['content'],
               recipient_pubkey=data['to_pubkey'])
    ev = dm.to_event()
    ev.sign(data['sender_privkey'])
    mgr = initialize_client()
    mgr.publish_event(ev)
    mgr.close_connections()
    return jsonify({"message":"DM sent successfully"})
