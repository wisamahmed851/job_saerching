import enum
from typing import List
from sqlalchemy import Integer, String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyRating(str, enum.Enum):
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    BELOW_AVERAGE = "BELOW_AVERAGE"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[CompanyRating] = mapped_column(
        Enum(CompanyRating, name="companyrating_enum"),
        default=CompanyRating.AVERAGE,
        nullable=False,
        server_default=CompanyRating.AVERAGE.value,
    )

    # Foreign Keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="companies")
    applications: Mapped[List["JobApplication"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
