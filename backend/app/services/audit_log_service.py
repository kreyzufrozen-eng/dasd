"""Thin write-only helper for app/models/audit_log.py — callers pass
whatever they already have on hand (request IP/user-agent, the acting
user id) rather than this module reaching into request state itself, so
it stays usable from both API routes and the bot.
"""
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_log_repository import AuditLogRepository


async def log_action(
    session: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    repo = AuditLogRepository(session)
    await repo.create(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ip_address,
        user_agent=(user_agent[:512] if user_agent else None),
        extra=extra,
    )
    # No commit here on purpose — the caller's own request-scoped
    # transaction (already committing the actual state change) covers
    # this row too, so a log write never partially succeeds on its own.
