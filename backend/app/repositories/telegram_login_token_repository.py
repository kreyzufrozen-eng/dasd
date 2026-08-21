from typing import Optional

from sqlalchemy import select

from app.models.telegram_login_token import TelegramLoginToken
from app.repositories.base import BaseRepository


class TelegramLoginTokenRepository(BaseRepository[TelegramLoginToken]):
    model = TelegramLoginToken

    async def get_by_token_hash(self, token_hash: str) -> Optional[TelegramLoginToken]:
        stmt = select(TelegramLoginToken).where(TelegramLoginToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
