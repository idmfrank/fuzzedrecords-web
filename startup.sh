#!/bin/bash
# Ensure dependencies are installed in the correct Python interpreter
python3 --version
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt --target=/home/site/wwwroot

# Start the Flask app with Gunicorn
gunicorn --bind=0.0.0.0 --timeout 600 app:app
