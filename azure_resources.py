import os, logging, requests
from requests.exceptions import RequestException
from flask import request
from flask_restful import Resource
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)
# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))

class Main(Resource):
    def post(self):
        return {"message": "Welcome to the Fuzzed Records Flask REST App"}

class NostrJson(Resource):
    def get(self):
        filter_name = request.args.get("name")
        if not filter_name:
            return {"error": "Missing name parameter"}, 400

        logger.info("Fetching admin users and relays from Entra ID")
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        missing = [
            name
            for name, value in {
                "TENANT_ID": tenant_id,
                "CLIENT_ID": client_id,
                "CLIENT_SECRET": client_secret,
            }.items()
            if not value
        ]
        if missing:
            logger.error("Missing Entra ID configuration: %s", ", ".join(missing))
            return {
                "error": "Missing Entra ID configuration",
                "missing": missing,
            }, 500
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        graph_api_base = "https://graph.microsoft.com/v1.0"

        app = ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
        token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in token:
            logger.error(
                "Failed to acquire token: %s %s",
                token.get("error"),
                token.get("error_description"),
            )
            return {
                "error": "Authentication failed. Check TENANT_ID, CLIENT_ID, and CLIENT_SECRET.",
            }, 502
        access_token = token["access_token"]
        # Fetch groups
        try:
            grp_resp = requests.get(
                f"{graph_api_base}/groups?$select=displayName,description",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=HTTP_TIMEOUT,
            )
            grp_resp.raise_for_status()
        except RequestException as e:
            logger.error("Error fetching groups: %s", e)
            return {"error": "Failed to retrieve groups"}, 502

        groups = grp_resp.json().get("value", [])
        relay_groups = {
            g["displayName"]: g["description"]
            for g in groups
            if g["displayName"].endswith("Relay")
               and g["description"].startswith("wss://")
        }
        # Fetch users
        try:
            usr_resp = requests.get(
                f"{graph_api_base}/users?$select=id,displayName,jobTitle,userPrincipalName",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=HTTP_TIMEOUT,
            )
            usr_resp.raise_for_status()
        except RequestException as e:
            logger.error("Error fetching users: %s", e)
            return {"error": "Failed to retrieve users"}, 502

        users = usr_resp.json().get("value", [])
        filter_name_l = filter_name.lower()
        names = {}
        relays = {}
        for u in users:
            pubkey = u.get("jobTitle")
            display_name = u.get("displayName")
            principal_name = u.get("userPrincipalName")
            if not pubkey or not display_name:
                continue
            name_matches = display_name.lower() == filter_name_l
            principal_matches = principal_name and principal_name.lower() == filter_name_l
            if filter_name_l and not (name_matches or principal_matches):
                continue
            name_key = principal_name if principal_matches else display_name
            names[name_key] = pubkey
            relays[pubkey] = []
            uid = u.get("id")
            try:
                mem_resp = requests.get(
                    f"{graph_api_base}/users/{uid}/memberOf?$select=displayName",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=HTTP_TIMEOUT,
                )
                mem_resp.raise_for_status()
            except RequestException as e:
                logger.error("Error fetching memberships for %s: %s", uid, e)
                return {"error": "Failed to retrieve group memberships"}, 502

            for g in mem_resp.json().get("value", []):
                dn = g.get("displayName")
                if dn in relay_groups:
                    relays[pubkey].append(relay_groups[dn])

        if filter_name and not names:
            return {}
        return {"names": names, "relays": relays}

def register_resources(api):
    api.add_resource(Main, '/')
    api.add_resource(NostrJson, '/.well-known/nostr.json')
