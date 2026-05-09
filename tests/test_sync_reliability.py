from __future__ import annotations

from datetime import datetime

from dexter_sync.models import Resident
from dexter_sync.provider_client import FailurePlan, MockCareProvider
from dexter_sync.repository import UpsertOutcome
from dexter_sync.sync import run_sync


def test_retries_rate_limit_and_transient_failures(data_dir, repository):
    plan = FailurePlan(
        rate_limit_failures_per_cursor={None: 1},
        transient_failures_per_cursor={"page_2": 2},
    )
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_1.json", "provider_page_2.json"],
        failure_plan=plan,
    )

    result = run_sync(provider, repository)

    assert repository.count() == 8
    assert result.errors == []
    assert provider.call_count == 5


def test_duplicate_cursor_trap_stops_without_duplicating_residents(data_dir, repository):
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_1.json"],
        duplicate_cursor_trap=True,
    )

    result = run_sync(provider, repository)

    assert repository.count() == 5
    assert provider.call_count == 2
    assert result.warnings == ["stopping sync: repeated cursor 'page_1'"]


def test_judgment_fixture_mapping_rules(data_dir, repository):
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_judgment.json"],
    )

    result = run_sync(provider, repository)

    assert result.failed == 0
    assert repository.get_resident("RES-2001").care_level == 3
    assert repository.get_resident("RES-2002").care_level == 2
    assert repository.get_resident("RES-2003").care_level is None
    assert repository.get_resident("RES-2004").is_active is False
    assert repository.get_resident("RES-2005").is_active is False
    assert repository.get_resident("RES-2001").full_name == "Harper Quinn"


def test_last_modified_by_caregiver_does_not_override_staleness(data_dir, repository):
    repository.upsert_resident(
        Resident(
            provider_id="RES-2004",
            full_name="Current Robin Frost",
            date_of_birth=None,
            room="CURRENT",
            care_level=5,
            updated_at=datetime.fromisoformat("2024-03-06T08:00:00+00:00"),
            is_active=True,
        )
    )
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_judgment.json"],
    )

    result = run_sync(provider, repository)

    resident = repository.get_resident("RES-2004")
    assert resident.room == "CURRENT"
    assert resident.is_active is True
    assert result.skipped == 1


def test_repository_conditional_upsert_is_stale_protected(repository):
    older = Resident(
        provider_id="RES-ATOMIC",
        full_name="Older Version",
        date_of_birth=None,
        room="OLD",
        care_level=1,
        updated_at=datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
        is_active=True,
    )
    newer = Resident(
        provider_id="RES-ATOMIC",
        full_name="Newer Version",
        date_of_birth=None,
        room="NEW",
        care_level=2,
        updated_at=datetime.fromisoformat("2024-02-01T00:00:00+00:00"),
        is_active=True,
    )

    assert repository.upsert_resident_if_newer(newer) == UpsertOutcome.CREATED
    assert repository.upsert_resident_if_newer(older) == UpsertOutcome.SKIPPED

    resident = repository.get_resident("RES-ATOMIC")
    assert resident.room == "NEW"
