import logging
import requests
import json
from flask import jsonify

from app import WAVLAKE_API_BASE, error_response

logger = logging.getLogger(__name__)

def fetch_artists():
    """Fetch artist data from Wavlake API."""
    try:
        resp = requests.get(f"{WAVLAKE_API_BASE}/artists")
        if resp.ok:
            return resp.json().get('data', [])
        logger.error(f"Error fetching artists: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Exception in fetch_artists: {e}")
        return []

def fetch_albums(artist_id):
    """Fetch albums for a given artist."""
    try:
        resp = requests.get(f"{WAVLAKE_API_BASE}/artists/{artist_id}/albums")
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
        resp = requests.get(f"{WAVLAKE_API_BASE}/albums/{album_id}/tracks")
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
        try:
            library = build_music_library()
            logger.info(f"Music Library: {library}")
            return jsonify({"tracks": library})
        except Exception as e:
            logger.error(f"Error in get_tracks route: {e}")
            return error_response(f"Error building library: {e}", 500)