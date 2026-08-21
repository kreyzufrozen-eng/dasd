"""UserLegalAcceptance: an immutable consent-log row. Never updated after
creation — a new acceptance (e.g. after a document version bump) is a new
row, not an edit, so the history stays intact for as long as it's kept.
"""
import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class UserLegalAcceptance(Base, TimestampMixin):
    __tablename__ = "user_legal_acceptances"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("legal_documents.id", ondelete="RESTRICT"), nullable=False
    )
    # Denormalized alongside document_id on purpose: even if the
    # LegalDocument row were ever edited in place (it shouldn't be —
    # versions are meant to be immutable too), this column is what was
    # true at the moment of acceptance and never changes.
    document_version: Mapped[str] = mapped_column(String(32), nullable=False)

    accepted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserLegalAcceptance id={self.id} user_id={self.user_id} "
            f"document_id={self.document_id} version={self.document_version!r}>"
        )
