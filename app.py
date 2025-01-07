from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_restful import Resource, Api
from flask_cors import CORS
from pynostr.relay_manager import RelayManager
from pynostr.filters import FiltersList, Filters
from pynostr.event import EventKind, Event
from functools import wraps
from datetime import datetime, timezone
import os, json, time, uuid, requests
import logging

# Initialize Flask App
app = Flask(__name__)
CORS(app)
api = Api(app)
WAVLAKE_API_BASE = "https://wavlake.com/api/v1"
SEARCH_TERM = " by Fuzzed Records"

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Flask app has started.")

# In-memory cache (simple dictionary)
cache = {}

# Cache settings
CACHE_TIMEOUT = 300  # Cache timeout in seconds (e.g., 5 minutes)

@app.route('/')
def index():
    logger.info("Request for index page received")
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_url = os.path.join(SITE_ROOT, "static", "nostr.json")
    jsonData = json.load(open(json_url))
    return render_template('index.html', nostrJson=jsonData)

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

        # Check if the profile is already cached
        if pubkey_hex in cache:
            cached_profile, timestamp = cache[pubkey_hex]
            if time.time() - timestamp < CACHE_TIMEOUT:
                logger.info(f'Profile for {pubkey_hex} returned from cache.')
                return jsonify(cached_profile)
            else:
                # Remove the stale cache entry
                del cache[pubkey_hex]

        # Initialize RelayManager with a timeout of 5 seconds and key trusted default relays
        relay_manager = RelayManager(timeout=5)
        relay_manager.add_relay("wss://relay.wavlake.com")
        relay_manager.add_relay("wss://relay.damus.io")
        relay_manager.add_relay("wss://relay.primal.net")
        relay_manager.add_relay("wss://relay.getalby.com/v1")


        # Create filters for kind 0 events (user profile)
        filters = FiltersList([Filters(authors=[pubkey_hex], kinds=[EventKind.SET_METADATA], limit=1)])
        subscription_id = uuid.uuid1().hex

        # Subscribe to all relays
        relay_manager.add_subscription_on_all_relays(subscription_id, filters)
        relay_manager.run_sync()

        profile_data = None

        # Process events
        while relay_manager.message_pool.has_events():
            event_msg = relay_manager.message_pool.get_event()
            if event_msg.event.kind == EventKind.SET_METADATA:
                # Parse the content field as JSON
                profile_content = json.loads(event_msg.event.content)
                profile_data = {
                    "id": event_msg.event.id,
                    "pubkey": event_msg.event.pubkey,
                    "created_at": event_msg.event.created_at,
                    "kind": event_msg.event.kind,
                    "tags": event_msg.event.tags,
                    "content": profile_content,  # Decoded JSON content
                    "sig": event_msg.event.sig
                }
                logger.info(f'Received profile event: {profile_data}')
                break

        # Close all relay connections
        relay_manager.close_all_relay_connections()

        # Validate NIP-05 if available
        if profile_data and 'nip05' in profile_data['content']:
            profile_data['nip05_verified'] = validate_nip05(profile_data['pubkey'], profile_data['content']['nip05'])
        else:
            profile_data['nip05_verified'] = False

        if profile_data:
            # Cache the profile
            cache[pubkey_hex] = (profile_data, time.time())
            return jsonify(profile_data)
        else:
            return jsonify({"error": "Profile not found or relay did not respond in time"})
    except Exception as e:
        logger.error(f'Error occurred in fetch-profile: {e}')
        return jsonify({"error": str(e)})

@app.route('/tracks', methods=['GET'])
def get_tracks():
    """Return the complete Fuzzed Records music library."""
    try:
        library = build_music_library()
        return jsonify({"tracks": library})
    except Exception as e:
        logger.error(f"Error building library: {e}")
        return jsonify({"error": "Unable to build music library"}), 500

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
@require_nip05_verification("fuzzedrecords.com")
def create_event():
    try:
        # Parse event data from request
        data = request.json
        title = data.get("title")
        venue = data.get("venue")
        date = data.get("date")
        price = data.get("price")
        description = data.get("description")
        pubkey = data.get("pubkey")
        sig = data.get("sig")

        if not all([title, venue, date, price, description, pubkey, sig]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Validate and normalize the date
        try:
            # Parse date and convert to UTC
            parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(timezone.utc)
            iso_date = parsed_date.isoformat()  # Format back to ISO 8601 (UTC)
        except ValueError:
            return jsonify({"error": "Invalid date format. Use ISO 8601 (e.g., 2024-12-24T18:30:00Z)."}), 400

        # Construct the event
        tags = [
            ["title", title],
            ["venue", venue],
            ["date", iso_date],
            ["price", str(price)]
        ]
        event = Event(
            kind=52,
            pubkey=pubkey,
            content=description,
            tags=tags
        )

        # Verify the signature using the provided public key
        if not event.verify(sig):
            return jsonify({"error": "Invalid signature"}), 403

        # Publish the event to NOSTR relays
        relays = ["wss://relay.damus.io", "wss://relay.primal.net", "wss://relay.getalby.com/v1"]
        for relay in relays:
            requests.post(f"{relay}/publish", json=event.to_dict())

        return jsonify({"message": "Event created successfully", "event_id": event.id})

    except Exception as e:
        logger.error(f"Error in create_event: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

def fetch_and_validate_profile(pubkey, required_domain):
    """
    Fetch the profile for a given pubkey and validate that it matches the required domain.
    """
    try:
        # Fetch profile using existing `fetch_profile` logic
        relay_manager = RelayManager(timeout=10)
        relay_manager.add_relay("wss://relay.damus.io")
        relay_manager.add_relay("wss://relay.primal.net")
        relay_manager.add_relay("wss://relay.getalby.com/v1")

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

def validate_nip05(pubkey, nip05_address):
    logger.info(f"In validate_nip05 with variables: {pubkey}, {nip05_address}")
    try:
        domain = nip05_address.split('@')[-1]
        logger.info(f"In validate_nip05 domain: {domain}")

        if domain == "pinkanki.org":
            # Directly access the nostr.json file for internal domain
            SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
            json_url = os.path.join(SITE_ROOT, "static", "nostr.json")
            with open(json_url, 'r') as f:
                data = json.load(f)
            logger.info(f"NIP-05 Check response from local file: {data}")

            # Check if the pubkey matches the one in the NIP-05 record
            if 'names' in data and nip05_address.split('@')[0] in data['names']:
                if data['names'][nip05_address.split('@')[0]] == pubkey:
                    return True
        else:
            # Perform NIP-05 lookup to find the well-known NOSTR JSON file
            well_known_url = f"https://{domain}/.well-known/nostr.json?name={nip05_address.split('@')[0]}"
            logger.info(f"In validate_nip05 well_known_url: {well_known_url}")
            response = requests.get(well_known_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"NIP-05 Check response: {data}")

                # Check if the pubkey matches the one in the NIP-05 record
                if 'names' in data and nip05_address.split('@')[0] in data['names']:
                    if data['names'][nip05_address.split('@')[0]] == pubkey:
                        return True

        return False
    except Exception as e:
        logger.error(f"Error during NIP-05 validation: {e}")
        return False

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

# Build Complete Library
def build_music_library():
    artists = fetch_artists()
    if not artists:
        return []

    music_library = []
    for artist in artists:
        full_artist_name = artist["name"]
        artist_name = full_artist_name.replace(" by Fuzzed Records", "").strip()
        artist_id = artist["id"]
        logger.info(f"Processing artist: {artist_name}")

        albums = fetch_albums(artist_id)
        for album in albums:
            album_title = album["title"]
            album_id = album["id"]
            albumArtUrl = album["albumArtUrl"]
            logger.info(f" - Processing album: {album_title}")

            tracks = fetch_tracks(album_id)
            for track in tracks:
                track_info = {
                    "artist": artist_name,
                    "album": album_title,
                    "albumArtUrl": albumArtUrl,
                    "title": track["title"],
                    "media_url": track["media_url"],
                    "track_id": track["track_id"],
                    "nostr_npub": track["nostr_npub"]
                }
                music_library.append(track_info)
    
    logger.info(f"Total tracks found: {len(music_library)}")
    return music_library

class Main(Resource):
    def post(self):
        return jsonify({'message': 'Welcome to the Fuzzed Records Flask REST App'})

class NostrJson(Resource):
    logger.info('::: In NostrJson :::')
    def get(self):
        logger.info('::: We now have a GET In NostrJson :::')
        SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
        json_url = os.path.join(SITE_ROOT, "static", "nostr.json")
        jsonData = json.load(open(json_url))
        namesList = jsonData['names']
        relayList = jsonData['relays']

        if 'name' not in request.args:
            logger.info('::: No name variable in request...returning whole nostr.json :::')
            nostrJsonResponse = jsonData
            return nostrJsonResponse
        else:
            nostrName = request.args.get('name')
            nostrName = nostrName.lower()
            logger.info('::: Found name variable in request... :::', nostrName)
            if nostrName in namesList:
                pubKey = namesList[nostrName]
                if pubKey in relayList:
                    pubRelays = relayList[pubKey]
                    nostrJsonResponse = { "names" : { nostrName : pubKey }, "relays" :  { pubKey :  pubRelays } }
                    return nostrJsonResponse
                else:
                    nostrJsonResponse = { "names" : { nostrName : pubKey } }
                    return nostrJsonResponse
            else:
                logger.info('::: No name variable found :::')
                nostrJsonResponse = { "names" : {} }
                return nostrJsonResponse

class LnURLp(Resource):
    logger.info('::: In LnURLp :::')
    def get(self, resource_name):
        logger.info('::: We now have a GET In LnURLp :::')
        try:
            # Attempt to read the JSON file
            SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
            with open(os.path.join(SITE_ROOT, "static", resource_name), 'r') as f:
                data = json.load(f)
            logger.info(f'Returning data for resource: {resource_name}')
            return jsonify(data)
        except FileNotFoundError:
            logger.info(f'File not found: {resource_name}')
            return {"error": "File not found"}, 404
        except json.JSONDecodeError:
            logger.info(f'Error decoding JSON file: {resource_name}')
            return {"error": "Error decoding JSON file"}, 500

# adding the defined resources along with their corresponding urls
api.add_resource(Main, '/')
api.add_resource(NostrJson, '/.well-known/nostr.json')
api.add_resource(LnURLp, '/.well-known/lnurlp/<string:resource_name>')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    app.run(debug=True)
