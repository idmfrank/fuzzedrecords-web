# Standard library
from flask import Flask, jsonify, render_template, send_from_directory, redirect
from asgiref.wsgi import WsgiToAsgi
# CORS configuration
from flask_cors import CORS
# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Custom storage schemes (register AzureTableStorage)
import azure_storage_limiter

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
asgi_app = WsgiToAsgi(app)

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/', subdomain='fuzzedguitars')
def guitars_redirect():
    return redirect('https://fuzzedrecords.com/', code=301)

# Allow path-based access (e.g., /fuzzedguitars) for convenience
@app.route('/fuzzedguitars')
def guitars_redirect_path():
    return redirect('https://fuzzedrecords.com/', code=301)
    
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
