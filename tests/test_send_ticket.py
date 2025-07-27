import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import ticket_utils
import app


class DummyEvent:
    def __init__(self):
        self.id = "dummy_event_id"
    def sign(self, priv):
        self.priv = priv


class DummyEncryptedDM:
    def encrypt(self, private_key_hex, cleartext_content, recipient_pubkey):
        self.args = (private_key_hex, cleartext_content, recipient_pubkey)
    def to_event(self):
        return DummyEvent()


class DummyRelayManager:
    def __init__(self):
        self.publish_count = 0
    def add_relay(self, url):
        self.last_relay = url
    def publish_event(self, ev):
        self.publish_count += 1
    def close_connections(self):
        self.closed = True


def test_send_ticket_as_dm(monkeypatch):
    mgr = DummyRelayManager()
    monkeypatch.setattr(ticket_utils, "EncryptedDirectMessage", DummyEncryptedDM)
    monkeypatch.setattr(ticket_utils, "initialize_client", lambda: mgr)
    monkeypatch.setattr(app, "initialize_client", lambda: mgr)
    monkeypatch.setattr(app, "RelayManager", DummyRelayManager)

    ev_id = ticket_utils.send_ticket_as_dm(
        "Concert", "recip_pubkey", "sender_privkey", timestamp=123
    )

    assert ev_id == "dummy_event_id"
    assert mgr.publish_count == 1
