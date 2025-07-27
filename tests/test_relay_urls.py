import os
import sys
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module


def test_relay_urls_strip(monkeypatch):
    original = os.environ.get("RELAY_URLS")
    monkeypatch.setenv("RELAY_URLS", "wss://a.com, wss://b.com")
    importlib.reload(app_module)
    assert app_module.RELAY_URLS == ["wss://a.com", "wss://b.com"]
    if original is not None:
        monkeypatch.setenv("RELAY_URLS", original)
    else:
        monkeypatch.delenv("RELAY_URLS", raising=False)
    importlib.reload(app_module)


def test_active_relays_default(monkeypatch, tmp_path):
    """ACTIVE_RELAYS should fall back to the default list when no files or env."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RELAY_URLS", raising=False)
    importlib.reload(app_module)

    assert app_module.ACTIVE_RELAYS == [
        "wss://relay.damus.io",
        "wss://relay.primal.net",
        "wss://relay.mostr.pub",
        "wss://nos.lol",
    ]
