"""Records consent at signup (both email registration and Telegram
login-complete call this). Only ever writes an acceptance row for a
document type that actually has a published active version — before any
LegalDocument is published (e.g. a fresh dev DB, or before the owner has
finished drafting real policy text), signup proceeds without one rather
than hard-failing, since there's nothing real to consent to yet.
"""
import datetime as dt
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LegalDocumentType
from app.repositories.legal_document_repository import LegalDocumentRepository
from app.repositories.user_legal_acceptance_repository import UserLegalAcceptanceRepository

REQUIRED_AT_SIGNUP: tuple[LegalDocumentType, ...] = (
    LegalDocumentType.PRIVACY_POLICY,
    LegalDocumentType.TERMS_OF_SERVICE,
)


async def legal_acceptance_required(session: AsyncSession) -> bool:
    """False on a fresh install / test DB with no published LegalDocument
    yet — there's nothing real to gate signup on until the owner actually
    publishes privacy policy / terms content. True as soon as either one
    goes live, which is when the "must tick the box" requirement starts
    applying for real."""
    doc_repo = LegalDocumentRepository(session)
    for doc_type in REQUIRED_AT_SIGNUP:
        if await doc_repo.get_active(doc_type.value) is not None:
            return True
    return False


async def record_signup_acceptance(
    session: AsyncSession,
    user_id: int,
    ip_address: str,
    user_agent: str,
    doc_types: Iterable[LegalDocumentType] = REQUIRED_AT_SIGNUP,
) -> None:
    doc_repo = LegalDocumentRepository(session)
    acceptance_repo = UserLegalAcceptanceRepository(session)
    now = dt.datetime.now(dt.timezone.utc)

    for doc_type in doc_types:
        active = await doc_repo.get_active(doc_type.value)
        if active is None:
            continue
        await acceptance_repo.create(
            user_id=user_id,
            document_id=active.id,
            document_version=active.version,
            accepted_at=now,
            ip_address=ip_address,
            user_agent=(user_agent[:512] if user_agent else "unknown"),
        )
