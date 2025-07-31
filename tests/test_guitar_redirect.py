import os
import sys
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module


def test_guitar_path_redirect():
    importlib.reload(app_module)
    with app_module.app.test_client() as client:
        resp = client.get('/fuzzedguitars')
        assert resp.status_code in (301, 302)
        assert resp.headers['Location'] == 'https://fuzzedrecords.com/#gear'
