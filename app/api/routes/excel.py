"""
Excel Import / Export Routes
=============================
Two endpoints only:
  GET  /applications/export  — streams the workbook download
  POST /applications/import  — accepts a file upload, runs import, returns JSON

Both require an authenticated user (cookie-based, same as all page routes).
All Excel logic is delegated to app/services/excel_service.py.
"""

from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_web
from app.models.user import User
from app.services.excel_service import (
    export_to_excel,
    import_from_excel,
    ImportError as ExcelImportError,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/export")
def export_applications(
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    """
    Build and stream the Excel workbook for the authenticated user.
    The browser receives it as a file download.
    """
    workbook_bytes = export_to_excel(db=db, user_id=current_user.id)

    filename = f"Job_Applications_{date.today().strftime('%Y_%m_%d')}.xlsx"

    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(workbook_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/import")
async def import_applications(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    """
    Accept an Excel workbook upload, validate it, and import the data.

    Returns JSON so the modal can display success or error without a page
    reload:
      200  {"ok": true,  "applications": N, "followups": M}
      422  {"ok": false, "error": "<friendly message>"}
    """
    # --- Basic file type check ---
    if not file.filename:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "No file was received."},
        )

    allowed_extensions = (".xlsx", ".xlsm", ".xltx", ".xltm")
    if not file.filename.lower().endswith(allowed_extensions):
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": (
                    f"'{file.filename}' is not a supported Excel file. "
                    "Please upload a .xlsx file exported from this application."
                ),
            },
        )

    # --- Read file bytes ---
    try:
        file_bytes = await file.read()
    except Exception as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": f"Failed to read the uploaded file: {exc}"},
        )

    if not file_bytes:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "The uploaded file is empty."},
        )

    # --- Delegate to service ---
    try:
        result = import_from_excel(db=db, user_id=current_user.id, file_bytes=file_bytes)
    except ExcelImportError as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": str(exc)},
        )
    except Exception as exc:
        # Catch-all — never expose raw tracebacks to the client
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": (
                    "An unexpected error occurred during import. "
                    f"Details: {exc}"
                ),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "applications": result["applications"],
            "followups": result["followups"],
        },
    )
