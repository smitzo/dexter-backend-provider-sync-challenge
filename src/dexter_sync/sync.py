"""Sync orchestrator.

Reads residents from a provider, writes them to a repository, and returns a
SyncResult describing what happened. The current implementation handles the
simplest case only — extend it.

Read `docs/PROVIDER_API.md` and the failing tests to understand what
production-quality means here.
"""
from __future__ import annotations

from dexter_sync.exceptions import (
    MalformedRecordError,
    PermanentProviderError,
    ProviderError,
)
from dexter_sync.models import Resident, SyncResult
from dexter_sync.provider_client import MockCareProvider
from dexter_sync.repository import InMemoryRepository


def run_sync(
    provider: MockCareProvider,
    repository: InMemoryRepository,
) -> SyncResult:
    """Sync residents from the provider into the repository."""
    result = SyncResult()

    try:
        page = provider.list_residents(cursor=None)
    except PermanentProviderError:
        return result
    except ProviderError as e:
        result.errors.append(str(e))
        return result

    raw_residents = page.get("residents", [])

    for raw in raw_residents:
        resident = Resident.from_provider_payload(raw)
        repository.upsert_resident(resident)

    return result
