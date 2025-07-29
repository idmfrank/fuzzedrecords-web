import os, sys, importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_update_relays_updates_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RELAY_URLS", "wss://a.com")
    import app as app_module
    importlib.reload(app_module)

    with app_module.app.test_client() as client:
        resp = client.post("/update-relays", json={"relays": ["wss://b.com"]})
        assert resp.status_code == 200
        assert set(app_module.ACTIVE_RELAYS) == {"wss://a.com", "wss://b.com"}
        with open("relays.txt") as f:
            lines = {l.strip() for l in f if l.strip()}
        assert lines == {"wss://a.com", "wss://b.com"}
        mgr = app_module.initialize_client()
        assert set(mgr.relays.keys()) == {"wss://a.com", "wss://b.com"}


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

