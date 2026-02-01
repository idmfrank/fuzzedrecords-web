#!/bin/bash
set -e

# Remove any stale local copies of coincurve that could shadow the installed package
rm -rf coincurve

# Install Python dependencies (ensures msal, hypercorn, coincurve, and other packages are available)
pip install --no-cache-dir -r requirements.txt || {
    echo "Error: Failed to install dependencies." >&2
    exit 1
}

# Reinstall coincurve to ensure native extension is present
pip install --no-cache-dir --force-reinstall coincurve || {
    echo "Error: Failed to reinstall coincurve." >&2
    exit 1
}

# Launch Hypercorn ASGI server
exec hypercorn --bind 0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    app:asgi_app
