from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CommitAnalysis(Base):
    __tablename__ = "commit_analyses"
    __table_args__ = (UniqueConstraint("project_id", "commit_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_repos.id", ondelete="CASCADE"))
    commit_hash: Mapped[str] = mapped_column(String(40))
    parent_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commit_ts: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    changed_files: Mapped[int] = mapped_column(default=0)
    diff_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    findings_count: Mapped[int] = mapped_column(default=0)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    project: Mapped["ProjectRepo"] = relationship(back_populates="commits")
    findings: Mapped[List["CommitFinding"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
