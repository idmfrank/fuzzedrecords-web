import os
import sys
import importlib
import requests

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import azure_resources

class DummyCCA:
    def __init__(self, *args, **kwargs):
        pass
    def acquire_token_for_client(self, scopes=None):
        return {"access_token": "tok"}

class DummyResponse:
    def __init__(self, data=None, status=200):
        self._data = data or {}
        self.status_code = status
    def json(self):
        return self._data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

def _reload_app(monkeypatch, get_func):
    monkeypatch.setattr(azure_resources, "ConfidentialClientApplication", DummyCCA)
    monkeypatch.setattr(azure_resources.requests, "get", get_func)
    monkeypatch.setenv("TENANT_ID", "t")
    monkeypatch.setenv("CLIENT_ID", "c")
    monkeypatch.setenv("CLIENT_SECRET", "s")
    import app as app_module
    importlib.reload(app_module)
    return app_module

def test_groups_request_exception(monkeypatch):
    def bad_get(url, *args, **kwargs):
        raise requests.RequestException("boom")
    app_module = _reload_app(monkeypatch, bad_get)
    with app_module.app.test_client() as client:
        resp = client.get("/.well-known/nostr.json")
        assert resp.status_code == 502
        assert resp.get_json()["error"] == "Failed to retrieve groups"

def test_membership_http_error(monkeypatch):
    responses = []
    # groups response
    responses.append(DummyResponse({"value": []}))
    # users response with one user
    responses.append(DummyResponse({"value": [{"id": "u1", "displayName": "User", "jobTitle": "pk"}]}))
    # membership response with HTTP error
    responses.append(DummyResponse({}, status=500))
    def seq_get(url, *args, **kwargs):
        return responses.pop(0)
    app_module = _reload_app(monkeypatch, seq_get)
    with app_module.app.test_client() as client:
        resp = client.get("/.well-known/nostr.json")
        assert resp.status_code == 502
        assert "memberships" in resp.get_json()["error"]
