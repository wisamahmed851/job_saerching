"""
CRUD for UserEmailConfig.
Encryption/decryption of the SMTP password is handled here,
keeping that concern out of routes and templates.
"""

from sqlalchemy.orm import Session

from app.models.user_email_config import UserEmailConfig
from app.services.encryption_service import encrypt_password, decrypt_password


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_email_config(db: Session, user_id: int) -> UserEmailConfig | None:
    """Return the user's email configuration record, or None if not set."""
    return (
        db.query(UserEmailConfig)
        .filter(UserEmailConfig.user_id == user_id)
        .first()
    )


def get_decrypted_password(config: UserEmailConfig) -> str:
    """Decrypt and return the SMTP password for the given config record."""
    return decrypt_password(config.smtp_password_encrypted)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_email_config(
    db: Session,
    user_id: int,
    smtp_username: str,
    smtp_from_name: str,
    smtp_from_email: str,
    new_plain_password: str | None = None,
) -> UserEmailConfig:
    """
    Create or update the email configuration for a user.

    If new_plain_password is None or blank the existing encrypted password
    is preserved unchanged.  This prevents accidental password removal when
    the user saves the form without re-entering their password.
    """
    config = get_email_config(db, user_id)

    if config is None:
        # New record — password is required
        if not new_plain_password:
            raise ValueError("SMTP password is required for a new email configuration.")
        config = UserEmailConfig(
            user_id=user_id,
            smtp_username=smtp_username.strip(),
            smtp_password_encrypted=encrypt_password(new_plain_password),
            smtp_from_name=smtp_from_name.strip(),
            smtp_from_email=smtp_from_email.strip(),
        )
        db.add(config)
    else:
        # Update — only replace encrypted password if a new one was supplied
        config.smtp_username = smtp_username.strip()
        config.smtp_from_name = smtp_from_name.strip()
        config.smtp_from_email = smtp_from_email.strip()
        if new_plain_password and new_plain_password.strip():
            config.smtp_password_encrypted = encrypt_password(new_plain_password)

    db.commit()
    db.refresh(config)
    return config
