from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(Text)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    affected_files: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    review: Mapped["Review"] = relationship(back_populates="findings")
    feedback: Mapped[Optional["DeveloperFeedback"]] = relationship(
        back_populates="finding", uselist=False
    )


class DeveloperFeedback(Base):
    __tablename__ = "developer_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("review_findings.id"))
    is_false_positive: Mapped[bool] = mapped_column(default=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    finding: Mapped["ReviewFinding"] = relationship(back_populates="feedback")
