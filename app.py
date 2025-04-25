from flask import Flask, jsonify, render_template, send_from_directory
from flask_restful import Api
# CORS configuration
from flask_cors import CORS
# Rate limiting
# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Custom storage schemes (register AzureTableStorage)
import azure_storage_limiter
# HTTP exception handling
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest, HTTPException
import os
import logging

# App init
app = Flask(__name__)
# Limit request payload size (e.g. default 1MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH", 1048576))
# Configure CORS origins from environment (comma-separated)
frontend_origins = [o for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o]
CORS(app, origins=frontend_origins, supports_credentials=True)
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
WAVLAKE_API_BASE = os.getenv("WAVLAKE_API_BASE", "https://api.wavlake.com/api/v1")
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


if __name__ == '__main__':
    # Toggle debug via FLASK_DEBUG env var
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode)