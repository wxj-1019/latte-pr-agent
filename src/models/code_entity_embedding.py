from datetime import datetime
from typing import List, Optional

from sqlalchemy import Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.vector_compat import VectorCompat
from utils.timezone import beijing_now


class CodeEntityEmbedding(Base):
    __tablename__ = "code_entity_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    repo_id: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorCompat(768), nullable=True)
    text_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)

    __table_args__ = (
        Index("idx_code_entity_emb_repo", "repo_id"),
        Index("idx_code_entity_emb_entity", "entity_id"),
    )
