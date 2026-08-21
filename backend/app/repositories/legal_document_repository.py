from typing import Optional, Sequence

from sqlalchemy import select

from app.models.legal_document import LegalDocument
from app.repositories.base import BaseRepository


class LegalDocumentRepository(BaseRepository[LegalDocument]):
    model = LegalDocument

    async def get_active(self, doc_type: str) -> Optional[LegalDocument]:
        stmt = select(LegalDocument).where(
            LegalDocument.type == doc_type, LegalDocument.is_active.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(self, doc_type: str) -> Sequence[LegalDocument]:
        stmt = (
            select(LegalDocument)
            .where(LegalDocument.type == doc_type)
            .order_by(LegalDocument.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def deactivate_all(self, doc_type: str) -> None:
        rows = await self.list_by_type(doc_type)
        for row in rows:
            if row.is_active:
                await self.update(row, is_active=False)
