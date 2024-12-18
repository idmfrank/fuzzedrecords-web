#!/bin/bash
# Clean up previous virtual environment if needed
rm -rf antenv

# Check if virtual environment exists, create it if not
if [ ! -d "antenv" ]; then
    python3 -m venv antenv
fi

# Activate the virtual environment
source antenv/bin/activate

# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt --upgrade

# Start Gunicorn and log output to stdout/stderr
gunicorn --bind=0.0.0.0:8000 --log-level debug --access-logfile - --error-logfile - app:app