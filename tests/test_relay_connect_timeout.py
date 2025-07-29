import os, sys, importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_relay_connect_timeout_env(monkeypatch):
    monkeypatch.setenv("RELAY_CONNECT_TIMEOUT", "6")
    import app as app_module
    importlib.reload(app_module)

    assert app_module.RELAY_CONNECT_TIMEOUT == 6.0
    mgr = app_module.initialize_client()
    assert all(r.timeout == 6.0 for r in mgr.relays.values())
