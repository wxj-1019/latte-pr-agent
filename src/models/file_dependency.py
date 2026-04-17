from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.timezone import beijing_now


class FileDependency(Base):
    __tablename__ = "file_dependencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    repo_id: Mapped[str] = mapped_column(String(100))
    downstream_file: Mapped[str] = mapped_column(Text)
    upstream_file: Mapped[str] = mapped_column(Text)
    relation_type: Mapped[str] = mapped_column(String(20), default="import")
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)
