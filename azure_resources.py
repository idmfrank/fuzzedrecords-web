import os, logging, requests
from flask import jsonify
from flask_restful import Resource
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)
# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))

class Main(Resource):
    def post(self):
        return jsonify({'message': 'Welcome to the Fuzzed Records Flask REST App'})

class NostrJson(Resource):
    def get(self):
        logger.info("Fetching admin users and relays from Entra ID")
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        graph_api_base = "https://graph.microsoft.com/v1.0"

        app = ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
        token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in token:
            logger.error("Failed to acquire token")
            return jsonify({"error": "Authentication failed"}), 500
        access_token = token["access_token"]
        # Fetch groups
        grp_resp = requests.get(
            f"{graph_api_base}/groups?$select=displayName,description",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT
        )
        groups = grp_resp.json().get("value", [])
        relay_groups = {
            g["displayName"]: g["description"]
            for g in groups
            if g["displayName"].endswith("Relay")
               and g["description"].startswith("wss://")
        }
        # Fetch users
        usr_resp = requests.get(
            f"{graph_api_base}/users?$select=id,displayName,jobTitle",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT
        )
        users = usr_resp.json().get("value", [])
        names = {}
        relays = {}
        for u in users:
            pubkey = u.get("jobTitle")
            name = u.get("displayName")
            if not pubkey or not name:
                continue
            names[name] = pubkey
            relays[pubkey] = []
            uid = u.get("id")
            mem_resp = requests.get(
                f"{graph_api_base}/users/{uid}/memberOf?$select=displayName",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=HTTP_TIMEOUT
            )
            for g in mem_resp.json().get("value", []):
                dn = g.get("displayName")
                if dn in relay_groups:
                    relays[pubkey].append(relay_groups[dn])
        return jsonify({"names": names, "relays": relays})

def register_resources(api):
    api.add_resource(Main, '/')
    api.add_resource(NostrJson, '/.well-known/nostr.json')