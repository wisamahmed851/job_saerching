from sqlalchemy.orm import Session
from app.models.developer_feedback import DeveloperFeedback


def create_feedback(db: Session, user_id: int, message: str | None) -> DeveloperFeedback:
    """
    Persist developer feedback submitted during registration.
    The message is optional — an empty / blank string is stored as None.
    """
    record = DeveloperFeedback(
        user_id=user_id,
        message=message.strip() if message and message.strip() else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
