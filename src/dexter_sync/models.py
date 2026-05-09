"""Internal data models.

Resident is the internal representation persisted to the repository.
SyncResult summarizes a sync run.

The provider's payload schema is documented in `docs/PROVIDER_API.md` —
read it before extending the mapping below.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dexter_sync.exceptions import MalformedRecordError


class Resident(BaseModel):
    """Internal resident record."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    provider_id: str
    full_name: str
    date_of_birth: date | None = None
    room: str | None = None
    care_level: int | None = None
    updated_at: datetime
    is_active: bool = True

    @classmethod
    def from_provider_payload(cls, raw: dict[str, Any]) -> "Resident":
        """Map a raw provider payload into the internal Resident model."""
        provider_id = _required_string(raw, "residentId")
        first_name = _required_string(raw, "first_name")
        last_name = _required_string(raw, "lastName")
        updated_at = _parse_datetime(raw, "last_updated", required=True)
        assert updated_at is not None
        deleted_at = _parse_datetime(raw, "deleted_at", required=False)
        is_active = _parse_is_active(raw)

        return cls(
            provider_id=provider_id,
            full_name=f"{first_name} {last_name}",
            date_of_birth=_parse_date(raw, "dob"),
            room=raw.get("room"),
            care_level=_parse_care_level(raw),
            updated_at=updated_at,
            is_active=(deleted_at is None) and is_active,
        )


class SyncResult(BaseModel):
    """Outcome of a sync run."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.created + self.updated + self.skipped + self.failed


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MalformedRecordError(f"missing or invalid {field}", raw=raw)
    return value.strip()


def _parse_date(raw: dict[str, Any], field: str) -> date | None:
    value = raw.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise MalformedRecordError(f"invalid {field}: expected ISO date string", raw=raw)
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise MalformedRecordError(f"invalid {field}: {value!r}", raw=raw) from e


def _parse_datetime(raw: dict[str, Any], field: str, *, required: bool) -> datetime | None:
    value = raw.get(field)
    if value in (None, ""):
        if required:
            raise MalformedRecordError(f"missing {field}", raw=raw)
        return None
    if not isinstance(value, str):
        raise MalformedRecordError(f"invalid {field}: expected ISO datetime string", raw=raw)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        raise MalformedRecordError(f"invalid {field}: {value!r}", raw=raw) from e
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_care_level(raw: dict[str, Any]) -> int | None:
    value = raw.get("care_level")
    if value is None:
        return None
    if isinstance(value, bool):
        raise MalformedRecordError(
            "invalid care_level: expected int, numeric string, or level_N", raw=raw
        )
    if isinstance(value, int):
        care_level = value
    elif isinstance(value, str):
        stripped = value.strip()
        match = re.fullmatch(r"(?i:level_)?(\d+)", stripped)
        if not match:
            raise MalformedRecordError(
                "invalid care_level: expected int, numeric string, or level_N", raw=raw
            )
        care_level = int(match.group(1))
    else:
        raise MalformedRecordError(
            "invalid care_level: expected int, numeric string, or level_N", raw=raw
        )

    if not 0 <= care_level <= 5:
        raise MalformedRecordError("invalid care_level: expected value between 0 and 5", raw=raw)
    return care_level


def _parse_is_active(raw: dict[str, Any]) -> bool:
    value = raw.get("is_active", True)
    if not isinstance(value, bool):
        raise MalformedRecordError("invalid is_active: expected boolean", raw=raw)
    return value
