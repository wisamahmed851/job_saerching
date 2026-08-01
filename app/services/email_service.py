"""
Email Service
=============
Sends plain-text emails via SMTP using only Python standard library.
No third-party email packages required.

Credential resolution order:
  1. If a UserEmailConfig object is passed → use its decrypted credentials.
  2. Otherwise → fall back to .env / config.py values (existing behaviour).

Template rendering is handled by template_service.py before calling send_email().
The SMTP server (host, port, TLS) is always taken from config.py/.env.
"""

from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.user_email_config import UserEmailConfig


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class EmailConfigError(Exception):
    """Raised when SMTP settings are missing or incomplete."""


class EmailAuthError(Exception):
    """Raised when the SMTP server rejects the login credentials."""


class EmailConnectionError(Exception):
    """Raised when a network/connection error occurs."""


class EmailSendError(Exception):
    """Raised for any other send-time failure."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_email(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
    attachment_filename: str | None = None,
    user_email_config: "UserEmailConfig | None" = None,
) -> None:
    """
    Send a plain-text email to `to_email`, with an optional file attachment.

    Args:
        to_email:            Recipient address.
        subject:             Email subject line.
        body:                Plain-text body.
        attachment_path:     Path to the file on disk, or None.
        attachment_filename: Display filename for the attachment.
        user_email_config:   If provided, use the user's stored credentials
                             instead of the global .env values.

    Raises:
        EmailConfigError     — SMTP credentials missing
        EmailAuthError       — SMTP login rejected
        EmailConnectionError — Cannot reach the mail server
        EmailSendError       — Any other SMTP error
    """
    # Resolve credentials
    smtp_username, smtp_password, from_name, from_email = _resolve_credentials(
        user_email_config
    )

    _validate_resolved(smtp_username, smtp_password, from_email)

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment_path is not None:
        _attach_file(msg, attachment_path, attachment_filename)

    try:
        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                _login(smtp, smtp_username, smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                _login(smtp, smtp_username, smtp_password)
                smtp.send_message(msg)

    except smtplib.SMTPAuthenticationError as exc:
        raise EmailAuthError(
            "SMTP authentication failed. Please verify your email configuration in Settings."
        ) from exc
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as exc:
        raise EmailConnectionError(
            f"Unable to connect to mail server '{settings.SMTP_HOST}:{settings.SMTP_PORT}'. "
            "Check SMTP_HOST and SMTP_PORT."
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailSendError(f"Failed to send email: {exc}") from exc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_credentials(
    user_config: "UserEmailConfig | None",
) -> tuple[str, str, str, str]:
    """
    Return (smtp_username, smtp_password, from_name, from_email).
    Uses user config when available; falls back to global .env settings.
    """
    if user_config is not None:
        # Import here to avoid circular imports at module load time
        from app.services.encryption_service import decrypt_password
        return (
            user_config.smtp_username,
            decrypt_password(user_config.smtp_password_encrypted),
            user_config.smtp_from_name,
            user_config.smtp_from_email,
        )

    return (
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_NAME,
        settings.SMTP_FROM_EMAIL,
    )


def _validate_resolved(
    smtp_username: str, smtp_password: str, from_email: str
) -> None:
    """Raise EmailConfigError if any required credential is blank."""
    missing = [
        name for name, val in [
            ("SMTP_HOST", settings.SMTP_HOST),
            ("SMTP username", smtp_username),
            ("SMTP password", smtp_password),
            ("From email", from_email),
        ]
        if not val
    ]
    if missing:
        raise EmailConfigError(
            f"Missing email configuration: {', '.join(missing)}. "
            "Please update your Settings or .env file."
        )


def _attach_file(
    msg: EmailMessage,
    file_path: str,
    display_filename: str | None = None,
) -> None:
    """Attach a file to the message, auto-detecting MIME type."""
    path = Path(file_path)
    file_bytes = path.read_bytes()
    filename = display_filename or path.name

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    msg.add_attachment(
        file_bytes,
        maintype=maintype,
        subtype=subtype,
        filename=filename,
    )


def _login(smtp: smtplib.SMTP, username: str, password: str) -> None:
    """Attempt SMTP login if credentials are present."""
    if username:
        smtp.login(username, password)
