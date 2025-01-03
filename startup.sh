#!/bin/bash
# Clean up previous virtual environment if needed
rm -rf antenv

# Check if virtual environment exists, create it if not
if [ ! -d "antenv" ]; then
    python3 -m venv antenv
fi

# Activate the virtual environment
source antenv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
if [ -d "wheels" ]; then
    # Use cached wheels if available
    pip install --no-index --find-links=./wheels -r requirements.txt
else
    # Otherwise, fetch from PyPI
    pip install -r requirements.txt
fi

# Start Gunicorn and log output to stdout/stderr
gunicorn --bind=0.0.0.0:8000 --log-level debug --access-logfile - --error-logfile - app:app
