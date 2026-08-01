from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash

def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetches a user from the database by email."""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> User | None:
    """Fetches a user from the database by username."""
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate, prehashed: bool = False) -> User:
    """
    Creates a new user in the database.
    If prehashed=True the password field already contains the bcrypt hash
    and must not be hashed again (used by the two-step registration flow).
    """
    hashed_password = user.password if prehashed else get_password_hash(user.password)
    
    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user
