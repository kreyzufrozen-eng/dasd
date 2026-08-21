import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import KeywordCategory


class KeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    category: str
    weight: float
    is_active: bool
    is_global: bool = True
    created_at: dt.datetime


class KeywordCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=255)
    category: str
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    is_active: bool = True

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        allowed = {c.value for c in KeywordCategory}
        if value not in allowed:
            raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")
        return value


class KeywordUpdate(BaseModel):
    keyword: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = None
    weight: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    is_active: Optional[bool] = None

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {c.value for c in KeywordCategory}
        if value not in allowed:
            raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")
        return value
