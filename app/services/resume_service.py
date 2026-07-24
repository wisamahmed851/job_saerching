"""
Resume Service
==============
Handles all file system operations for CV/Resume uploads.
No HTTP or database concerns live here — only disk I/O and validation.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Root upload directory (relative to the project root where uvicorn is run)
UPLOAD_ROOT = Path("uploads") / "resumes"

# 10 MB limit
MAX_FILE_SIZE = 10 * 1024 * 1024  # bytes

# Allowed MIME types and their canonical extensions
ALLOWED_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

# Friendly label for error messages
ALLOWED_EXTENSIONS_LABEL = "PDF, DOC, or DOCX"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ResumeValidationError(Exception):
    """Raised when an uploaded file fails validation."""


def validate_resume_file(filename: str, content_type: str, file_size: int) -> None:
    """
    Validate the uploaded file against allowed types and size limits.
    Raises ResumeValidationError with a user-friendly message on failure.
    """
    # --- Size check ---
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        raise ResumeValidationError(
            f"File is too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB."
        )

    if file_size == 0:
        raise ResumeValidationError("The uploaded file is empty.")

    # --- MIME type check ---
    if content_type not in ALLOWED_TYPES:
        # Also check by extension as a fallback (some browsers send incorrect MIME types)
        ext = Path(filename).suffix.lower()
        allowed_exts = set(ALLOWED_TYPES.values())
        if ext not in allowed_exts:
            raise ResumeValidationError(
                f"'{filename}' is not a supported file type. "
                f"Please upload a {ALLOWED_EXTENSIONS_LABEL} file."
            )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def get_user_upload_dir(user_id: int) -> Path:
    """Return (and create if needed) the upload directory for a specific user."""
    user_dir = UPLOAD_ROOT / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def generate_stored_filename(original_filename: str) -> str:
    """
    Generate a unique filename for physical storage.
    The original filename is never used on disk — only preserved in the DB.
    Format: <uuid4><original_extension>
    """
    ext = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def save_resume_file(user_id: int, stored_filename: str, file_bytes: bytes) -> Path:
    """
    Write the file bytes to disk at uploads/resumes/{user_id}/{stored_filename}.
    Returns the full Path of the saved file.
    """
    user_dir = get_user_upload_dir(user_id)
    dest = user_dir / stored_filename
    dest.write_bytes(file_bytes)
    return dest


def delete_resume_file(file_path: str) -> None:
    """
    Delete the physical file from disk.
    Silently ignores the case where the file no longer exists
    (idempotent — safe to call even after a partial failure).
    """
    path = Path(file_path)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # Log in production; for now we swallow the error so the DB
        # record deletion still proceeds.
        pass


def read_resume_file(file_path: str) -> bytes:
    """
    Read and return the raw bytes of a stored resume file.
    Raises FileNotFoundError if the file has been removed from disk.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found on disk: {file_path}")
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------

def ensure_upload_dirs() -> None:
    """
    Create the base upload directory tree on application startup.
    Called once from app/main.py.
    """
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
