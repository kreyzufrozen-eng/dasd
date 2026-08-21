import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_ACTIONS = {"relevant", "irrelevant", "saved", "contacted"}


class LeadFeedbackCreate(BaseModel):
    action: str
    comment: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        if value not in _ALLOWED_ACTIONS:
            raise ValueError(f"must be one of: {', '.join(sorted(_ALLOWED_ACTIONS))}")
        return value


class LeadFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    action: Optional[str] = None
    feedback_type: str
    comment: Optional[str] = None
    created_at: dt.datetime
