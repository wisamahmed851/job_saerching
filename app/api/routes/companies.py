from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.crud.company import search_companies
from app.schemas.company import CompanyResponse
from app.models.user import User

router = APIRouter()

@router.get("/search", response_model=List[CompanyResponse])
def search_companies_api(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    JSON API endpoint to power the Vanilla JS autocomplete dropdown.
    Accepts a query string 'q' and returns a list of matching CompanyResponse objects.
    Uses 'get_current_user' so that if the cookie is invalid, it returns a standard JSON 401.
    """
    companies = search_companies(db, user_id=current_user.id, query=q)
    return companies
