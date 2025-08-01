import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_client


def _make_event(priv):
    pub = nostr_client.derive_public_key_hex(priv)
    return nostr_client.Event(
        public_key=pub,
        content="hello",
        kind=nostr_client.EventKind.TEXT_NOTE,
        tags=[],
        created_at=123,
    )


def test_event_sign_and_verify():
    priv = "11" * 32
    ev = _make_event(priv)
    ev.sign(priv)
    assert ev.verify()


def test_event_verify_fails_when_modified():
    priv = "11" * 32
    ev = _make_event(priv)
    ev.sign(priv)
    # modify content after signing
    ev.content = "tampered"
    assert not ev.verify()
