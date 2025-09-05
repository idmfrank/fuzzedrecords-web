import os
import sys
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module


def test_shop_route_accessible():
    importlib.reload(app_module)
    with app_module.app.test_client() as client:
        resp = client.get('/shop')
        assert resp.status_code == 200
        assert b'Custom Guitars' in resp.data
