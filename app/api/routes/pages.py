from datetime import date, timedelta, datetime, timezone
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import ValidationError
from jose import jwt, JWTError
import sys

from app.api.deps import get_db, get_current_user_web
from app.crud.user import get_user_by_email, get_user_by_username, create_user as crud_create_user
from app.crud.developer_feedback import create_feedback
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.config import settings
from app.models.user import User

from app.crud.application import (
    get_due_followups, 
    get_recent_applications, 
    get_application_stats, 
    create_job_application,
    get_applications,
    delete_application,
    get_application_by_id,
    update_job_application
)
from app.crud.followup import create_followup
from app.crud.resume import get_active_resumes_for_user, get_resume_by_id, create_resume
from app.crud.user_email_config import get_email_config, upsert_email_config
from app.crud.email_template import (
    get_email_template,
    get_or_default_template,
    upsert_email_template,
    delete_email_template,
)
from app.services.template_service import (
    DEFAULT_SUBJECT,
    DEFAULT_BODY,
    render_subject_and_body,
)
from app.schemas.application import ApplicationCreate, FollowupCreate
from app.schemas.user import UserCreate
from app.models.application import ApplicationStatus
from app.models.followup import FollowupType, FollowupResponse
from app.services.email_service import (
    send_email,
    EmailAuthError,
    EmailConnectionError,
    EmailConfigError,
    EmailSendError,
)
from app.services.resume_service import (
    validate_resume_file,
    generate_stored_filename,
    save_resume_file,
    ResumeValidationError,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_by_email(db, email=email)
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Invalid email or password", "email": email},
            status_code=400
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False, 
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return response

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
def register_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    errors = {}

    # --- Validation ---
    if len(username.strip()) < 2:
        errors["username"] = "Full name must be at least 2 characters."

    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."

    if password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if not errors:
        if get_user_by_email(db, email=email):
            errors["email"] = "An account with this email already exists."

    if errors:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "errors": errors,
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    # --- Hash password and store pending registration in a signed cookie ---
    hashed_password = get_password_hash(password)

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REGISTRATION_TOKEN_EXPIRE_MINUTES
    )
    pending_token = jwt.encode(
        {
            "sub": email,
            "username": username.strip(),
            "hashed_password": hashed_password,
            "exp": expire,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = RedirectResponse(url="/register/message", status_code=302)
    response.set_cookie(
        key="pending_registration",
        value=pending_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REGISTRATION_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.get("/register/message", response_class=HTMLResponse)
def register_message_page(request: Request):
    # If no pending registration cookie exists, redirect back to register
    if not request.cookies.get("pending_registration"):
        return RedirectResponse(url="/register", status_code=302)
    return templates.TemplateResponse("register_message.html", {"request": request})


@router.post("/register/message", response_class=HTMLResponse)
def register_message_post(
    request: Request,
    message: str = Form(""),
    db: Session = Depends(get_db)
):
    pending_token = request.cookies.get("pending_registration")
    if not pending_token:
        return RedirectResponse(url="/register", status_code=302)

    # Decode the signed pending-registration token
    try:
        payload = jwt.decode(
            pending_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload["sub"]
        username: str = payload["username"]
        hashed_password: str = payload["hashed_password"]
    except (JWTError, KeyError):
        response = RedirectResponse(url="/register", status_code=302)
        response.delete_cookie("pending_registration")
        return response

    # Guard against duplicate emails (race condition or back-button resubmit)
    if get_user_by_email(db, email=email):
        response = templates.TemplateResponse(
            "register_message.html",
            {
                "request": request,
                "error": "This email is already registered. Please log in instead.",
            },
            status_code=400,
        )
        response.delete_cookie("pending_registration")
        return response

    # Create the user with the already-hashed password
    from app.schemas.user import UserCreate as _UserCreate
    new_user = crud_create_user(
        db,
        _UserCreate(username=username, email=email, password=hashed_password),
        prehashed=True,
    )

    # Save optional developer feedback
    create_feedback(db, user_id=new_user.id, message=message)

    # Clear the pending cookie and redirect to login with success flag
    response = RedirectResponse(url="/login?registered=1", status_code=302)
    response.delete_cookie("pending_registration")
    return response


@router.post("/logout", response_class=HTMLResponse)
def logout_post():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    print("Dashboard route called")
    sys.stdout.write(f"MAX_FOLLOWUPS = {settings.MAX_FOLLOWUPS}\n")
    sys.stdout.flush()
    import traceback
    from fastapi.responses import PlainTextResponse
    
    try:
        due_followups = get_due_followups(db, current_user.id)
        recent_applications = get_recent_applications(db, current_user.id)
        stats = get_application_stats(db, current_user.id)

        print("=" * 50)
        print("MAX_FOLLOWUPS:", settings.MAX_FOLLOWUPS, flush=True)
        print("TYPE:", type(settings.MAX_FOLLOWUPS), flush=True)
        print("=" * 50)
        
        for app in due_followups:
            print(app.next_followup_date)
            print(type(app.next_followup_date))
        return templates.TemplateResponse(
            "dashboard.html", 
            {
                "request": request, 
                "user": current_user,
                "due_followups": due_followups,
                "recent_applications": recent_applications,
                "stats": stats,
                "max_followups": settings.MAX_FOLLOWUPS
            }
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        return PlainTextResponse(f"INTERNAL SERVER ERROR :\n\n{error_trace}", status_code=500)

@router.get("/applications", response_class=HTMLResponse)
def list_applications_page(
    request: Request,
    company_id: int | None = Query(None),
    company_name: str | None = Query(None),
    position: str | None = Query(None),
    application_method: str | None = Query(None),
    status: ApplicationStatus | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort_order: str = Query("newest"),
    success: str | None = Query(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    applications = get_applications(
        db=db,
        user_id=current_user.id,
        company_id=company_id,
        company_name=company_name,
        position=position,
        application_method=application_method,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_order=sort_order
    )
    
    return templates.TemplateResponse(
        "applications.html",
        {
            "request": request,
            "user": current_user,
            "applications": applications,
            "success": success,
            "filters": {
                "company_id": company_id or "",
                "company_name": company_name or "",
                "position": position or "",
                "application_method": application_method or "",
                "status": status.value if status else "",
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
                "sort_order": sort_order
            }
        }
    )

@router.get("/applications/new", response_class=HTMLResponse)
def new_application_page(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    resumes = get_active_resumes_for_user(db, user_id=current_user.id)
    return templates.TemplateResponse(
        "application_form.html",
        {"request": request, "user": current_user, "resumes": resumes}
    )

@router.post("/applications/new", response_class=HTMLResponse)
def create_application_post(
    request: Request,
    company_name: str = Form(...),
    position: str = Form(...),
    application_method: str = Form(...),
    applied_date: date = Form(...),
    company_id: int | None = Form(None), 
    company_website: str | None = Form(None),
    company_email: str | None = Form(None),
    job_post_url: str | None = Form(None),
    resume_id: int | None = Form(None),
    notes: str | None = Form(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    try:
        form_data = ApplicationCreate(
            company_id=company_id,
            company_name=company_name,
            company_website=company_website,
            company_email=company_email,
            position=position,
            application_method=application_method,
            job_post_url=job_post_url,
            applied_date=applied_date,
            resume_id=resume_id,
            notes=notes
        )
    except ValidationError:
        resumes = get_active_resumes_for_user(db, user_id=current_user.id)
        return templates.TemplateResponse(
            "application_form.html",
            {
                "request": request, 
                "user": current_user,
                "resumes": resumes,
                "error": "Invalid form data provided. Please check your inputs."
            },
            status_code=400
        )
        
    create_job_application(db=db, user_id=current_user.id, form_data=form_data)
    return RedirectResponse(url="/applications?success=Application+Created+Successfully", status_code=302)

@router.get("/applications/{application_id}", response_class=HTMLResponse)
def view_application_page(
    application_id: int,
    request: Request,
    success: str | None = Query(None),
    error: str | None = Query(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    application = get_application_by_id(db, current_user.id, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resumes = get_active_resumes_for_user(db, user_id=current_user.id)

    return templates.TemplateResponse(
        "application_detail.html",
        {
            "request": request, 
            "user": current_user, 
            "application": application,
            "resumes": resumes,
            "success": success,
            "error": error,
        }
    )

@router.get("/applications/{application_id}/edit", response_class=HTMLResponse)
def edit_application_page(
    application_id: int,
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    application = get_application_by_id(db, current_user.id, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resumes = get_active_resumes_for_user(db, user_id=current_user.id)
    return templates.TemplateResponse(
        "application_form.html",
        {"request": request, "user": current_user, "application": application, "resumes": resumes}
    )

@router.post("/applications/{application_id}/edit", response_class=HTMLResponse)
def edit_application_post(
    application_id: int,
    request: Request,
    company_name: str = Form(...),
    position: str = Form(...),
    application_method: str = Form(...),
    applied_date: date = Form(...),
    status: ApplicationStatus = Form(...),
    company_id: int | None = Form(None), 
    company_website: str | None = Form(None),
    company_email: str | None = Form(None),
    job_post_url: str | None = Form(None),
    resume_id: int | None = Form(None),
    notes: str | None = Form(None),
    next_followup_date: date | None = Form(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    try:
        form_data = ApplicationCreate(
            company_id=company_id,
            company_name=company_name,
            company_website=company_website,
            company_email=company_email,
            position=position,
            application_method=application_method,
            job_post_url=job_post_url,
            applied_date=applied_date,
            resume_id=resume_id,
            notes=notes,
            status=status,
            next_followup_date=next_followup_date
        )
    except ValidationError:
        application = get_application_by_id(db, current_user.id, application_id)
        resumes = get_active_resumes_for_user(db, user_id=current_user.id)
        return templates.TemplateResponse(
            "application_form.html",
            {
                "request": request, 
                "user": current_user, 
                "application": application,
                "resumes": resumes,
                "error": "Invalid form data provided. Please check your inputs."
            },
            status_code=400
        )
        
    update_job_application(db=db, user_id=current_user.id, application_id=application_id, form_data=form_data)
    return RedirectResponse(url=f"/applications?success=Application+Updated+Successfully", status_code=302)

@router.post("/applications/{application_id}/delete", response_class=HTMLResponse)
def delete_application_action(
    application_id: int,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    delete_application(db, user_id=current_user.id, application_id=application_id)
    return RedirectResponse(url="/applications", status_code=302)

@router.post("/applications/{application_id}/followup", response_class=HTMLResponse)
def add_followup_post(
    application_id: int,
    request: Request,
    followup_date: date = Form(...),
    followup_type: FollowupType = Form(...),
    response: FollowupResponse = Form(...),
    next_followup_date: date | None = Form(None),
    notes: str | None = Form(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    """
    Handles the Follow-up Modal submission.
    """
    try:
        form_data = FollowupCreate(
            followup_date=followup_date,
            followup_type=followup_type,
            response=response,
            next_followup_date=next_followup_date,
            notes=notes
        )
    except ValidationError:
        return RedirectResponse(url=f"/applications/{application_id}?error=Invalid+form+data", status_code=302)
        
    followup = create_followup(db, current_user.id, application_id, form_data)
    if not followup:
        raise HTTPException(status_code=404, detail="Application not found")
        
    return RedirectResponse(url=f"/applications/{application_id}?success=Follow-up+Added+Successfully", status_code=302)


@router.post("/applications/{application_id}/send-email", response_class=HTMLResponse)
async def send_followup_email(
    application_id: int,
    subject: str = Form(...),
    body: str = Form(...),
    next_followup_date: date | None = Form(None),
    existing_resume_id: int | None = Form(None),
    new_resume_file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db)
):
    """
    Sends a follow-up email to the company, with an optional resume attachment.
    Attachment source priority:
      1. new_resume_file  — uploaded inline, saved to the Resume Library, then attached
      2. existing_resume_id — picked from the user's Resume Library
      3. neither           — no attachment
    Ownership of the application is always verified.
    """
    # 1. Load and verify ownership
    application = get_application_by_id(db, current_user.id, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # 2. Verify company email exists
    if not application.company.email:
        return RedirectResponse(
            url=f"/applications/{application_id}?error=No+company+email+address+on+file",
            status_code=302
        )

    # 3. Resolve attachment (path on disk + display filename)
    attachment_path: str | None = None
    attachment_filename: str | None = None
    attachment_label: str | None = None   # used in timeline note

    # Check if a real file was actually uploaded (not just an empty file input)
    has_new_file = (
        new_resume_file is not None
        and new_resume_file.filename
        and new_resume_file.filename.strip() != ""
    )

    if has_new_file:
        # --- Case A: new upload — reuse Resume service & CRUD (same as CV Library page) ---
        file_bytes = await new_resume_file.read()
        original_filename = new_resume_file.filename
        content_type = new_resume_file.content_type or ""

        try:
            validate_resume_file(
                filename=original_filename,
                content_type=content_type,
                file_size=len(file_bytes),
            )
        except ResumeValidationError as exc:
            return RedirectResponse(
                url=f"/applications/{application_id}?error={str(exc).replace(' ', '+')}",
                status_code=302
            )

        stored_filename = generate_stored_filename(original_filename)
        saved_path = save_resume_file(
            user_id=current_user.id,
            stored_filename=stored_filename,
            file_bytes=file_bytes,
        )

        # Persist to Resume Library so it appears in CV Management
        resume_record = create_resume(
            db=db,
            user_id=current_user.id,
            display_name=original_filename.rsplit(".", 1)[0],  # strip extension for display name
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(saved_path),
            file_size=len(file_bytes),
            mime_type=content_type,
        )

        attachment_path = resume_record.file_path
        attachment_filename = resume_record.original_filename
        attachment_label = resume_record.original_filename

    elif existing_resume_id:
        # --- Case B: existing resume from library ---
        resume_record = get_resume_by_id(db, user_id=current_user.id, resume_id=existing_resume_id)
        if not resume_record:
            return RedirectResponse(
                url=f"/applications/{application_id}?error=Selected+resume+not+found",
                status_code=302
            )
        attachment_path = resume_record.file_path
        attachment_filename = resume_record.original_filename
        attachment_label = resume_record.original_filename

    # 4. Render subject + body from user's saved template (or built-in default)
    subject_tpl, body_tpl = get_or_default_template(db, user_id=current_user.id)
    rendered_subject, rendered_body = render_subject_and_body(
        subject_template=subject_tpl,
        body_template=body_tpl,
        company_name=application.company.name,
        position=application.position,
        user_name=current_user.username.title(),
    )

    # 5. Send the email — use user's config if available, else fall back to .env
    user_email_config = get_email_config(db, user_id=current_user.id)
    try:
        send_email(
            to_email=application.company.email,
            subject=rendered_subject,
            body=rendered_body,
            attachment_path=attachment_path,
            attachment_filename=attachment_filename,
            user_email_config=user_email_config,
        )
    except EmailConfigError:
        return RedirectResponse(
            url=f"/applications/{application_id}?error=Email+not+configured.+Please+check+Settings+or+.env",
            status_code=302
        )
    except EmailAuthError:
        return RedirectResponse(
            url=f"/applications/{application_id}?error=Could+not+send+email.+Please+verify+your+email+configuration+in+Settings.",
            status_code=302
        )
    except EmailConnectionError:
        return RedirectResponse(
            url=f"/applications/{application_id}?error=Unable+to+connect+to+mail+server.",
            status_code=302
        )
    except EmailSendError:
        return RedirectResponse(
            url=f"/applications/{application_id}?error=Email+sending+failed.+Please+try+again.",
            status_code=302
        )

    # 5. Auto-log the email as a follow-up timeline entry
    from datetime import date as date_type
    today = date_type.today()

    if attachment_label:
        timeline_note = f"Email follow-up sent with attachment: {attachment_label}"
    else:
        timeline_note = "Email follow-up sent through built-in email system."

    create_followup(
        db=db,
        user_id=current_user.id,
        application_id=application_id,
        form_data=FollowupCreate(
            followup_date=today,
            followup_type=FollowupType.EMAIL,
            response=FollowupResponse.WAITING,
            notes=timeline_note,
            next_followup_date=next_followup_date,
        )
    )

    return RedirectResponse(
        url=f"/applications/{application_id}?success=Email+sent+successfully",
        status_code=302
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    success: str | None = Query(None),
    error: str | None = Query(None),
    active_tab: str | None = Query(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    config = get_email_config(db, user_id=current_user.id)
    email_template = get_email_template(db, user_id=current_user.id)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": current_user,
            "config": config,
            "smtp_host": settings.SMTP_HOST,
            "smtp_port": settings.SMTP_PORT,
            "email_template": email_template,
            "default_subject": DEFAULT_SUBJECT,
            "default_body": DEFAULT_BODY,
            "active_tab": active_tab or "email-config",
            "success": success,
            "error": error,
        },
    )


@router.post("/settings", response_class=HTMLResponse)
def settings_post(
    request: Request,
    smtp_username: str = Form(...),
    smtp_password: str = Form(""),
    smtp_from_name: str = Form(...),
    smtp_from_email: str = Form(...),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    errors: dict[str, str] = {}

    if not smtp_username.strip():
        errors["smtp_username"] = "SMTP username is required."
    if not smtp_from_name.strip():
        errors["smtp_from_name"] = "From name is required."
    if not smtp_from_email.strip():
        errors["smtp_from_email"] = "From email is required."
    elif "@" not in smtp_from_email:
        errors["smtp_from_email"] = "Please enter a valid email address."

    # Password is only required when there is no existing config
    existing_config = get_email_config(db, user_id=current_user.id)
    if not existing_config and not smtp_password.strip():
        errors["smtp_password"] = "SMTP password is required for a new configuration."

    if errors:
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "user": current_user,
                "config": existing_config,
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
                "errors": errors,
            },
            status_code=400,
        )

    try:
        upsert_email_config(
            db=db,
            user_id=current_user.id,
            smtp_username=smtp_username,
            smtp_from_name=smtp_from_name,
            smtp_from_email=smtp_from_email,
            new_plain_password=smtp_password if smtp_password.strip() else None,
        )
    except Exception:
        return RedirectResponse(
            url="/settings?error=Failed+to+save+configuration.+Please+try+again.",
            status_code=302,
        )

    return RedirectResponse(
        url="/settings?success=Email+configuration+saved+successfully.",
        status_code=302,
    )


@router.post("/settings/template", response_class=HTMLResponse)
def settings_template_post(
    request: Request,
    subject_template: str = Form(...),
    body_template: str = Form(...),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    errors: dict[str, str] = {}

    if not subject_template.strip():
        errors["subject_template"] = "Subject cannot be empty."
    if not body_template.strip():
        errors["body_template"] = "Body cannot be empty."

    if errors:
        config = get_email_config(db, user_id=current_user.id)
        email_template = get_email_template(db, user_id=current_user.id)
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "user": current_user,
                "config": config,
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
                "email_template": email_template,
                "default_subject": DEFAULT_SUBJECT,
                "default_body": DEFAULT_BODY,
                "active_tab": "email-template",
                "template_errors": errors,
                # Preserve submitted values so the form doesn't clear on error
                "submitted_subject": subject_template,
                "submitted_body": body_template,
            },
            status_code=400,
        )

    upsert_email_template(
        db=db,
        user_id=current_user.id,
        subject_template=subject_template,
        body_template=body_template,
    )
    return RedirectResponse(
        url="/settings?success=Email+template+saved+successfully.&active_tab=email-template",
        status_code=302,
    )


@router.post("/settings/template/reset", response_class=HTMLResponse)
def settings_template_reset(
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    """Delete the user's custom template, reverting to the built-in default."""
    delete_email_template(db, user_id=current_user.id)
    return RedirectResponse(
        url="/settings?success=Email+template+reset+to+default.&active_tab=email-template",
        status_code=302,
    )
