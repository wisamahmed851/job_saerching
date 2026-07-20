import enum
from datetime import date, datetime
from typing import List
from sqlalchemy import Integer, String, Date, ForeignKey, Enum, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class ApplicationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    GHOSTED = "GHOSTED"
    INTERVIEW = "INTERVIEW"

class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position: Mapped[str] = mapped_column(String, nullable=False)
    application_method: Mapped[str] = mapped_column(String, nullable=False)
    job_post_url: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_followup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resume_version: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="applicationstatus_enum"), 
        default=ApplicationStatus.ACTIVE, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Foreign Keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="applications")
    company: Mapped["Company"] = relationship(back_populates="applications")
    followups: Mapped[List["ApplicationFollowUp"]] = relationship(back_populates="application", cascade="all, delete-orphan")
