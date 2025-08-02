#!/bin/bash
set -e

# Ensure system packages needed for secp256k1 are installed
if ! command -v pkg-config >/dev/null 2>&1; then
    apt-get update && \
    apt-get install -y pkg-config libsecp256k1-dev && \
    rm -rf /var/lib/apt/lists/*
fi

# Install Python dependencies (ensures msal, hypercorn, and other packages are available)
pip install --no-cache-dir -r requirements.txt || {
    echo "Error: Failed to install dependencies." >&2
    exit 1
}

# Launch Hypercorn ASGI server
exec hypercorn --bind 0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    app:app
