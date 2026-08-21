from app.models.user_legal_acceptance import UserLegalAcceptance
from app.repositories.base import BaseRepository


class UserLegalAcceptanceRepository(BaseRepository[UserLegalAcceptance]):
    model = UserLegalAcceptance
