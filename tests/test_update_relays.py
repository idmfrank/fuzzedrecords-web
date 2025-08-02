import os, sys, importlib, asyncio

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_update_relays_updates_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RELAY_URLS", "wss://a.com")
    import app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_pool_started", True)

    with app_module.app.test_client() as client:
        resp = client.post("/update-relays", json={"relays": ["wss://b.com"]})
        assert resp.status_code == 200
        assert set(app_module.ACTIVE_RELAYS) == {"wss://a.com", "wss://b.com"}
        with open("relays.txt") as f:
            lines = {l.strip() for l in f if l.strip()}
        assert lines == {"wss://a.com", "wss://b.com"}
        class DummyRelayManager:
            def __init__(self, timeout=None):
                self.relays = {}
            def add_relay(self, url):
                self.relays[url] = object()
            async def prepare_relays(self):
                pass
            async def close_connections(self):
                pass
        asyncio.run(app_module.close_relay_managers())
        monkeypatch.setattr(app_module, "RelayManager", DummyRelayManager)
        mgr = asyncio.run(app_module.get_relay_manager())
        try:
            assert set(mgr.relays.keys()) == {"wss://a.com", "wss://b.com"}
        finally:
            asyncio.run(app_module.release_relay_manager(mgr))


def test_update_relays_rejects_invalid_urls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RELAY_URLS", "wss://a.com")
    import app as app_module
    import importlib
    importlib.reload(app_module)

    with app_module.app.test_client() as client:
        resp = client.post("/update-relays", json={"relays": ["http://bad.com"]})
        assert resp.status_code == 400
        assert "Invalid relay URL" in resp.get_json()["error"]

