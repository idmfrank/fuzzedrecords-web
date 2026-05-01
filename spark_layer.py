from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class UserWallet:
    user_id: str
    username: str
    spark_address: str
    encrypted_mnemonic: str
    balances: dict[str, int] = field(default_factory=lambda: {"BTC": 0, "USDC": 0, "USDB": 0})


class InMemorySparkLayer:
    """MVP Spark-compatible service with deterministic local state.

    This service is intentionally provider-agnostic so we can swap in a real Spark
    SDK adapter later without changing Flask routes.
    """

    def __init__(self, domain: str):
        self.domain = domain
        self._wallets_by_user: dict[str, UserWallet] = {}
        self._wallets_by_username: dict[str, UserWallet] = {}
        self._ledger: list[dict[str, Any]] = []
        self._lock = Lock()

    def _spark_address(self, username: str) -> str:
        return f"{username}@{self.domain}"

    def create_wallet(self, user_id: str, username: str) -> UserWallet:
        with self._lock:
            if user_id in self._wallets_by_user:
                return self._wallets_by_user[user_id]

            encrypted_mnemonic = f"vault://{uuid.uuid4()}"  # placeholder custody ref
            wallet = UserWallet(
                user_id=user_id,
                username=username,
                spark_address=self._spark_address(username),
                encrypted_mnemonic=encrypted_mnemonic,
            )
            self._wallets_by_user[user_id] = wallet
            self._wallets_by_username[username] = wallet
            return wallet

    def get_wallet_by_username(self, username: str) -> UserWallet | None:
        return self._wallets_by_username.get(username)

    def transfer(self, sender_id: str, receiver_username: str, amount_sats: int, idempotency_key: str | None) -> dict[str, Any]:
        if amount_sats <= 0:
            raise ValueError("amount_sats must be > 0")
        with self._lock:
            sender = self._wallets_by_user.get(sender_id)
            receiver = self._wallets_by_username.get(receiver_username)
            if not sender or not receiver:
                raise ValueError("sender or receiver wallet not found")
            if sender.balances["BTC"] < amount_sats:
                raise ValueError("insufficient funds")

            sender.balances["BTC"] -= amount_sats
            receiver.balances["BTC"] += amount_sats
            tx = {
                "id": str(uuid.uuid4()),
                "idempotency_key": idempotency_key,
                "type": "internal_transfer",
                "sender_user_id": sender_id,
                "receiver_user_id": receiver.user_id,
                "amount_sats": amount_sats,
                "timestamp": int(time.time()),
            }
            self._ledger.append(tx)
            return tx

    def pay_lightning_invoice(self, sender_id: str, invoice: str, amount_sats: int, max_fee_sats: int) -> dict[str, Any]:
        if amount_sats <= 0:
            raise ValueError("amount_sats must be > 0")
        with self._lock:
            sender = self._wallets_by_user.get(sender_id)
            if not sender:
                raise ValueError("sender wallet not found")
            total = amount_sats + max_fee_sats
            if sender.balances["BTC"] < total:
                raise ValueError("insufficient funds")
            sender.balances["BTC"] -= total
            tx = {
                "id": str(uuid.uuid4()),
                "type": "lightning_payout",
                "sender_user_id": sender_id,
                "invoice": invoice,
                "amount_sats": amount_sats,
                "fee_sats": max_fee_sats,
                "timestamp": int(time.time()),
            }
            self._ledger.append(tx)
            return tx

    def credit(self, user_id: str, asset: str, amount: int):
        with self._lock:
            wallet = self._wallets_by_user[user_id]
            wallet.balances[asset] += amount

    def get_balance(self, user_id: str) -> dict[str, int]:
        wallet = self._wallets_by_user.get(user_id)
        if not wallet:
            raise ValueError("wallet not found")
        return dict(wallet.balances)

    def ledger(self) -> list[dict[str, Any]]:
        return list(self._ledger)


def lnurlp_response(api_base: str, username: str) -> dict[str, Any]:
    return {
        "callback": f"{api_base}/pay/{username}",
        "minSendable": 1000,
        "maxSendable": 100000000,
        "metadata": '[["text/plain", "Pay user"]]',
        "tag": "payRequest",
    }
