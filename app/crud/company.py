from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, func

from app.models.company import Company, CompanyRating
from app.models.application import JobApplication
from app.schemas.company import CompanyCreate, CompanyUpdate


# ---------------------------------------------------------------------------
# Autocomplete (used by application create/edit)
# ---------------------------------------------------------------------------

def search_companies(db: Session, user_id: int, query: str, limit: int = 5):
    """Returns companies matching the query for the JS autocomplete dropdown."""
    return (
        db.query(Company)
        .filter(Company.user_id == user_id, Company.name.ilike(f"%{query}%"))
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Application create/edit helper (get or create, update fields + rating)
# ---------------------------------------------------------------------------

def get_or_create_company(
    db: Session,
    user_id: int,
    name: str,
    company_id: int | None = None,
    website: str | None = None,
    email: str | None = None,
    rating: CompanyRating = CompanyRating.AVERAGE,
) -> Company:
    """
    If an exact company_id is provided from the autocomplete dropdown, fetch it
    and update its editable fields.  Otherwise fall back to a case-insensitive
    name search.  Create a new record when nothing matches.
    """
    if company_id:
        company = (
            db.query(Company)
            .filter(Company.id == company_id, Company.user_id == user_id)
            .first()
        )
        if company:
            company.name = name
            company.website = website
            company.email = email
            company.rating = rating
            db.commit()
            db.refresh(company)
            return company

    # Fallback to name search
    company = (
        db.query(Company)
        .filter(Company.user_id == user_id, Company.name.ilike(name.strip()))
        .first()
    )

    if company:
        # Update fields for the existing record
        company.website = website
        company.email = email
        company.rating = rating
        db.commit()
        db.refresh(company)
        return company

    # Brand new company
    company = Company(
        name=name.strip(),
        website=website.strip() if website else None,
        email=email.strip() if email else None,
        rating=rating,
        user_id=user_id,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


# ---------------------------------------------------------------------------
# Standalone Company Module CRUD
# ---------------------------------------------------------------------------

def get_companies(
    db: Session,
    user_id: int,
    name: str | None = None,
    rating: CompanyRating | None = None,
    sort_order: str = "name_asc",
):
    """Return all companies for a user with optional filtering and sorting."""
    query = (
        db.query(Company)
        .options(joinedload(Company.applications))
        .filter(Company.user_id == user_id)
    )

    if name:
        query = query.filter(Company.name.ilike(f"%{name}%"))
    if rating:
        query = query.filter(Company.rating == rating)

    if sort_order == "apps_desc":
        # Sort by application count descending — do in Python after loading
        results = query.order_by(asc(Company.name)).all()
        results.sort(key=lambda c: len(c.applications), reverse=True)
        return results

    # Default: alphabetical A-Z
    return query.order_by(asc(Company.name)).all()


def get_company_by_id(db: Session, user_id: int, company_id: int) -> Company | None:
    return (
        db.query(Company)
        .options(joinedload(Company.applications).joinedload(JobApplication.company))
        .filter(Company.id == company_id, Company.user_id == user_id)
        .first()
    )


def create_company(db: Session, user_id: int, data: CompanyCreate) -> Company:
    company = Company(
        name=data.name.strip(),
        website=data.website.strip() if data.website else None,
        email=data.email.strip() if data.email else None,
        rating=data.rating,
        user_id=user_id,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def update_company(
    db: Session, user_id: int, company_id: int, data: CompanyUpdate
) -> Company | None:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.user_id == user_id)
        .first()
    )
    if not company:
        return None
    company.name = data.name.strip()
    company.website = data.website.strip() if data.website else None
    company.email = data.email.strip() if data.email else None
    company.rating = data.rating
    db.commit()
    db.refresh(company)
    return company


def delete_company(
    db: Session, user_id: int, company_id: int
) -> tuple[bool, str]:
    """
    Returns (True, "") on success.
    Returns (False, message) when the company has linked applications.
    """
    company = (
        db.query(Company)
        .options(joinedload(Company.applications))
        .filter(Company.id == company_id, Company.user_id == user_id)
        .first()
    )
    if not company:
        return False, "Company not found."
    if company.applications:
        return False, (
            "This company cannot be deleted because applications are linked to it."
        )
    db.delete(company)
    db.commit()
    return True, ""
