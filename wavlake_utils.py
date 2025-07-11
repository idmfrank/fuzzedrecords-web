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

from app import WAVLAKE_API_BASE, error_response, SEARCH_TERM

logger = logging.getLogger(__name__)

_update_lock = threading.Lock()
_updating = False

def fetch_artists():
    """Fetch artist data from Wavlake API via search term."""
    try:
        resp = requests.get(
            f"{WAVLAKE_API_BASE}/content/search",
            params={"term": SEARCH_TERM},
            headers={"accept": "application/json"},
            timeout=HTTP_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        # Expecting a list of artists or a dict with 'data'
        if isinstance(data, list):
            return [artist for artist in data if artist.get('id')]
        return data.get('data', [])
    except Exception as e:
        logger.error(f"Exception in fetch_artists: {e}")
        # Propagate errors to trigger failure handling
        raise

def fetch_albums(artist_id):
    """Fetch albums for a given artist."""
    """Fetch albums for a given artist via content endpoint."""
    try:
        resp = requests.get(
            f"{WAVLAKE_API_BASE}/content/artist/{artist_id}",
            headers={"accept": "application/json"},
            timeout=HTTP_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        albums = data.get('albums', [])
        return [album for album in albums if album.get('id')]
    except Exception as e:
        logger.error(f"Exception in fetch_albums: {e}")
        return []

def fetch_tracks(album_id):
    """Fetch tracks for a given album."""
    """Fetch tracks for a given album via content endpoint."""
    try:
        resp = requests.get(
            f"{WAVLAKE_API_BASE}/content/album/{album_id}",
            headers={"accept": "application/json"},
            timeout=HTTP_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        tracks = data.get('tracks', [])
        return [track for track in tracks if track.get('id')]
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
                # Extract artist name without the search-term suffix
                artist_full = track.get('artist', '')
                artist_name = artist_full.replace(SEARCH_TERM, '')
                library.append({
                    'artist': artist_name,
                    'album': track.get('albumTitle', ''),
                    'title': track.get('title', ''),
                    'media_url': track.get('mediaUrl', ''),
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
        """Serve cached music library immediately; refresh in background when missing or stale."""
        global _updating
        now = time.time()
        cached = _track_cache.get('library')
        stale = (cached is None) or (now - _track_cache['ts'] > TRACK_CACHE_TIMEOUT)
        if stale:
            # Trigger background update if not already running
            with _update_lock:
                if not _updating:
                    _updating = True
                    threading.Thread(target=_update_library_background, daemon=True).start()
        # If no data yet, return empty while update is in progress
        if cached is None:
            logger.warning("Cache empty, returning empty library while update is in progress")
            return jsonify({"tracks": []})
        # If stale, warn; else debug fresh cache
        if stale:
            logger.warning("Serving stale music library while background update is in progress")
        else:
            logger.debug("Returning cached music library")
        return jsonify({"tracks": cached})
