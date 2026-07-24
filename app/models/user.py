from typing import List
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    username: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    password: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    # Relationships
    companies: Mapped[List["Company"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["JobApplication"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    resumes: Mapped[List["Resume"]] = relationship(back_populates="user", cascade="all, delete-orphan")