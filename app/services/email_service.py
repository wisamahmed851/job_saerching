"""
Email Service
=============
Sends plain-text emails via SMTP using only Python standard library.
No third-party email packages required.

Configuration is read from app.core.config.settings (populated from .env).
"""

from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings


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
) -> None:
    """
    Send a plain-text email to `to_email`, with an optional file attachment.

    Args:
        to_email:            Recipient address.
        subject:             Email subject line.
        body:                Plain-text body.
        attachment_path:     Absolute or relative path to the file on disk.
                             Pass None to send without an attachment.
        attachment_filename: The filename shown to the recipient in their email
                             client.  If omitted, the basename of attachment_path
                             is used.

    Raises:
        EmailConfigError     — SMTP settings missing in .env
        EmailAuthError       — SMTP login rejected
        EmailConnectionError — Cannot reach the mail server
        EmailSendError       — Any other SMTP error
    """
    _validate_config()

    msg = EmailMessage()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    # --- Optional attachment ---
    if attachment_path is not None:
        _attach_file(msg, attachment_path, attachment_filename)

    try:
        if settings.SMTP_USE_TLS:
            # STARTTLS — connect on plain port then upgrade (e.g. Gmail :587)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                _login(smtp)
                smtp.send_message(msg)
        else:
            # SSL on port 465
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                _login(smtp)
                smtp.send_message(msg)

    except smtplib.SMTPAuthenticationError as exc:
        raise EmailAuthError(
            "SMTP authentication failed. Please verify SMTP_USERNAME and SMTP_PASSWORD."
        ) from exc
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as exc:
        raise EmailConnectionError(
            f"Unable to connect to mail server '{settings.SMTP_HOST}:{settings.SMTP_PORT}'. "
            "Check SMTP_HOST and SMTP_PORT."
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailSendError(f"Failed to send email: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attach_file(
    msg: EmailMessage,
    file_path: str,
    display_filename: str | None = None,
) -> None:
    """
    Read a file from disk and attach it to `msg`.
    MIME type is inferred from the file extension; falls back to
    application/octet-stream for unknown types.
    """
    path = Path(file_path)
    file_bytes = path.read_bytes()

    filename = display_filename or path.name

    # Detect MIME type from extension
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


def _validate_config() -> None:
    """Raise EmailConfigError if any required SMTP setting is blank."""
    missing = [
        name for name, val in [
            ("SMTP_HOST", settings.SMTP_HOST),
            ("SMTP_USERNAME", settings.SMTP_USERNAME),
            ("SMTP_PASSWORD", settings.SMTP_PASSWORD),
            ("SMTP_FROM_EMAIL", settings.SMTP_FROM_EMAIL),
        ]
        if not val
    ]
    if missing:
        raise EmailConfigError(
            f"Missing SMTP configuration in .env: {', '.join(missing)}"
        )


def _login(smtp: smtplib.SMTP) -> None:
    """Attempt SMTP login; raises SMTPAuthenticationError on failure."""
    if settings.SMTP_USERNAME:
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
