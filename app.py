# Standard library
import threading
from flask import Flask, jsonify, render_template, send_from_directory, redirect, request
from flask_restful import Api
# CORS configuration
from flask_cors import CORS
# Rate limiting
# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Custom storage schemes (register AzureTableStorage)
import azure_storage_limiter

# NIP-19 helpers provided by our minimal Nostr client implementation
from nostr_client import (
    nprofile_decode,
    nprofile_encode,
    RelayManager,
    Filter,
    FiltersList,
    derive_public_key_hex,
    nsec_to_hex,
)

def nip19_decode(value: str):
    """Alias for ``nprofile_decode`` to match prior API."""
    return nprofile_decode(value)
# HTTP exception handling
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest, HTTPException
import os
import logging

# App init
app = Flask(__name__)
# Limit request payload size (e.g. default 1MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH", 1048576))
# Configure CORS origins from environment (comma-separated). Fallback to '*' if not set.
origins_env = os.getenv("FRONTEND_ORIGINS", "").strip()
if origins_env:
    origins = [o.strip() for o in origins_env.split(",") if o.strip()]
else:
    origins = ["*"]
CORS(app, origins=origins, supports_credentials=True)
# Rate limiting (IP-based)
# Configure Flask-Limiter storage backend via URI and options
storage_options = {}
azure_conn = os.getenv("AZURE_TABLES_CONNECTION_STRING")
if azure_conn:
    # Use our AzureTableStorage scheme (must set RATELIMIT_STORAGE_URI to 'azuretables://')
    storage_uri = "azuretables://"
    storage_options["connection_string"] = azure_conn
    storage_options["table_name"] = os.getenv("RATELIMIT_TABLE_NAME", "RateLimit")
else:
    # Fallback to environment URI or in-memory
    storage_uri = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
# Initialize limiter with storage settings
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=storage_uri,
    storage_options=storage_options,
)
api = Api(app)

# Configuration
RELAY_URLS = [
    u.strip()
    for u in os.getenv(
        "RELAY_URLS",
        "wss://relay.damus.io,wss://relay.primal.net,wss://relay.nostr.pub,wss://nos.lol",
    ).split(",")
]
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", 300))
REQUIRED_DOMAIN = os.getenv("REQUIRED_DOMAIN", "fuzzedrecords.com")
# Base URL for Wavlake API; can be overridden via environment
# Default updated to use wavlake.com domain as per API docs
WAVLAKE_API_BASE = os.getenv("WAVLAKE_API_BASE", "https://wavlake.com/api/v1")
SEARCH_TERM = os.getenv("SEARCH_TERM", " by Fuzzed Records")
PROFILE_FETCH_TIMEOUT = float(os.getenv("PROFILE_FETCH_TIMEOUT", "5"))
RELAY_CONNECT_TIMEOUT = float(os.getenv("RELAY_CONNECT_TIMEOUT", "2"))
DISABLE_TLS_VERIFY = os.getenv("DISABLE_TLS_VERIFY", "0").lower() in {"1", "true", "yes"}

_privkey_env = os.getenv("WALLET_PRIVKEY_HEX", "").strip()
if _privkey_env.startswith("nsec"):
    try:
        WALLET_PRIVKEY_HEX = nsec_to_hex(_privkey_env)
    except Exception:
        logger.error("Invalid nsec key provided for WALLET_PRIVKEY_HEX")
        WALLET_PRIVKEY_HEX = ""
else:
    WALLET_PRIVKEY_HEX = _privkey_env

SERVER_WALLET_PUBKEY = (
    derive_public_key_hex(WALLET_PRIVKEY_HEX) if WALLET_PRIVKEY_HEX else ""
)

# Comma-separated list of pubkeys allowed to publish calendar events. If unset,
# a local cache file specified by IDENTITIES_CACHE (default 'azure_identities.json')
# is read when present.
def load_valid_pubkeys():
    env_val = os.getenv("VALID_PUBKEYS", "").strip()
    if env_val:
        return [p.strip() for p in env_val.split(",") if p.strip()]
    cache_file = os.getenv("IDENTITIES_CACHE", "azure_identities.json")
    if os.path.exists(cache_file):
        try:
            import json
            with open(cache_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                return [p for p in data if isinstance(p, str)]
            if isinstance(data, dict):
                # Expect structure from azure_resources {"names": {name: pubkey}}
                if "names" in data and isinstance(data["names"], dict):
                    return [pk for pk in data["names"].values() if isinstance(pk, str)]
        except Exception as e:
            logger.warning("Failed to load identities cache %s: %s", cache_file, e)
    return []

VALID_PUBKEYS = load_valid_pubkeys()

# Logging setup
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)

# Active relay list loaded from files/environment
RELAYS_LOCK = threading.Lock()

def load_relays_from_file():
    """Load relay URLs from good-relays.txt, relays.txt or RELAY_URLS env."""
    for fname in ("good-relays.txt", "relays.txt"):
        if os.path.exists(fname):
            with open(fname) as f:
                rels = [l.strip() for l in f if l.strip()]
            if rels:
                return rels
    # Fallback to the module constant if the environment variable isn't set
    return [
        u.strip()
        for u in os.getenv("RELAY_URLS", ",".join(RELAY_URLS)).split(",")
        if u.strip()
    ]

# Initialize at startup
ACTIVE_RELAYS = load_relays_from_file()

# Utilities: error responses, caching, and Nostr relay client
import time
from flask import jsonify
import asyncio
from contextlib import asynccontextmanager
from nostr_client import RelayManager, Filter, MessagePool

# Protect in-memory cache access
_cache_lock = threading.Lock()

# Simple in-memory cache for user profiles
_cache = {}
def get_cached_item(key):
    with _cache_lock:
        item = _cache.get(key)
    if not item:
        return None
    value, ts = item
    if time.time() - ts > CACHE_TIMEOUT:
        with _cache_lock:
            del _cache[key]
        return None
    return value

def set_cached_item(key, value):
    with _cache_lock:
        _cache[key] = (value, time.time())

def error_response(message, status_code):
    return jsonify({'error': message}), status_code

# Relay manager pool
_manager_pool = []
_pool_lock = asyncio.Lock()

async def get_relay_manager():
    """Borrow a RelayManager from the pool.

    Websocket connections in ``RelayManager`` instances are bound to the
    event loop that created them.  Previous changes reused managers across
    ``asyncio.run`` calls which each spin up a new loop, leaving those
    connections unusable.  To ensure we always have connections tied to the
    current loop, relays are (re)prepared every time a manager is borrowed
    from the pool, even if it was previously returned.
    """

    async with _pool_lock:
        if _manager_pool:
            mgr = _manager_pool.pop()
        else:
            mgr = RelayManager(timeout=RELAY_CONNECT_TIMEOUT)
        for url in ACTIVE_RELAYS:
            if url not in mgr.relays:
                mgr.add_relay(url)
    await mgr.prepare_relays()
    return mgr

async def release_relay_manager(mgr):
    """Return ``mgr`` to the pool, closing any open connections.

    Closing the websocket connections avoids reusing them across different
    event loops which previously resulted in dead relays and missing profile
    data.  Each borrow will reconnect as needed.
    """
    if mgr is None:
        return
    await mgr.close_connections()
    mgr.message_pool = MessagePool()
    async with _pool_lock:
        _manager_pool.append(mgr)

@asynccontextmanager
async def relay_manager():
    mgr = await get_relay_manager()
    try:
        yield mgr
    finally:
        await release_relay_manager(mgr)

async def close_relay_managers():
    """Close all RelayManager connections and clear the pool."""
    async with _pool_lock:
        managers = list(_manager_pool)
        _manager_pool.clear()
    for mgr in managers:
        await mgr.close_connections()

_pool_started = False

@app.before_request
def _startup_pool():
    global _pool_started
    if not _pool_started:
        mgr = asyncio.run(get_relay_manager())
        asyncio.run(release_relay_manager(mgr))
        _pool_started = True

import atexit

@atexit.register
def _shutdown_pool():
    asyncio.run(close_relay_managers())

# Helper to fetch a profile event (kind 0) by pubkey from given relays
def fetch_profile_by_pubkey(pubkey, relays):
    import json
    import asyncio

    manager = RelayManager(timeout=RELAY_CONNECT_TIMEOUT)
    for r in relays:
        manager.add_relay(r)

    async def _run():
        await manager.prepare_relays()
        sub_id = "profile_sub"
        await manager.add_subscription_on_all_relays(sub_id, FiltersList([Filter(authors=[pubkey], kinds=[0])]))
        profile = None
        start = time.time()
        try:
            while time.time() - start < PROFILE_FETCH_TIMEOUT:
                if manager.message_pool.has_events():
                    msg = manager.message_pool.get_event()
                    if msg.subscription_id == sub_id:
                        try:
                            profile = json.loads(msg.event.content)
                        except Exception:
                            profile = None
                        break
                if manager.message_pool.has_eose_notices():
                    notice = manager.message_pool.get_eose_notice()
                    if notice.subscription_id == sub_id:
                        continue
                await asyncio.sleep(0.1)
        finally:
            await manager.close_connections()
        return profile

    return asyncio.run(_run())
 
# Centralized error handlers
@app.errorhandler(RequestEntityTooLarge)
def handle_payload_too_large(e):
    return jsonify({"error": "Payload too large"}), 413

@app.errorhandler(BadRequest)
def handle_bad_request_error(e):
    return jsonify({"error": "Bad request"}), 400

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    logger.error(f"Unhandled exception: {e}", exc_info=e)
    return jsonify({"error": "Internal server error"}), code

# Register modular routes
from azure_resources import register_resources
from wavlake_utils import register_wavlake_routes
from ticket_utils import register_ticket_routes
import nostr_utils  # registers Nostr routes

register_resources(api)
register_wavlake_routes(
    app,
    base_url=WAVLAKE_API_BASE,
    search_term=SEARCH_TERM,
    error_handler=error_response,
)
register_ticket_routes(app)

@app.route('/')
def index():
    pubkey = SERVER_WALLET_PUBKEY
    return render_template('index.html', serverWalletPubkey=pubkey)

@app.route('/', subdomain='fuzzedguitars')
def guitars_redirect():
    return redirect('https://fuzzedrecords.com/#gear', code=301)

# Allow path-based access (e.g., /fuzzedguitars) for convenience
@app.route('/fuzzedguitars')
def guitars_redirect_path():
    return redirect('https://fuzzedrecords.com/#gear', code=301)
    
# Health check for uptime probes (e.g. random /robotsXYZ.txt)
@app.route('/robots<filename>.txt')
def robots_txt(filename):
    # Return 200 to satisfy health checks
    return ('', 200)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


@app.route('/update-relays', methods=['POST'])
def update_relays():
    data = request.get_json() or {}
    relays = data.get('relays')
    if not relays or not isinstance(relays, list):
        return jsonify({'error': 'Invalid relays'}), 400
    relays = [r.strip() for r in relays if isinstance(r, str) and r.strip()]
    from urllib.parse import urlparse
    for url in relays:
        parsed = urlparse(url)
        if parsed.scheme not in ('ws', 'wss'):
            return jsonify({'error': f'Invalid relay URL: {url}'}), 400
    with RELAYS_LOCK:
        merged = set(ACTIVE_RELAYS)
        merged.update(relays)
        ACTIVE_RELAYS[:] = sorted(merged)
        with open('relays.txt', 'w') as f:
            for url in ACTIVE_RELAYS:
                f.write(url + '\n')

    return jsonify({'status': 'updated', 'count': len(ACTIVE_RELAYS)})


# Endpoint to fetch metadata by nprofile (NIP-19)
@app.route('/fetch-nprofile', methods=['POST'])
def fetch_nprofile():
    data = request.get_json()
    nprofile = data.get('nprofile') if data else None

    if not nprofile:
        return jsonify({'error': 'Missing nprofile'}), 400

    try:
        default_relays = [
            'wss://relay.damus.io',
            'wss://nos.lol',
            'wss://relay.nostr.band'
        ]

        type_, data = nip19_decode(nprofile)
        if type_ != 'nprofile':
            return jsonify({'error': 'Invalid nprofile type'}), 400
        pubkey = data['pubkey']
        relays = data.get('relays', default_relays)

        metadata = fetch_profile_by_pubkey(pubkey, relays)

        return jsonify({'pubkey': pubkey, 'metadata': metadata})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Toggle debug via FLASK_DEBUG env var
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode)
