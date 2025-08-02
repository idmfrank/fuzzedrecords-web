import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def test_build_music_library(monkeypatch):
    base_url = 'https://wavlake.com/api/v1'
    search_term = ' by Fuzzed Records'
    monkeypatch.setenv('WAVLAKE_API_BASE', base_url)
    monkeypatch.setenv('SEARCH_TERM', search_term)

    import importlib
    wavlake_utils = importlib.reload(importlib.import_module('wavlake_utils'))

    artists = [{"id": "artist1", "name": "Test Artist"}]
    albums = [{"id": "album1", "title": "Test Album"}]
    tracks = [
        {
            "id": "track1",
            "artist": f"Test Artist{search_term}",
            "albumTitle": "Test Album",
            "title": "Track One",
            "mediaUrl": "url1",
        },
        {
            "id": "track2",
            "artist": f"Test Artist{search_term}",
            "albumTitle": "Test Album",
            "title": "Track Two",
            "mediaUrl": "url2",
        },
    ]

    def mock_get(url, *args, **kwargs):
        if url.endswith("/content/search"):
            return DummyResponse({"data": artists})
        if url.endswith("/content/artist/artist1"):
            return DummyResponse({"albums": albums})
        if url.endswith("/content/album/album1"):
            return DummyResponse({"tracks": tracks})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(wavlake_utils.requests, "get", mock_get)

    expected = [
        {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Track One",
            "media_url": "url1",
            "track_id": "track1",
        },
        {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Track Two",
            "media_url": "url2",
            "track_id": "track2",
        },
    ]

    library = wavlake_utils.build_music_library()
    assert library == expected
