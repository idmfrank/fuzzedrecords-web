from flask import Flask, jsonify, render_template, send_from_directory
from flask_restful import Api
from flask_cors import CORS
import os
import logging

# App init
app = Flask(__name__)
CORS(app)
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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    app.run(debug=True)