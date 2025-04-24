#!/bin/bash

# Launch Gunicorn WSGI server
exec gunicorn --bind=0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    app:app
