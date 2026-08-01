from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserEmailConfig(Base):
    __tablename__ = "user_email_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # One-to-one with User
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # User-specific SMTP credentials (server host/port/tls stays in .env)
    smtp_username: Mapped[str] = mapped_column(String, nullable=False)
    smtp_password_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    smtp_from_name: Mapped[str] = mapped_column(String, nullable=False)
    smtp_from_email: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="email_config")
