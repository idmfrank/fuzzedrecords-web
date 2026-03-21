import importlib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module


def test_cors_disabled_when_frontend_origins_unset(monkeypatch):
    monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)
    importlib.reload(app_module)

    with app_module.app.test_client() as client:
        response = client.get("/", headers={"Origin": "https://evil.example"})

    assert app_module.ALLOWED_CORS_ORIGINS == []
    assert app_module.CORS_CREDENTIALS_ENABLED is False
    assert response.headers.get("Access-Control-Allow-Origin") is None
    assert response.headers.get("Access-Control-Allow-Credentials") is None


def test_cors_allows_only_configured_origins(monkeypatch):
    monkeypatch.setenv(
        "FRONTEND_ORIGINS",
        "https://app.example.com, https://admin.example.com",
    )
    importlib.reload(app_module)

    with app_module.app.test_client() as client:
        allowed = client.get("/", headers={"Origin": "https://app.example.com"})
        blocked = client.get("/", headers={"Origin": "https://evil.example"})

    assert app_module.ALLOWED_CORS_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert app_module.CORS_CREDENTIALS_ENABLED is True
    assert allowed.headers.get("Access-Control-Allow-Origin") == "https://app.example.com"
    assert allowed.headers.get("Access-Control-Allow-Credentials") == "true"
    assert blocked.headers.get("Access-Control-Allow-Origin") is None
    assert blocked.headers.get("Access-Control-Allow-Credentials") is None
