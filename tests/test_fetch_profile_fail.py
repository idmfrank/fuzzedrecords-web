import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
from app import app

class DummyMgr:
    async def prepare_relays(self):
        pass
    @property
    def connection_statuses(self):
        return {"r1": False, "r2": False}

def test_fetch_profile_returns_503(monkeypatch):
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: DummyMgr())
    with app.test_client() as client:
        resp = client.post("/fetch-profile", json={"pubkey": "abc"})
        assert resp.status_code == 503
        assert resp.get_json()["error"] == "Unable to connect to Nostr relays"
