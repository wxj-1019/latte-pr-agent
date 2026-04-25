from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.timezone import beijing_now


class CodeRelationship(Base):
    __tablename__ = "code_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    repo_id: Mapped[str] = mapped_column(String(100))
    source_entity_id: Mapped[int] = mapped_column(Integer)
    target_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    relation_type: Mapped[str] = mapped_column(String(20))  # calls, inherits, implements, contains, decorates
    source_file: Mapped[str] = mapped_column(Text)
    target_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)

    __table_args__ = (
        Index("idx_code_rel_repo", "repo_id"),
        Index("idx_code_rel_source", "source_entity_id"),
        Index("idx_code_rel_target", "target_entity_id"),
        Index("idx_code_rel_type", "repo_id", "relation_type"),
    )
