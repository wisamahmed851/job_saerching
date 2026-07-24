from datetime import date
from pydantic import BaseModel
from app.models.application import ApplicationStatus

class ApplicationCreate(BaseModel):
    # Company Fields
    company_id: int | None = None
    company_name: str
    company_website: str | None = None
    company_email: str | None = None
    
    # Application Fields
    position: str
    application_method: str
    job_post_url: str | None = None
    applied_date: date
    next_followup_date: date | None = None
    status: ApplicationStatus | None = None
    resume_id: int | None = None   # replaces resume_version string field
    notes: str | None = None

from app.models.followup import FollowupType, FollowupResponse

class FollowupCreate(BaseModel):
    followup_date: date
    followup_type: FollowupType
    response: FollowupResponse
    next_followup_date: date | None = None
    notes: str | None = None
