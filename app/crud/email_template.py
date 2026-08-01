"""
CRUD for EmailTemplate.
Uses template_service.py for default values — this module is DB-only.
"""

from sqlalchemy.orm import Session

from app.models.email_template import EmailTemplate
from app.services.template_service import DEFAULT_SUBJECT, DEFAULT_BODY


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_email_template(db: Session, user_id: int) -> EmailTemplate | None:
    """Return the user's saved email template, or None if not customised."""
    return (
        db.query(EmailTemplate)
        .filter(EmailTemplate.user_id == user_id)
        .first()
    )


def get_or_default_template(db: Session, user_id: int) -> tuple[str, str]:
    """
    Return (subject_template, body_template) for the user.
    Falls back to built-in defaults when no custom template exists.
    """
    record = get_email_template(db, user_id)
    if record:
        return record.subject_template, record.body_template
    return DEFAULT_SUBJECT, DEFAULT_BODY


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_email_template(
    db: Session,
    user_id: int,
    subject_template: str,
    body_template: str,
) -> EmailTemplate:
    """Create or update the user's email template."""
    record = get_email_template(db, user_id)

    if record is None:
        record = EmailTemplate(
            user_id=user_id,
            subject_template=subject_template.strip(),
            body_template=body_template.strip(),
        )
        db.add(record)
    else:
        record.subject_template = subject_template.strip()
        record.body_template = body_template.strip()

    db.commit()
    db.refresh(record)
    return record


def delete_email_template(db: Session, user_id: int) -> None:
    """Delete the user's custom template, reverting them to the built-in default."""
    record = get_email_template(db, user_id)
    if record:
        db.delete(record)
        db.commit()
