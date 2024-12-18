#!/bin/bash
# Check if virtual environment exists, create it if not
if [ ! -d "antenv" ]; then
    python3 -m venv antenv
fi

# Activate the virtual environment
source antenv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt --upgrade

# Start the application with Gunicorn
gunicorn --bind=0.0.0.0:8000 app:app
