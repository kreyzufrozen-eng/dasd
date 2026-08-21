import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LegalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    version: str
    title: str
    content: str
    published_at: Optional[dt.datetime] = None
    is_active: bool
    created_at: dt.datetime


class LegalDocumentCreate(BaseModel):
    type: str
    version: str
    title: str
    content: str
