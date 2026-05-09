"""Internal data models.

Resident is the internal representation persisted to the repository.
SyncResult summarizes a sync run.

The provider's payload schema is documented in `docs/PROVIDER_API.md` —
read it before extending the mapping below.
"""
from __future__ import annotations

from datetime import date, datetime
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
        provider_id = raw.get("residentId")
        if not provider_id:
            raise MalformedRecordError("missing residentId", raw=raw)

        return cls(
            provider_id=str(provider_id),
            full_name=raw.get("first_name", ""),
            date_of_birth=None,
            room=raw.get("room"),
            care_level=raw.get("care_level"),
            updated_at=datetime.fromisoformat(raw["last_updated"]),
            is_active=raw.get("is_active", True),
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
