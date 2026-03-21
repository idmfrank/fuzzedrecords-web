import os
import time
from typing import Optional
from urllib.parse import quote

from azure.core import MatchConditions
from azure.core.exceptions import (
    AzureError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.data.tables import TableServiceClient, UpdateMode
from limits.storage import Storage

"""Azure Table Storage backend for Flask-Limiter."""


class AzureTableStorage(Storage):
    # Register this storage backend under the "azuretables" scheme
    STORAGE_SCHEME = "azuretables"
    """
    A Flask-Limiter storage backend using Azure Table Storage.
    Registered under the 'azuretables://' scheme.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
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
        self.max_retries = int(options.get("max_retries") or os.getenv("RATELIMIT_AZURE_RETRIES", "5"))
        # Initialize table client
        service = TableServiceClient.from_connection_string(conn_str)
        self.client = service.get_table_client(table_name)
        # Ensure table exists
        try:
            self.client.create_table()
        except ResourceExistsError:
            pass

    def _sanitize_key(self, key: str) -> str:
        """Return a version of ``key`` safe for Azure Table Storage."""
        return quote(key, safe="")

    def _get_partition_and_row(self, key: str) -> tuple[str, str]:
        """Return a tuple of (PartitionKey, RowKey) for a given limiter ``key``.

        The PartitionKey groups related keys together (for example by IP address)
        while the RowKey stores the fully sanitized key value.
        """
        sanitized = self._sanitize_key(key)
        parts = key.split("/", 2)
        if len(parts) > 1:
            partition = self._sanitize_key(parts[1])
        else:
            partition = sanitized
        return partition, sanitized

    @staticmethod
    def _extract_etag(entity) -> Optional[str]:
        metadata = getattr(entity, "metadata", None)
        if metadata:
            return metadata.get("etag")
        if isinstance(entity, dict):
            return entity.get("etag")
        return None

    def incr(
        self,
        key: str,
        expiry: int,
        elastic_expiry: bool = False,
        amount: int = 1,
    ) -> int:
        """Increment the count for ``key`` by ``amount`` and set expiry.

        Azure Table Storage does not support server-side atomic increments, so we
        use optimistic concurrency with entity ETags to avoid lost updates under
        concurrent traffic.
        """
        partition_key, row_key = self._get_partition_and_row(key)

        for _ in range(self.max_retries):
            now = int(time.time())
            try:
                entity = self.client.get_entity(partition_key, row_key)
            except ResourceNotFoundError:
                entity = {
                    "PartitionKey": partition_key,
                    "RowKey": row_key,
                    "count": amount,
                    "expire_at": now + expiry,
                }
                try:
                    self.client.create_entity(entity)
                    return amount
                except ResourceExistsError:
                    continue

            count = entity.get("count", 0)
            expire_at = entity.get("expire_at", 0)
            if now > expire_at:
                count = amount
                expire_at = now + expiry
            else:
                count += amount
                if elastic_expiry:
                    expire_at = now + expiry

            entity["count"] = count
            entity["expire_at"] = expire_at

            try:
                self.client.update_entity(
                    entity,
                    mode=UpdateMode.MERGE,
                    etag=self._extract_etag(entity),
                    match_condition=MatchConditions.IfNotModified,
                )
                return count
            except (ResourceModifiedError, ResourceNotFoundError):
                continue

        raise RuntimeError(f"Failed to increment rate-limit key after {self.max_retries} retries: {key}")

    def get(self, key: str) -> int:
        """Return the current count for a key, or 0 if non-existent/expired."""
        now = int(time.time())
        partition_key, row_key = self._get_partition_and_row(key)
        try:
            entity = self.client.get_entity(partition_key, row_key)
            expire_at = entity.get("expire_at", 0)
            if now > expire_at:
                return 0
            return entity.get("count", 0)
        except ResourceNotFoundError:
            return 0

    def clear(self, key: str) -> None:
        """Reset the count for a key by deleting the entity."""
        partition_key, row_key = self._get_partition_and_row(key)
        try:
            self.client.delete_entity(partition_key, row_key)
        except ResourceNotFoundError:
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
