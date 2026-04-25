from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.timezone import beijing_now


class CodeEntity(Base):
    __tablename__ = "code_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    repo_id: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(20))  # function, class, interface, module
    name: Mapped[str] = mapped_column(String(200))
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)

    __table_args__ = (
        Index("idx_code_entities_repo_file", "repo_id", "file_path"),
        Index("idx_code_entities_repo_type", "repo_id", "entity_type"),
        Index("idx_code_entities_repo_name", "repo_id", "name"),
    )
