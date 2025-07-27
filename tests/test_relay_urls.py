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
