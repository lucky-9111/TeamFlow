from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Workspace(TimestampMixin, Base):
    """The single company workspace. Exactly one row is created by `create-admin`."""

    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
