from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CommitFinding(Base):
    __tablename__ = "commit_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    commit_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("commit_analyses.id", ondelete="CASCADE")
    )
    file_path: Mapped[str] = mapped_column(String(500))
    line_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.5)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    analysis: Mapped["CommitAnalysis"] = relationship(back_populates="findings")
