"""Sync orchestrator.

Reads residents from a provider, writes them to a repository, and returns a
SyncResult describing what happened. The current implementation handles the
simplest case only — extend it.

Read `docs/PROVIDER_API.md` and the failing tests to understand what
production-quality means here.
"""
from __future__ import annotations

import time
from typing import Any

from dexter_sync.exceptions import (
    MalformedRecordError,
    PermanentProviderError,
    ProviderError,
    RateLimitError,
    TransientProviderError,
)
from dexter_sync.models import Resident, SyncResult
from dexter_sync.provider_client import MockCareProvider
from dexter_sync.repository import InMemoryRepository, UpsertOutcome

MAX_FETCH_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 0.01


def run_sync(
    provider: MockCareProvider,
    repository: InMemoryRepository,
) -> SyncResult:
    """Sync residents from the provider into the repository."""
    result = SyncResult()
    cursor: str | None = None
    seen_cursors: set[str | None] = set()

    while True:
        if cursor in seen_cursors:
            result.warnings.append(f"stopping sync: repeated cursor {cursor!r}")
            break
        seen_cursors.add(cursor)

        try:
            page = _fetch_page_with_retries(provider, cursor)
        except PermanentProviderError as e:
            result.errors.append(f"permanent provider error at cursor={cursor!r}: {e}")
            break
        except ProviderError as e:
            result.errors.append(f"provider error at cursor={cursor!r}: {e}")
            break

        raw_residents = page.get("residents", [])
        if not isinstance(raw_residents, list):
            result.errors.append(f"permanent provider error at cursor={cursor!r}: residents is not a list")
            break

        for record_index, raw in enumerate(raw_residents):
            if not isinstance(raw, dict):
                result.failed += 1
                result.errors.append(
                    f"cursor={cursor!r} record_index={record_index}: record is not an object"
                )
                continue
            _process_record(raw, repository, result, cursor=cursor, record_index=record_index)

        next_cursor = page.get("next_cursor")
        if next_cursor is not None and not isinstance(next_cursor, str):
            result.errors.append(
                f"permanent provider error at cursor={cursor!r}: next_cursor is not a string"
            )
            break
        if next_cursor is None:
            break
        cursor = next_cursor

    return result


def _fetch_page_with_retries(
    provider: MockCareProvider,
    cursor: str | None,
) -> dict[str, Any]:
    last_error: ProviderError | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            return provider.list_residents(cursor=cursor)
        except PermanentProviderError:
            raise
        except RateLimitError as e:
            last_error = e
            if attempt == MAX_FETCH_ATTEMPTS:
                break
            time.sleep(min(max(e.retry_after, 0.0), 1.0))
        except TransientProviderError as e:
            last_error = e
            if attempt == MAX_FETCH_ATTEMPTS:
                break
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    assert last_error is not None
    raise last_error


def _process_record(
    raw: dict[str, Any],
    repository: InMemoryRepository,
    result: SyncResult,
    *,
    cursor: str | None,
    record_index: int,
) -> None:
    try:
        resident = Resident.from_provider_payload(raw)
    except MalformedRecordError as e:
        result.failed += 1
        provider_id = raw.get("residentId", "<missing>")
        result.errors.append(
            f"cursor={cursor!r} record_index={record_index} provider_id={provider_id!r}: {e}"
        )
        return

    outcome = repository.upsert_resident_if_newer(resident)
    if outcome == UpsertOutcome.CREATED:
        result.created += 1
        return

    if outcome == UpsertOutcome.SKIPPED:
        result.skipped += 1
        return

    result.updated += 1
