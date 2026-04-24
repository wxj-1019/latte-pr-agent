from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.timezone import beijing_now


class PromptExperiment(Base):
    __tablename__ = "prompt_experiments"

    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    prompt_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(nullable=True)
    repo_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)


class PromptExperimentAssignment(Base):
    __tablename__ = "prompt_experiment_assignments"
    __table_args__ = (UniqueConstraint("repo_id", "experiment_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[str] = mapped_column(String(100))
    experiment_name: Mapped[str] = mapped_column(String(50), default="default")
    version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(default=beijing_now)
