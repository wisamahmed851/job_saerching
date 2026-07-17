from datetime import date
from sqlalchemy import Integer, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class ApplicationFollowUp(Base):
    __tablename__ = "application_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    followup_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign Keys
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id"), nullable=False)

    # Relationships
    application: Mapped["JobApplication"] = relationship(back_populates="followups")
