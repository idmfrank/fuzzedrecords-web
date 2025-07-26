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

# NIP-19 decoding helpers
try:
    from pynostr.utils import nprofile_decode, nprofile_encode
except Exception:  # pragma: no cover - fallback if module missing
    def nprofile_decode(value):
        raise NotImplementedError("nprofile decode not available")

    def nprofile_encode(pubkey, relays):
        raise NotImplementedError("nprofile encode not available")
# NIP-19 decoding
try:
    from pynostr.nip19 import decode as nip19_decode
except Exception:  # pragma: no cover - fallback if module missing
    def nip19_decode(value):
        raise NotImplementedError("nip19 decode not available")
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
RELAY_URLS = os.getenv(
    "RELAY_URLS",
    "wss://relay.damus.io,wss://relay.primal.net,wss://relay.mostr.pub"
).split(',')
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", 300))
REQUIRED_DOMAIN = os.getenv("REQUIRED_DOMAIN", "fuzzedrecords.com")
# Base URL for Wavlake API; can be overridden via environment
# Default updated to use wavlake.com domain as per API docs
WAVLAKE_API_BASE = os.getenv("WAVLAKE_API_BASE", "https://wavlake.com/api/v1")
SEARCH_TERM = " by Fuzzed Records"

# Logging setup
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)

# Utilities: error responses, caching, and Nostr relay client
import time
from flask import jsonify
from pynostr.relay_manager import RelayManager

# Simple in-memory cache for user profiles
_cache = {}
def get_cached_item(key):
    item = _cache.get(key)
    if not item:
        return None
    value, ts = item
    if time.time() - ts > CACHE_TIMEOUT:
        del _cache[key]
        return None
    return value

def set_cached_item(key, value):
    _cache[key] = (value, time.time())

def error_response(message, status_code):
    return jsonify({'error': message}), status_code

def initialize_client():
    # Initialize Nostr RelayManager and add configured relays
    mgr = RelayManager()
    for url in RELAY_URLS:
        mgr.add_relay(url)
    return mgr

# Helper to fetch a profile event (kind 0) by pubkey from given relays
def fetch_profile_by_pubkey(pubkey, relays):
    from pynostr.relay_manager import RelayManager
    from pynostr.message_type import ClientMessageType
    from pynostr.filter import Filter
    import time
    import json

    manager = RelayManager()
    for r in relays:
        manager.add_relay(r)
    manager.open_connections({"cert_reqs": 0})
    time.sleep(1.25)

    sub_id = "profile_sub"
    filt = Filter(authors=[pubkey], kinds=[0])
    req = json.dumps([ClientMessageType.REQUEST, sub_id, filt.to_json()])
    manager.publish_message_to_all(req)
    time.sleep(2)

    metadata = None
    for event in manager.message_pool.get_events():
        try:
            metadata = json.loads(event.content)
            break
        except Exception:
            continue

    manager.close_connections()
    return metadata
 
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
register_wavlake_routes(app)
register_ticket_routes(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/', subdomain='fuzzedguitars')
def guitars_redirect():
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


# Endpoint to fetch metadata by nprofile (NIP-19)
@app.route('/fetch-nprofile', methods=['POST'])
def fetch_nprofile():
    data = request.get_json()
    nprofile = data.get('nprofile') if data else None

    if not nprofile:
        return jsonify({'error': 'Missing nprofile'}), 400

    try:
        pubkey, relays = nprofile_decode(nprofile)
        if not pubkey:
            return jsonify({'error': 'Invalid nprofile'}), 400

        if not relays:
            relays = [
                'wss://relay.damus.io',
                'wss://nos.lol',
                'wss://relay.nostr.band'
            ]
        type_, nprofile_data = nip19_decode(nprofile)
        if type_ != 'nprofile':
            return jsonify({'error': 'Invalid nprofile type'}), 400

        pubkey = nprofile_data['pubkey']
        relays = nprofile_data.get('relays', [
            'wss://relay.damus.io',
            'wss://nos.lol',
            'wss://relay.nostr.band'
        ])

        metadata = fetch_profile_by_pubkey(pubkey, relays)

        return jsonify({'pubkey': pubkey, 'metadata': metadata})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Toggle debug via FLASK_DEBUG env var
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode)
