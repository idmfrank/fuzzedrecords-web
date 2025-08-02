#!/bin/bash

# Install dependencies (ensures msal, hypercorn, and other packages are available)
pip install --no-cache-dir -r requirements.txt

# Launch Hypercorn ASGI server
exec hypercorn --bind 0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    app:app
