import os
import sys

from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import azure_storage_limiter


class DummyEntity(dict):
    def __init__(self, *args, etag=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata = {"etag": etag}


class DummyTableClient:
    def __init__(self):
        self.entities = {}
        self.conflict_once = False
        self.create_conflict_once = False

    def create_table(self):
        pass

    def _next_etag(self, previous=None):
        if previous and previous.startswith("v") and previous[1:].isdigit():
            return f"v{int(previous[1:]) + 1}"
        return "v1"

    def get_entity(self, pk, rk):
        if (pk, rk) not in self.entities:
            raise ResourceNotFoundError("not found")
        entity = self.entities[(pk, rk)]
        return DummyEntity(entity, etag=entity["etag"])

    def update_entity(self, entity, mode="MERGE", *, etag=None, match_condition=None):
        key = (entity["PartitionKey"], entity["RowKey"])
        if key not in self.entities:
            raise ResourceNotFoundError("not found")

        stored = self.entities[key]
        if self.conflict_once:
            stored["count"] += 1
            stored["etag"] = self._next_etag(stored["etag"])
            self.conflict_once = False

        if match_condition == MatchConditions.IfNotModified and etag != stored["etag"]:
            raise ResourceModifiedError("etag mismatch")

        new_entity = dict(entity)
        new_entity["etag"] = self._next_etag(stored["etag"])
        self.entities[key] = new_entity

    def create_entity(self, entity):
        key = (entity["PartitionKey"], entity["RowKey"])
        if self.create_conflict_once:
            self.entities[key] = {**entity, "count": 1, "etag": "v1"}
            self.create_conflict_once = False
            raise ResourceExistsError("already exists")
        if key in self.entities:
            raise ResourceExistsError("already exists")
        self.entities[key] = {**entity, "etag": "v1"}

    def delete_entity(self, pk, rk):
        self.entities.pop((pk, rk), None)


class DummyService:
    def __init__(self, *args, **kwargs):
        self.client = DummyTableClient()

    @classmethod
    def from_connection_string(cls, conn_str):
        return cls()

    def get_table_client(self, table_name):
        return self.client


def build_limiter(monkeypatch):
    monkeypatch.setattr(azure_storage_limiter, "TableServiceClient", DummyService)
    return azure_storage_limiter.AzureTableStorage(connection_string="conn")


def test_key_sanitization(monkeypatch):
    limiter = build_limiter(monkeypatch)

    key = "LIMITER/169.254.130.1/generic_endpoint/10/1/minute"

    assert limiter.incr(key, expiry=60) == 1
    assert limiter.incr(key, expiry=60) == 2
    assert limiter.get(key) == 2

    partition, row = limiter._get_partition_and_row(key)
    assert partition in {ent[0] for ent in limiter.client.entities.keys()}
    assert row in {ent[1] for ent in limiter.client.entities.keys()}

    limiter.clear(key)
    assert limiter.get(key) == 0


def test_incr_retries_on_optimistic_concurrency_conflict(monkeypatch):
    limiter = build_limiter(monkeypatch)
    key = "LIMITER/127.0.0.1/conflict"

    assert limiter.incr(key, expiry=60) == 1
    limiter.client.conflict_once = True

    assert limiter.incr(key, expiry=60) == 3
    assert limiter.get(key) == 3


def test_incr_retries_when_create_races(monkeypatch):
    limiter = build_limiter(monkeypatch)
    key = "LIMITER/127.0.0.1/create-race"

    limiter.client.create_conflict_once = True

    assert limiter.incr(key, expiry=60) == 2
    assert limiter.get(key) == 2
