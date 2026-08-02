"""
Company Management page routes (HTML).
Kept separate from the JSON autocomplete API in companies.py.
"""

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_web
from app.models.user import User
from app.models.company import CompanyRating
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.crud.company import (
    get_companies,
    get_company_by_id,
    create_company,
    update_company,
    delete_company,
)
from app.services.company_export_service import export_companies_to_excel

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/companies", response_class=HTMLResponse)
def list_companies_page(
    request: Request,
    name: str | None = Query(None),
    rating: CompanyRating | None = Query(None),
    sort_order: str = Query("name_asc"),
    success: str | None = Query(None),
    error: str | None = Query(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    companies = get_companies(
        db=db,
        user_id=current_user.id,
        name=name,
        rating=rating,
        sort_order=sort_order,
    )
    return templates.TemplateResponse(
        "companies/list.html",
        {
            "request": request,
            "user": current_user,
            "companies": companies,
            "success": success,
            "error": error,
            "filters": {
                "name": name or "",
                "rating": rating.value if rating else "",
                "sort_order": sort_order,
            },
        },
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.get("/companies/new", response_class=HTMLResponse)
def new_company_page(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "companies/create.html",
        {"request": request, "user": current_user},
    )


@router.post("/companies/new", response_class=HTMLResponse)
def create_company_post(
    request: Request,
    name: str = Form(...),
    website: str | None = Form(None),
    email: str | None = Form(None),
    rating: str = Form("AVERAGE"),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    if not name.strip():
        return templates.TemplateResponse(
            "companies/create.html",
            {
                "request": request,
                "user": current_user,
                "error": "Company name is required.",
                "form": {"name": name, "website": website, "email": email, "rating": rating},
            },
            status_code=400,
        )

    try:
        rating_enum = CompanyRating(rating)
    except ValueError:
        rating_enum = CompanyRating.AVERAGE

    data = CompanyCreate(
        name=name,
        website=website or None,
        email=email or None,
        rating=rating_enum,
    )
    create_company(db=db, user_id=current_user.id, data=data)
    return RedirectResponse(
        url="/companies?success=Company+created+successfully.", status_code=302
    )


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

@router.get("/companies/{company_id}/edit", response_class=HTMLResponse)
def edit_company_page(
    company_id: int,
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    company = get_company_by_id(db, user_id=current_user.id, company_id=company_id)
    if not company:
        return RedirectResponse(url="/companies?error=Company+not+found.", status_code=302)
    return templates.TemplateResponse(
        "companies/edit.html",
        {"request": request, "user": current_user, "company": company},
    )


@router.post("/companies/{company_id}/edit", response_class=HTMLResponse)
def edit_company_post(
    company_id: int,
    request: Request,
    name: str = Form(...),
    website: str | None = Form(None),
    email: str | None = Form(None),
    rating: str = Form("AVERAGE"),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    if not name.strip():
        company = get_company_by_id(db, user_id=current_user.id, company_id=company_id)
        return templates.TemplateResponse(
            "companies/edit.html",
            {
                "request": request,
                "user": current_user,
                "company": company,
                "error": "Company name is required.",
            },
            status_code=400,
        )

    try:
        rating_enum = CompanyRating(rating)
    except ValueError:
        rating_enum = CompanyRating.AVERAGE

    data = CompanyUpdate(
        name=name,
        website=website or None,
        email=email or None,
        rating=rating_enum,
    )
    result = update_company(
        db=db, user_id=current_user.id, company_id=company_id, data=data
    )
    if not result:
        return RedirectResponse(url="/companies?error=Company+not+found.", status_code=302)

    return RedirectResponse(
        url=f"/companies/{company_id}?success=Company+updated+successfully.", status_code=302
    )


# ---------------------------------------------------------------------------
# Export  (must be before /{company_id} to avoid shadowing)
# ---------------------------------------------------------------------------

@router.get("/companies/export")
def export_companies(
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    file_bytes = export_companies_to_excel(db=db, user_id=current_user.id)
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=companies.xlsx"},
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/companies/{company_id}", response_class=HTMLResponse)
def view_company_page(
    company_id: int,
    request: Request,
    success: str | None = Query(None),
    error: str | None = Query(None),
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    company = get_company_by_id(db, user_id=current_user.id, company_id=company_id)
    if not company:
        return RedirectResponse(url="/companies?error=Company+not+found.", status_code=302)
    return templates.TemplateResponse(
        "companies/detail.html",
        {
            "request": request,
            "user": current_user,
            "company": company,
            "success": success,
            "error": error,
        },
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.post("/companies/{company_id}/delete", response_class=HTMLResponse)
def delete_company_post(
    company_id: int,
    current_user: User = Depends(get_current_user_web),
    db: Session = Depends(get_db),
):
    ok, message = delete_company(
        db=db, user_id=current_user.id, company_id=company_id
    )
    if ok:
        return RedirectResponse(
            url="/companies?success=Company+deleted+successfully.", status_code=302
        )
    # Show the error on the detail page
    return RedirectResponse(
        url=f"/companies/{company_id}?error={message.replace(' ', '+')}", status_code=302
    )


# ---------------------------------------------------------------------------
# Export  (must be before /{company_id} to avoid shadowing)
# ---------------------------------------------------------------------------
