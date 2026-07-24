"""
Resume Routes
=============
Handles the CV Library page and all resume actions:
  GET  /resumes                  — CV Library page
  POST /resumes/upload           — Handle upload form submission
  GET  /resumes/{id}/download    — Secure file download (owner only)
  POST /resumes/{id}/delete      — Delete resume (nullifies FK on applications)

All file I/O is delegated to app/services/resume_service.py.
All DB operations are delegated to app/crud/resume.py.
"""

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_web
from app.models.user import User
from app.crud.resume import (
    get_resumes_for_user,
    get_resume_by_id,
    create_resume,
    delete_resume,
    count_applications_using_resume,
)
from app.services.resume_service import (
    validate_resume_file,
    generate_stored_filename,
    save_resume_file,
    delete_resume_file,
    read_resume_file,
    ResumeValidationError,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# CV Library page
# ---------------------------------------------------------------------------

@router.get("/resumes", response_class=HTMLResponse)
def resumes_page(
    request: Request,
    success: str | None = None,
    error: str | None = None,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    resumes = get_resumes_for_user(db, user_id=current_user.id)
    return templates.TemplateResponse(
        "resumes.html",
        {
            "request": request,
            "user": current_user,
            "resumes": resumes,
            "success": success,
            "error": error,
        },
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/resumes/upload", response_class=HTMLResponse)
async def upload_resume(
    request: Request,
    display_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    # Read file bytes first so we know the real size
    file_bytes = await file.read()
    file_size = len(file_bytes)
    original_filename = file.filename or "upload"
    content_type = file.content_type or ""

    # Validate
    try:
        validate_resume_file(
            filename=original_filename,
            content_type=content_type,
            file_size=file_size,
        )
    except ResumeValidationError as exc:
        resumes = get_resumes_for_user(db, user_id=current_user.id)
        return templates.TemplateResponse(
            "resumes.html",
            {
                "request": request,
                "user": current_user,
                "resumes": resumes,
                "error": str(exc),
                "upload_display_name": display_name,
            },
            status_code=422,
        )

    # Generate a unique stored filename and save to disk
    stored_filename = generate_stored_filename(original_filename)
    saved_path = save_resume_file(
        user_id=current_user.id,
        stored_filename=stored_filename,
        file_bytes=file_bytes,
    )

    # Persist the record
    create_resume(
        db=db,
        user_id=current_user.id,
        display_name=display_name.strip() or original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=str(saved_path),
        file_size=file_size,
        mime_type=content_type,
    )

    return RedirectResponse(
        url="/resumes?success=Resume+uploaded+successfully",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

@router.get("/resumes/{resume_id}/download")
def download_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    resume = get_resume_by_id(db, user_id=current_user.id, resume_id=resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    try:
        file_bytes = read_resume_file(resume.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    # Serve the original filename to the browser
    safe_name = resume.original_filename.replace('"', "'")

    return Response(
        content=file_bytes,
        media_type=resume.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(file_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.post("/resumes/{resume_id}/delete", response_class=HTMLResponse)
def delete_resume_action(
    resume_id: int,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    resume = get_resume_by_id(db, user_id=current_user.id, resume_id=resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Delete physical file first, then the DB record
    # (if file deletion fails we still proceed — the DB record is the source of truth)
    delete_resume_file(resume.file_path)
    delete_resume(db, resume)

    return RedirectResponse(
        url="/resumes?success=Resume+deleted+successfully",
        status_code=302,
    )
