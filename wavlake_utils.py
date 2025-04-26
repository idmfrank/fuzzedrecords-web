import logging
import os
import time
import requests
import json
from flask import jsonify
import threading
# Timeout for external API calls
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))

# Simple in-memory cache for music library
_track_cache = {'library': None, 'ts': 0}
TRACK_CACHE_TIMEOUT = int(os.getenv("TRACK_CACHE_TIMEOUT", "300"))

from app import WAVLAKE_API_BASE, error_response

logger = logging.getLogger(__name__)

_update_lock = threading.Lock()
_updating = False

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
 
def _update_library_background():
    """Background thread target to refresh the music library cache."""
    global _updating
    try:
        library = build_music_library()
        _track_cache['library'] = library
        _track_cache['ts'] = time.time()
        logger.debug("Background music library update complete")
    except Exception as e:
        logger.error(f"Exception during background music library update: {e}")
    finally:
        with _update_lock:
            _updating = False

def register_wavlake_routes(app):
    """Register the /tracks endpoint on the app."""
    @app.route('/tracks', methods=['GET'])
    def get_tracks():
        """Serve music library: block on initial load, thereafter serve cache and refresh stale data in background."""
        global _updating
        now = time.time()
        cached = _track_cache.get('library')
        # Initial load: no cached library yet
        if cached is None:
            try:
                library = build_music_library()
                _track_cache['library'] = library
                _track_cache['ts'] = now
                logger.info(f"Initial music library loaded with {len(library)} tracks")
                return jsonify({"tracks": library})
            except Exception as e:
                logger.error(f"Error in get_tracks initial load: {e}")
                return error_response(f"Error fetching music library: {e}", 500)
        # Cache exists: check staleness
        if now - _track_cache['ts'] > TRACK_CACHE_TIMEOUT:
            # Trigger background refresh if not already running
            with _update_lock:
                if not _updating:
                    _updating = True
                    threading.Thread(target=_update_library_background, daemon=True).start()
            logger.warning("Serving stale music library; background update started")
        else:
            logger.debug("Returning fresh music library from cache")
        # Return cached library (either fresh or stale)
        return jsonify({"tracks": cached})