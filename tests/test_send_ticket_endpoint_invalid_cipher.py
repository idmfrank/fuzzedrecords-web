import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
import ticket_utils


def test_send_ticket_endpoint_invalid_cipher(monkeypatch):
    monkeypatch.setattr(ticket_utils, "wallet_priv_hex", "11" * 32)

    def bad_decrypt(priv, pub, cipher):
        raise ValueError("bad cipher")

    monkeypatch.setattr(ticket_utils, "nip44_decrypt", bad_decrypt)

    with app_module.app.test_client() as client:
        resp = client.post(
            "/send_ticket",
            json={"id": "1", "pubkey": "abc", "content": "bad"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Invalid encrypted payload"
