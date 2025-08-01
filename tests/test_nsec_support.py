import os
import sys
import importlib
import bech32

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_client


def _encode_nsec(hex_key: str) -> str:
    words = bech32.convertbits(bytes.fromhex(hex_key), 8, 5)
    return bech32.bech32_encode("nsec", words)


def test_nsec_env(monkeypatch):
    hex_key = "11" * 32
    nsec = _encode_nsec(hex_key)
    monkeypatch.setenv("WALLET_PRIVKEY_HEX", nsec)
    import app as app_module
    importlib.reload(app_module)
    assert app_module.WALLET_PRIVKEY_HEX == hex_key
    assert app_module.SERVER_WALLET_PUBKEY


def test_nsec_to_hex_roundtrip():
    priv_hex = "22" * 32
    nsec = _encode_nsec(priv_hex)
    assert nostr_client.nsec_to_hex(nsec) == priv_hex

