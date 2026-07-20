from sqlalchemy.orm import Session
from app.models.followup import ApplicationFollowUp, FollowupResponse
from app.models.application import JobApplication, ApplicationStatus
from app.schemas.application import FollowupCreate

def create_followup(
    db: Session, 
    user_id: int, 
    application_id: int, 
    form_data: FollowupCreate
) -> ApplicationFollowUp | None:
    """
    Records a follow-up and automatically updates the Application status and next follow-up date.
    """
    # 1. Verify ownership
    application = db.query(JobApplication).filter(
        JobApplication.id == application_id,
        JobApplication.user_id == user_id
    ).first()
    
    if not application:
        return None

    # 2. Create the follow-up record
    followup = ApplicationFollowUp(
        application_id=application.id,
        followup_date=form_data.followup_date,
        followup_type=form_data.followup_type,
        response=form_data.response,
        notes=form_data.notes
    )
    db.add(followup)

    # 3. Business logic to automatically update JobApplication status
    if form_data.response == FollowupResponse.INTERVIEW:
        application.status = ApplicationStatus.INTERVIEW
    elif form_data.response == FollowupResponse.REJECTED:
        application.status = ApplicationStatus.REJECTED
    elif form_data.response == FollowupResponse.OFFER:
        application.status = ApplicationStatus.OFFER
    elif form_data.response in (FollowupResponse.WAITING, FollowupResponse.NO_REPLY):
        # Even if waiting, keep it active
        if application.status not in (ApplicationStatus.OFFER, ApplicationStatus.REJECTED):
            application.status = ApplicationStatus.ACTIVE

    # 4. Advance the next follow-up date
    application.next_followup_date = form_data.next_followup_date

    db.commit()
    db.refresh(followup)
    return followup
