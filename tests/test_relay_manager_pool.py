import asyncio

import app


class DummyRelayManager:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.relays = {}
        self.prepare_count = 0
        self.closed = False

    def add_relay(self, url):
        self.relays[url] = object()

    async def prepare_relays(self):
        self.prepare_count += 1

    async def publish_event(self, ev):
        pass

    async def close_connections(self):
        self.closed = True


def test_manager_reuse(monkeypatch):
    asyncio.run(app.close_relay_managers())
    monkeypatch.setattr(app, "_pool_started", True)
    monkeypatch.setattr(app, "RelayManager", DummyRelayManager)

    async def run_test():
        mgr1 = await app.get_relay_manager()
        await app.release_relay_manager(mgr1)
        mgr2 = await app.get_relay_manager()
        await app.release_relay_manager(mgr2)
        assert mgr1 is mgr2
        assert mgr1.prepare_count == 1

    asyncio.run(run_test())


def test_shutdown_closes_connections(monkeypatch):
    asyncio.run(app.close_relay_managers())
    monkeypatch.setattr(app, "_pool_started", True)
    monkeypatch.setattr(app, "RelayManager", DummyRelayManager)

    async def run_test():
        mgr = await app.get_relay_manager()
        await app.release_relay_manager(mgr)
        await app.close_relay_managers()
        assert mgr.closed

    asyncio.run(run_test())

