import os
import time
from limits.storage import Storage
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, AzureError
"""
Azure Table Storage backend for Flask-Limiter.
"""

class AzureTableStorage(Storage):
    # Register this storage backend under the "azuretables" scheme
    STORAGE_SCHEME = "azuretables"
    """
    A Flask-Limiter storage backend using Azure Table Storage.
    Registered under the 'azuretables://' scheme.
    """
    # Underlying TableServiceClient storage
    def __init__(
        self,
        uri: str | None = None,
        wrap_exceptions: bool = False,
        **options: str,
    ):
        # Base Storage init
        super().__init__(uri, wrap_exceptions, **options)
        # Acquire connection string and table name
        conn_str = options.get("connection_string") or os.getenv("AZURE_TABLES_CONNECTION_STRING")
        if not conn_str:
            raise ValueError("AZURE_TABLES_CONNECTION_STRING must be set to use AzureTableStorage")
        table_name = options.get("table_name") or os.getenv("RATELIMIT_TABLE_NAME", "RateLimit")
        # Initialize table client
        service = TableServiceClient.from_connection_string(conn_str)
        self.client = service.get_table_client(table_name)
        # Ensure table exists
        try:
            self.client.create_table()
        except ResourceExistsError:
            pass

    def incr(self, key: str, expiry: int, elastic_expiry: bool = False) -> int:
        """
        Increment the count for a given key and set expiry.
        """
        now = int(time.time())
        partition_key = key
        row_key = key
        try:
            entity = self.client.get_entity(partition_key, row_key)
            count = entity.get("count", 0)
            expire_at = entity.get("expire_at", 0)
            # Reset or increment
            if now > expire_at:
                count = 1
                expire_at = now + expiry
            else:
                count += 1
                if elastic_expiry:
                    expire_at = now + expiry
            entity["count"] = count
            entity["expire_at"] = expire_at
            self.client.update_entity(entity, mode="MERGE")
        except AzureError:
            # Entity not found or any error: create new entity
            count = 1
            expire_at = now + expiry
            entity = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "count": count,
                "expire_at": expire_at
            }
            self.client.create_entity(entity)
        return count

    def get(self, key: str) -> int:
        """Return the current count for a key, or 0 if non-existent/expired."""
        now = int(time.time())
        partition_key = key
        row_key = key
        try:
            entity = self.client.get_entity(partition_key, row_key)
            expire_at = entity.get("expire_at", 0)
            if now > expire_at:
                return 0
            return entity.get("count", 0)
        except AzureError:
            return 0

    def clear(self, key: str) -> None:
        """Reset the count for a key by deleting the entity."""
        partition_key = key
        row_key = key
        try:
            self.client.delete_entity(partition_key, row_key)
        except AzureError:
            pass

    # Exceptions to catch during storage operations
    base_exceptions = (AzureError,)

    def check(self, key: str, limit: int, window) -> bool:
        """Return True if current count is below limit."""
        return self.get(key) < limit

    def get_expiry(self, window) -> int:
        """Convert a window (int or timedelta) to seconds."""
        import datetime
        if isinstance(window, datetime.timedelta):
            return int(window.total_seconds())
        try:
            return int(window)
        except Exception:
            return 0

    def reset(self) -> None:
        """Reset all counters. No-op for AzureTableStorage."""
        pass