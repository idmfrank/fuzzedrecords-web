import os
import sys
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_tracks_first_request_builds_library(monkeypatch):
    import app as app_module
    import wavlake_utils
    importlib.reload(app_module)
    importlib.reload(wavlake_utils)

    sample = [{
        "artist": "A",
        "album": "B",
        "title": "T",
        "media_url": "url",
        "track_id": "1",
    }]

    # Ensure cache empty
    wavlake_utils._track_cache = {"library": None, "ts": 0}

    monkeypatch.setattr(wavlake_utils, "build_music_library", lambda: sample)

    with app_module.app.test_client() as client:
        resp = client.get("/tracks")
        assert resp.status_code == 200
        assert resp.get_json() == {"tracks": sample}

