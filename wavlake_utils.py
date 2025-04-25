import logging
import os
import time
import requests
import json
from flask import jsonify
# Timeout for external API calls
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))

# Simple in-memory cache for music library
_track_cache = {'library': None, 'ts': 0}
TRACK_CACHE_TIMEOUT = int(os.getenv("TRACK_CACHE_TIMEOUT", "300"))

from app import WAVLAKE_API_BASE, error_response

logger = logging.getLogger(__name__)

def fetch_artists():
    """Fetch artist data from Wavlake API."""
    try:
        resp = requests.get(f"{WAVLAKE_API_BASE}/artists", timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get('data', [])
    except Exception as e:
        logger.error(f"Exception in fetch_artists: {e}")
        # Propagate errors to trigger 503 in get_tracks
        raise

def fetch_albums(artist_id):
    """Fetch albums for a given artist."""
    try:
        resp = requests.get(f"{WAVLAKE_API_BASE}/artists/{artist_id}/albums", timeout=HTTP_TIMEOUT)
        if resp.ok:
            return resp.json().get('data', [])
        logger.error(f"Error fetching albums for {artist_id}: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Exception in fetch_albums: {e}")
        return []

def fetch_tracks(album_id):
    """Fetch tracks for a given album."""
    try:
        resp = requests.get(f"{WAVLAKE_API_BASE}/albums/{album_id}/tracks", timeout=HTTP_TIMEOUT)
        if resp.ok:
            return resp.json().get('data', [])
        logger.error(f"Error fetching tracks for {album_id}: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Exception in fetch_tracks: {e}")
        return []

def build_music_library():
    """Aggregate artists, albums, tracks into a flat library list."""
    library = []
    artists = fetch_artists()
    for artist in artists:
        artist_id = artist.get('id')
        if not artist_id:
            continue
        albums = fetch_albums(artist_id)
        for album in albums:
            album_id = album.get('id')
            if not album_id:
                continue
            tracks = fetch_tracks(album_id)
            for track in tracks:
                library.append({
                    'artist': track.get('artist_name', ''),
                    'album': track.get('album_title', ''),
                    'title': track.get('title', ''),
                    'media_url': track.get('media_url', ''),
                    'track_id': track.get('id', '')
                })
    return library

def register_wavlake_routes(app):
    """Register the /tracks endpoint on the app."""
    @app.route('/tracks', methods=['GET'])
    def get_tracks():
        now = time.time()
        # Serve from cache if fresh
        cached = _track_cache.get('library')
        if cached is not None and now - _track_cache['ts'] <= TRACK_CACHE_TIMEOUT:
            logger.debug("Returning cached music library")
            return jsonify({"tracks": cached})
        # Fetch new library
        try:
            library = build_music_library()
            # Update cache
            _track_cache['library'] = library
            _track_cache['ts'] = now
            logger.debug(f"Fetched music library: {library}")
            return jsonify({"tracks": library})
        except Exception as e:
            logger.error(f"Error in get_tracks route: {e}")
            # On failure, serve stale cache if available
            if cached is not None:
                logger.warning("Serving stale music library due to fetch error")
                return jsonify({"tracks": cached})
            # No cache to serve
            return error_response(f"Error fetching music library: {e}", 503)