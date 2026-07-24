from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ResumeUpload(BaseModel):
    """Data collected from the upload form (file itself is handled separately)."""
    display_name: str


class ResumeResponse(BaseModel):
    """Shape returned to templates / API callers."""
    id: int
    user_id: int
    display_name: str
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    uploaded_at: datetime
    is_active: bool

    # Count of applications currently referencing this resume.
    # Populated manually in CRUD — not a DB column.
    application_count: int = 0

    model_config = ConfigDict(from_attributes=True)
