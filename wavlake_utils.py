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

# Configuration defaults sourced from environment
WAVLAKE_API_BASE = os.getenv("WAVLAKE_API_BASE", "https://wavlake.com/api/v1")
SEARCH_TERM = os.getenv("SEARCH_TERM", "")

def _default_error_handler(message, status_code):
    return jsonify({'error': message}), status_code

_error_handler = _default_error_handler

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

def register_wavlake_routes(app, base_url=None, search_term=None, error_handler=None):
    """Register the /tracks endpoint on the app."""
    global WAVLAKE_API_BASE, SEARCH_TERM, _error_handler
    WAVLAKE_API_BASE = base_url or os.getenv("WAVLAKE_API_BASE", WAVLAKE_API_BASE)
    SEARCH_TERM = search_term or os.getenv("SEARCH_TERM", SEARCH_TERM)
    _error_handler = error_handler or _default_error_handler
    @app.route('/tracks', methods=['GET'])
    def get_tracks():
        """Return the music library, building it on-demand if missing."""
        global _updating
        now = time.time()
        cached = _track_cache.get('library')

        if cached is None:
            # No library yet - build synchronously so the first request has data
            logger.info("Cache empty, building music library synchronously")
            try:
                library = build_music_library()
            except Exception as e:
                logger.error(f"Failed to build music library: {e}")
                return _error_handler("Failed to load library", 500)
            _track_cache['library'] = library
            _track_cache['ts'] = now
            cached = library
            logger.debug("Music library loaded")
            stale = False
        else:
            stale = now - _track_cache['ts'] > TRACK_CACHE_TIMEOUT
            if stale:
                # Trigger background update if not already running
                with _update_lock:
                    if not _updating:
                        _updating = True
                        threading.Thread(target=_update_library_background, daemon=True).start()
                logger.warning("Serving stale music library while background update is in progress")

        if not stale:
            logger.debug("Returning cached music library")

        return jsonify({"tracks": cached})
