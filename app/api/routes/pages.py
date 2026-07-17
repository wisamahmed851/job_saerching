from datetime import timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_web
from app.crud.user import get_user_by_email
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.models.user import User

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    """
    Root page.
    If the user has an access_token cookie, redirect to dashboard.
    Otherwise, redirect to login.
    """
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """
    Renders the login.html template.
    """
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Handles the form submission from login.html.
    Validates credentials, sets an HttpOnly cookie, and redirects to dashboard.
    """
    user = get_user_by_email(db, email=email)
    
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "error": "Invalid email or password", 
                "email": email
            },
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

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user_web)
):
    """
    Protected dashboard route.
    If get_current_user_web fails, the user is automatically redirected to /login.
    """
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "user": current_user}
    )

@router.post("/logout", response_class=HTMLResponse)
def logout_post():
    """
    Logs out the user by deleting the HttpOnly cookie.
    Redirects to the login page.
    """
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response
