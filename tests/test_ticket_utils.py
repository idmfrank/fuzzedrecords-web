import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ticket_utils import generate_ticket


def test_generate_ticket_returns_expected_values():
    payload_str, img_io = generate_ticket('Concert', 'pubkey', 12345)
    assert payload_str == '{"event": "Concert", "pubkey": "pubkey", "timestamp": 12345}'
    assert img_io is not None
    assert len(img_io.getvalue()) > 0

