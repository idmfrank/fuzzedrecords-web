#!/bin/bash
# Ensure pip dependencies are installed
pip install --upgrade pip
pip install -r requirements.txt

# Start the Flask app using Gunicorn
gunicorn --bind=0.0.0.0 --timeout 600 app:app
