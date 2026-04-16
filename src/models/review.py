from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Text, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("platform", "repo_id", "pr_number", "head_sha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    platform: Mapped[str] = mapped_column(String(20))
    repo_id: Mapped[str] = mapped_column(String(100))
    pr_number: Mapped[int] = mapped_column(Integer)
    pr_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pr_author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    head_branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    risk_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    review_mode: Mapped[str] = mapped_column(String(20), default="incremental")
    diff_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    findings: Mapped[List["ReviewFinding"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin"
    )
    pr_files: Mapped[List["PRFile"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin"
    )


class PRFile(Base):
    __tablename__ = "pr_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(Text)
    change_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    diff_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    review: Mapped["Review"] = relationship(back_populates="pr_files")


class ProjectConfig(Base):
    __tablename__ = "project_configs"
    __table_args__ = (UniqueConstraint("org_id", "platform", "repo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    platform: Mapped[str] = mapped_column(String(20))
    repo_id: Mapped[str] = mapped_column(String(100))
    config_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
