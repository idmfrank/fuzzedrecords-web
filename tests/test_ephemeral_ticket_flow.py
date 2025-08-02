import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
import ticket_utils


def test_generate_and_confirm_ticket(monkeypatch):
    monkeypatch.setattr(ticket_utils, "wallet_priv_hex", "11" * 32)

    called = {}

    async def fake_send(pubkey, ticket_id, event_id, note=""):
        called["args"] = (pubkey, ticket_id, event_id)
        return "evt123"

    monkeypatch.setattr(ticket_utils, "send_ephemeral_ticket", fake_send)

    with app_module.app.test_client() as client:
        resp = client.post(
            "/generate-ticket",
            json={"event_id": "event_xyz", "pubkey": "a" * 64},
        )
        assert resp.status_code == 200
        invoice = resp.get_json()["invoice"]

        resp2 = client.post("/confirm-payment", json={"invoice": invoice})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["status"] == "sent"
        assert "ticket" in data2
        assert data2["ticket"]["ticket_id"] == resp.get_json()["ticket_id"]
        assert called["args"][1] == resp.get_json()["ticket_id"]

        resp3 = client.post("/confirm-payment", json={"invoice": invoice})
        assert resp3.status_code == 400
