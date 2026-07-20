import enum
from datetime import date
from sqlalchemy import Integer, Date, ForeignKey, Text, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class FollowupType(str, enum.Enum):
    EMAIL = "Email"
    LINKEDIN = "LinkedIn Message"
    PHONE = "Phone Call"
    WHATSAPP = "WhatsApp"
    OTHER = "Other"

class FollowupResponse(str, enum.Enum):
    WAITING = "Waiting"
    NO_REPLY = "No Reply"
    REPLIED = "Replied"
    INTERVIEW = "Interview Scheduled"
    REJECTED = "Rejected"
    OFFER = "Offer Received"

class ApplicationFollowUp(Base):
    __tablename__ = "application_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    followup_date: Mapped[date] = mapped_column(Date, nullable=False)
    followup_type: Mapped[FollowupType] = mapped_column(Enum(FollowupType, name="followuptype_enum"), nullable=False, default=FollowupType.EMAIL)
    response: Mapped[FollowupResponse] = mapped_column(Enum(FollowupResponse, name="followupresponse_enum"), nullable=False, default=FollowupResponse.WAITING)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign Keys
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id"), nullable=False)

    # Relationships
    application: Mapped["JobApplication"] = relationship(back_populates="followups")
