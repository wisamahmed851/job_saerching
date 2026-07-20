from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import ValidationError
import sys

from app.api.deps import get_db, get_current_user_web
from app.crud.user import get_user_by_email
from app.core.security import verify_password, create_access_token
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
from app.schemas.application import ApplicationCreate, FollowupCreate
from app.models.application import ApplicationStatus
from app.models.followup import FollowupType, FollowupResponse

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
    current_user: User = Depends(get_current_user_web)
):
    return templates.TemplateResponse(
        "application_form.html",
        {"request": request, "user": current_user}
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
    resume_version: str | None = Form(None),
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
            resume_version=resume_version,
            notes=notes
        )
    except ValidationError:
        return templates.TemplateResponse(
            "application_form.html",
            {
                "request": request, 
                "user": current_user, 
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
        
    return templates.TemplateResponse(
        "application_detail.html",
        {
            "request": request, 
            "user": current_user, 
            "application": application,
            "success": success,
            "error": error
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
        
    return templates.TemplateResponse(
        "application_form.html",
        {"request": request, "user": current_user, "application": application}
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
    resume_version: str | None = Form(None),
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
            resume_version=resume_version,
            notes=notes,
            status=status,
            next_followup_date=next_followup_date
        )
    except ValidationError:
        application = get_application_by_id(db, current_user.id, application_id)
        return templates.TemplateResponse(
            "application_form.html",
            {
                "request": request, 
                "user": current_user, 
                "application": application,
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
