"""In-memory repository.

Stands in for a Firestore-like persistence layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock

from dexter_sync.models import Resident


class UpsertOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


class InMemoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, Resident] = {}
        self._lock = Lock()

    def get_resident(self, provider_id: str) -> Resident | None:
        with self._lock:
            return self._store.get(provider_id)

    def upsert_resident(self, resident: Resident) -> None:
        """Insert or replace by provider_id."""
        with self._lock:
            self._store[resident.provider_id] = resident

    def upsert_resident_if_newer(self, resident: Resident) -> UpsertOutcome:
        """Create or update a resident only when the incoming record is newer.

        This keeps stale-write protection next to the write itself. A real
        Firestore implementation would use a transaction or conditional write;
        the in-memory version uses a lock so the read/compare/write sequence is
        atomic inside this repository.
        """
        with self._lock:
            existing = self._store.get(resident.provider_id)
            if existing is None:
                self._store[resident.provider_id] = resident
                return UpsertOutcome.CREATED

            if _as_aware_utc(existing.updated_at) >= _as_aware_utc(resident.updated_at):
                return UpsertOutcome.SKIPPED

            self._store[resident.provider_id] = resident
            return UpsertOutcome.UPDATED

    def list_residents(self) -> list[Resident]:
        with self._lock:
            return list(self._store.values())

    def count(self) -> int:
        with self._lock:
            return len(self._store)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
