import os
import time
from limits.storage import Storage
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, AzureError

class AzureTableStorage(Storage):
    """
    A Flask-Limiter storage backend using Azure Table Storage.
    Stores rate limit counters with an expiration timestamp.
    """
    def __init__(self, connection_string: str, table_name: str = None):
        if not connection_string:
            raise ValueError("AZURE_TABLES_CONNECTION_STRING must be set to use AzureTableStorage")
        self.table_name = table_name or os.getenv("RATELIMIT_TABLE_NAME", "RateLimit")
        # Initialize table client
        service = TableServiceClient.from_connection_string(connection_string)
        self.client = service.get_table_client(self.table_name)
        # Ensure table exists
        try:
            self.client.create_table()
        except ResourceExistsError:
            # Table already exists; ignore
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

    # Abstract methods required by limits.storage.Storage
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