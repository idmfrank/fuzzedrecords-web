import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app


def test_parse_rate_limit_config_defaults(monkeypatch):
    monkeypatch.delenv("RATELIMIT_DEFAULT", raising=False)

    assert app.parse_rate_limit_config("RATELIMIT_DEFAULT", "60 per minute") == ["60 per minute"]


def test_parse_rate_limit_config_supports_semicolon_lists(monkeypatch):
    monkeypatch.setenv("RATELIMIT_APPLICATION", "100 per minute; 1000 per hour")

    assert app.parse_rate_limit_config("RATELIMIT_APPLICATION") == [
        "100 per minute",
        "1000 per hour",
    ]
