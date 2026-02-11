import os
import sys
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_send_dm_missing_fields_returns_400():
    import app as app_module
    import nostr_utils
    importlib.reload(app_module)
    importlib.reload(nostr_utils)

    with app_module.app.test_client() as client:
        resp = client.post('/send_dm', json={"to_pubkey": "abc"})
        assert resp.status_code == 400
        assert resp.get_json() == {"error": "Missing DM fields"}
