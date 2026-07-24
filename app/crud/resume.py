"""
CRUD operations for the Resume model.
All file I/O is handled by resume_service.py — this module is DB-only.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.resume import Resume
from app.models.application import JobApplication


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_resumes_for_user(db: Session, user_id: int) -> list[Resume]:
    """
    Return all resumes owned by the user, newest first.
    Each resume object is annotated with an `application_count` attribute
    so templates don't need a second query.
    """
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == user_id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )

    # Annotate each resume with how many applications reference it
    for resume in resumes:
        resume.application_count = (
            db.query(func.count(JobApplication.id))
            .filter(JobApplication.resume_id == resume.id)
            .scalar()
        )

    return resumes


def get_active_resumes_for_user(db: Session, user_id: int) -> list[Resume]:
    """
    Return only active resumes for the user.
    Used to populate the dropdown on the application form.
    """
    return (
        db.query(Resume)
        .filter(Resume.user_id == user_id, Resume.is_active == True)
        .order_by(Resume.display_name.asc())
        .all()
    )


def get_resume_by_id(db: Session, user_id: int, resume_id: int) -> Resume | None:
    """Fetch a single resume, enforcing ownership."""
    return (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user_id)
        .first()
    )


def count_applications_using_resume(db: Session, resume_id: int) -> int:
    """How many job applications currently reference this resume."""
    return (
        db.query(func.count(JobApplication.id))
        .filter(JobApplication.resume_id == resume_id)
        .scalar()
    )


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def create_resume(
    db: Session,
    user_id: int,
    display_name: str,
    original_filename: str,
    stored_filename: str,
    file_path: str,
    file_size: int,
    mime_type: str,
) -> Resume:
    """Persist a new Resume record after the file has been saved to disk."""
    resume = Resume(
        user_id=user_id,
        display_name=display_name.strip(),
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        is_active=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def delete_resume(db: Session, resume: Resume) -> None:
    """
    Delete the Resume DB record and set resume_id = NULL on all
    job applications that referenced it.
    The physical file deletion is handled by resume_service.py before
    this function is called.
    """
    # Nullify FK on all affected applications — do NOT delete the applications
    (
        db.query(JobApplication)
        .filter(JobApplication.resume_id == resume.id)
        .update({JobApplication.resume_id: None}, synchronize_session="fetch")
    )

    db.delete(resume)
    db.commit()


def get_resume_by_display_name(db: Session, user_id: int, display_name: str) -> Resume | None:
    """
    Case-insensitive lookup by display name.
    Used during Excel import to match resumes by name.
    """
    return (
        db.query(Resume)
        .filter(
            Resume.user_id == user_id,
            func.lower(Resume.display_name) == display_name.strip().lower(),
        )
        .first()
    )
