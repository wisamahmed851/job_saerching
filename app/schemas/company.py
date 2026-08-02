from pydantic import BaseModel, ConfigDict
from app.models.company import CompanyRating


class CompanyResponse(BaseModel):
    """Used by the JSON autocomplete API."""
    id: int
    name: str
    website: str | None = None
    email: str | None = None
    rating: CompanyRating = CompanyRating.AVERAGE

    model_config = ConfigDict(from_attributes=True)


class CompanyCreate(BaseModel):
    name: str
    website: str | None = None
    email: str | None = None
    rating: CompanyRating = CompanyRating.AVERAGE


class CompanyUpdate(BaseModel):
    name: str
    website: str | None = None
    email: str | None = None
    rating: CompanyRating = CompanyRating.AVERAGE
