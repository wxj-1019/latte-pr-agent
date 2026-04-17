from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.timezone import beijing_now


class BugKnowledge(Base):
    __tablename__ = "bug_knowledge"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    repo_id: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bug_pattern: Mapped[str] = mapped_column(Text)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    fix_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    fix_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # embedding is handled via raw SQL for pgvector; kept nullable here for ORM compatibility
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)
