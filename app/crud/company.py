from sqlalchemy.orm import Session
from app.models.company import Company

def get_or_create_company(
    db: Session, 
    user_id: int, 
    name: str, 
    company_id: int | None = None,
    website: str | None = None, 
    email: str | None = None
) -> Company:
    """
    If an exact company_id is provided from the autocomplete dropdown, it fetches it directly.
    Otherwise, falls back to a case-insensitive search by name.
    If nothing matches, a new company record is created.
    """
    if company_id:
        company = db.query(Company).filter(
            Company.id == company_id, 
            Company.user_id == user_id
        ).first()
        if company:
            return company

    # Fallback to name search
    company = db.query(Company).filter(
        Company.user_id == user_id,
        Company.name.ilike(name.strip())
    ).first()
    
    if not company:
        company = Company(
            name=name.strip(),
            website=website.strip() if website else None,
            email=email.strip() if email else None,
            user_id=user_id
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    
    return company

def search_companies(db: Session, user_id: int, query: str, limit: int = 5):
    """
    Returns a list of companies matching the search query for the JSON autocomplete API.
    """
    return db.query(Company).filter(
        Company.user_id == user_id,
        Company.name.ilike(f"%{query}%")
    ).limit(limit).all()
