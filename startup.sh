#!/bin/bash

# Install dependencies (ensures msal, gunicorn, and other packages are available)
pip install --no-cache-dir -r requirements.txt

# Launch Gunicorn WSGI server
exec gunicorn --bind=0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    app:app
