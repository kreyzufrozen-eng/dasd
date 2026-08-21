from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.source_schemas import SourceRead


class SearchProfileSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    search_profile_id: int
    source_id: int
    enabled: bool
    source: SourceRead


class SearchProfileSourceAttach(BaseModel):
    """Link an EXISTING catalog Source to this profile."""

    source_id: int
    enabled: bool = True


class SearchProfileSourceCreateCustom(BaseModel):
    """Add a brand-new Source (e.g. the user's own Telegram chat link) and
    link it to this profile in one call. Dedups against an existing Source
    with the same (type, external_identifier) before creating a new row —
    see app/api/search_profile_sources.py."""

    name: str = Field(min_length=1, max_length=255)
    type: str
    url: Optional[str] = Field(default=None, max_length=1024)
    external_identifier: Optional[str] = Field(default=None, max_length=255)


class SearchProfileSourceUpdate(BaseModel):
    enabled: bool


class SearchProfileSourceBulkAttach(BaseModel):
    """Link many existing catalog Sources in one call — see
    SearchProfileSourceRepository.bulk_attach."""

    source_ids: list[int] = Field(max_length=5000)


class SearchProfileSourceBulkAttachResult(BaseModel):
    attached: int
