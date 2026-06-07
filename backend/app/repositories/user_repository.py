from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.auth import UserCreate

class UserRepository(BaseRepository[User, UserCreate, UserCreate]):
    """
    User specific repository for database operations on the users table.
    """
    def __init__(self):
        super().__init__(User)

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """
        Retrieves a user by their unique email address.
        """
        query = select(self.model).where(self.model.email == email)
        result = await db.execute(query)
        return result.scalars().first()

    async def update_last_login(self, db: AsyncSession, user_id: UUID) -> None:
        """
        Updates the user's last login timestamp to the current UTC time.
        """
        query = (
            update(self.model)
            .where(self.model.id == user_id)
            .values(last_login=datetime.now(timezone.utc))
        )
        await db.execute(query)
        await db.flush()

user_repo = UserRepository()
