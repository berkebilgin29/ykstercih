"""Department ve Comment tabloları için SQLAlchemy ORM modelleri."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Department(Base):
    """Bir üniversite bölümünün geçmiş sıralama ve kontenjan bilgilerini tutar."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    university_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    faculty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    score_type: Mapped[str] = mapped_column(String(10), nullable=False)
    education_type: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    quota_2025: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_2023: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_2024: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_2025: Mapped[int] = mapped_column(Integer, nullable=False)
    score_2025: Mapped[float] = mapped_column(Float, nullable=False)
    user_demand_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="department", cascade="all, delete-orphan"
    )


class Comment(Base):
    """Bir bölüme öğrenciler tarafından bırakılan yorumları tutar."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=False, index=True
    )
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    department: Mapped["Department"] = relationship("Department", back_populates="comments")
