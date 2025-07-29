import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from app import app
from nostr_client import nprofile_encode


def test_fetch_nprofile_fallback(monkeypatch):
    pubkey = "00" * 32
    nprof = nprofile_encode(pubkey, ["wss://relay.example.com"])

    monkeypatch.setattr(app_module, "fetch_profile_by_pubkey", lambda p, r: {"name": "x"})

    with app.test_client() as client:
        resp = client.post("/fetch-nprofile", json={"nprofile": nprof})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pubkey"] == pubkey
        assert data["metadata"] == {"name": "x"}
