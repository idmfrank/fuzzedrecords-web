import os
import sys
import base64

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
import ticket_utils


def test_send_ticket_endpoint_invalid_pubkey(monkeypatch):
    monkeypatch.setattr(ticket_utils, "wallet_priv_hex", "11" * 32)
    with app_module.app.test_client() as client:
        resp = client.post(
            "/send_ticket",
            json={
                "id": "1",
                "pubkey": "abc",
                "content": base64.b64encode(b"cipher").decode(),
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Invalid pubkey"


def test_send_ticket_endpoint_invalid_content(monkeypatch):
    monkeypatch.setattr(ticket_utils, "wallet_priv_hex", "11" * 32)
    with app_module.app.test_client() as client:
        resp = client.post(
            "/send_ticket",
            json={"id": "1", "pubkey": "a" * 64, "content": "bad"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Invalid encrypted payload"
