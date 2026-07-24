from datetime import date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc
from app.models.application import JobApplication, ApplicationStatus
from app.models.company import Company
from app.models.followup import ApplicationFollowUp, FollowupType, FollowupResponse
from app.schemas.application import ApplicationCreate, FollowupCreate
from app.crud.company import get_or_create_company
from app.crud.followup import create_followup

def create_job_application(db: Session, user_id: int, form_data: ApplicationCreate) -> JobApplication:
    # 1. Find or create company (now passes company_id if selected from autocomplete)
    company = get_or_create_company(
        db=db,
        user_id=user_id,
        name=form_data.company_name,
        company_id=form_data.company_id,
        website=form_data.company_website,
        email=form_data.company_email
    )
    
    # 2. Calculate next followup date (default = applied_date + 2 days)
    next_followup = form_data.applied_date + timedelta(days=2)
    
    # 3. Create application
    application = JobApplication(
        position=form_data.position,
        application_method=form_data.application_method,
        job_post_url=form_data.job_post_url,
        applied_date=form_data.applied_date,
        next_followup_date=next_followup,
        resume_id=form_data.resume_id,
        notes=form_data.notes,
        user_id=user_id,
        company_id=company.id,
        status=ApplicationStatus.ACTIVE
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    
    # 4. Create initial follow-up history log based on the application event itself
    create_followup(
        db=db,
        user_id=user_id,
        application_id=application.id,
        form_data=FollowupCreate(
            followup_date=form_data.applied_date,
            followup_type=FollowupType.OTHER,
            response=FollowupResponse.WAITING,
            notes=f"Initial application submitted via {form_data.application_method}.",
            next_followup_date=next_followup,
        )
    )
    
    return application

def get_due_followups(db: Session, user_id: int):
    today = date.today()
    return (
        db.query(JobApplication)
        .options(joinedload(JobApplication.followups))
        .filter(
            JobApplication.user_id == user_id,
            JobApplication.status == ApplicationStatus.ACTIVE,
            JobApplication.next_followup_date <= today,
        )
        .order_by(JobApplication.next_followup_date.asc())
        .all()
    )

def get_recent_applications(db: Session, user_id: int, limit: int = 5):
    return db.query(JobApplication).filter(
        JobApplication.user_id == user_id
    ).order_by(JobApplication.applied_date.desc()).limit(limit).all()

def get_application_stats(db: Session, user_id: int):
    total = db.query(JobApplication).filter(JobApplication.user_id == user_id).count()
    active = db.query(JobApplication).filter(
        JobApplication.user_id == user_id, 
        JobApplication.status == ApplicationStatus.ACTIVE
    ).count()
    return {"total": total, "active": active}

def get_applications(
    db: Session, 
    user_id: int,
    company_id: int | None = None,
    company_name: str | None = None,
    position: str | None = None,
    application_method: str | None = None,
    status: ApplicationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_order: str = "newest"
):
    """
    Fetches all applications for the user, applying dynamic filters and sorting.
    """
    # Join Company table so we can filter by company name
    query = db.query(JobApplication).join(Company).filter(JobApplication.user_id == user_id)
    
    if company_id:
        query = query.filter(JobApplication.company_id == company_id)
    elif company_name:
        query = query.filter(Company.name.ilike(f"%{company_name}%"))
    if position:
        query = query.filter(JobApplication.position.ilike(f"%{position}%"))
    if application_method:
        query = query.filter(JobApplication.application_method == application_method)
    if status:
        query = query.filter(JobApplication.status == status)
    if date_from:
        query = query.filter(JobApplication.applied_date >= date_from)
    if date_to:
        query = query.filter(JobApplication.applied_date <= date_to)
        
    if sort_order == "oldest":
        query = query.order_by(asc(JobApplication.applied_date))
    else:
        query = query.order_by(desc(JobApplication.applied_date))
        
    return query.all()

def delete_application(db: Session, user_id: int, application_id: int):
    """
    Deletes an application securely by verifying it belongs to the user.
    Note: Due to our SQLAlchemy models, deleting the JobApplication cascades
    to delete ApplicationFollowUp history, but it does NOT delete the parent Company.
    """
    application = db.query(JobApplication).filter(
        JobApplication.id == application_id,
        JobApplication.user_id == user_id
    ).first()
    
    if application:
        db.delete(application)
        db.commit()

def get_application_by_id(db: Session, user_id: int, application_id: int) -> JobApplication | None:
    """
    Fetches a single application by ID securely.
    """
    return db.query(JobApplication).filter(
        JobApplication.id == application_id,
        JobApplication.user_id == user_id
    ).first()

def update_job_application(
    db: Session, 
    user_id: int, 
    application_id: int, 
    form_data: ApplicationCreate
) -> JobApplication | None:
    """
    Updates an existing application. Checks if the company changed and handles it appropriately.
    """
    application = get_application_by_id(db, user_id, application_id)
    if not application:
        return None
        
    # Handle Company updates (if they changed the company name, find/create the new one)
    company = get_or_create_company(
        db=db,
        user_id=user_id,
        name=form_data.company_name,
        company_id=form_data.company_id,
        website=form_data.company_website,
        email=form_data.company_email
    )
    
    application.company_id = company.id
    application.position = form_data.position
    application.application_method = form_data.application_method
    application.job_post_url = form_data.job_post_url
    application.applied_date = form_data.applied_date
    application.resume_id = form_data.resume_id
    application.notes = form_data.notes
    application.next_followup_date = form_data.next_followup_date
    
    if form_data.status:
        application.status = form_data.status
        
    db.commit()
    db.refresh(application)
    return application
