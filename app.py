from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_restful import Resource, Api
from flask_cors import CORS
from pynostr.relay_manager import RelayManager
from pynostr.filters import FiltersList, Filters
from pynostr.event import EventKind, Event
from functools import wraps
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
import os, json, time, uuid, requests
import logging

# Initialize Flask App
app = Flask(__name__)
CORS(app)
api = Api(app)

# Configuration
RELAY_URLS = os.getenv("RELAY_URLS", "wss://relay.damus.io,wss://relay.primal.net").split(',')
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", 300))
REQUIRED_DOMAIN = os.getenv("REQUIRED_DOMAIN", "fuzzedrecords.com")
WAVLAKE_API_BASE = "https://wavlake.com/api/v1"
SEARCH_TERM = " by Fuzzed Records"

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Flask app has started.")

# In-memory cache
cache = {}

def get_cached_item(cache_key):
    item = cache.get(cache_key)
    if item and time.time() - item[1] < CACHE_TIMEOUT:
        return item[0]
    return None

def set_cached_item(cache_key, item):
    cache[cache_key] = (item, time.time())

def initialize_relay_manager(timeout=10):
    relay_manager = RelayManager(timeout=timeout)
    for relay in RELAY_URLS:
        relay_manager.add_relay(relay)
    return relay_manager

def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code

@app.route('/')
def index():
    logger.info("Request for index page received")
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/fetch-profile', methods=['POST'])
def fetch_profile():
    try:
        data = request.json
        pubkey_hex = data['pubkey']
        logger.info(f'Received request to fetch profile for pubkey: {pubkey_hex}')

        cached_profile = get_cached_item(pubkey_hex)
        if cached_profile:
            logger.info(f'Profile for {pubkey_hex} returned from cache.')
            return jsonify(cached_profile)

        relay_manager = initialize_relay_manager()
        filters = FiltersList([Filters(authors=[pubkey_hex], kinds=[EventKind.SET_METADATA], limit=1)])
        subscription_id = uuid.uuid1().hex
        relay_manager.add_subscription_on_all_relays(subscription_id, filters)
        relay_manager.run_sync()

        profile_data = None
        while relay_manager.message_pool.has_events():
            event_msg = relay_manager.message_pool.get_event()
            if event_msg.event.kind == EventKind.SET_METADATA:
                profile_content = json.loads(event_msg.event.content)
                profile_data = {
                    "id": event_msg.event.id,
                    "pubkey": event_msg.event.pubkey,
                    "content": profile_content,
                    "sig": event_msg.event.sig
                }
                break

        relay_manager.close_all_relay_connections()

        if profile_data:
            set_cached_item(pubkey_hex, profile_data)
            return jsonify(profile_data)
        return error_response("Profile not found or relay did not respond in time", 404)

    except Exception as e:
        logger.error(f'Error in fetch-profile: {e}')
        return error_response(str(e), 500)

@app.route('/tracks', methods=['GET'])
def get_tracks():
    try:
        library = build_music_library()
        logger.info(f'Music Library: {library}')
        return jsonify({"tracks": library})
    except Exception as e:
        logger.error(f"Error building library: {e}")
        return error_response(f"Error building library: {e}", 500)

@app.route('/validate-profile', methods=['POST'])
def validate_profile():
    """
    Validate the NIP-05 for a given pubkey and ensure it's within the fuzzedrecords.com domain.
    """
    try:
        data = request.json
        pubkey = data.get("pubkey")

        if not pubkey:
            return jsonify({"error": "Missing pubkey"}), 400

        # Fetch and validate profile
        is_valid = fetch_and_validate_profile(pubkey, "fuzzedrecords.com")

        if is_valid:
            return jsonify({"message": "Profile is valid and verified.", 
                            "content": data.get("content")})
        else:
            return jsonify({"error": "Profile validation failed."}), 403

    except Exception as e:
        logger.error(f"Error in validate_profile: {e}")
        return jsonify({"error": f"An internal error occurred: {e}"}), 500

# Validate nip05 domain.
def require_nip05_verification(required_domain):
    """
    Decorator to enforce NIP-05 verification for a specific domain.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Extract the public key (pubkey) from the request data
                data = request.json
                pubkey = data.get("pubkey")

                if not pubkey:
                    return jsonify({"error": "Missing pubkey"}), 400

                # Validate the profile for the given pubkey and domain
                is_valid = fetch_and_validate_profile(pubkey, required_domain)

                if not is_valid:
                    logger.warning(f"NIP-05 verification failed for pubkey: {pubkey}")
                    return jsonify({"error": "NIP-05 verification failed"}), 403

                # Proceed with the original function
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Error in require_nip05_verification: {e}")
                return jsonify({"error": "An internal error occurred"}), 500

        return wrapper
    return decorator

@app.route('/create_event', methods=['POST'])
@require_nip05_verification(REQUIRED_DOMAIN)
def create_event():
    try:
        data = request.json
        required_fields = ["title", "venue", "date", "price", "description", "pubkey", "sig"]
        if not all(field in data for field in required_fields):
            return error_response("Missing required fields")

        parsed_date = datetime.fromisoformat(data["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
        event = Event(
            kind=52,
            pubkey=data["pubkey"],
            content=data["description"],
            tags=[["title", data["title"]], ["venue", data["venue"]], ["date", parsed_date.isoformat()], ["price", str(data["price"])]],
        )

        if not event.verify(data["sig"]):
            return error_response("Invalid signature", 403)

        for relay in RELAY_URLS:
            requests.post(f"{relay}/publish", json=event.to_dict())

        return jsonify({"message": "Event created successfully", "event_id": event.id})
    except Exception as e:
        logger.error(f"Error in create_event: {e}")
        return error_response("An internal error occurred", 500)

def fetch_and_validate_profile(pubkey, required_domain):
    """
    Fetch the profile for a given pubkey and validate that it matches the required domain.
    """
    try:
        # Fetch profile using existing `fetch_profile` logic
        relay_manager = RelayManager(timeout=10)
        relay_manager.add_relay("wss://relay.damus.io")
        relay_manager.add_relay("wss://relay.primal.net")

        filters = FiltersList([Filters(authors=[pubkey], kinds=[EventKind.SET_METADATA], limit=1)])
        subscription_id = uuid.uuid1().hex
        relay_manager.add_subscription_on_all_relays(subscription_id, filters)
        logger.info(f"Fetching and Validating Profile with the following filters: {filters}")
        relay_manager.run_sync()
        logger.info("Relay manager completed sync")

        profile_data = None
        while relay_manager.message_pool.has_events():
            event_msg = relay_manager.message_pool.get_event()
            logger.info(f"Relay Manager event message returned: {event_msg}")
            if event_msg.event.kind == EventKind.SET_METADATA:
                profile_content = json.loads(event_msg.event.content)
                profile_data = {
                    "id": event_msg.event.id,
                    "pubkey": event_msg.event.pubkey,
                    "content": profile_content,
                }
                logger.info(f"Profile Data: {profile_data}")
                break

        relay_manager.close_all_relay_connections()
        logger.info("Relay manager Closed Connections")

        if not profile_data:
            logger.warning(f"No profile found for pubkey: {pubkey}")
            return False

        # Validate NIP-05 if available
        nip05 = profile_data["content"].get("nip05")
        if not nip05:
            logger.warning(f"Profile does not have NIP-05 for pubkey: {pubkey}")
            return False

        # Ensure the domain matches
        domain = nip05.split("@")[-1]
        if domain != required_domain:
            logger.warning(f"NIP-05 domain mismatch. Expected {required_domain}, got {domain}")
            return False

        return True
    except Exception as e:
        logger.error(f"Error in fetch_and_validate_profile: {e}")
        return False

# Helper to build music library
def build_music_library():
    artists = fetch_artists()
    music_library = []
    for artist in artists:
        for album in fetch_albums(artist["id"]):
            for track in fetch_tracks(album["id"]):
                music_library.append({
                    "artist": artist["name"].replace(SEARCH_TERM, ""),
                    "album": album["title"],
                    "title": track["title"],
                    "media_url": track["media_url"],
                    "track_id": track["id"]
                })
    return music_library

# Fetch Artists by Search Term
def fetch_artists():
    url = f"{WAVLAKE_API_BASE}/content/search"
    params = {"term": SEARCH_TERM}
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            logger.info(f"Received response: {response.text}")
            artists = response.json()
            logger.info(f"Fetched {len(artists)} artist(s).")
            return [{"id": artist["id"], "name": artist["name"], "art_url": artist.get("artistArtUrl", "")} for artist in artists]
        else:
            logger.info(f"Error fetching artists: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error in fetch_artists: {e}")
        return []

# Fetch Albums for an Artist
def fetch_albums(artist_id):
    url = f"{WAVLAKE_API_BASE}/content/artist/{artist_id}"
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"Received response: {response.text}")
            artist_data = response.json()
            albums = artist_data.get("albums", [])
            logger.info(f"Fetched {len(albums)} album(s) for artist {artist_id}.")
            return [{"id": album["id"], "title": album["title"], "albumArtUrl": album["albumArtUrl"]} for album in albums]
        else:
            logger.info(f"Error fetching albums for {artist_id}: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error in fetch_albums: {e}")
        return []

# Fetch Tracks for an Album
def fetch_tracks(album_id):
    url = f"{WAVLAKE_API_BASE}/content/album/{album_id}"
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"Received response: {response.text}")
            album_data = response.json()
            tracks = album_data.get("tracks", [])
            logger.info(f"Fetched {len(tracks)} track(s) for album {album_id}.")
            return [
                {
                    "title": track["title"],
                    "media_url": track["mediaUrl"],
                    "album": track.get("albumTitle", ""),
                    "artist": track.get("artist", ""),
                    "track_id": track["id"],  # Include track_id for embedding
                    "nostr_npub": track.get("artistNpub", "")
                }
                for track in tracks
            ]
        else:
            logger.info(f"Error fetching tracks for {album_id}: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error in fetch_tracks: {e}")
        return []

class Main(Resource):
    def post(self):
        return jsonify({'message': 'Welcome to the Fuzzed Records Flask REST App'})

class NostrJson(Resource):
    def get(self):
        logger.info("Fetching admin users and relays from Entra ID")

        # MSAL App Configuration
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        graph_api_base = "https://graph.microsoft.com/v1.0"

        app = ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )

        # Get Token
        token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" not in token:
            logger.error("Failed to acquire token")
            return jsonify({"error": "Authentication failed"}), 500

        access_token = token["access_token"]

        # Fetch Groups
        group_response = requests.get(
            f"{graph_api_base}/groups?$select=displayName,description",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        groups = group_response.json().get("value", [])

        # Map Relay Groups
        relay_groups = {
            group["displayName"]: group["description"]
            for group in groups
            if group["displayName"].endswith("Relay") and group["description"].startswith("wss://")
        }

        # Fetch Users
        user_response = requests.get(
            f"{graph_api_base}/users?$select=id,displayName,jobTitle",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        users = user_response.json().get("value", [])
        
        # Debugging: Log the response for inspection
        logger.debug(f"Users response: {users}")

        # Map User Data
        names = {}
        relays = {}

        for user in users:
            pubkey = user.get("jobTitle")
            name = user.get("displayName")

            if not name or not pubkey:
                continue

            names[name] = pubkey
            relays[pubkey] = []

            # Fetch User Group Memberships
            user_id = user["id"]
            membership_response = requests.get(
                f"{graph_api_base}/users/{user_id}/memberOf?$select=displayName",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            memberships = membership_response.json().get("value", [])

            for group in memberships:
                group_name = group.get("displayName")
                if group_name in relay_groups:
                    relays[pubkey].append(relay_groups[group_name])

        return jsonify({"names": names, "relays": relays})

# adding the defined resources along with their corresponding urls
api.add_resource(Main, '/')
api.add_resource(NostrJson, '/.well-known/nostr.json')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    app.run(debug=True)
