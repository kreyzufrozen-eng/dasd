import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SourceType


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    url: Optional[str] = None
    external_identifier: Optional[str] = None
    is_active: bool
    category: Optional[str] = None
    last_checked_at: Optional[dt.datetime] = None
    created_at: dt.datetime
    updated_at: dt.datetime


class SourceWithLeadCount(SourceRead):
    lead_count: int = 0


class SourceCatalogEntry(SourceRead):
    """A source as shown in the browsable catalog — includes whether the
    calling profile already has it linked, so the UI can render a
    checkbox without a second round-trip."""

    already_added: bool = False
    enabled_for_profile: bool = False


# Field lengths mirror the DB columns in app/models/source.py — enforcing
# them here means a too-long value gets a clean 422 instead of a DB-level
# "value too long for type character varying(255)" error surfacing later.
class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str
    url: Optional[str] = Field(default=None, max_length=1024)
    external_identifier: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=64)
    is_active: bool = True

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        allowed = {t.value for t in SourceType}
        if value not in allowed:
            raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")
        return value


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, max_length=1024)
    external_identifier: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None
