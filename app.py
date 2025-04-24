from flask import Flask, jsonify, render_template, send_from_directory
from flask_restful import Api
from flask_cors import CORS
import os, logging

# App initialization
app = Flask(__name__)
CORS(app)
api = Api(app)

# Configuration constants
RELAY_URLS = os.getenv(
    "RELAY_URLS",
    "wss://relay.damus.io,wss://relay.primal.net,wss://relay.mostr.pub"
).split(',')
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", 300))
REQUIRED_DOMAIN = os.getenv("REQUIRED_DOMAIN", "fuzzedrecords.com")
WAVLAKE_API_BASE = "https://wavlake.com/api/v1"
SEARCH_TERM = " by Fuzzed Records"

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Register modular resources and routes
from azure_resources import register_resources
from wavlake_utils import register_wavlake_routes
from ticket_utils import register_ticket_routes
import nostr_utils  # side-effect: registers Nostr routes

register_resources(api)
register_wavlake_routes(app)
register_ticket_routes(app)

# Static page endpoints
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