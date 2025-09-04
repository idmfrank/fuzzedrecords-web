import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import azure_storage_limiter


class DummyTableClient:
    def __init__(self):
        self.entities = {}

    def create_table(self):
        pass

    def get_entity(self, pk, rk):
        if (pk, rk) not in self.entities:
            from azure.core.exceptions import AzureError

            raise AzureError("not found")
        return dict(self.entities[(pk, rk)])

    def update_entity(self, entity, mode="MERGE"):
        self.entities[(entity["PartitionKey"], entity["RowKey"])] = entity

    def create_entity(self, entity):
        self.entities[(entity["PartitionKey"], entity["RowKey"])] = entity

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


def test_key_sanitization(monkeypatch):
    monkeypatch.setattr(azure_storage_limiter, "TableServiceClient", DummyService)
    limiter = azure_storage_limiter.AzureTableStorage(connection_string="conn")

    key = "LIMITER/169.254.130.1/generic_endpoint/10/1/minute"

    assert limiter.incr(key, expiry=60) == 1
    assert limiter.incr(key, expiry=60) == 2
    assert limiter.get(key) == 2

    partition, row = limiter._get_partition_and_row(key)
    assert partition in {ent[0] for ent in limiter.client.entities.keys()}
    assert row in {ent[1] for ent in limiter.client.entities.keys()}

    limiter.clear(key)
    assert limiter.get(key) == 0

