from fastapi import FastAPI
from pydantic import BaseModel
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.models.user import User

app = FastAPI(title="My API")

Base.metadata.create_all(bind=engine)
@app.get("/")
def root():
    return {'message': "Welcome to FastAPI!"}

print("main laoded")
print("Database url", settings.DATABASE_URL)