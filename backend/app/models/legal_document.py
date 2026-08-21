"""LegalDocument: a versioned copy of a legal text (privacy policy, terms
of service, cookie policy) the product actually shows users. Versioned so
UserLegalAcceptance can record *which exact version* someone agreed to —
required to answer "what did this user actually consent to on this date"
later, which a single mutable "current text" column can't do.
"""
import datetime as dt
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class LegalDocument(Base, TimestampMixin):
    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("type", "version", name="uq_legal_doc_type_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # privacy_policy | terms_of_service | cookie_policy — see
    # app/models/enums.py LegalDocumentType.
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    published_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Exactly one row per `type` should be is_active=True at a time — the
    # one new registrations/logins are asked to accept. Enforced at the
    # application layer (publish_document swaps the flag), not the DB.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LegalDocument id={self.id} type={self.type} version={self.version!r}>"
