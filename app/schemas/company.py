from pydantic import BaseModel, ConfigDict

class CompanyResponse(BaseModel):
    id: int
    name: str
    website: str | None = None
    
    # Allows Pydantic to read data directly from the SQLAlchemy Company model
    model_config = ConfigDict(from_attributes=True)
