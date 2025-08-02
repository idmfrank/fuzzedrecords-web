import os, sys, importlib, asyncio

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_relay_connect_timeout_env(monkeypatch):
    monkeypatch.setenv("RELAY_CONNECT_TIMEOUT", "6")
    import app as app_module
    importlib.reload(app_module)

    assert app_module.RELAY_CONNECT_TIMEOUT == 6.0

    class DummyRelay:
        def __init__(self, url, timeout):
            self.url = url
            self.timeout = timeout

    class DummyRelayManager:
        def __init__(self, timeout=None):
            self.timeout = timeout
            self.relays = {}

        def add_relay(self, url):
            self.relays[url] = DummyRelay(url, self.timeout)

        async def prepare_relays(self):
            pass

        async def close_connections(self):
            pass

    monkeypatch.setattr(app_module, "RelayManager", DummyRelayManager)

    mgr = asyncio.run(app_module.get_relay_manager())
    try:
        assert all(r.timeout == 6.0 for r in mgr.relays.values())
    finally:
        asyncio.run(app_module.release_relay_manager(mgr))


def test_tls_disable_warning(monkeypatch, caplog):
    monkeypatch.setenv("DISABLE_TLS_VERIFY", "1")
    import nostr_client
    importlib.reload(nostr_client)

    async def dummy_connect(*args, **kwargs):
        class DummyWS:
            async def close(self):
                pass

        return DummyWS()

    async def dummy_recv_loop(self, relay):
        pass

    monkeypatch.setattr(nostr_client.websockets, "connect", dummy_connect)
    monkeypatch.setattr(nostr_client.RelayManager, "_recv_loop", dummy_recv_loop)

    mgr = nostr_client.RelayManager()
    mgr.add_relay("wss://example.com")

    caplog.set_level("WARNING")
    asyncio.run(mgr.prepare_relays())

    assert any("TLS verification is disabled" in rec.message for rec in caplog.records)

