from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from utils.timezone import beijing_now


class ProjectRepo(Base):
    __tablename__ = "project_repos"
    __table_args__ = (UniqueConstraint("org_id", "platform", "repo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    platform: Mapped[str] = mapped_column(String(20))
    repo_id: Mapped[str] = mapped_column(String(200))
    repo_url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(200), default="main")
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_analyzed_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    total_commits: Mapped[int] = mapped_column(default=0)
    total_findings: Mapped[int] = mapped_column(default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(
        default=beijing_now,
        onupdate=beijing_now,
    )

    commits: Mapped[List["CommitAnalysis"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
