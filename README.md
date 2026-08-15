# Fuzzed Records

Fuzzed Records is a simple independent music hub for noisy, guitar-driven music from the edges. The public site offers a low-friction SoundCloud listening experience, project updates, and straightforward ways to help the artists reach more listeners.

## Features

- Responsive, SoundCloud-first homepage
- Sections for listening, artist support, future bands, and project information
- Flask backend served through Hypercorn
- Configurable CORS allowlist
- IP-based rate limiting with optional Azure Table Storage persistence
- Legacy `/fuzzedguitars` redirect

## Requirements

- Python 3.11 or newer
- The packages listed in `requirements.txt`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The development server uses Flask's default address. For a production-style local run:

```bash
hypercorn --bind 0.0.0.0:8000 app:asgi_app
```

## Configuration

- `MAX_CONTENT_LENGTH`: Maximum request payload size in bytes; defaults to `1048576`.
- `FRONTEND_ORIGINS`: Comma-separated list of trusted origins. Credentialed cross-origin requests are disabled when unset.
- `AZURE_TABLES_CONNECTION_STRING`: Optional Azure connection string for persistent rate-limit storage.
- `RATELIMIT_TABLE_NAME`: Azure table name; defaults to `RateLimit`.
- `RATELIMIT_DEFAULT`: Semicolon-separated default per-route limits; defaults to `60 per minute`.
- `RATELIMIT_APPLICATION`: Optional semicolon-separated application-wide limits.
- `RATELIMIT_AZURE_RETRIES`: Retry count for concurrent Azure counter updates; defaults to `5`.
- `RATELIMIT_STORAGE_URI`: Alternate limiter storage URI; defaults to `memory://`.
- `LOG_LEVEL`: Application log level; defaults to `DEBUG`.
- `FLASK_DEBUG`: Set to `1`, `true`, or `yes` to enable local debug mode.

## Tests

```bash
pytest -q
```

## Container build

```bash
docker build -t fuzzedrecords .
docker run --rm -p 8000:8000 fuzzedrecords
```

The site will be available at `http://localhost:8000`.

## Project structure

```text
app.py                     Flask application and routes
azure_storage_limiter.py   Azure-backed rate-limit storage
requirements.txt           Python dependencies
startup.sh                 Production startup script
templates/index.html       Homepage markup
static/style.css           Site styles
static/scripts/utils.js    Navigation behavior
tests/                     Automated tests
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
