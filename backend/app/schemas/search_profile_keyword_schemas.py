import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import KeywordCategory


def _validate_category(value: str) -> str:
    allowed = {c.value for c in KeywordCategory}
    if value not in allowed:
        raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")
    return value


class SearchProfileKeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    search_profile_id: int
    keyword_id: Optional[int] = None
    text: str
    category: str
    weight: float
    enabled: bool
    created_at: dt.datetime


class SearchProfileKeywordCreate(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    category: str
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    enabled: bool = True

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        return _validate_category(value)


class SearchProfileKeywordUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = None
    weight: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    enabled: Optional[bool] = None

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: Optional[str]) -> Optional[str]:
        return _validate_category(value) if value is not None else value


class KeywordGenerateRequest(BaseModel):
    """Optional extra hints on top of the profile's own description/services
    — the button works with zero input, this just lets a future "regenerate
    with this steer" flow pass one."""

    extra_context: Optional[str] = Field(default=None, max_length=2000)


class KeywordGenerateResponse(BaseModel):
    created: List[SearchProfileKeywordRead]
