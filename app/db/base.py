"""SQLAlchemy Base and model imports for Alembic autogenerate."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Import all models here so Alembic can discover them
# These imports should be commented out to avoid circular dependencies
# They are only needed in Alembic env.py for autogenerate
# from app.models.feedback import Feedback  # noqa
# from app.models.customer import Customer  # noqa
# from app.models.company import Company  # noqa
# from app.models.classification import Classification  # noqa
# from app.models.theme import Theme  # noqa
# from app.models.clustering import ClusteringRun, ThemeMembership  # noqa
# from app.models.bet import ProductBet, BetEvidence, WritebackLog  # noqa
