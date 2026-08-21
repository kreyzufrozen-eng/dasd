"""REST API: legal documents.

GET /api/legal/{type} is public (no auth) — the /privacy, /terms,
/cookies pages and the bot's /privacy command all read from it. Admin
management (draft a new version, publish it) lives under
/api/admin/legal/*, gated the same way as the rest of app/api/admin.py.

Publishing swaps is_active on the whole type in one call
(deactivate_all + activate the chosen version) so there's never a moment
with two active versions of the same document type, and never a moment
with zero once at least one has ever been published.
"""
import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInputError, NotFoundError
from app.core.security import get_current_admin_user
from app.db.session import get_db_session
from app.models.enums import LegalDocumentType
from app.models.user import User
from app.repositories.legal_document_repository import LegalDocumentRepository
from app.schemas.legal_document_schemas import LegalDocumentCreate, LegalDocumentRead

public_router = APIRouter(prefix="/api/legal", tags=["legal"])
admin_router = APIRouter(prefix="/api/admin/legal", tags=["admin"])

_VALID_TYPES = {t.value for t in LegalDocumentType}


@public_router.get("/{doc_type}", response_model=LegalDocumentRead)
async def get_active_legal_document(
    doc_type: str, db: AsyncSession = Depends(get_db_session)
) -> LegalDocumentRead:
    if doc_type not in _VALID_TYPES:
        raise NotFoundError("Unknown document type")
    doc = await LegalDocumentRepository(db).get_active(doc_type)
    if doc is None:
        raise NotFoundError("Документ ещё не опубликован")
    return doc


@admin_router.get("/{doc_type}", response_model=list[LegalDocumentRead])
async def list_legal_document_versions(
    doc_type: str,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[LegalDocumentRead]:
    if doc_type not in _VALID_TYPES:
        raise InvalidInputError("Unknown document type")
    return list(await LegalDocumentRepository(db).list_by_type(doc_type))


@admin_router.post("", response_model=LegalDocumentRead, status_code=201)
async def create_legal_document_draft(
    payload: LegalDocumentCreate,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> LegalDocumentRead:
    if payload.type not in _VALID_TYPES:
        raise InvalidInputError("Unknown document type")
    repo = LegalDocumentRepository(db)
    doc = await repo.create(
        type=payload.type,
        version=payload.version,
        title=payload.title,
        content=payload.content,
        is_active=False,
    )
    await db.commit()
    return doc


@admin_router.post("/{document_id}/publish", response_model=LegalDocumentRead)
async def publish_legal_document(
    document_id: int,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> LegalDocumentRead:
    repo = LegalDocumentRepository(db)
    doc = await repo.get(document_id)
    if doc is None:
        raise NotFoundError("Document not found")

    await repo.deactivate_all(doc.type)
    doc = await repo.update(doc, is_active=True, published_at=dt.datetime.now(dt.timezone.utc))
    await db.commit()
    return doc
