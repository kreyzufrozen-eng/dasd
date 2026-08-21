"""AuditLog: append-only record of security/privacy-relevant actions
(login, logout, telegram_connect, profile create/delete, settings
change, data export, account deletion, subscription change, admin
actions). Never write passwords, tokens, secrets, or more PII than the
action itself already implies — `metadata` is for small structured
context (e.g. {"plan": "free"}), not a place to dump request bodies.
"""
from typing import Any, Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable: some actions worth auditing happen before a session exists
    # (e.g. a failed/aborted login attempt tied only to an IP).
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    extra: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} action={self.action!r} user_id={self.user_id}>"
