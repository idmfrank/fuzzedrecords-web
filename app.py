from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_restful import Resource, Api
from flask_cors import CORS
from pynostr.relay_manager import RelayManager
from pynostr.filters import FiltersList, Filters
from pynostr.event import EventKind
import os, json, time, uuid, requests

app = Flask(__name__)
CORS(app)
api = Api(app)
WAVLAKE_BASE_URL = "https://api.wavlake.com/v1/content"

# In-memory cache (simple dictionary)
cache = {}

# Cache settings
CACHE_TIMEOUT = 300  # Cache timeout in seconds (e.g., 5 minutes)

@app.route('/')
def index():
    print('Request for index page received')
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
        print(f'Received request to fetch profile for pubkey: {pubkey_hex}')

        # Check if the profile is already cached
        if pubkey_hex in cache:
            cached_profile, timestamp = cache[pubkey_hex]
            if time.time() - timestamp < CACHE_TIMEOUT:
                print(f'Profile for {pubkey_hex} returned from cache.')
                return jsonify(cached_profile)
            else:
                # Remove the stale cache entry
                del cache[pubkey_hex]

        # Initialize RelayManager with a timeout of 2 seconds and key trusted default relays
        relay_manager = RelayManager(timeout=2)
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
                print(f'Received profile event: {profile_data}')
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
        print(f'Error occurred in fetch-profile: {e}')
        return jsonify({"error": str(e)})

@app.route('/tracks', methods=['GET'])
def get_fuzzed_records_tracks():
    """Fetch and return all tracks from artists signed to Fuzzed Records."""
    try:
        tracks = build_fuzzed_records_library()
        return jsonify({"tracks": tracks})
    except Exception as e:
        print(f"Error fetching track library: {e}")
        return jsonify({"error": "Unable to fetch track library"}), 500

def validate_nip05(pubkey, nip05_address):
    print(f"In validate_nip05 with variables: {pubkey}, {nip05_address}")
    try:
        domain = nip05_address.split('@')[-1]
        print(f"In validate_nip05 domain: {domain}")

        if domain == "pinkanki.org":
            # Directly access the nostr.json file for internal domain
            SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
            json_url = os.path.join(SITE_ROOT, "static", "nostr.json")
            with open(json_url, 'r') as f:
                data = json.load(f)
            print(f"NIP-05 Check response from local file: {data}")

            # Check if the pubkey matches the one in the NIP-05 record
            if 'names' in data and nip05_address.split('@')[0] in data['names']:
                if data['names'][nip05_address.split('@')[0]] == pubkey:
                    return True
        else:
            # Perform NIP-05 lookup to find the well-known NOSTR JSON file
            well_known_url = f"https://{domain}/.well-known/nostr.json?name={nip05_address.split('@')[0]}"
            print(f"In validate_nip05 well_known_url: {well_known_url}")
            response = requests.get(well_known_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"NIP-05 Check response: {data}")

                # Check if the pubkey matches the one in the NIP-05 record
                if 'names' in data and nip05_address.split('@')[0] in data['names']:
                    if data['names'][nip05_address.split('@')[0]] == pubkey:
                        return True

        return False
    except Exception as e:
        print(f"Error during NIP-05 validation: {e}")
        return False

def search_artists_by_name(query):
    """Search for artists whose names include a specific query."""
    url = f"{WAVLAKE_BASE_URL}/search"
    params = {"q": query, "type": "artist"}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            artists = response.json().get("artists", [])
            return [{"id": artist["id"], "name": artist["name"]} for artist in artists]
        else:
            print(f"Error fetching artists: {response.status_code}")
            return []
    except Exception as e:
        print(f"An error occurred while searching for artists: {e}")
        return []

def fetch_tracks_for_artist(artist_id):
    """Fetch all tracks for a given artist ID."""
    url = f"{WAVLAKE_BASE_URL}/artists/{artist_id}/tracks"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            tracks = response.json().get("tracks", [])
            return [{"title": track["title"], "audio_url": track["audio_url"]} for track in tracks]
        else:
            print(f"Error fetching tracks for artist {artist_id}: {response.status_code}")
            return []
    except Exception as e:
        print(f"An error occurred while fetching tracks: {e}")
        return []

def build_fuzzed_records_library():
    """Build a track library for all artists signed to Fuzzed Records."""
    query = "by Fuzzed Records"
    print("Searching for artists ending with 'by Fuzzed Records'...")
    artists = search_artists_by_name(query)
    
    if not artists:
        print("No artists found.")
        return []

    print(f"Found {len(artists)} artist(s):")
    for artist in artists:
        print(f" - {artist['name']} (ID: {artist['id']})")

    # Fetch all tracks for each artist
    all_tracks = []
    for artist in artists:
        print(f"\nFetching tracks for artist: {artist['name']}")
        tracks = fetch_tracks_for_artist(artist["id"])
        for track in tracks:
            print(f"  - {track['title']}")
            all_tracks.append({
                "artist": artist["name"],
                "title": track["title"],
                "audio_url": track["audio_url"]
            })
    
    return all_tracks

class Main(Resource):
    def post(self):
        return jsonify({'message': 'Welcome to the Fuzzed Records Flask REST App'})

class NostrJson(Resource):
    print('::: In NostrJson :::')
    def get(self):
        print('::: We now have a GET In NostrJson :::')
        SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
        json_url = os.path.join(SITE_ROOT, "static", "nostr.json")
        jsonData = json.load(open(json_url))
        namesList = jsonData['names']
        relayList = jsonData['relays']

        if 'name' not in request.args:
            print('::: No name variable in request...returning whole nostr.json :::')
            nostrJsonResponse = jsonData
            return nostrJsonResponse
        else:
            nostrName = request.args.get('name')
            nostrName = nostrName.lower()
            print('::: Found name variable in request... :::', nostrName)
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
                print('::: No name variable found :::')
                nostrJsonResponse = { "names" : {} }
                return nostrJsonResponse

class LnURLp(Resource):
    print('::: In LnURLp :::')
    def get(self, resource_name):
        print('::: We now have a GET In LnURLp :::')
        try:
            # Attempt to read the JSON file
            SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
            with open(os.path.join(SITE_ROOT, "static", resource_name), 'r') as f:
                data = json.load(f)
            print(f'Returning data for resource: {resource_name}')
            return jsonify(data)
        except FileNotFoundError:
            print(f'File not found: {resource_name}')
            return {"error": "File not found"}, 404
        except json.JSONDecodeError:
            print(f'Error decoding JSON file: {resource_name}')
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
