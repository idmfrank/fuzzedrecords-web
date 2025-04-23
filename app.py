from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from flask_restful import Resource, Api
from flask_cors import CORS
from pynostr.relay_manager import RelayManager
from pynostr.key import PrivateKey
from pynostr.event import Event, EventKind
from pynostr.encrypt import encrypt_message
from pynostr.utils import get_public_key
from pynostr.filters import Filters, FiltersList
from functools import wraps
from msal import ConfidentialClientApplication
from io import BytesIO
import os, json, time, requests, asyncio
import logging
import qrcode

# Initialize Flask App
app = Flask(__name__)
CORS(app)
api = Api(app)

# Configuration
RELAY_URLS = os.getenv("RELAY_URLS", "wss://relay.damus.io,wss://relay.primal.net,wss://relay.mostr.pub").split(',')
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

def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code

def initialize_client():
    """Instantiate and open connections to all relays."""
    manager = RelayManager()
    for url in RELAY_URLS:
        manager.add_relay(url)
    # Blocking open of all relay connections
    manager.open_connections()
    return manager

@app.route('/')
def index():
    logger.info("Request for index page received")
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/fetch-profile', methods=['POST'])
async def fetch_profile():
    try:
        data = request.json or {}
        pubkey_hex = data.get('pubkey')
        logger.info(f"Fetch-profile request for pubkey: {pubkey_hex}")
        if not pubkey_hex:
            return error_response("Missing pubkey", 400)

        cached = get_cached_item(pubkey_hex)
        if cached:
            logger.info(f"Returning cached profile for {pubkey_hex}")
            return jsonify(cached)

        manager = initialize_client()
        filt = FiltersList([Filters(authors=[pubkey_hex], kinds=[EventKind.SET_METADATA], limit=1)])
        sub_id = f"fetch_{pubkey_hex}"
        manager.add_subscription_on_all_relays(sub_id, filt)

        # allow time to receive events
        await asyncio.sleep(1)
        profile_data = {}
        for msg in manager.message_pool.get_all_events():
            ev = msg.event
            try:
                content = json.loads(ev.content)
            except json.JSONDecodeError:
                continue
            profile_data = {"id": ev.id, "pubkey": ev.pubkey, "content": content}
            break

        manager.close_connections()
        if profile_data:
            set_cached_item(pubkey_hex, profile_data)
            return jsonify(profile_data)
        return error_response("Profile not found or no relay response", 404)
    except Exception as e:
        logger.error(f"Error in fetch_profile: {e}")
        return error_response(str(e), 500)
 
@app.route('/generate_qr')
def generate_qr():
    ticket_id = request.args.get('ticket_id')
    event_id = request.args.get('event_id')

    qr_data = {
        "ticket_id": ticket_id,
        "event_id": event_id
    }

    qr = qrcode.make(json.dumps(qr_data))
    img_io = BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

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
    Validate the NIP-05 for a given pubkey and ensure it's within the REQUIRED_DOMAIN domain.
    """
    try:
        data = request.json
        pubkey = data.get("pubkey")

        if not pubkey:
            return jsonify({"error": "Missing pubkey"}), 400

        # Fetch and validate profile
        is_valid = fetch_and_validate_profile(pubkey, REQUIRED_DOMAIN)

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
async def create_event():
    try:
        data = request.json or {}
        logger.debug(f"Create_event data: {data}")
        # Expect user-supplied signed event or create-and-sign server-side
        # Here we expect a fully populated signed event dict
        required = ["pubkey", "sig", "content", "kind", "created_at", "tags"]
        if not all(k in data for k in required):
            return error_response("Missing required event fields", 400)

        # Reconstruct Event and verify signature
        ev = Event(
            public_key=data["pubkey"],
            content=data["content"],
            kind=EventKind(data["kind"]),
            tags=data["tags"],
            created_at=data["created_at"]
        )
        ev.sig = data.get("sig")
        if not ev.verify():
            logger.warning("Invalid event signature")
            return error_response("Invalid signature", 403)

        mgr = initialize_client()
        mgr.publish_event(ev)
        mgr.close_connections()
        return jsonify({"message": "Event successfully broadcasted"})
    except Exception as e:
        logger.error(f"Error in create_event: {e}")
        return error_response("An internal error occurred", 500)

@app.route('/fuzzed_events', methods=['GET'])
async def get_fuzzed_events():
    try:
        mgr = initialize_client()
        filt = FiltersList([Filters(kinds=[52])])
        sub_id = "fuzzed_events"
        mgr.add_subscription_on_all_relays(sub_id, filt)
        await asyncio.sleep(1)

        results = []
        seen = set()
        for msg in mgr.message_pool.get_all_events():
            ev = msg.event
            if ev.pubkey in seen:
                continue
            seen.add(ev.pubkey)
            if await fetch_and_validate_profile(ev.pubkey, REQUIRED_DOMAIN):
                results.append({
                    "id": ev.id,
                    "pubkey": ev.pubkey,
                    "content": ev.content,
                    "tags": ev.tags,
                    "created_at": ev.created_at
                })

        mgr.close_connections()
        if not results:
            return jsonify({"message": f"No events from {REQUIRED_DOMAIN}"})
        logger.info(f"Found fuzzed events: {results}")
        return jsonify({"events": results})
    except Exception as e:
        logger.error(f"Error in get_fuzzed_events: {e}")
        return error_response("Error fetching fuzzed events", 500)

@app.route('/send_dm', methods=['POST'])
async def send_dm():
    try:
        data = request.json or {}
        # Expect to_pubkey, content, sender_privkey
        required = ["to_pubkey", "content", "sender_privkey"]
        if not all(k in data for k in required):
            return error_response("Missing DM fields", 400)

        # Encrypt the message
        ciphertext = encrypt_message(
            data["content"], data["to_pubkey"], data["sender_privkey"]
        )
        # Build and sign the DM event
        ev = Event(
            public_key=get_public_key(data["sender_privkey"]),
            content=ciphertext,
            kind=EventKind.ENCRYPTED_DIRECT_MESSAGE,
            tags=[["p", data["to_pubkey"]]],
            created_at=int(time.time())
        )
        priv = PrivateKey.from_nsec(data["sender_privkey"])
        ev.sign(priv)
        if not ev.verify():
            return error_response("Invalid DM signature", 403)

        mgr = initialize_client()
        mgr.publish_event(ev)
        mgr.close_connections()
        return jsonify({"message": "Encrypted DM sent successfully"})
    except Exception as e:
        logger.error(f"Error in send_dm: {e}")
        return error_response("Error sending DM", 500)

async def fetch_and_validate_profile(pubkey, required_domain):
    """
    Fetch the profile for a given pubkey and validate that it matches the required domain.
    """
    try:
        client = initialize_client()
        filters = [Filter(authors=[pubkey], kinds=[0])]  # Kind 0 is used for metadata events

        profile_data = {}

        def handle_event(event):
            """ Callback to process profile data """
            logger.info(f"Received event for profile validation: {event}")
            profile_content = json.loads(event.content)
            profile_data.update({
                "id": event.id,
                "pubkey": event.pubkey,
                "content": profile_content
            })

        # Subscribe and wait
        client.subscribe(filters, handle_event)
        await client.close()

        if not profile_data:
            logger.warning(f"No profile found for pubkey: {pubkey}")
            return False

        # Validate NIP-05 if available
        nip05 = profile_data["content"].get("nip05")
        if not nip05 or "@" not in nip05:
            logger.warning(f"Invalid or missing NIP-05 for pubkey: {pubkey}")
            return False

        # Ensure domain matches
        domain = nip05.split("@")[1]
        if domain != required_domain:
            logger.warning(f"NIP-05 domain mismatch. Expected {required_domain}, got {domain}")
            return False

        return True
    except Exception as e:
        logger.error(f"Error in fetch_and_validate_profile: {e}")
        return False

# Helper to build music library
def build_music_library():
    try:
        artists = fetch_artists()
        if not artists:
            logger.warning("No artists found.")
            return []

        music_library = []
        for artist in artists:
            if "id" not in artist:
                logger.warning(f"Artist missing 'id': {artist}")
                continue

            albums = fetch_albums(artist["id"])
            if not albums:
                logger.warning(f"No albums found for artist: {artist['name']}")
                continue

            for album in albums:
                if "id" not in album:
                    logger.warning(f"Album missing 'id': {album}")
                    continue

                tracks = fetch_tracks(album["id"])
                if not tracks:
                    logger.warning(f"No tracks found for album: {album['title']}")
                    continue

                for track in tracks:
                    # Check for 'track_id' instead of 'id'
                    if "track_id" not in track:
                        logger.warning(f"Track missing 'track_id': {track}")
                        continue

                    # Build the music library entry
                    music_library.append({
                        "artist": artist["name"].replace(SEARCH_TERM, ""),
                        "album": album["title"],
                        "title": track["title"],
                        "media_url": track["media_url"],
                        "track_id": track["track_id"]
                    })

        logger.debug(f"Music library built with {len(music_library)} tracks.")
        return music_library

    except Exception as e:
        logger.error(f"Error in build_music_library: {e}")
        return []


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
            # Validate artist structure
            valid_artists = [
                {
                    "id": artist.get("id"),
                    "name": artist.get("name", "Unknown Artist"),
                    "art_url": artist.get("artistArtUrl", "")
                }
                for artist in artists
                if "id" in artist  # Ensure "id" exists
            ]
            logger.info(f"Fetched {len(valid_artists)} valid artist(s).")
            return valid_artists
        else:
            logger.warning(f"Error fetching artists: {response.status_code}")
            return error_response(f"Error fetching artists: {response.status_code}", 500)
    except Exception as e:
        logger.error(f"Error in fetch_artists: {e}")
        return error_response(f"Error in fetch_artists: {e}", 500)

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
            return error_response(f"Error fetching albums for {artist_id}: {response.status_code}", 500)
    except Exception as e:
        logger.error(f"Error in fetch_albums: {e}")
        return error_response(f"Error in fetch_albums: {e}", 500)

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
            return error_response(f"Error fetching tracks for {album_id}: {response.status_code}", 500)
    except Exception as e:
        logger.error(f"Error in fetch_tracks: {e}")
        return error_response(f"Error in fetch_tracks: {e}", 500)

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
