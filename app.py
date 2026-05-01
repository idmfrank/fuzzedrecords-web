# Standard library
from flask import Flask, jsonify, render_template, send_from_directory, redirect, request
from asgiref.wsgi import WsgiToAsgi
from flask_restful import Api
# CORS configuration
from flask_cors import CORS
# Rate limiting
# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Custom storage schemes (register AzureTableStorage)
import azure_storage_limiter

from spark_layer import InMemorySparkLayer, lnurlp_response
# HTTP exception handling
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest, HTTPException
import os
import logging

# Logging setup (must be defined before any logger usage)
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)

# App init
app = Flask(__name__)
# Limit request payload size (e.g. default 1MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH", 1048576))


def configure_cors(flask_app):
    """Configure CORS with an explicit allowlist for credentialed requests.

    Credentialed cross-origin requests are only allowed when
    ``FRONTEND_ORIGINS`` is set to a comma-separated list of trusted
    origins. If the variable is unset, cross-origin credentialed requests are
    disabled entirely instead of falling back to a wildcard.
    """

    origins_env = os.getenv("FRONTEND_ORIGINS", "").strip()
    if origins_env:
        origins = [o.strip() for o in origins_env.split(",") if o.strip()]
        CORS(flask_app, origins=origins, supports_credentials=True)
        logger.info(
            "Credentialed CORS enabled for %d configured origin(s).",
            len(origins),
        )
        return origins, True

    logger.warning(
        "FRONTEND_ORIGINS is not set; credentialed cross-origin requests are "
        "disabled. Set FRONTEND_ORIGINS to explicit trusted origins."
    )
    CORS(flask_app, origins=[], supports_credentials=False)
    return [], False


ALLOWED_CORS_ORIGINS, CORS_CREDENTIALS_ENABLED = configure_cors(app)


def parse_rate_limit_config(env_var: str, default: str | None = None) -> list[str] | None:
    """Parse a semicolon-delimited rate-limit config from the environment."""

    raw_value = os.getenv(env_var, "").strip()
    if raw_value:
        limits = [item.strip() for item in raw_value.split(";") if item.strip()]
        if limits:
            return limits
    return [default] if default else None


DEFAULT_RATE_LIMITS = parse_rate_limit_config("RATELIMIT_DEFAULT", "60 per minute")
APPLICATION_RATE_LIMITS = parse_rate_limit_config("RATELIMIT_APPLICATION")

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
    default_limits=DEFAULT_RATE_LIMITS,
    application_limits=APPLICATION_RATE_LIMITS,
    storage_uri=storage_uri,
    storage_options=storage_options,
)
api = Api(app)
asgi_app = WsgiToAsgi(app)

REQUIRED_DOMAIN = os.getenv("REQUIRED_DOMAIN", "fuzzedrecords.com")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.fuzzedrecords.com")
# Base URL for Wavlake API; can be overridden via environment
# Default updated to use wavlake.com domain as per API docs
WAVLAKE_API_BASE = os.getenv("WAVLAKE_API_BASE", "https://wavlake.com/api/v1")
SEARCH_TERM = os.getenv("SEARCH_TERM", " by Fuzzed Records")
spark = InMemorySparkLayer(REQUIRED_DOMAIN)

def error_response(message, status_code):
    return jsonify({'error': message}), status_code

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
    return render_template('index.html', serverWalletPubkey="")

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


@app.route("/api/wallets", methods=["POST"])
def create_wallet():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    username = data.get("username")
    if not user_id or not username:
        return jsonify({"error": "user_id and username are required"}), 400
    wallet = spark.create_wallet(user_id, username)
    return jsonify({"user_id": wallet.user_id, "spark_address": wallet.spark_address}), 201


@app.route("/api/wallets/<user_id>/balances", methods=["GET"])
def get_balance(user_id):
    try:
        return jsonify(spark.get_balance(user_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/transfers/internal", methods=["POST"])
def internal_transfer():
    data = request.get_json() or {}
    try:
        tx = spark.transfer(
            sender_id=data["sender_user_id"],
            receiver_username=data["receiver_username"],
            amount_sats=int(data["amount_sats"]),
            idempotency_key=data.get("idempotency_key"),
        )
        return jsonify(tx), 201
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/transfers/lightning", methods=["POST"])
def pay_lightning():
    data = request.get_json() or {}
    try:
        tx = spark.pay_lightning_invoice(
            sender_id=data["sender_user_id"],
            invoice=data["invoice"],
            amount_sats=int(data["amount_sats"]),
            max_fee_sats=int(data.get("max_fee_sats", 10)),
        )
        return jsonify(tx), 201
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/.well-known/lnurlp/<username>", methods=["GET"])
def lnurlp(username):
    if not spark.get_wallet_by_username(username):
        return jsonify({"status": "ERROR", "reason": "User not found"}), 404
    return jsonify(lnurlp_response(API_BASE_URL, username))


@app.route("/pay/<username>", methods=["GET"])
def pay_callback(username):
    amount = int(request.args.get("amount", "0"))
    wallet = spark.get_wallet_by_username(username)
    if not wallet:
        return jsonify({"status": "ERROR", "reason": "User not found"}), 404
    if amount <= 0:
        return jsonify({"status": "ERROR", "reason": "Invalid amount"}), 400
    invoice = f"lnbc{amount}n1p{username}mockinvoice"
    return jsonify({"pr": invoice, "routes": []})


if __name__ == '__main__':
    # Toggle debug via FLASK_DEBUG env var
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode)
