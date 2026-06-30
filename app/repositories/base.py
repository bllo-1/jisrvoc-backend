"""Base repository with common CRUD operations."""

from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with generic CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        """Create a new instance.

        Args:
            **kwargs: Model field values

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get instance by ID.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Get all instances with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of model instances
        """
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        """Update an instance.

        Args:
            instance: Model instance to update
            **kwargs: Fields to update

        Returns:
            Updated model instance
        """
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Delete an instance.

        Args:
            instance: Model instance to delete
        """
        await self.session.delete(instance)
        await self.session.flush()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()
