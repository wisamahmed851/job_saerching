from typing import Generator
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.config import settings
from app.schemas.token import TokenData
from app.crud.user import get_user_by_email
from app.models.user import User

# auto_error=False prevents FastAPI from automatically throwing a JSON 401 
# if the Authorization header is missing. This allows us to manually check the cookie.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

def get_db() -> Generator:
    """Dependency that creates and yields a database session, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    token_from_header: str = Depends(oauth2_scheme)
) -> User | None:
    """
    Core authentication logic for both APIs and Web Pages.
    Checks the header first, then the HttpOnly cookie. 
    Decodes the JWT and fetches the user. Returns None if invalid.
    """
    token = token_from_header or request.cookies.get("access_token")
    if not token:
        return None
        
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        token_data = TokenData(email=email)
    except JWTError:
        return None
    
    user = get_user_by_email(db, email=token_data.email)
    return user

def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    """Dependency for JSON APIs: Returns 401 Unauthorized if invalid."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_user_web(user: User | None = Depends(get_current_user_optional)) -> User:
    """Dependency for HTML Pages: Redirects to /login if invalid."""
    if not user:
        # Raising a 302 HTTPException forces the browser to redirect immediately
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"}
        )
    return user
