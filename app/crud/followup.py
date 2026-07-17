from datetime import date
from sqlalchemy.orm import Session
from app.models.followup import ApplicationFollowUp

def create_followup(
    db: Session, 
    application_id: int, 
    followup_date: date, 
    notes: str | None = None
) -> ApplicationFollowUp:
    """
    Records an immutable history log for a job application follow-up event.
    """
    followup = ApplicationFollowUp(
        application_id=application_id,
        followup_date=followup_date,
        notes=notes
    )
    db.add(followup)
    db.commit()
    db.refresh(followup)
    return followup
